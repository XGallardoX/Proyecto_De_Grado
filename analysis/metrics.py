from sim.datos import CAUSAS


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
        # plano de datos (sim/datos.py): acumulados y la fracción entregada
        # en la última ventana; sin tráfico quedan en 0, 0 y 1.0
        self.datos_enviados = []
        self.datos_entregados = []
        self.entrega_datos = []
        # descentralización: qué fracción de los pares (a, b) cree lo
        # correcto sobre si puede llegar a b, y cuántos nodos son críticos
        self.exactitud = []
        self.rutas_fantasma = []
        self.rutas_faltantes = []
        self.nodos_criticos = []
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

        datos = getattr(sim, "datos", None)
        self.datos_enviados.append(datos.enviados if datos else 0)
        self.datos_entregados.append(datos.entregados if datos else 0)
        self.entrega_datos.append(datos.entrega_reciente(sim.t) if datos else 1.0)

        exacta, fantasma, faltante = conocimiento(sim)
        self.exactitud.append(exacta)
        self.rutas_fantasma.append(fantasma)
        self.rutas_faltantes.append(faltante)
        self.nodos_criticos.append(len(puntos_articulacion(sim)))

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
    `FaultManager.failed` sólo se limpia cuando llega un beacon directo o
    un OGM nuevo del nodo, así que tarda en apagarse. Con cualquiera de
    las dos, en `denso` con `repartir` ningún episodio se cerraba.

    Es el mismo criterio para la métrica tiempo_reconvergencia_rutas_s y
    para la interfaz web (tabla de rutas y matriz de conocimiento).
    """
    ruta = origen.router.routes.get(destino_id)
    return ruta is not None and sim.t - ruta.last_seen <= sim.cfg['timeout']


def conocimiento(sim):
    """Cuánto coincide lo que cree cada nodo con la realidad, sobre los
    pares ordenados (a, b) de nodos vivos distintos. Devuelve fracciones
    (exactos, fantasmas, faltantes):
    - exacto: a tiene ruta vigente hacia b si y sólo si la radio los
      conecta (mismo grupo de radio);
    - fantasma: a tiene ruta vigente, pero la radio ya no los conecta;
    - faltante: la radio los conecta, pero a no tiene ruta vigente.
    Con menos de dos nodos vivos, (1.0, 0.0, 0.0). Ver ruta_vigente."""
    vivos, find, idx = sim._union_find()
    pares = fantasmas = faltantes = 0
    for a in vivos:
        for b in vivos:
            if a is b:
                continue
            pares += 1
            fisico = find(idx[a.id]) == find(idx[b.id])
            cree = ruta_vigente(sim, a, b.id)
            fantasmas += cree and not fisico
            faltantes += fisico and not cree
    if not pares:
        return 1.0, 0.0, 0.0
    return (1 - (fantasmas + faltantes) / pares, fantasmas / pares,
            faltantes / pares)


def _adyacencia(sim, vivos):
    return {a.id: [b.id for b in vivos
                   if b is not a and sim.medium.reliability(a, b) > 0.0]
            for a in vivos}


def puntos_articulacion(sim):
    """Ids de los nodos vivos cuya caída parte su grupo de radio en dos o
    más (puntos de articulación del grafo de enlaces): los puntos únicos de
    falla de la malla. Tarjan iterativo, en orden de id (determinista)."""
    vivos = sorted((n for n in sim.nodes.values() if n.alive), key=lambda n: n.id)
    ady = _adyacencia(sim, vivos)
    orden, bajo, criticos = {}, {}, set()
    contador = 0
    for raiz in ady:
        if raiz in orden:
            continue
        orden[raiz] = bajo[raiz] = contador
        contador += 1
        hijos_raiz = 0
        pila = [(raiz, None, iter(ady[raiz]))]
        while pila:
            v, padre, vecinos = pila[-1]
            avanzo = False
            for w in vecinos:
                if w == padre:
                    continue
                if w in orden:
                    bajo[v] = min(bajo[v], orden[w])
                else:
                    orden[w] = bajo[w] = contador
                    contador += 1
                    if v == raiz:
                        hijos_raiz += 1
                    pila.append((w, v, iter(ady[w])))
                    avanzo = True
                    break
            if avanzo:
                continue
            pila.pop()
            if padre is not None:
                bajo[padre] = min(bajo[padre], bajo[v])
                if padre != raiz and bajo[v] >= orden[padre]:
                    criticos.add(padre)
        if hijos_raiz > 1:
            criticos.add(raiz)
    return sorted(criticos)


def nodos_cortados(sim, nid):
    """Cuántos nodos vivos quedarían separados del grupo de radio más
    grande si `nid` cayera (sin contar a `nid`). 0 si no es crítico."""
    vivos = [n for n in sim.nodes.values() if n.alive and n.id != nid]
    ady = _adyacencia(sim, vivos)
    vistos, mayor = set(), 0
    for inicio in ady:
        if inicio in vistos:
            continue
        grupo, pila = 0, [inicio]
        vistos.add(inicio)
        while pila:
            v = pila.pop()
            grupo += 1
            for w in ady[v]:
                if w not in vistos:
                    vistos.add(w)
                    pila.append(w)
        mayor = max(mayor, grupo)
    return len(vivos) - mayor


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
    ("cobertura_media", "Cobertura media de Nodos de usuario", 3),
    ("entrega_datos", "Entrega de datos", 3),
    ("entrega_datos_con_camino", "Entrega de datos con camino por radio", 3),
    ("saltos_datos", "Saltos de los datos entregados", 2),
    ("estiramiento_datos", "Estiramiento (saltos / camino más corto)", 3),
    ("perdida_destino_caido", "Datos perdidos: destino caído", 3),
    ("perdida_sin_camino", "Datos perdidos: sin camino por radio", 3),
    ("perdida_sin_ruta", "Datos perdidos: sin ruta", 3),
    ("perdida_ruta_vieja", "Datos perdidos: ruta vieja", 3),
    ("perdida_enlace", "Datos perdidos: la radio perdió el salto", 3),
    ("perdida_bucle", "Datos perdidos: bucle", 3),
    ("exactitud_conocimiento", "Exactitud del conocimiento de rutas", 3),
    ("rutas_fantasma", "Pares con ruta fantasma", 3),
    ("rutas_faltantes", "Pares con ruta faltante", 3),
    ("nodos_criticos_medio", "Nodos críticos (articulación), media", 2),
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
    - cobertura_media: promedio en el tiempo de la fracción de Nodos de
      usuario vivos que están alcanzables (node_reach / alive_N). Se saltan
      las muestras sin Nodos vivos; None si no queda ninguna. A diferencia
      de nodos_alcanzables_finales, cuenta cuánta cobertura se perdió
      mientras un Gateway estuvo caído.
    - entrega_datos: paquetes de datos entregados / enviados por el plano
      de datos (sim/datos.py), enrutados salto a salto por las tablas de
      BATMAN. None si no hubo tráfico; lo mismo las demás de datos.
    - entrega_datos_con_camino: lo mismo, sólo entre los paquetes que
      tenían destino vivo y algún camino por radio al enviarse: cuánto
      entrega el enrutamiento cuando la física lo permite. None si ninguno.
    - saltos_datos / estiramiento_datos: media de los saltos de los
      entregados, y de saltos / saltos del camino más corto por radio en
      el instante del envío (1.0 = BATMAN eligió un camino mínimo).
    - perdida_*: fracción de los enviados que se perdió por cada causa de
      sim.datos.CAUSAS; suman 1 - entrega_datos.
    - exactitud_conocimiento / rutas_fantasma / rutas_faltantes: promedio
      en el tiempo de conocimiento(): la fracción de pares (a, b) de nodos
      vivos en que a cree lo correcto sobre si puede llegar a b, y las
      que cree tener sin que la radio los conecte o al revés.
    - nodos_criticos_medio: promedio en el tiempo de la cantidad de puntos
      de articulación de la malla (puntos únicos de falla).
    """
    reconv = [fin - ini for ini, fin, _causa
              in getattr(sim.recorder, "reconv_rutas", []) if fin is not None]
    rec = sim.recorder
    fracciones = [alc / vivos for alc, vivos in zip(rec.node_reach, rec.alive_N)
                  if vivos > 0]
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
        "cobertura_media": (sum(fracciones) / len(fracciones)
                            if fracciones else None),
        **_resumen_datos(getattr(sim, "datos", None)),
        "exactitud_conocimiento": _media(getattr(rec, "exactitud", [])),
        "rutas_fantasma": _media(getattr(rec, "rutas_fantasma", [])),
        "rutas_faltantes": _media(getattr(rec, "rutas_faltantes", [])),
        "nodos_criticos_medio": _media(getattr(rec, "nodos_criticos", [])),
    }


def _media(xs):
    return sum(xs) / len(xs) if xs else None


def _resumen_datos(datos):
    """Las métricas del plano de datos de resumen_corrida."""
    claves = ("entrega_datos", "entrega_datos_con_camino", "saltos_datos",
              "estiramiento_datos") + tuple(f"perdida_{c}" for c in CAUSAS)
    if datos is None or not datos.enviados:
        return dict.fromkeys(claves)
    env = datos.enviados
    con_camino = env - datos.perdidas["destino_caido"] - datos.perdidas["sin_camino"]
    media = lambda xs: sum(xs) / len(xs) if xs else None
    return {
        "entrega_datos": datos.entregados / env,
        "entrega_datos_con_camino": (datos.entregados / con_camino
                                     if con_camino else None),
        "saltos_datos": media(datos.saltos),
        "estiramiento_datos": media(datos.estiramientos),
        **{f"perdida_{c}": datos.perdidas[c] / env for c in CAUSAS},
    }
