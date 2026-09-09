import json
import os

VALID_ROLES = {"G", "N"}


def load_scenario(path, default_building=None):
    """Carga y valida un archivo de escenario, en JSON (.json) o texto
    plano (.txt) — el formato se detecta por la extensión.

    Formato JSON esperado:
        {
          "name": "...",
          "building": {"ancho": .., "alto": .., "piso_h": .., "n_pisos": ..,
                       "stair_xy": [x, y], "stair_half_w": ..},
          "medium": {"rango_comm": .., "falloff": .., ...},
          "protocol": {"timeout": .., "beacon_cada": .., ...},
          "nodes": [{"id": 1, "role": "G", "x": 7, "y": 27}, ...]
        }

    Formato .txt equivalente (ver README para el detalle completo):
        name: mi_escenario

        [building]
        ancho=40
        alto=30

        [protocol]
        static=true

        [nodes]
        1  G  7   27
        2  N  10  10

    En vez de nodos explícitos, [nodes] también acepta modo aleatorio:
        [nodes]
        mode=random
        n_nodes=5
        n_gateways=2

    Sólo "nodes" (o el modo aleatorio) es obligatorio; el resto usa los
    valores de `default_building`/los DEFAULTS del simulador si falta.
    Lanza ValueError con un mensaje claro ante cualquier config inválida.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext == ".txt":
        data = _parse_txt(path)
    else:
        data = _parse_json(path)
    return _validate(data, path, default_building)


def _parse_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise ValueError(f"{path}: archivo no encontrado")
    except json.JSONDecodeError as e:
        raise ValueError(f"{path}: JSON inválido ({e})")


def _parse_value(raw):
    raw = raw.strip()
    low = raw.lower()
    if low in ("true", "yes", "si", "sí"):
        return True
    if low in ("false", "no"):
        return False
    if "," in raw:
        return [_parse_value(p) for p in raw.split(",")]
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def _parse_txt(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        raise ValueError(f"{path}: archivo no encontrado")

    data = {"building": {}, "medium": {}, "protocol": {}, "nodes": [], "events": []}
    random_cfg = {}
    section = None

    for lineno, raw_line in enumerate(lines, start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
            if section not in ("building", "medium", "protocol", "nodes", "events"):
                raise ValueError(f"{path}:{lineno}: sección desconocida '[{section}]'")
            continue

        if section is None:
            key, sep, value = line.partition(":")
            if not sep or key.strip().lower() != "name":
                raise ValueError(
                    f"{path}:{lineno}: se esperaba 'name: ...' o una sección "
                    f"'[building]/[medium]/[protocol]/[nodes]/[events]', se "
                    f"encontró '{line}'"
                )
            data["name"] = value.strip()

        elif section in ("building", "medium", "protocol"):
            key, sep, value = line.partition("=")
            if not sep:
                raise ValueError(
                    f"{path}:{lineno}: se esperaba 'clave=valor' en "
                    f"[{section}], se encontró '{line}'"
                )
            key, value = key.strip(), _parse_value(value)
            if section == "protocol" and key.lower() == "static":
                if value:
                    data["protocol"]["move_speed"] = 0
                continue
            data[section][key] = value

        elif section == "nodes":
            if "=" in line:
                key, _, value = line.partition("=")
                random_cfg[key.strip().lower()] = _parse_value(value)
                continue
            parts = line.split()
            if len(parts) not in (4, 5):
                raise ValueError(
                    f"{path}:{lineno}: nodo inválido '{line}' (se esperaba "
                    f"'id role x y [battery]')"
                )
            try:
                node = {"id": int(parts[0]), "role": parts[1],
                        "x": float(parts[2]), "y": float(parts[3])}
                if len(parts) == 5:
                    node["battery"] = float(parts[4])
            except ValueError:
                raise ValueError(f"{path}:{lineno}: nodo inválido '{line}'")
            data["nodes"].append(node)

        elif section == "events":
            parts = line.split()
            if len(parts) != 3:
                raise ValueError(
                    f"{path}:{lineno}: evento inválido '{line}' (se esperaba "
                    f"'type node_id until')"
                )
            ev_type, nid, until = parts
            try:
                data["events"].append(
                    {"type": ev_type, "node_id": int(nid), "until": float(until)}
                )
            except ValueError:
                raise ValueError(f"{path}:{lineno}: evento inválido '{line}'")

    if random_cfg:
        if data["nodes"]:
            raise ValueError(
                f"{path}: [nodes] no puede mezclar nodos explícitos con "
                f"'mode=random'"
            )
        del data["nodes"]
        data["random"] = random_cfg

    return data


def _validate(data, path, default_building=None):
    building = dict(default_building or {})
    building.update(data.get("building", {}))
    ancho = building.get("ancho", 40.0)
    alto = building.get("alto", 30.0)

    if "random" in data:
        rnd = data["random"]
        n_nodes = rnd.get("n_nodes")
        n_gateways = rnd.get("n_gateways", 1)
        if not isinstance(n_nodes, (int, float)) or n_nodes <= 1:
            raise ValueError(
                f"{path}: modo random requiere 'n_nodes' > 1"
            )
        if not isinstance(n_gateways, (int, float)) or n_gateways >= n_nodes:
            raise ValueError(
                f"{path}: modo random requiere 'n_gateways' < 'n_nodes'"
            )
        data["random"] = {"n_nodes": int(n_nodes), "n_gateways": int(n_gateways)}
        data["building"] = building
        return data

    nodes = data.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError(
            f"{path}: falta 'nodes' (o [nodes]/'mode=random') o está vacío"
        )

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
