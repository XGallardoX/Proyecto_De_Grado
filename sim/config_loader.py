import copy
import json
import os

VALID_ROLES = {"G", "N"}
TIPOS_MAPA = ("edificio", "campo")

# Tipos de evento del escenario. `wander` aleja un Gateway hasta `until`;
# `fail`/`recover` hacen caer o volver un nodo en el instante `t` (los
# aplica Simulation.step, igual que las teclas F/G o la interfaz web).
TIPOS_EVENTO = ("wander", "fail", "recover", "fail_azar", "fail_critico")
EVENTOS_PROGRAMADOS = ("fail", "recover")
# Caídas cuyo nodo se elige al llegar el instante `t`, entre los vivos de
# `rol` ("G", "N" o "*"): uno al azar, o el más crítico (el que deja más
# nodos separados del grupo de radio más grande). Para comparar fallos al
# azar con ataques dirigidos.
EVENTOS_ELEGIDOS = ("fail_azar", "fail_critico")
ROLES_EVENTO = ("G", "N", "*")

# Modelos de movilidad de los Gateway (clave "movilidad" de medium/protocol):
#   seguir   -> cada Gateway camina hacia el Nodo de usuario más cercano
#               (el de siempre, por defecto);
#   repartir -> un Gateway por Nodo de usuario vivo, emparejando primero
#               los pares más cercanos (ver docs/movimiento_nodos.md);
#   descentralizada -> cada Gateway decide sólo con lo que oye en los
#               beacons de sus vecinos (fuerzas virtuales, SimNode).
# seguir y repartir miran las posiciones de todos los nodos: son la línea
# base centralizada contra la que se compara la descentralizada.
MOVILIDADES = ("seguir", "repartir", "descentralizada")

# Cómo viajan los datos (sim/datos.py): "batman" = salto a salto por las
# tablas de BatmanRouter; "inundacion" = cada nodo reenvía una vez cada
# paquete nuevo, sin tablas (el protocolo de comparación).
PROTOCOLOS_DATOS = ("batman", "inundacion")

# Movilidad de los Nodos de usuario (SimNode.move): "quietos" = casi
# estáticos (un temblor mínimo, como siempre); "random_waypoint" = cada uno
# va a un punto al azar, espera y elige otro; "grupos" = de a tres, el
# primero hace random waypoint y los demás lo siguen (RPGM).
MOVILIDADES_USUARIOS = ("quietos", "random_waypoint", "grupos")

# Parámetros del simulador que se pueden fijar con --param clave=valor, con
# "parametros" en una entrada de lote o en vivo desde la interfaz web: sólo
# claves que el núcleo vuelve a leer de sim.cfg en cada paso (verificado
# una por una):
#   RadioMedium.reliability -> rango_comm, falloff, perdida_base,
#     floor_atten (medium.cfg es el mismo dict que sim.cfg);
#   SimNode.tick -> timeout, beacon_cada, batman_cada, battery_drain,
#     battery_drain_nodo; SimNode._make_ogm -> ttl;
#   SimNode.move -> move_speed, movilidad, movilidad_usuarios,
#     velocidad_usuarios; PlanoDatos.enviar -> protocolo_datos.
# (tipo, mínimo, máximo) o (str, opciones).
PARAMETROS = {
    "rango_comm": (float, 4.0, 60.0),
    "falloff": (float, 0.0, 1.5),
    "perdida_base": (float, 0.0, 1.0),
    "floor_atten": (float, 0.0, 1.0),
    "timeout": (float, 1.0, 300.0),
    "ttl": (int, 1, 20),
    "beacon_cada": (float, 0.5, 30.0),
    "batman_cada": (float, 0.5, 30.0),
    "battery_drain": (float, 0.0, 5.0),
    "battery_drain_nodo": (float, 0.0, 5.0),
    "move_speed": (float, 0.0, 2.0),
    "movilidad": (str, MOVILIDADES),
    "movilidad_usuarios": (str, MOVILIDADES_USUARIOS),
    "velocidad_usuarios": (float, 0.0, 2.0),
    "protocolo_datos": (str, PROTOCOLOS_DATOS),
}


def valor_parametro(clave, valor):
    """Valida y convierte el valor de un parámetro de PARAMETROS (ValueError
    con un mensaje claro si la clave o el valor no valen)."""
    if clave not in PARAMETROS:
        raise ValueError(f"parámetro desconocido: {clave!r} (válidos: "
                         f"{', '.join(PARAMETROS)})")
    spec = PARAMETROS[clave]
    if spec[0] is str:
        if valor not in spec[1]:
            raise ValueError(f"'{clave}' debe ser una de {', '.join(spec[1])}")
        return valor
    tipo, minimo, maximo = spec
    try:
        v = tipo(float(valor))
    except (TypeError, ValueError):
        raise ValueError(f"'{clave}' debe ser numérico")
    if not (minimo <= v <= maximo):
        raise ValueError(f"'{clave}' debe estar entre {minimo:g} y {maximo:g}")
    return v


# Sección "traffic" (plano de datos, sim/datos.py): flujos explícitos
# {"src", "dst", "cada", "desde", "hasta"} y/o K flujos "aleatorios" entre
# Nodos de usuario; "cada" (s) es el intervalo por defecto.
CLAVES_TRAFICO = ("flujos", "aleatorios", "cada")
CLAVES_FLUJO = ("src", "dst", "cada", "desde", "hasta")

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
        fail_critico  G  120   # tipo  rol (G/N/*)  t: el nodo se elige ahí

        [traffic]
        aleatorios=2       # flujos entre pares de Nodos de usuario al azar
        cada=2             # s entre paquetes (por defecto de los flujos)
        2  1               # src dst [cada] [desde] [hasta]

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
    trafico = {}
    random_cfg = {}
    section = None

    for lineno, raw_line in enumerate(lines, start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
            if section not in ("building", "medium", "protocol", "nodes",
                               "events", "traffic"):
                raise ValueError(f"{path}:{lineno}: sección desconocida '[{section}]'")
            continue

        if section is None:
            key, sep, value = line.partition(":")
            if not sep or key.strip().lower() != "name":
                raise ValueError(
                    f"{path}:{lineno}: se esperaba 'name: ...' o una sección "
                    f"'[building]/[medium]/[protocol]/[nodes]/[events]/"
                    f"[traffic]', se "
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
            if ev_type in EVENTOS_ELEGIDOS:
                try:
                    data["events"].append(
                        {"type": ev_type, "rol": nid, "t": float(instante)})
                except ValueError:
                    raise ValueError(f"{path}:{lineno}: evento inválido '{line}'")
                continue
            clave = "t" if ev_type in EVENTOS_PROGRAMADOS else "until"
            try:
                data["events"].append(
                    {"type": ev_type, "node_id": int(nid), clave: float(instante)}
                )
            except ValueError:
                raise ValueError(f"{path}:{lineno}: evento inválido '{line}'")

        elif section == "traffic":
            if "=" in line:
                key, _, value = line.partition("=")
                trafico[key.strip().lower()] = _parse_value(value)
                continue
            parts = line.split()
            if not 2 <= len(parts) <= 5:
                raise ValueError(
                    f"{path}:{lineno}: flujo inválido '{line}' (se esperaba "
                    f"'src dst [cada] [desde] [hasta]')"
                )
            try:
                flujo = {"src": int(parts[0]), "dst": int(parts[1])}
                for clave, valor in zip(("cada", "desde", "hasta"), parts[2:]):
                    flujo[clave] = float(valor)
            except ValueError:
                raise ValueError(f"{path}:{lineno}: flujo inválido '{line}'")
            trafico.setdefault("flujos", []).append(flujo)

    if trafico:
        data["traffic"] = trafico

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
        for clave in ("movilidad_usuarios", "protocolo_datos"):
            if isinstance(valores, dict) and clave in valores:
                try:
                    valor_parametro(clave, valores[clave])
                except ValueError as e:
                    raise ValueError(f"{path}: {e}")
    building = dict(default_building or {})
    building.update(data.get("building", {}))
    ancho = building.get("ancho", 40.0)
    alto = building.get("alto", 30.0)
    # "edificio": corte vertical con pisos y escalera; "campo": vista en
    # planta de un área abierta (un solo "piso" del alto del área)
    if building.get("tipo", "edificio") not in TIPOS_MAPA:
        raise ValueError(f"{path}: building.tipo debe ser uno de "
                         f"{', '.join(TIPOS_MAPA)}")
    if building.get("tipo") == "campo":
        # lo del escenario manda; si no lo dice, un solo "piso" sin escalera
        # (pisa los valores por defecto del edificio)
        propio = data.get("building", {})
        for clave, valor in (("n_pisos", 1), ("piso_h", alto),
                             ("stair_half_w", 0.0), ("stair_xy", [0.0, 0.0])):
            if clave not in propio:
                building[clave] = valor

    if "random" in data:
        if any(isinstance(ev, dict) and ev.get("type") in
               EVENTOS_PROGRAMADOS + EVENTOS_ELEGIDOS
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
        _validar_trafico(data, path, None)
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
        if tipo in EVENTOS_ELEGIDOS:
            if ev.setdefault("rol", "G") not in ROLES_EVENTO:
                raise ValueError(
                    f"{path}: evento '{tipo}' con rol {ev['rol']!r} (válidos: "
                    f"{', '.join(ROLES_EVENTO)})"
                )
            instante = ev.get("t")
            if (isinstance(instante, bool) or not isinstance(instante, (int, float))
                    or instante < 0):
                raise ValueError(f"{path}: evento '{tipo}' necesita un instante "
                                 f"'t' numérico >= 0")
            continue
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

    _validar_trafico(data, path, seen_ids)
    data["building"] = building
    return data


def _numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _validar_trafico(data, path, ids):
    """Valida la sección "traffic". `ids`: los ids de los nodos explícitos,
    o None en el modo random (ahí sólo valen flujos aleatorios)."""
    trafico = data.get("traffic")
    if trafico is None:
        return
    if not isinstance(trafico, dict):
        raise ValueError(f"{path}: 'traffic' debe ser un objeto")
    for clave in trafico:
        if clave not in CLAVES_TRAFICO:
            raise ValueError(f"{path}: clave desconocida en 'traffic': {clave!r} "
                             f"(válidas: {', '.join(CLAVES_TRAFICO)})")
    cada = trafico.get("cada", 2.0)
    if not _numero(cada) or cada <= 0:
        raise ValueError(f"{path}: 'traffic.cada' debe ser un número > 0")
    k = trafico.get("aleatorios", 0)
    if not isinstance(k, int) or isinstance(k, bool) or k < 0:
        raise ValueError(f"{path}: 'traffic.aleatorios' debe ser un entero >= 0")
    flujos = trafico.get("flujos", [])
    if not isinstance(flujos, list):
        raise ValueError(f"{path}: 'traffic.flujos' debe ser una lista")
    if flujos and ids is None:
        raise ValueError(f"{path}: los flujos explícitos necesitan nodos "
                         f"explícitos, no el modo random (usa 'aleatorios')")
    for f in flujos:
        if not isinstance(f, dict) or "src" not in f or "dst" not in f:
            raise ValueError(f"{path}: flujo {f} sin 'src' y 'dst'")
        for clave in f:
            if clave not in CLAVES_FLUJO:
                raise ValueError(f"{path}: clave desconocida en el flujo {f}: "
                                 f"{clave!r}")
        for extremo in ("src", "dst"):
            if f[extremo] not in ids:
                raise ValueError(f"{path}: el flujo {f} referencia el nodo "
                                 f"{f[extremo]}, que no existe en 'nodes'")
        if f["src"] == f["dst"]:
            raise ValueError(f"{path}: el flujo {f} tiene el mismo origen y destino")
        if "cada" in f and (not _numero(f["cada"]) or f["cada"] <= 0):
            raise ValueError(f"{path}: el flujo {f} necesita 'cada' > 0")
        desde = f.get("desde", 0)
        if not _numero(desde) or desde < 0:
            raise ValueError(f"{path}: el flujo {f} necesita 'desde' >= 0")
        hasta = f.get("hasta")
        if hasta is not None and (not _numero(hasta) or hasta < desde):
            raise ValueError(f"{path}: el flujo {f} necesita 'hasta' >= 'desde'")
