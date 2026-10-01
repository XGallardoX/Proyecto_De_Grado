"""Funciones puras que traducen el estado de una Simulation (y de la
Sesion que la envuelve) a diccionarios serializables en JSON.

Nada aquí modifica `sim`: son sólo lecturas. El llamador (Sesion o los
handlers HTTP) es responsable de tomar el lock antes de usarlas.
"""
import math
import re

from analysis.inspector import snapshot_red
from sim.radio import fiabilidad

ESQUEMA = 1

# Claves de sim.cfg que van en cada sección al exportar un escenario.
CLAVES_MEDIUM = ("rango_comm", "perdida_base", "falloff", "floor_atten")
CLAVES_PROTOCOL = ("timeout", "beacon_cada", "batman_cada", "ttl",
                   "battery_drain", "battery_drain_nodo", "move_speed",
                   "movilidad")

_PATRON_ETIQUETA = re.compile(r"\b([GN]\d+)\b")

# Cuántas líneas de log y eventos recientes van en cada frame. El cliente
# reconstruye el historial completo con /api/series si lo necesita (al
# cargar la página, por ejemplo); el frame sólo lleva lo último para que
# sea liviano a 15-20 Hz.
MAX_LOG_FRAME = 20
MAX_EVENTOS_FRAME = 20


def _colores(sim):
    return {
        "gateway": list(sim.C_GATEWAY),
        "nodo": sim.C_NODO,
        "caido": sim.C_DEAD,
        "alerta": sim.C_ALERT,
        "ogm": sim.C_OGM,
        "bcn": sim.C_BCN,
        "mensaje": sim.C_MSG,
        "fondo": sim.C_BG,
        "pared": sim.C_WALL,
        "piso": sim.C_FLOOR,
    }


def _cfg_editable(sim):
    """Sólo los parámetros de medium/protocol (no 'nodes'/'events', que son
    la definición estática del escenario, no algo que se edite en vivo)."""
    claves = set(sim.DEFAULTS.keys())
    return {k: v for k, v in sim.cfg.items() if k in claves}


def _nodos(sim):
    out = []
    for n in sim.nodes.values():
        en_alerta = (n.role == 'G' and n.alive and
                     any(p.in_alert for p in n.router.peers.values()))
        beacon = n.alive and bool(n.last_msg) and (sim.t - n.t_beacon) < 1.4
        out.append({
            "id": n.id,
            "etiqueta": n.label,
            "rol": n.role,
            "x": n.x,
            "y": n.y,
            "piso": n.piso,
            "vivo": n.alive,
            "bateria": n.battery,
            "color": n.color(),
            "en_alerta": en_alerta,
            "estela": [list(p) for p in n.history[-40:]],
            "beacon": beacon,
            "ultimo_mensaje": n.last_msg if beacon else None,
        })
    return out


def _enlaces(sim):
    vivos = [n for n in sim.nodes.values() if n.alive]
    out = []
    for i, a in enumerate(vivos):
        for b in vivos[i + 1:]:
            rel = sim.medium.reliability(a, b)
            if rel > 0.0:
                out.append({"a": a.id, "b": b.id, "fiabilidad": rel})
    return out


def _paquetes(sim):
    out = []
    for p in sim.medium.packets_visual:
        out.append({
            "origen_x": p.x, "origen_y": p.y,
            "destino_x": p.tx, "destino_y": p.ty,
            "progreso": p.progress, "tipo": p.tipo,
            "origen": p.origen, "ttl": p.ttl,
            "emisor": p.emisor, "receptor": p.receptor,
        })
    return out


def _vigilancia_de(sim, g):
    """Qué Gateways vigila `g` (los que FaultManager.check revisa) y cuánto
    lleva sin oír a cada uno, contra el timeout."""
    if g.role != 'G' or not g.alive:
        return []
    timeout = sim.cfg['timeout']
    with g.router._lock:
        peers = [p for p in g.router.peers.values()
                 if sim.is_gateway(p.node_id)]
        caidos = set(g.fault.failed)
    return [{
        "observador": g.id, "observado": p.node_id,
        "silencio": sim.t - p.last_seen, "timeout": timeout,
        "cree_caido": p.node_id in caidos,
        "proximo_chequeo": g.t_fault + 5.0,
    } for p in sorted(peers, key=lambda p: p.node_id)]


def _vigilancia(sim):
    out = []
    for n in sim.nodes.values():
        out.extend(_vigilancia_de(sim, n))
    return out


def _contadores(sim):
    """Uso del código real (mesh/) contra lo que aporta el modelo."""
    nodos = list(sim.nodes.values())
    return {
        "ogms_procesados": sum(n.ogms_procesados for n in nodos),
        "ogms_nuevos": sum(n.ogms_nuevos for n in nodos),
        "beacons_procesados": sum(n.beacons_procesados for n in nodos),
        "chequeos_fallo": sum(n.chequeos_fallo for n in nodos),
        "rutas_en_tablas": sum(len(n.router.routes) for n in nodos if n.alive),
        "caidas_detectadas": sum(len(n.fault.failed) for n in nodos if n.alive),
        "paquetes_intentados": sim.medium.attempted,
        "paquetes_entregados": sim.medium.delivered,
    }


def nodos_de_texto(sim, texto):
    """Ids de los nodos que menciona un texto de evento (por etiqueta)."""
    por_etiqueta = {n.label: n.id for n in sim.nodes.values()}
    return [por_etiqueta[e] for e in _PATRON_ETIQUETA.findall(texto)
            if e in por_etiqueta]


def _evento(sim, indice, t, tipo, texto):
    return {"indice": indice, "t": t, "tipo": tipo, "texto": texto,
            "nodos": nodos_de_texto(sim, texto)}


def _grupos(sim):
    alive, find, idx = sim._union_find()
    grupos = {}
    for n in alive:
        grupos.setdefault(find(idx[n.id]), []).append(n.id)
    return list(grupos.values())


def frame(sim, *, velocidad=1.0, semilla=None, error=None, generacion=0,
          static=False, intervenciones=0):
    """El estado completo de una Simulation para dibujar un cuadro en el
    navegador. Ligero: lo pesado (tabla de rutas por nodo, series
    completas, matriz, cobertura, inspector) va por sus propios
    endpoints."""
    rec = sim.recorder
    eventos = rec.events[-MAX_EVENTOS_FRAME:]
    desde = len(rec.events) - len(eventos)
    claves = set(sim.DEFAULTS.keys())
    return {
        "esquema": ESQUEMA,
        "generacion": generacion,
        "t": sim.t,
        "pausado": sim.paused,
        "velocidad": velocidad,
        "escenario": sim.escenario,
        "semilla": semilla,
        "static": static,
        "intervenciones": intervenciones,
        "error": error,
        "cfg_base": {k: v for k, v in sim._base_cfg.items() if k in claves},
        "vigilancia": _vigilancia(sim),
        "contadores": _contadores(sim),
        "edificio": {
            "ancho": sim.ANCHO, "alto": sim.ALTO,
            "piso_h": sim.PISO_H, "n_pisos": sim.N_PISOS,
            "stair_xy": list(sim.STAIR_XY),
            "stair_half_w": sim.STAIR_HALF_W,
        },
        "cfg": _cfg_editable(sim),
        "colores": _colores(sim),
        "nodos": _nodos(sim),
        "enlaces": _enlaces(sim),
        "paquetes": _paquetes(sim),
        "resumen": sim.summary(),
        "grupos": _grupos(sim),
        "nodos_alcanzables": sim.nodes_in_mesh(),
        "eventos_nuevos": [
            _evento(sim, desde + i, t, tipo, texto)
            for i, (t, tipo, texto) in enumerate(eventos)
        ],
        "eventos_total": len(rec.events),
        "log": [
            {"t": t, "texto": texto, "tipo": tipo}
            for (t, texto, tipo) in sim.log_lines[-MAX_LOG_FRAME:]
        ],
        "ultima_muestra": _ultima_muestra(rec),
    }


def _ultima_muestra(rec):
    if not rec.t:
        return None
    i = -1
    return {
        "t": rec.t[i], "alive_g": rec.alive_G[i], "alive_n": rec.alive_N[i],
        "comp_g": rec.comp_G[i], "node_reach": rec.node_reach[i],
        "avg_tq": rec.avg_tq[i], "avg_hops": rec.avg_hops[i],
        "max_silence": rec.max_silence[i],
        "deliver_ratio": rec.deliver_ratio[i],
        "alerts_active": rec.alerts_active[i], "bandwidth": rec.bandwidth[i],
    }


def nodo_detalle(sim, nid):
    """Detalle de un nodo: tabla de rutas, vecinos y a quién cree caído.
    None si `nid` no existe."""
    n = sim.nodes.get(nid)
    if n is None:
        return None
    timeout = sim.cfg['timeout']
    with n.router._lock:
        peers = dict(n.router.peers)
        routes = list(n.router.routes.values())
        failed = sorted(n.fault.failed)

    rutas = []
    for r in sorted(routes, key=lambda r: r.dest):
        p = peers.get(r.dest)
        obsoleta = bool(p and (p.in_alert or p.is_lost(sim.t, timeout)))
        rutas.append({
            "destino": r.dest, "destino_etiqueta": sim.label_of(r.dest),
            "via": r.via_id, "via_etiqueta": sim.label_of(r.via_id),
            "hops": r.hops, "tq": r.tq, "seq": r.seq,
            "edad_s": sim.t - r.last_seen, "obsoleta": obsoleta,
        })

    vecinos = []
    for p in sorted(peers.values(), key=lambda p: p.node_id):
        vecinos.append({
            "id": p.node_id, "etiqueta": sim.label_of(p.node_id),
            "ultimo_visto_s": sim.t - p.last_seen, "tq": p.tq,
            "hops": p.hops, "bateria": p.battery, "en_alerta": p.in_alert,
        })

    # Lo que la radio conecta (mismo grupo de _union_find) pero el nodo
    # todavía no tiene en su tabla: "aún no converge".
    sin_ruta = []
    if n.alive:
        alive, find, idx = sim._union_find()
        mio = find(idx[n.id])
        conocidos = {r.dest for r in routes}
        sin_ruta = sorted(m.id for m in alive
                          if m.id != n.id and find(idx[m.id]) == mio
                          and m.id not in conocidos)

    return {
        "id": n.id, "etiqueta": n.label, "rol": n.role, "vivo": n.alive,
        "bateria": n.battery, "x": n.x, "y": n.y, "piso": n.piso,
        "rutas": rutas, "vecinos": vecinos,
        "cree_caidos": [{"id": fid, "etiqueta": sim.label_of(fid)}
                        for fid in failed],
        "alcanzables_sin_ruta": [{"id": i, "etiqueta": sim.label_of(i)}
                                 for i in sin_ruta],
        "vigilancia": _vigilancia_de(sim, n),
    }


SERIES_CAMPOS = ("t", "alive_G", "alive_N", "comp_G", "node_reach",
                 "avg_tq", "avg_hops", "max_silence", "deliver_ratio",
                 "alerts_active", "bandwidth")


def series(sim, desde=0, desde_evento=0):
    """Series del Recorder a partir de la muestra `desde` (0 = completas,
    para reconstruir las gráficas al conectar o recargar) y los eventos a
    partir de `desde_evento`, cada uno con su índice. `total` y
    `eventos_total` permiten al cliente pedir sólo lo nuevo."""
    rec = sim.recorder
    desde = max(0, int(desde))
    desde_evento = max(0, int(desde_evento))
    return {
        "desde": desde,
        "total": len(rec.t),
        "series": {campo: list(getattr(rec, campo)[desde:])
                   for campo in SERIES_CAMPOS},
        "eventos_total": len(rec.events),
        "eventos": [_evento(sim, desde_evento + i, t, tipo, texto)
                    for i, (t, tipo, texto)
                    in enumerate(rec.events[desde_evento:])],
        "timeout": sim.cfg['timeout'],
    }


def _orden(sim, n):
    return (n.role, sim.local_index[n.id])


def matriz_conocimiento(sim):
    """Matriz N×N: fila = el nodo que sabe, columna = el destino. Cada
    celda es 'vigente' (ruta en la tabla, con sus saltos), 'obsoleta'
    (ruta en la tabla pero el destino está en alerta o su last_seen supera
    el timeout), 'sin_converger' (sin ruta, pero la radio los conecta) o
    'sin_conexion'. Métrica sólo de visualización: no va a los reportes."""
    nodos = sorted(sim.nodes.values(), key=lambda n: _orden(sim, n))
    alive, find, idx = sim._union_find()
    grupo = {n.id: find(idx[n.id]) for n in alive}
    timeout = sim.cfg['timeout']
    filas, conectados, con_ruta = [], 0, 0
    for a in nodos:
        with a.router._lock:
            rutas = dict(a.router.routes)
            peers = dict(a.router.peers)
        celdas = []
        for b in nodos:
            if a.id == b.id:
                celdas.append({"estado": "propio"})
                continue
            fisico = (a.id in grupo and b.id in grupo
                      and grupo[a.id] == grupo[b.id])
            r = rutas.get(b.id) if a.alive else None
            if r is not None:
                p = peers.get(b.id)
                obsoleta = bool(p and (p.in_alert or p.is_lost(sim.t, timeout)))
                celda = {"estado": "obsoleta" if obsoleta else "vigente",
                         "hops": r.hops}
            elif fisico:
                celda = {"estado": "sin_converger"}
            else:
                celda = {"estado": "sin_conexion"}
            if fisico:
                conectados += 1
                con_ruta += celda["estado"] == "vigente"
            celdas.append(celda)
        filas.append({"id": a.id, "etiqueta": a.label, "vivo": a.alive,
                      "celdas": celdas})
    return {
        "nodos": [{"id": n.id, "etiqueta": n.label} for n in nodos],
        "filas": filas,
        "pares_conectados": conectados,
        "pares_con_ruta": con_ruta,
    }


def cobertura(sim, paso=1.0):
    """Mapa de cobertura: en cada celda del edificio, la mejor fiabilidad
    hacia algún Gateway vivo, con la misma fórmula del medio
    (sim.radio.fiabilidad). Filas de abajo hacia arriba (y creciente)."""
    gateways = [n for n in sim.nodes.values() if n.role == 'G' and n.alive]
    nx = max(1, int(math.ceil(sim.ANCHO / paso)))
    ny = max(1, int(math.ceil(sim.ALTO / paso)))
    valores = []
    for j in range(ny):
        y = (j + 0.5) * paso
        piso = max(1, min(sim.N_PISOS, int(y // sim.PISO_H) + 1))
        for i in range(nx):
            x = (i + 0.5) * paso
            mejor = 0.0
            for g in gateways:
                rel = fiabilidad(math.hypot(g.x - x, g.y - y),
                                 abs(g.piso - piso), sim.cfg)
                if rel > mejor:
                    mejor = rel
            valores.append(mejor)
    return {"paso": paso, "nx": nx, "ny": ny, "valores": valores}


def escenario_actual(sim, posiciones="iniciales"):
    """El escenario de la sesión como dict con el esquema de los JSON de
    escenarios/ (lo que abre el editor). Con posiciones='iniciales' usa
    las del archivo cuando existen (los nodos añadidos después, con la
    posición actual); con 'actuales', dónde están ahora."""
    iniciales = {s["id"]: s for s in (sim.cfg.get("nodes") or [])}
    nodos = []
    for n in sorted(sim.nodes.values(), key=lambda n: n.id):
        spec = iniciales.get(n.id)
        if posiciones == "iniciales" and spec is not None:
            x, y = spec["x"], spec["y"]
        else:
            x, y = n.x, n.y
        nodo = {"id": n.id, "role": n.role,
                "x": round(float(x), 2), "y": round(float(y), 2)}
        if spec is not None and "battery" in spec:
            nodo["battery"] = spec["battery"]
        nodos.append(nodo)
    return {
        "name": sim.escenario,
        "building": {"ancho": sim.ANCHO, "alto": sim.ALTO,
                     "piso_h": sim.PISO_H, "n_pisos": sim.N_PISOS,
                     "stair_xy": list(sim.STAIR_XY),
                     "stair_half_w": sim.STAIR_HALF_W},
        "medium": {k: sim.cfg[k] for k in CLAVES_MEDIUM if k in sim.cfg},
        "protocol": {k: sim.cfg[k] for k in CLAVES_PROTOCOL if k in sim.cfg},
        "nodes": nodos,
        "events": [dict(e) for e in (sim.cfg.get("events") or [])],
    }


def inspector_texto(sim):
    return snapshot_red(sim)
