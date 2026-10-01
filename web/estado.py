"""Funciones puras que traducen el estado de una Simulation (y de la
Sesion que la envuelve) a diccionarios serializables en JSON.

Nada aquí modifica `sim`: son sólo lecturas. El llamador (Sesion o los
handlers HTTP) es responsable de tomar el lock antes de usarlas.
"""
from analysis.inspector import snapshot_red

ESQUEMA = 1

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
        if p.color == sim.C_OGM:
            tipo = "OGM"
        elif p.color == sim.C_BCN:
            tipo = "BCN"
        else:
            tipo = "MSG"
        out.append({
            "origen_x": p.x, "origen_y": p.y,
            "destino_x": p.tx, "destino_y": p.ty,
            "progreso": p.progress, "tipo": tipo,
        })
    return out


def _grupos(sim):
    alive, find, idx = sim._union_find()
    grupos = {}
    for n in alive:
        grupos.setdefault(find(idx[n.id]), []).append(n.id)
    return list(grupos.values())


def frame(sim, *, velocidad=1.0, semilla=None, error=None):
    """El estado completo de una Simulation para dibujar un cuadro en el
    navegador. Ligero: lo pesado (tabla de rutas por nodo, series
    completas, inspector) va por sus propios endpoints."""
    rec = sim.recorder
    eventos = rec.events[-MAX_EVENTOS_FRAME:]
    desde = len(rec.events) - len(eventos)
    return {
        "esquema": ESQUEMA,
        "t": sim.t,
        "pausado": sim.paused,
        "velocidad": velocidad,
        "escenario": sim.escenario,
        "semilla": semilla,
        "error": error,
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
            {"indice": desde + i, "t": t, "tipo": tipo, "texto": texto}
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

    return {
        "id": n.id, "etiqueta": n.label, "rol": n.role, "vivo": n.alive,
        "bateria": n.battery, "x": n.x, "y": n.y, "piso": n.piso,
        "rutas": rutas, "vecinos": vecinos,
        "cree_caidos": [{"id": fid, "etiqueta": sim.label_of(fid)}
                        for fid in failed],
    }


SERIES_CAMPOS = ("t", "alive_G", "alive_N", "comp_G", "node_reach",
                 "avg_tq", "avg_hops", "max_silence", "deliver_ratio",
                 "alerts_active", "bandwidth")


def series(sim):
    """Series completas del Recorder (para reconstruir las gráficas al
    conectar o recargar) más los eventos, cada uno con su índice."""
    rec = sim.recorder
    return {
        "series": {campo: list(getattr(rec, campo)) for campo in SERIES_CAMPOS},
        "eventos": [{"indice": i, "t": t, "tipo": tipo, "texto": texto}
                    for i, (t, tipo, texto) in enumerate(rec.events)],
    }


def inspector_texto(sim):
    return snapshot_red(sim)
