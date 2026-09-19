"""Runner de lote: valida el archivo de lote, agrega las métricas de
varias corridas (media ± desviación estándar por escenario) y exporta el
resumen. Correr cada corrida lo hace main.py (ejecutar_lote), que es
quien sabe construir una Simulation; aquí sólo hay lógica pura.

Formato del archivo de lote (JSON):
    {
      "nombre": "tesis",
      "duracion": 200,
      "semillas": 10,
      "figuras": false,
      "escenarios": [
        {"escenario": "base"},
        {"escenario": "base", "static": true},
        {"config": "escenarios/x.json", "semillas": [1, 2, 3],
         "duracion": 100, "etiqueta": "x_corto"}
      ]
    }

Sólo "escenarios" es obligatorio. Cada entrada lleva exactamente uno de
"escenario" (un predefinido, como --escenario) o "config" (una ruta, como
--config); "semillas" es un entero N (semillas 1..N) o una lista
explícita; "duracion", "semillas" y "static" de la entrada pisan los
valores del lote. Detalle en el README.
"""
import csv
import json
import os
import re
import statistics

from analysis.metrics import METRICAS_CORRIDA

CLAVES_LOTE = ("nombre", "duracion", "semillas", "figuras", "escenarios")
CLAVES_ENTRADA = ("escenario", "config", "etiqueta", "semillas", "duracion",
                  "static")
PATRON_ETIQUETA = re.compile(r"^[\w.-]+$")


# ── carga y validación ────────────────────────────────────────────────
def cargar_lote(path, escenarios_disponibles, duracion_default, duracion_minima):
    """Lee y valida un archivo de lote. Devuelve un dict normalizado:

        {"nombre": str, "figuras": bool,
         "escenarios": [{"etiqueta": str, "escenario": str | None,
                         "config": str | None, "static": bool,
                         "semillas": [int, ...], "duracion": float}, ...]}

    Exactamente uno de "escenario"/"config" queda definido por entrada.
    Lanza ValueError con un mensaje claro ante cualquier problema.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ValueError(f"{path}: archivo no encontrado")
    except json.JSONDecodeError as e:
        raise ValueError(f"{path}: JSON inválido ({e})")

    if not isinstance(data, dict):
        raise ValueError(f"{path}: se esperaba un objeto JSON con 'escenarios'")
    _claves_conocidas(data, CLAVES_LOTE, path)

    nombre = data.get("nombre")
    if nombre is None:
        nombre = _a_etiqueta(os.path.splitext(os.path.basename(path))[0])
    elif not isinstance(nombre, str) or not PATRON_ETIQUETA.match(nombre):
        raise ValueError(f"{path}: 'nombre' debe usar sólo letras, números, "
                         f"'_', '-' o '.', se encontró {nombre!r}")

    figuras = data.get("figuras", False)
    if not isinstance(figuras, bool):
        raise ValueError(f"{path}: 'figuras' debe ser true o false")

    duracion = _duracion(data.get("duracion", duracion_default),
                         duracion_minima, path)
    semillas = (_semillas(data["semillas"], path)
                if "semillas" in data else None)

    entradas = data.get("escenarios")
    if not isinstance(entradas, list) or not entradas:
        raise ValueError(f"{path}: falta 'escenarios' (lista no vacía)")

    escenarios = []
    for i, entrada in enumerate(entradas, start=1):
        donde = f"{path}: escenarios[{i}]"
        escenarios.append(_entrada(entrada, donde, escenarios_disponibles,
                                   duracion, semillas, duracion_minima))

    vistas = set()
    for e in escenarios:
        if e["etiqueta"] in vistas:
            raise ValueError(
                f"{path}: etiqueta repetida '{e['etiqueta']}' — usa "
                f"\"etiqueta\" para distinguir esas entradas")
        vistas.add(e["etiqueta"])

    return {"nombre": nombre, "figuras": figuras, "escenarios": escenarios}


def _entrada(entrada, donde, escenarios_disponibles, duracion, semillas,
             duracion_minima):
    if not isinstance(entrada, dict):
        raise ValueError(f"{donde}: se esperaba un objeto")
    _claves_conocidas(entrada, CLAVES_ENTRADA, donde)

    escenario, config = entrada.get("escenario"), entrada.get("config")
    if (escenario is None) == (config is None):
        raise ValueError(f"{donde}: debe tener exactamente uno de 'escenario' "
                         f"(predefinido) o 'config' (ruta a un archivo)")
    if escenario is not None and escenario not in escenarios_disponibles:
        raise ValueError(f"{donde}: escenario desconocido {escenario!r} "
                         f"(disponibles: {', '.join(escenarios_disponibles)})")
    if config is not None and not isinstance(config, str):
        raise ValueError(f"{donde}: 'config' debe ser una ruta")

    static = entrada.get("static", False)
    if not isinstance(static, bool):
        raise ValueError(f"{donde}: 'static' debe ser true o false")

    if "semillas" in entrada:
        semillas = _semillas(entrada["semillas"], donde)
    elif semillas is None:
        raise ValueError(f"{donde}: faltan 'semillas' (en la entrada o "
                         f"como default del lote)")

    if "duracion" in entrada:
        duracion = _duracion(entrada["duracion"], duracion_minima, donde)

    etiqueta = entrada.get("etiqueta")
    if etiqueta is None:
        base = escenario or os.path.splitext(os.path.basename(config))[0]
        etiqueta = _a_etiqueta(base) + ("_static" if static else "")
    elif not isinstance(etiqueta, str) or not PATRON_ETIQUETA.match(etiqueta):
        raise ValueError(f"{donde}: 'etiqueta' debe usar sólo letras, "
                         f"números, '_', '-' o '.', se encontró {etiqueta!r}")

    return {"etiqueta": etiqueta, "escenario": escenario, "config": config,
            "static": static, "semillas": semillas, "duracion": duracion}


def _claves_conocidas(d, validas, donde):
    for clave in d:
        if clave not in validas:
            raise ValueError(f"{donde}: clave desconocida '{clave}' "
                             f"(válidas: {', '.join(validas)})")


def _es_entero(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _semillas(valor, donde):
    if _es_entero(valor) and valor >= 1:
        return list(range(1, valor + 1))
    if (isinstance(valor, list) and valor
            and all(_es_entero(s) for s in valor)):
        if len(set(valor)) != len(valor):
            raise ValueError(f"{donde}: 'semillas' tiene valores repetidos")
        return list(valor)
    raise ValueError(f"{donde}: 'semillas' debe ser un entero >= 1 (semillas "
                     f"1..N) o una lista no vacía de enteros")


def _duracion(valor, minima, donde):
    if (not isinstance(valor, (int, float)) or isinstance(valor, bool)
            or valor < minima):
        raise ValueError(f"{donde}: 'duracion' debe ser un número >= "
                         f"{minima:g} (segundos simulados)")
    return float(valor)


def _a_etiqueta(texto):
    return re.sub(r"[^\w.-]+", "_", texto) or "lote"


# ── agregación ────────────────────────────────────────────────────────
def resumir(valores):
    """Media y desviación estándar muestral (n - 1) de los valores que no
    son None (en una corrida donde la métrica no aplica, no cuenta).

    Devuelve {"media", "desv", "n"}: media es None si n = 0 y desv es
    None si n < 2 (con una sola corrida no hay dispersión que medir).
    """
    datos = [v for v in valores if v is not None]
    n = len(datos)
    return {"media": statistics.fmean(datos) if n else None,
            "desv": statistics.stdev(datos) if n >= 2 else None,
            "n": n}


def agregar(corridas):
    """corridas: [{"etiqueta", "semilla", "metricas": {clave: valor}}, ...]

    Devuelve {etiqueta: {clave: resumir(valores de esa clave)}}, con las
    etiquetas en el orden en que aparecen y las claves de METRICAS_CORRIDA.
    """
    por_etiqueta = {}
    for c in corridas:
        por_etiqueta.setdefault(c["etiqueta"], []).append(c["metricas"])
    return {etiqueta: {clave: resumir([m[clave] for m in metricas])
                       for clave, _, _ in METRICAS_CORRIDA}
            for etiqueta, metricas in por_etiqueta.items()}


# ── presentación y exportación ────────────────────────────────────────
def formatear_estadistica(r, decimales, total):
    """'0.412 ± 0.013' más cuántas corridas aportaron el valor."""
    if r["n"] == 0:
        return f"no aplica (0 de {total} corridas)"
    texto = f"{r['media']:.{decimales}f}"
    if r["desv"] is not None:
        texto += f" ± {r['desv']:.{decimales}f}"
    n = f"n={r['n']}" if r["n"] == total else f"n={r['n']} de {total}"
    return f"{texto:<18} ({n})"


def describir_semillas(semillas):
    if semillas == list(range(semillas[0], semillas[0] + len(semillas))):
        if len(semillas) == 1:
            return str(semillas[0])
        return f"{semillas[0]}-{semillas[-1]}"
    return ", ".join(str(s) for s in semillas)


def formatear_resumen(lote, agregado, fecha):
    """Resumen legible del lote: un bloque por escenario con media ±
    desviación estándar de cada métrica."""
    total = sum(len(e["semillas"]) for e in lote["escenarios"])
    lineas = [
        "=" * 76,
        f" RESUMEN DEL LOTE '{lote['nombre']}' · {fecha}",
        f" {len(lote['escenarios'])} escenarios · {total} corridas · "
        f"media ± desviación estándar muestral",
        " (n = corridas en las que la métrica aplica)",
        "=" * 76,
    ]
    for e in lote["escenarios"]:
        origen = e["escenario"] or e["config"]
        extra = ", nodos fijos" if e["static"] else ""
        lineas += [
            "",
            f"{e['etiqueta']}  ({origen}{extra} · {e['duracion']:g} s "
            f"simulados · semillas {describir_semillas(e['semillas'])})",
        ]
        for clave, etiqueta, decimales in METRICAS_CORRIDA:
            valor = formatear_estadistica(agregado[e["etiqueta"]][clave],
                                          decimales, len(e["semillas"]))
            lineas.append(f"  {etiqueta:<38} {valor}")
    lineas += ["", "=" * 76]
    return "\n".join(lineas)


def _celda(valor):
    return "" if valor is None else valor


def exportar_resumen(lote, corridas, agregado, out_dir, fecha, archivo=None):
    """Escribe en out_dir:
      - resumen.txt: el resumen legible (formatear_resumen).
      - resumen.csv: una fila por escenario, con <métrica>_media,
        <métrica>_desv y <métrica>_n para cada métrica.
      - resumen.json: metadatos del lote, agregado por escenario y
        corridas individuales.
      - corridas.csv: una fila por corrida (etiqueta, semilla, carpeta y
        cada métrica).
    Celdas vacías / null = no aplica. Devuelve las rutas escritas."""
    os.makedirs(out_dir, exist_ok=True)
    claves = [clave for clave, _, _ in METRICAS_CORRIDA]
    rutas = {clave: os.path.join(out_dir, nombre) for clave, nombre in
             (("txt", "resumen.txt"), ("csv", "resumen.csv"),
              ("json", "resumen.json"), ("corridas", "corridas.csv"))}

    with open(rutas["txt"], "w", encoding="utf-8") as f:
        f.write(formatear_resumen(lote, agregado, fecha) + "\n")

    with open(rutas["csv"], "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["etiqueta", "escenario", "config", "static",
                         "duracion_s", "corridas"]
                        + [f"{c}_{s}" for c in claves
                           for s in ("media", "desv", "n")])
        for e in lote["escenarios"]:
            fila = [e["etiqueta"], _celda(e["escenario"]), _celda(e["config"]),
                    e["static"], e["duracion"], len(e["semillas"])]
            for c in claves:
                r = agregado[e["etiqueta"]][c]
                fila += [_celda(r["media"]), _celda(r["desv"]), r["n"]]
            writer.writerow(fila)

    with open(rutas["corridas"], "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["etiqueta", "semilla", "carpeta"] + claves)
        for c in corridas:
            writer.writerow([c["etiqueta"], c["semilla"], c["carpeta"]]
                            + [_celda(c["metricas"][k]) for k in claves])

    datos = {
        "metadatos": {"nombre": lote["nombre"], "archivo_lote": archivo,
                      "fecha_ejecucion": fecha, "figuras": lote["figuras"],
                      "estadistica": "media y desviación estándar muestral "
                                     "(n - 1); n = corridas donde aplica"},
        "escenarios": [dict(e, metricas=agregado[e["etiqueta"]])
                       for e in lote["escenarios"]],
        "corridas": corridas,
    }
    with open(rutas["json"], "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
    return rutas
