class Recorder:
    def __init__(self):
        self.t = []
        self.alive_G = []
        self.alive_N = []
        self.comp_G = []            
        self.node_reach = []        
        self.avg_tq = []
        self.avg_hops = []
        self.max_silence = []       
        self.deliver_ratio = []     
        self.alerts_active = []
        self.bandwidth = []
        self.events = []
        # Episodios de reconvergencia de rutas: [inicio, fin, causa]. Los
        # abre el motor al recuperar un Gateway (RECOVER) o al reunificarse
        # la malla (HEAL); se cierran en la primera muestra en que todos
        # los pares de Gateways conectados por radio tienen ruta vigente
        # (rutas_convergidas). fin = None si la corrida terminó antes.
        self.reconv_rutas = []
        self._reconv_abierta = None

    def event(self, t, tipo, texto):
        self.events.append((t, tipo, texto))

    def abrir_reconvergencia(self, t, causa):
        """Abre un episodio, salvo que ya haya uno abierto: entonces el
        nuevo disparador se suma a ese, que se sigue midiendo desde el
        primero. Así, un Gateway puente que vuelve (RECOVER) y la
        reunificación que eso provoca medio paso después (HEAL) cuentan
        como un solo episodio."""
        if self._reconv_abierta is not None:
            return
        self._reconv_abierta = [t, None, causa]
        self.reconv_rutas.append(self._reconv_abierta)

    def sample(self, sim, medium):
        self.t.append(sim.t)
        gateways = [n for n in sim.nodes.values() if n.role == 'G']
        nodes = [n for n in sim.nodes.values() if n.role == 'N']
        self.alive_G.append(sum(1 for n in gateways if n.alive))
        self.alive_N.append(sum(1 for n in nodes if n.alive))
        self.comp_G.append(sim.gateway_components())
        self.node_reach.append(sim.nodes_in_mesh())

        tqs, hops = [], []
        for n in gateways + nodes:
            if not n.alive:
                continue
            with n.router._lock:
                for r in n.router.routes.values():
                    tqs.append(r.tq)
                    hops.append(r.hops)
        self.avg_tq.append(sum(tqs) / len(tqs) if tqs else 0.0)
        self.avg_hops.append(sum(hops) / len(hops) if hops else 0.0)

        # cuánto lleva el gateway más "callado" sin que otro lo oiga
        sil = 0.0
        for n in gateways:
            if not n.alive:
                continue
            for m in gateways:
                if m is n or not m.alive:
                    continue
                p = m.router.peers.get(n.id)
                if p is not None:
                    sil = max(sil, sim.t - p.last_seen)
        self.max_silence.append(sil)

        at, dl = medium._step_attempt, medium._step_deliver
        self.deliver_ratio.append(dl / at if at else 1.0)

        self.alerts_active.append(sum(
            1 for n in gateways + nodes if n.alive
            for p in n.router.peers.values() if p.in_alert))

        
        total_bw = 0.0
        for n in nodes:
            if n.alive:
                min_dist = float('inf')
                for g in gateways:
                    if g.alive:
                        dist = ((n.x - g.x)**2 + (n.y - g.y)**2)**0.5
                        if dist < min_dist:
                            min_dist = dist
                if min_dist != float('inf'):
                    # Max BW = 100 Mbps, atenuación 5 Mbps por metro
                    bw = max(0.0, 100.0 - min_dist * 5.0)
                    total_bw += bw
        self.bandwidth.append(total_bw)

        # sólo se mira mientras haya un episodio abierto: no cuesta nada
        # en las corridas sin recuperaciones ni reunificaciones
        if self._reconv_abierta is not None and rutas_convergidas(sim):
            self._reconv_abierta[1] = sim.t
            self._reconv_abierta = None


# ══════════════════════════════════════════════════════════════════════════
#  RUTAS VIGENTES
# ══════════════════════════════════════════════════════════════════════════
def ruta_vigente(sim, origen, destino_id):
    """¿`origen` (un SimNode) tiene una ruta vigente hacia `destino_id`?

    Vigente = la ruta existe en su BatmanRouter y su `last_seen` no supera
    el `timeout`. Es el `last_seen` de la ruta (RouteEntry), que sólo
    refrescan los OGM; no el del vecino (PeerInfo), que también refrescan
    los beacons. Las rutas de BatmanRouter no expiran solas, por eso hace
    falta este criterio.

    No mira las alertas: `PeerInfo.in_alert` se contagia (cada OGM lleva
    la lista de caídos de quien lo emite y marca en alerta a esos nodos en
    todos los que lo reciben, aunque los oigan bien), y
    `FaultManager.failed` sólo se limpia con un beacon directo, así que
    un Gateway a varios saltos queda marcado para siempre. Con cualquiera
    de las dos, en `denso` con `repartir` ningún episodio se cerraba.

    Es el mismo criterio para la métrica tiempo_reconvergencia_rutas_s y
    para la interfaz web (tabla de rutas y matriz de conocimiento).
    """
    ruta = origen.router.routes.get(destino_id)
    return ruta is not None and sim.t - ruta.last_seen <= sim.cfg['timeout']


def rutas_convergidas(sim):
    """True si todo par ordenado de Gateways vivos del mismo componente de
    radio tiene ruta vigente (ver ruta_vigente)."""
    vivos, find, idx = sim._union_find()
    gateways = [n for n in vivos if n.role == 'G']
    for a in gateways:
        for b in gateways:
            if a is not b and find(idx[a.id]) == find(idx[b.id]) \
                    and not ruta_vigente(sim, a, b.id):
                return False
    return True


# ══════════════════════════════════════════════════════════════════════════
#  RESUMEN DE UNA CORRIDA
# ══════════════════════════════════════════════════════════════════════════
# Métricas escalares de una corrida completa, todas derivadas de la serie
# temporal del Recorder, de sus eventos y de los contadores del medio (no
# hay instrumentación aparte). Orden de presentación: (clave, etiqueta,
# decimales). Un valor None significa "no aplica" en esa corrida.
METRICAS_CORRIDA = [
    ("tq_medio", "TQ medio de rutas", 3),
    ("saltos_medio", "Saltos medios por ruta", 2),
    ("tasa_entrega", "Tasa de entrega del radio", 3),
    ("componentes_finales", "Componentes de la malla al final", 2),
    ("nodos_alcanzables_finales", "Nodos de usuario alcanzables al final", 2),
    ("gateways_vivos_finales", "Gateways vivos al final", 2),
    ("particiones", "Episodios de partición", 2),
    ("tiempo_particionado_s", "Tiempo con la malla partida (s)", 1),
    ("tiempo_reconvergencia_s", "Tiempo de reconvergencia (s)", 1),
    ("alertas_gateway", "Alertas de gateway perdido", 2),
    ("t_primera_alerta_s", "Primera alerta (s)", 1),
    ("tiempo_reconvergencia_rutas_s", "Reconvergencia de rutas BATMAN (s)", 1),
]


def episodios_particion(t, comps, gateways_vivos):
    """Episodios en que la malla de gateways estuvo partida (comps > 1).

    Devuelve [(inicio, fin, reunificada), ...]: `fin` es el primer instante
    en que dejó de estar partida (None si siguió partida hasta el final), y
    `reunificada` dice si ese cierre fue una reunificación de verdad: volvió
    a un solo componente sin perder gateways en ese paso (el mismo criterio
    que el evento HEAL). Si la partición desaparece porque cayó un gateway
    (p. ej. el aislado se quedó sin batería) o porque no queda ninguno
    (comps == 0), el episodio se cierra sin reunificación.
    """
    episodios = []
    inicio = None
    for i, (ti, c) in enumerate(zip(t, comps)):
        if inicio is None:
            if c > 1:
                inicio = ti
        elif c <= 1:
            reunificada = (c == 1 and
                           gateways_vivos[i] >= gateways_vivos[i - 1])
            episodios.append((inicio, ti, reunificada))
            inicio = None
    if inicio is not None:
        episodios.append((inicio, None, False))
    return episodios


def resumen_corrida(sim):
    """Métricas escalares de la corrida (claves de METRICAS_CORRIDA).

    - tq_medio / saltos_medio: promedio en el tiempo de avg_tq / avg_hops
      (igual que "PROMEDIOS DE RENDIMIENTO" de reporte.txt).
    - tasa_entrega: paquetes entregados / intentados en toda la corrida.
    - componentes_finales, nodos_alcanzables_finales,
      gateways_vivos_finales: última muestra de comp_G, node_reach, alive_G.
    - particiones: episodios con la malla de gateways partida.
    - tiempo_particionado_s: muestras con comp_G > 1, por DT.
    - tiempo_reconvergencia_s: duración media de los episodios que se
      cerraron con una reunificación (ver episodios_particion); None si
      ninguno. Ojo: mide la duración de la partición *física* (enlaces de
      radio), no lo que tarda BATMAN en volver a tener rutas.
    - alertas_gateway / t_primera_alerta_s: cantidad de eventos ALERT_ON
      (un gateway deja de oír a otro más allá del timeout) y el instante
      del primero; None si no hubo.
    - tiempo_reconvergencia_rutas_s: duración media de los episodios de
      reconvergencia de rutas que se cerraron (Recorder.reconv_rutas):
      desde que vuelve un Gateway (RECOVER) o se reunifica la malla (HEAL)
      hasta que todo par de Gateways conectados por radio tiene ruta
      vigente (ver ruta_vigente). None si ninguno se cerró.
    """
    reconv = [fin - ini for ini, fin, _causa
              in getattr(sim.recorder, "reconv_rutas", []) if fin is not None]
    rec = sim.recorder
    n = len(rec.t)
    episodios = episodios_particion(rec.t, rec.comp_G, rec.alive_G)
    cerrados = [fin - ini for ini, fin, reunificada in episodios
                if reunificada]
    alertas = [t for (t, tipo, _txt) in rec.events if tipo == 'ALERT_ON']
    medio = sim.medium
    return {
        "tq_medio": sum(rec.avg_tq) / n if n else None,
        "saltos_medio": sum(rec.avg_hops) / n if n else None,
        "tasa_entrega": (medio.delivered / medio.attempted
                         if medio.attempted else None),
        "componentes_finales": rec.comp_G[-1] if n else None,
        "nodos_alcanzables_finales": rec.node_reach[-1] if n else None,
        "gateways_vivos_finales": rec.alive_G[-1] if n else None,
        "particiones": len(episodios),
        "tiempo_particionado_s": sum(1 for c in rec.comp_G if c > 1) * sim.DT,
        "tiempo_reconvergencia_s": (sum(cerrados) / len(cerrados)
                                    if cerrados else None),
        "alertas_gateway": len(alertas),
        "t_primera_alerta_s": min(alertas) if alertas else None,
        "tiempo_reconvergencia_rutas_s": (sum(reconv) / len(reconv)
                                          if reconv else None),
    }
