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

    def event(self, t, tipo, texto):
        self.events.append((t, tipo, texto))

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
]


def episodios_particion(t, comps):
    """Episodios en que la malla de gateways estuvo partida (comps > 1).

    Devuelve [(inicio, fin), ...]: `fin` es el primer instante en que volvió
    a haber un solo componente (el mismo criterio que el evento HEAL), o
    None si el episodio no se cerró (siguió partida hasta el final, o se
    quedó sin gateways vivos: comps == 0).
    """
    episodios = []
    inicio = None
    for ti, c in zip(t, comps):
        if inicio is None:
            if c > 1:
                inicio = ti
        elif c <= 1:
            episodios.append((inicio, ti if c == 1 else None))
            inicio = None
    if inicio is not None:
        episodios.append((inicio, None))
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
      cerraron (volvió a 1 componente); None si ninguno se cerró.
    - alertas_gateway / t_primera_alerta_s: cantidad de eventos ALERT_ON
      (un gateway deja de oír a otro más allá del timeout) y el instante
      del primero; None si no hubo.
    """
    rec = sim.recorder
    n = len(rec.t)
    episodios = episodios_particion(rec.t, rec.comp_G)
    cerrados = [fin - ini for ini, fin in episodios if fin is not None]
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
    }
