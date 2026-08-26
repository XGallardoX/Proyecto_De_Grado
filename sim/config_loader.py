import json

VALID_ROLES = {"G", "N"}


def load_scenario(path, default_building=None):
    """Carga y valida un archivo de escenario JSON.

    Formato esperado:
        {
          "name": "...",
          "building": {"ancho": .., "alto": .., "piso_h": .., "n_pisos": ..,
                       "stair_xy": [x, y], "stair_half_w": ..},
          "medium": {"rango_comm": .., "falloff": .., ...},
          "protocol": {"timeout": .., "beacon_cada": .., ...},
          "nodes": [{"id": 1, "role": "G", "x": 7, "y": 27}, ...]
        }

    Sólo "nodes" es obligatorio; el resto usa los valores de
    `default_building`/los DEFAULTS del simulador si falta.
    Lanza ValueError con un mensaje claro ante cualquier config inválida.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ValueError(f"{path}: archivo no encontrado")
    except json.JSONDecodeError as e:
        raise ValueError(f"{path}: JSON inválido ({e})")

    nodes = data.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError(f"{path}: falta 'nodes' o está vacío")

    building = dict(default_building or {})
    building.update(data.get("building", {}))
    ancho = building.get("ancho", 40.0)
    alto = building.get("alto", 30.0)

    seen_ids = set()
    n_gateways = 0
    for spec in nodes:
        for field in ("id", "role", "x", "y"):
            if field not in spec:
                raise ValueError(f"{path}: nodo {spec} sin campo obligatorio '{field}'")
        nid = spec["id"]
        if nid in seen_ids:
            raise ValueError(f"{path}: id de nodo duplicado: {nid}")
        seen_ids.add(nid)

        role = spec["role"]
        if role not in VALID_ROLES:
            raise ValueError(
                f"{path}: rol inválido '{role}' en nodo {nid} "
                f"(debe ser 'G'=Gateway o 'N'=Nodo)"
            )
        if role == "G":
            n_gateways += 1

        x, y = spec["x"], spec["y"]
        if not (0 <= x <= ancho and 0 <= y <= alto):
            raise ValueError(
                f"{path}: nodo {nid} en ({x}, {y}) queda fuera del "
                f"edificio [0,{ancho}]x[0,{alto}]"
            )

        if "battery" in spec and not (0 <= spec["battery"] <= 100):
            raise ValueError(
                f"{path}: nodo {nid} tiene battery={spec['battery']} "
                f"fuera de [0,100]"
            )

    if n_gateways == 0:
        raise ValueError(f"{path}: se requiere al menos un nodo con role 'G' (Gateway)")

    for ev in data.get("events", []):
        if ev.get("type") != "wander":
            raise ValueError(f"{path}: tipo de evento desconocido: {ev.get('type')}")
        if ev.get("node_id") not in seen_ids:
            raise ValueError(
                f"{path}: evento 'wander' referencia node_id "
                f"{ev.get('node_id')} que no existe en 'nodes'"
            )
        if "until" not in ev:
            raise ValueError(f"{path}: evento 'wander' sin campo 'until'")

    data["building"] = building
    return data
