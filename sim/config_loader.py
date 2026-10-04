import copy
import json
import os

VALID_ROLES = {"G", "N"}

# Tipos de evento del escenario. `wander` aleja un Gateway hasta `until`;
# `fail`/`recover` hacen caer o volver un nodo en el instante `t` (los
# aplica Simulation.step, igual que las teclas F/G o la interfaz web).
TIPOS_EVENTO = ("wander", "fail", "recover")
EVENTOS_PROGRAMADOS = ("fail", "recover")

# Modelos de movilidad de los Gateway (clave "movilidad" de medium/protocol):
#   seguir   -> cada Gateway camina hacia el Nodo de usuario más cercano
#               (el de siempre, por defecto);
#   repartir -> un Gateway por Nodo de usuario vivo, emparejando primero
#               los pares más cercanos (ver docs/movimiento_nodos.md).
MOVILIDADES = ("seguir", "repartir")

# Claves de medium/protocol renombradas al pasar del vocabulario R/S al
# G/N. El nombre viejo se sigue aceptando para no romper escenarios
# escritos antes del cambio.
CLAVES_RENOMBRADAS = {"battery_drain_surv": "battery_drain_nodo"}


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

        [events]
        wander   4  80     # tipo  node_id  until
        fail     2  60     # tipo  node_id  t
        recover  2  90

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


def validar_escenario(data, origen="<escenario>", default_building=None):
    """Valida un escenario ya en memoria (un dict con el mismo esquema que
    el JSON) con las mismas reglas y mensajes que load_scenario. No
    modifica `data`: devuelve una copia validada. Lanza ValueError."""
    if not isinstance(data, dict):
        raise ValueError(f"{origen}: se esperaba un objeto con 'nodes'")
    try:
        return _validate(copy.deepcopy(data), origen, default_building)
    except (TypeError, AttributeError, KeyError) as e:
        raise ValueError(f"{origen}: escenario mal formado ({e})")


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
                    f"'wander node_id until' o 'fail|recover node_id t')"
                )
            ev_type, nid, instante = parts
            clave = "t" if ev_type in EVENTOS_PROGRAMADOS else "until"
            try:
                data["events"].append(
                    {"type": ev_type, "node_id": int(nid), clave: float(instante)}
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


def _renombrar_claves_viejas(data):
    for seccion in ("medium", "protocol"):
        valores = data.get(seccion)
        if not isinstance(valores, dict):
            continue
        for vieja, nueva in CLAVES_RENOMBRADAS.items():
            if vieja in valores:
                valor = valores.pop(vieja)
                valores.setdefault(nueva, valor)


def _validate(data, path, default_building=None):
    _renombrar_claves_viejas(data)
    for seccion in ("medium", "protocol"):
        valores = data.get(seccion)
        if isinstance(valores, dict) and "movilidad" in valores \
                and valores["movilidad"] not in MOVILIDADES:
            raise ValueError(
                f"{path}: movilidad desconocida {valores['movilidad']!r} "
                f"(válidas: {', '.join(MOVILIDADES)})"
            )
    building = dict(default_building or {})
    building.update(data.get("building", {}))
    ancho = building.get("ancho", 40.0)
    alto = building.get("alto", 30.0)

    if "random" in data:
        if any(isinstance(ev, dict) and ev.get("type") in EVENTOS_PROGRAMADOS
               for ev in data.get("events", [])):
            raise ValueError(
                f"{path}: los eventos 'fail'/'recover' necesitan nodos "
                f"explícitos, no el modo random"
            )
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
        tipo = ev.get("type")
        if tipo not in TIPOS_EVENTO:
            raise ValueError(
                f"{path}: tipo de evento desconocido: {tipo} (válidos: "
                f"{', '.join(TIPOS_EVENTO)})"
            )
        if ev.get("node_id") not in seen_ids:
            raise ValueError(
                f"{path}: evento '{tipo}' referencia node_id "
                f"{ev.get('node_id')} que no existe en 'nodes'"
            )
        if tipo == "wander":
            if "until" not in ev:
                raise ValueError(f"{path}: evento 'wander' sin campo 'until'")
            continue
        instante = ev.get("t")
        if isinstance(instante, bool) or not isinstance(instante, (int, float)):
            raise ValueError(
                f"{path}: evento '{tipo}' del nodo {ev['node_id']} sin un "
                f"instante 't' numérico"
            )
        if not (0 <= instante < float("inf")):
            raise ValueError(
                f"{path}: evento '{tipo}' del nodo {ev['node_id']} con "
                f"t={instante} (debe ser >= 0)"
            )

    data["building"] = building
    return data
