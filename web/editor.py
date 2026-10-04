"""Editor de escenarios de la interfaz web: valida con las mismas reglas
que sim.config_loader y guarda en escenarios/ como JSON, sin pisar los
escenarios predefinidos y sin salir de la carpeta."""
import json
import os
import re

from sim.config_loader import validar_escenario

PATRON_NOMBRE = re.compile(r"^[\w.-]+$")


def _base_edificio():
    from main import ALTO, ANCHO, N_PISOS, PISO_H
    return dict(ancho=ANCHO, alto=ALTO, piso_h=PISO_H, n_pisos=N_PISOS)


def validar(escenario):
    """Devuelve un resumen del escenario validado; ValueError si no vale."""
    datos = validar_escenario(escenario, "escenario del editor",
                              _base_edificio())
    nodos = datos.get("nodes", [])
    return {"nodos": len(nodos),
            "gateways": sum(1 for n in nodos if n["role"] == "G")}


def guardar(escenario, nombre, sobrescribir=False):
    """Valida y escribe escenarios/<nombre>.json. Nunca pisa uno de los
    escenarios predefinidos; cualquier otro archivo existente sólo con
    `sobrescribir`. Devuelve la ruta relativa y el comando para correrlo."""
    from main import ESCENARIOS_DIR, ESCENARIOS_DISPONIBLES
    if not isinstance(nombre, str) or not PATRON_NOMBRE.match(nombre) \
            or nombre.startswith("."):
        raise ValueError("el nombre sólo puede usar letras, números, '_', "
                         "'-' o '.'")
    nombre = nombre[:-5] if nombre.endswith(".json") else nombre
    if nombre in ESCENARIOS_DISPONIBLES:
        raise ValueError(f"'{nombre}' es un escenario predefinido: elige "
                         f"otro nombre")
    validar(escenario)

    ruta = os.path.join(ESCENARIOS_DIR, f"{nombre}.json")
    if os.path.exists(ruta) and not sobrescribir:
        raise ValueError(f"ya existe escenarios/{nombre}.json (marca "
                         f"'sobrescribir' para reemplazarlo)")
    datos = dict(escenario)
    datos["name"] = nombre
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
        f.write("\n")
    relativa = f"escenarios/{nombre}.json"
    return {"archivo": f"{nombre}.json", "ruta": relativa,
            "comando": f"python main.py --config {relativa}",
            "comando_headless": f"python main.py --headless --config "
                                f"{relativa} --seed 1"}
