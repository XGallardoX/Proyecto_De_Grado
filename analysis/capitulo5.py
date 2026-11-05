"""Tablas y figuras del Capítulo 5 a partir de los reportes de lote.

    python -m analysis.capitulo5                      # últimos lotes en reportes/
    python -m analysis.capitulo5 --fallos DIR --movilidad DIR --plantilla DIR

Lee la salida de `--batch` (resumen.json, corridas.csv y, para la cobertura
en el tiempo, el reporte.csv de cada corrida) de `lotes/capitulo5_fallos.json`,
`capitulo5_fallos_movil.json`, `movilidad.json`, `movilidad_datos.json`,
`robustez.json` y `generalidad.json`, y escribe en la plantilla del documento:

- MainMatter/Cap5/tablas/*.tex: tablas listas para \\input{}.
- Images/Cap5/*.pdf: figuras vectoriales.

No corre simulaciones: los números son exactamente los del resumen del
lote (ver docs/guia_ejecucion.md, casos 11 y 14).
"""
import argparse
import csv
import glob
import json
import math
import os
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from sim.config_loader import load_scenario  # noqa: E402
from sim.radio import fiabilidad  # noqa: E402

# Paleta: un solo tono por panel donde hay una serie; dos tonos categóricos
# (validados para visión normal y daltonismo) donde se comparan seguir y
# repartir. El texto va siempre en tinta neutra, nunca en el color de la
# serie.
AZUL = "#2a78d6"
NARANJA = "#eb6834"
VERDE = "#2f9e6e"
TINTA = "#222222"
TINTA_2 = "#5f5e5a"
GRILLA = "#e4e2dc"
CAIDA = "#d9d6cf"

AQUA = "#1baf7a"
AMARILLO = "#eda100"
GRIS = "#a3a29c"

ANCHO_TEXTO_IN = 6.1        # \textwidth de la plantilla (15.6 cm)

RAIZ_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESCENARIO_DESPLIEGUE = os.path.join(RAIZ_REPO, "escenarios", "fallos",
                                    "cobertura_edificio.txt")

ETIQUETAS_FALLOS = {
    "cobertura_edificio": "Control (sin fallos)",
    "fallo_redundante": "Gateway redundante",
    "fallo_puente": "Gateway puente",
    "fallo_borde": "Gateway de borde",
    "fallo_cascada": "Cascada",
}
ESCENARIOS_MOVILIDAD = ["base", "colapso_progresivo", "particion",
                        "rescatista_perdido", "denso"]
# Modos de movilidad de los Gateway que compara lotes/movilidad.json
# (D8 de contexto/PLAN_SIGUIENTE.md): los dos centralizados de línea base y
# el descentralizado, que es el valor por defecto.
MODOS_MOVILIDAD = [("seguir", AZUL), ("repartir", NARANJA),
                   ("descentralizada", VERDE)]

# lotes/movilidad_datos.json: los escenarios con tráfico de datos.
ESCENARIOS_DATOS = ["base", "colapso_progresivo", "denso"]
ETIQUETAS_ROBUSTEZ = {"azar": "Fallos al azar", "dirigida": "Fallos dirigidos"}
# lotes/generalidad.json: (entorno, etiqueta sin el protocolo)
ENTORNOS_GENERALIDAD = [("Campo abierto, usuarios en grupos", "campo_grupos"),
                        ("Campo abierto, random waypoint", "campo_rwp"),
                        ("Edificio, nodos fijos", "edificio")]
# De qué vive cada paquete enviado: suman 1. Las causas se agrupan para que
# la figura se lea (el detalle completo queda en resumen.txt de cada lote).
DESTINOS_PAQUETE = [
    ("Entregado", ("entrega_datos",), AZUL),
    ("Salto perdido por la radio", ("perdida_enlace",), NARANJA),
    ("Sin ruta en la tabla", ("perdida_sin_ruta",), AQUA),
    ("Ruta vieja o bucle", ("perdida_ruta_vieja", "perdida_bucle"), AMARILLO),
    ("Sin camino por radio", ("perdida_sin_camino", "perdida_destino_caido"),
     GRIS),
]
# t de Student a dos colas al 95 %, por grados de libertad (1 a 30).
T_95 = (12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228,
        2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086,
        2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042)


# ── lectura ───────────────────────────────────────────────────────────────
def ultimo_lote(nombre, raiz="reportes"):
    carpetas = sorted(glob.glob(os.path.join(raiz, f"lote_{nombre}_[0-9]*")))
    if not carpetas:
        raise SystemExit(f"No hay salida de lote '{nombre}' en {raiz}/: "
                         f"corre antes python main.py --batch lotes/{nombre}.json")
    return carpetas[-1]


def leer_resumen(carpeta):
    with open(os.path.join(carpeta, "resumen.json"), encoding="utf-8") as f:
        datos = json.load(f)
    return {e["etiqueta"]: e for e in datos["escenarios"]}


def leer_corridas(carpeta):
    """corridas.csv de un lote: {etiqueta: {semilla: {métrica: float|None}}}."""
    corridas = {}
    with open(os.path.join(carpeta, "corridas.csv"),
              encoding="utf-8-sig") as f:
        for fila in csv.DictReader(f):
            valores = {}
            for clave, v in fila.items():
                try:
                    valores[clave] = float(v)
                except (TypeError, ValueError):
                    valores[clave] = None
            corridas.setdefault(fila["etiqueta"], {})[fila["semilla"]] = valores
    return corridas


def diferencia_pareada(corridas, a, b, clave):
    """Diferencia a - b emparejando por semilla: (media, semiancho del
    intervalo de confianza t al 95 %, n). Las semillas sin valor en alguno
    de los dos no cuentan. (None, None, n) con menos de dos pares."""
    difs = [corridas[a][s][clave] - corridas[b][s][clave]
            for s in corridas[a] if s in corridas[b]
            and corridas[a][s][clave] is not None
            and corridas[b][s][clave] is not None]
    n = len(difs)
    if n < 2:
        return None, None, n
    t = T_95[n - 2] if n - 2 < len(T_95) else 1.96
    return statistics.mean(difs), t * statistics.stdev(difs) / math.sqrt(n), n


def leer_serie(ruta):
    """Una corrida: (t, fracción de Nodos vivos alcanzables, eventos)."""
    t, frac, eventos = [], [], []
    with open(ruta, encoding="utf-8-sig") as f:
        for fila in csv.DictReader(f):
            vivos = int(fila["nodos_activos"])
            t.append(float(fila["tiempo_s"]))
            frac.append(int(fila["nodos_alcanzables"]) / vivos if vivos
                        else math.nan)
            if fila["tipo_evento"] in ("FAIL", "RECOVER"):
                eventos.append((float(fila["tiempo_s"]), fila["tipo_evento"],
                                fila["descripcion_evento"].split(" ")[0]))
    return t, frac, eventos


def ventanas_caida(eventos, fin):
    """[(inicio, fin, etiqueta)] de cada nodo caído, a partir de FAIL y
    RECOVER (un nodo que no vuelve queda caído hasta `fin`)."""
    abiertas, ventanas = {}, []
    for t, tipo, nodo in eventos:
        if tipo == "FAIL":
            abiertas[nodo] = t
        elif nodo in abiertas:
            ventanas.append((abiertas.pop(nodo), t, nodo))
    ventanas += [(ini, fin, nodo) for nodo, ini in abiertas.items()]
    return sorted(ventanas)


# ── formato ───────────────────────────────────────────────────────────────
def metrica(esc, clave):
    return esc["metricas"][clave]


def fmt(m, dec, con_n=True):
    """'media ± desv' como en resumen.txt; 'no aplica' si n = 0."""
    if not m["n"]:
        return "no aplica"
    s = f"{m['media']:.{dec}f}"
    if m["desv"]:
        s += f" $\\pm$ {m['desv']:.{dec}f}"
    return s


def tabla_tex(etiqueta, titulo, cabeceras, filas, anchos, nota=None):
    col = "|" + "|".join(f">{{\\raggedright\\arraybackslash\\hspace{{0pt}}}}p{{{a}}}"
                         for a in anchos) + "|"
    lineas = [
        "% Generado por python -m analysis.capitulo5 (no editar a mano).",
        "\\begin{table}[htbp!]",
        "    \\centering",
        f"    \\caption{{{titulo}}}",
        f"    \\label{{{etiqueta}}}",
        "    \\footnotesize",
        "    \\setlength{\\tabcolsep}{3pt}",
        f"    \\begin{{tabular}}{{{col}}}",
        "        \\hline",
        "        " + " & ".join(f"\\textbf{{{c}}}" for c in cabeceras) + " \\\\",
        "        \\hline",
    ]
    for fila in filas:
        lineas += ["        " + " & ".join(fila) + " \\\\", "        \\hline"]
    lineas.append("    \\end{tabular}")
    if nota:
        lineas += ["", f"    \\vspace{{0.4em}}\\parbox{{{sum_cm(anchos)}}}"
                       f"{{\\scriptsize {nota}}}"]
    lineas += ["\\end{table}", ""]
    return "\n".join(lineas)


def sum_cm(anchos):
    return f"{sum(float(a.rstrip('cm')) for a in anchos) + 0.2 * len(anchos):.1f}cm"


# ── tablas ────────────────────────────────────────────────────────────────
def tablas_fallos(fallos, n_semillas, duracion, sufijo="", cual=""):
    """`sufijo` (p. ej. \"-movil\") y `cual` (texto para el pie) distinguen la
    variante con Gateway móviles de la principal, de nodos fijos."""
    filas = []
    for etq, nombre in ETIQUETAS_FALLOS.items():
        e = fallos[etq]
        filas.append([
            nombre,
            fmt(metrica(e, "tiempo_particionado_s"), 1),
            fmt(metrica(e, "tiempo_reconvergencia_rutas_s"), 1),
            fmt(metrica(e, "alertas_gateway"), 1),
            fmt(metrica(e, "cobertura_media"), 3),
            fmt(metrica(e, "nodos_alcanzables_finales"), 0),
        ])
    principal = tabla_tex(
        f"tab:cap5-fallos{sufijo}",
        f"Respuesta de la malla a cada fallo{cual}",
        ["Experimento", "Malla partida (s)", "Reconvergencia de rutas (s)",
         "Alertas", "Cobertura media", "Nodos cubiertos al final"],
        filas, ["2.9cm", "1.7cm", "2.6cm", "1.9cm", "2.2cm", "1.7cm"],
        nota=(f"Media $\\pm$ desviación estándar muestral de {n_semillas} "
              f"corridas de {duracion:.0f} s simulados (semillas 1 a "
              f"{n_semillas}); sin $\\pm$, la desviación es 0. "
              "``No aplica'': ningún episodio de reconvergencia se cerró."))
    filas = []
    for etq, nombre in ETIQUETAS_FALLOS.items():
        e = fallos[etq]
        filas.append([nombre, fmt(metrica(e, "tq_medio"), 3),
                      fmt(metrica(e, "saltos_medio"), 2),
                      fmt(metrica(e, "tasa_entrega"), 3)])
    calidad = tabla_tex(
        f"tab:cap5-calidad{sufijo}",
        f"Calidad de las rutas y del medio en los experimentos de fallo{cual}",
        ["Experimento", "TQ medio de rutas", "Saltos medios por ruta",
         "Tasa de entrega del radio"],
        filas, ["3.2cm", "2.8cm", "2.8cm", "2.8cm"])
    return principal, calidad


def tabla_movilidad(mov):
    filas = []
    for esc in ESCENARIOS_MOVILIDAD:
        for modo, _ in MODOS_MOVILIDAD:
            m = mov[f"{esc}_{modo}"]
            filas.append([esc.replace("_", "\\_"), modo,
                          fmt(metrica(m, "cobertura_media"), 2),
                          fmt(metrica(m, "componentes_finales"), 1),
                          fmt(metrica(m, "tiempo_particionado_s"), 0),
                          fmt(metrica(m, "tasa_entrega"), 2),
                          fmt(metrica(m, "tq_medio"), 2)])
    return tabla_tex(
        "tab:cap5-movilidad",
        "Movilidad de los Gateway: \\emph{seguir}, \\emph{repartir} y "
        "\\emph{descentralizada}",
        ["Escenario", "Movilidad", "Cobertura media", "Componentes al final",
         "Malla partida (s)", "Entrega del radio", "TQ medio"],
        filas, ["2.85cm", "2.5cm", "1.9cm", "1.6cm", "1.4cm", "1.9cm",
                "1.9cm"],
        nota=("Media $\\pm$ desviación estándar de 10 corridas de 200 s "
              "simulados (lote \\texttt{lotes/movilidad.json}). "
              "\\emph{seguir} y \\emph{repartir} son la línea base "
              "centralizada; \\emph{descentralizada} decide cada Gateway "
              "solo con lo que oye."))


def fila_diferencia(corridas, nombre, a, b, clave, dec=3):
    d, h, n = diferencia_pareada(corridas, a, b, clave)
    if d is None:
        return [nombre, "no aplica", "no aplica", "no"]
    distinta = (d - h) * (d + h) > 0
    return [nombre, f"{d:+.{dec}f}".replace("-", "$-$"),
            f"[{d - h:+.{dec}f}, {d + h:+.{dec}f}]".replace("-", "$-$"),
            "sí" if distinta else "no"]


def tabla_movilidad_datos(datos):
    filas = []
    for esc in ESCENARIOS_DATOS:
        for modo, _ in MODOS_MOVILIDAD:
            m = datos[f"{esc}_{modo}_trafico6"]
            filas.append([esc.replace("_", "\\_"), modo,
                          fmt(metrica(m, "entrega_datos"), 2),
                          fmt(metrica(m, "entrega_datos_con_camino"), 2),
                          fmt(metrica(m, "perdida_sin_camino"), 2),
                          fmt(metrica(m, "estiramiento_datos"), 2),
                          fmt(metrica(m, "exactitud_conocimiento"), 2)])
    return tabla_tex(
        "tab:cap5-movilidad-datos",
        "Plano de datos según la movilidad de los Gateway",
        ["Escenario", "Movilidad", "Entrega de datos", "Entrega con camino",
         "Pérdida sin camino", "Estiramiento", "Exactitud del conocimiento"],
        filas, ["2.85cm", "2.5cm", "1.75cm", "1.75cm", "1.75cm", "1.75cm", "1.75cm"],
        nota=("Media $\\pm$ desviación estándar de 10 corridas de 200 s con "
              "6 flujos de datos aleatorios (lote "
              "\\texttt{lotes/movilidad\\_datos.json})."))


def tabla_robustez(rob):
    filas = []
    for etq, nombre in ETIQUETAS_ROBUSTEZ.items():
        e = rob[etq]
        filas.append([nombre, fmt(metrica(e, "tiempo_particionado_s"), 0),
                      fmt(metrica(e, "entrega_datos"), 3),
                      fmt(metrica(e, "entrega_datos_con_camino"), 3),
                      fmt(metrica(e, "cobertura_media"), 3),
                      fmt(metrica(e, "rutas_fantasma"), 3)])
    return tabla_tex(
        "tab:cap5-robustez",
        "Dos caídas al azar contra dos caídas dirigidas al nodo más crítico",
        ["Experimento", "Malla partida (s)", "Entrega de datos",
         "Entrega con camino", "Cobertura media", "Rutas fantasma"],
        filas, ["2.8cm", "2.1cm", "2.2cm", "2.2cm", "2.2cm", "2.0cm"],
        nota=("Media $\\pm$ desviación estándar de 10 corridas de 240 s con 6 "
              "flujos de datos, caídas a los 60 y 120 s (lote "
              "\\texttt{lotes/robustez.json})."))


def tabla_generalidad(gen):
    filas = []
    for nombre, base in ENTORNOS_GENERALIDAD:
        for proto, rotulo in (("batman", "B.A.T.M.A.N."),
                              ("inundacion", "Inundación")):
            e = gen[f"{base}_{proto}"]
            filas.append([nombre, rotulo, fmt(metrica(e, "entrega_datos"), 3),
                          fmt(metrica(e, "entrega_datos_con_camino"), 3),
                          fmt(metrica(e, "transmisiones_por_dato"), 2),
                          fmt(metrica(e, "saltos_datos"), 2)])
    return tabla_tex(
        "tab:cap5-generalidad",
        "B.A.T.M.A.N. contra inundación en dos mapas",
        ["Entorno", "Protocolo", "Entrega de datos", "Entrega con camino",
         "Transmisiones por paquete", "Saltos"],
        filas, ["3.3cm", "2.2cm", "2.1cm", "2.1cm", "2.1cm", "1.6cm"],
        nota=("Media $\\pm$ desviación estándar de 10 corridas de 300 s (lote "
              "\\texttt{lotes/generalidad.json}). B.A.T.M.A.N. reintenta cada "
              "salto hasta 3 veces (unicast); la inundación difunde una vez, "
              "sin reintentos."))


def tabla_diferencias(datos, rob, gen):
    filas = []
    if datos:
        for esc in ESCENARIOS_DATOS:
            esc_tex = esc.replace("_", "\\_")
            for otro in ("seguir", "repartir"):
                filas.append(fila_diferencia(
                    datos, f"{esc_tex}: entrega, "
                    f"descentralizada $-$ {otro}",
                    f"{esc}_descentralizada_trafico6",
                    f"{esc}_{otro}_trafico6", "entrega_datos"))
            filas.append(fila_diferencia(
                datos, f"{esc_tex}: entrega con camino, descentralizada "
                "$-$ seguir", f"{esc}_descentralizada_trafico6",
                f"{esc}_seguir_trafico6", "entrega_datos_con_camino"))
    if rob:
        filas.append(fila_diferencia(rob, "Robustez: entrega, azar $-$ dirigida",
                                     "azar", "dirigida", "entrega_datos"))
        filas.append(fila_diferencia(rob, "Robustez: cobertura, azar $-$ dirigida",
                                     "azar", "dirigida", "cobertura_media"))
    if gen:
        for nombre, base in ENTORNOS_GENERALIDAD:
            filas.append(fila_diferencia(
                gen, f"{nombre}: entrega con camino, inundación $-$ B.A.T.M.A.N.",
                f"{base}_inundacion", f"{base}_batman",
                "entrega_datos_con_camino"))
    return tabla_tex(
        "tab:cap5-diferencias",
        "Diferencias pareadas por semilla, con intervalo de confianza del 95~\\%",
        ["Comparación", "Diferencia media", "Intervalo del 95~\\%",
         "¿Excluye el 0?"],
        filas, ["7.2cm", "1.9cm", "3.0cm", "1.5cm"],
        nota=("Intervalo $t$ de Student con 9 grados de libertad sobre las "
              "diferencias entre corridas con la misma semilla. Sin corrección "
              "por comparaciones múltiples."))


# ── figuras ───────────────────────────────────────────────────────────────
def _estilo(ax):
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(TINTA_2)
        ax.spines[lado].set_linewidth(0.6)
    ax.tick_params(colors=TINTA_2, labelsize=7, width=0.6, length=3)
    ax.grid(color=GRILLA, linewidth=0.6)
    ax.set_axisbelow(True)


def figura_cobertura(carpeta_fallos, duracion, salida):
    """Un panel por experimento: fracción de Nodos de usuario vivos
    cubiertos en el tiempo (media de las semillas y su rango), con las
    caídas sombreadas."""
    etiquetas = list(ETIQUETAS_FALLOS)
    fig, ejes = plt.subplots(len(etiquetas), 1, sharex=True,
                             figsize=(ANCHO_TEXTO_IN, 6.4))
    for ax, etq in zip(ejes, etiquetas):
        corridas = [leer_serie(r) for r in sorted(glob.glob(
            os.path.join(carpeta_fallos, etq, "semilla_*", "reporte.csv")))]
        if not corridas:
            raise SystemExit(f"{carpeta_fallos}/{etq}: faltan los reporte.csv "
                             "de las corridas")
        t = corridas[0][0]
        columnas = list(zip(*(c[1] for c in corridas)))
        media = [sum(v) / len(v) for v in columnas]
        bajo = [min(v) for v in columnas]
        alto = [max(v) for v in columnas]
        _estilo(ax)
        for i, (ini, fin, nodo) in enumerate(
                ventanas_caida(corridas[0][2], duracion)):
            ax.axvspan(ini, fin, color=CAIDA, alpha=0.6, linewidth=0)
            # rótulo al inicio de cada caída, escalonado si hay varias
            ax.text(ini + 2, 0.06 + 0.12 * i, f"cae {nodo}", ha="left",
                    va="bottom", fontsize=6.5, color=TINTA_2)
        ax.fill_between(t, bajo, alto, color=AZUL, alpha=0.15, linewidth=0)
        ax.plot(t, media, color=AZUL, linewidth=1.4)
        ax.set_ylim(0, 1.08)
        ax.set_yticks([0, 0.5, 1])
        ax.set_xlim(0, duracion)
        ax.set_title(ETIQUETAS_FALLOS[etq], fontsize=8, color=TINTA,
                     loc="left", pad=3)
    ejes[len(ejes) // 2].set_ylabel(
        "Fracción de Nodos de usuario cubiertos", fontsize=8, color=TINTA)
    ejes[-1].set_xlabel("Tiempo simulado (s)", fontsize=8, color=TINTA)
    fig.tight_layout(h_pad=0.6)
    fig.savefig(salida)
    plt.close(fig)


def figura_comparacion(fallos, salida):
    """Tres paneles (uno por métrica, cada uno con su escala): barras
    horizontales con la desviación estándar."""
    paneles = [("tiempo_reconvergencia_rutas_s",
                "Reconvergencia de\nrutas BATMAN (s)"),
               ("alertas_gateway", "Alertas de\ngateway perdido"),
               ("cobertura_media", "Cobertura media\n(fracción del tiempo)")]
    etiquetas = list(ETIQUETAS_FALLOS)
    y = list(range(len(etiquetas)))[::-1]
    fig, ejes = plt.subplots(1, 3, sharey=True,
                             figsize=(ANCHO_TEXTO_IN, 2.4))
    for ax, (clave, titulo) in zip(ejes, paneles):
        _estilo(ax)
        ax.grid(axis="y", visible=False)
        for yi, etq in zip(y, etiquetas):
            m = metrica(fallos[etq], clave)
            if not m["n"]:
                ax.text(0, yi, " no aplica", va="center", fontsize=6.5,
                        color=TINTA_2)
                continue
            ax.barh(yi, m["media"], height=0.6, color=AZUL)
            if m["desv"]:
                ax.errorbar(m["media"], yi, xerr=m["desv"], color=TINTA,
                            linewidth=0.8, capsize=2)
        ax.set_title(titulo, fontsize=7.5, color=TINTA, loc="left")
        ax.set_xlim(left=0)
        if clave == "cobertura_media":
            ax.set_xlim(0, 1.05)
    ejes[0].set_yticks(y)
    ejes[0].set_yticklabels([ETIQUETAS_FALLOS[e] for e in etiquetas],
                            fontsize=7, color=TINTA)
    fig.tight_layout(w_pad=1.0)
    fig.savefig(salida)
    plt.close(fig)


def figura_movilidad(mov, salida):
    """Cuatro paneles (uno por métrica) con los tres modos lado a lado
    por escenario."""
    paneles = [("cobertura_media", "Cobertura media"),
               ("tasa_entrega", "Tasa de entrega del radio"),
               ("tq_medio", "TQ medio de rutas"),
               ("tiempo_particionado_s", "Tiempo con la malla partida (s)")]
    y = list(range(len(ESCENARIOS_MOVILIDAD)))[::-1]
    alto_barra = 0.26
    n = len(MODOS_MOVILIDAD)
    fig, ejes = plt.subplots(2, 2, sharey=True,
                             figsize=(ANCHO_TEXTO_IN, 4.6))
    for ax, (clave, titulo) in zip(ejes.flat, paneles):
        _estilo(ax)
        ax.grid(axis="y", visible=False)
        for yi, esc in zip(y, ESCENARIOS_MOVILIDAD):
            for i, (modo, color) in enumerate(MODOS_MOVILIDAD):
                desp = ((n - 1) / 2 - i) * (alto_barra + 0.02)
                m = metrica(mov[f"{esc}_{modo}"], clave)
                ax.barh(yi + desp, m["media"], height=alto_barra,
                        color=color, label=modo if yi == y[0] else None)
                if m["desv"]:
                    ax.errorbar(m["media"], yi + desp, xerr=m["desv"],
                                color=TINTA, linewidth=0.7, capsize=1.5)
        ax.set_title(titulo, fontsize=7.5, color=TINTA, loc="left")
        ax.set_xlim(left=0)
    for fila in ejes:
        fila[0].set_yticks(y)
        fila[0].set_yticklabels(ESCENARIOS_MOVILIDAD, fontsize=7,
                                color=TINTA)
    fig.legend(*ejes[0][0].get_legend_handles_labels(), loc="upper center",
               ncol=n, frameon=False, fontsize=7.5,
               bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.95), w_pad=1.0, h_pad=1.0)
    fig.savefig(salida)
    plt.close(fig)


def _barras_paquetes(ax, filas):
    """Barras apiladas de 0 a 1: en qué terminó cada paquete enviado.
    `filas`: [(rótulo, escenario de resumen.json)], de arriba abajo."""
    y = list(range(len(filas)))[::-1]
    for yi, (_rotulo, esc) in zip(y, filas):
        izq = 0.0
        for nombre, claves, color in DESTINOS_PAQUETE:
            v = sum(metrica(esc, c)["media"] or 0.0 for c in claves)
            # el borde blanco separa los segmentos
            ax.barh(yi, v, left=izq, height=0.68, color=color,
                    edgecolor="white", linewidth=0.8,
                    label=nombre if yi == y[0] else None)
            izq += v
        entrega = metrica(esc, "entrega_datos")["media"] or 0.0
        if entrega >= 0.09:
            ax.text(entrega / 2, yi, f"{entrega:.2f}", ha="center",
                    va="center", fontsize=6.5, color="white")
    _estilo(ax)
    ax.grid(axis="y", visible=False)
    ax.set_yticks(y)
    ax.set_yticklabels([f[0] for f in filas], fontsize=7, color=TINTA)
    ax.set_xlim(0, 1)
    ax.set_xlabel("Fracción de los paquetes enviados", fontsize=8, color=TINTA)


def _guardar_barras(ax, fig, salida):
    fig.legend(*ax.get_legend_handles_labels(), loc="upper center", ncol=3,
               frameon=False, fontsize=7, bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(salida)
    plt.close(fig)


def figura_paquetes_movilidad(datos, salida):
    filas = [(f"{esc}, {modo}", datos[f"{esc}_{modo}_trafico6"])
             for esc in ESCENARIOS_DATOS for modo, _ in MODOS_MOVILIDAD]
    fig, ax = plt.subplots(figsize=(ANCHO_TEXTO_IN, 3.5))
    _barras_paquetes(ax, filas)
    _guardar_barras(ax, fig, salida)


def figura_paquetes_comparacion(rob, gen, salida):
    filas = [(ETIQUETAS_ROBUSTEZ[e], rob[e]) for e in ETIQUETAS_ROBUSTEZ]
    for nombre, base in ENTORNOS_GENERALIDAD:
        filas.append((f"{nombre}, B.A.T.M.A.N.", gen[f"{base}_batman"]))
        filas.append((f"{nombre}, inundación", gen[f"{base}_inundacion"]))
    fig, ax = plt.subplots(figsize=(ANCHO_TEXTO_IN, 3.4))
    _barras_paquetes(ax, filas)
    _guardar_barras(ax, fig, salida)


def figura_fiabilidad(salida):
    """Fiabilidad contra distancia en el medio por defecto y en el del
    despliegue del Capítulo 5, en el mismo piso y a un piso de diferencia."""
    defecto = {"rango_comm": 16.0, "falloff": 0.85, "perdida_base": 0.02,
               "floor_atten": 0.55}
    despliegue = {"rango_comm": 12.0, "falloff": 0.5, "perdida_base": 0.02,
                  "floor_atten": 0.8}
    fig, ax = plt.subplots(figsize=(ANCHO_TEXTO_IN, 2.5))
    _estilo(ax)
    xs = [i / 10 for i in range(0, 181)]
    for cfg, nombre, color in ((defecto, "Medio por defecto", NARANJA),
                               (despliegue, "Despliegue de cobertura", AZUL)):
        for df, trazo, rotulo in ((0, "-", "mismo piso"),
                                  (1, "--", "un piso de diferencia")):
            pares = [(d, fiabilidad(d, df, cfg)) for d in xs
                     if d <= cfg["rango_comm"]]
            ax.plot([p[0] for p in pares], [p[1] for p in pares], trazo,
                    color=color, linewidth=1.4, label=f"{nombre}, {rotulo}")
    ax.set_xlim(0, 18)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Distancia entre nodos (m)", fontsize=8, color=TINTA)
    ax.set_ylabel("Probabilidad de entrega", fontsize=8, color=TINTA)
    ax.legend(frameon=False, fontsize=7, loc="lower left")
    fig.tight_layout()
    fig.savefig(salida)
    plt.close(fig)


def figura_despliegue(escenario, salida):
    """Corte vertical del edificio con el despliegue de cobertura: nodos y
    enlaces de radio, más gruesos cuanto más fiables."""
    datos = load_scenario(escenario)
    cfg = {"perdida_base": 0.02, **datos["medium"]}
    ancho, alto, piso_h = 40, 30, 10
    fig, ax = plt.subplots(figsize=(ANCHO_TEXTO_IN, 3.5))
    piso = lambda n: int(n["y"] // piso_h)
    nodos = datos["nodes"]
    for i, a in enumerate(nodos):
        for b in nodos[i + 1:]:
            d = math.hypot(a["x"] - b["x"], a["y"] - b["y"])
            rel = fiabilidad(d, abs(piso(a) - piso(b)), cfg)
            if rel > 0:
                ax.plot([a["x"], b["x"]], [a["y"], b["y"]], color=TINTA_2,
                        linewidth=0.3 + 1.6 * rel, alpha=0.55, zorder=1)
    for k in range(1, 3):
        ax.axhline(k * piso_h, color=GRILLA, linewidth=1.0, zorder=0)
    for k in range(3):
        ax.text(0.4, (k + 1) * piso_h - 0.5, f"Piso {k + 1}", fontsize=7,
                color=TINTA_2, va="top")
    for n in nodos:
        es_g = n["role"] == "G"
        ax.scatter(n["x"], n["y"], s=70 if es_g else 44,
                   marker="o" if es_g else "s", zorder=3,
                   color=AZUL if es_g else NARANJA,
                   edgecolors="white", linewidths=0.8,
                   label="Gateway" if es_g else "Nodo de usuario")
        rot = f"G{n['id']}" if es_g else f"N{n['id'] - 100}"
        ax.annotate(rot, (n["x"], n["y"]), xytext=(5, 5), fontsize=7,
                    color=TINTA, textcoords="offset points", zorder=4)
    ax.set_xlim(0, ancho)
    ax.set_ylim(0, alto)
    ax.set_aspect("equal")
    ax.set_xlabel("Posición horizontal (m)", fontsize=8, color=TINTA)
    ax.set_ylabel("Altura en el corte (m)", fontsize=8, color=TINTA)
    ax.tick_params(colors=TINTA_2, labelsize=7, width=0.6, length=3)
    for lado in ax.spines.values():
        lado.set_color(TINTA_2)
        lado.set_linewidth(0.6)
    unicos = dict(zip(*reversed(ax.get_legend_handles_labels())))
    ax.legend(list(unicos.values()), list(unicos.keys()), frameon=False,
              fontsize=7, loc="upper center", ncol=2,
              bbox_to_anchor=(0.5, 1.1))
    fig.tight_layout()
    fig.savefig(salida)
    plt.close(fig)


# ── principal ─────────────────────────────────────────────────────────────
def generar(carpeta_fallos, carpeta_movilidad, plantilla,
            carpeta_fallos_movil=None, carpeta_datos=None,
            carpeta_robustez=None, carpeta_generalidad=None):
    dir_tablas = os.path.join(plantilla, "MainMatter", "Cap5", "tablas")
    dir_figuras = os.path.join(plantilla, "Images", "Cap5")
    os.makedirs(dir_tablas, exist_ok=True)
    os.makedirs(dir_figuras, exist_ok=True)

    fallos = leer_resumen(carpeta_fallos)
    ref = fallos["cobertura_edificio"]
    principal, calidad = tablas_fallos(fallos, len(ref["semillas"]),
                                       ref["duracion"])
    escritos = []
    for nombre, texto in (("fallos.tex", principal),
                          ("calidad.tex", calidad)):
        escritos.append(_escribir(os.path.join(dir_tablas, nombre), texto))
    figura_cobertura(carpeta_fallos, ref["duracion"],
                     os.path.join(dir_figuras, "cobertura_tiempo.pdf"))
    figura_comparacion(fallos, os.path.join(dir_figuras, "comparacion_fallos.pdf"))
    escritos += [os.path.join(dir_figuras, "cobertura_tiempo.pdf"),
                 os.path.join(dir_figuras, "comparacion_fallos.pdf")]

    if carpeta_fallos_movil:
        # Mismos cinco experimentos con los Gateway moviéndose por la
        # movilidad descentralizada (D8): tablas hermanas de las de nodos fijos.
        fm = leer_resumen(carpeta_fallos_movil)
        ref_m = fm["cobertura_edificio"]
        p_m, c_m = tablas_fallos(fm, len(ref_m["semillas"]), ref_m["duracion"],
                                 sufijo="-movil",
                                 cual=" con Gateway móviles (descentralizada)")
        for nombre, texto in (("fallos_movil.tex", p_m),
                              ("calidad_movil.tex", c_m)):
            escritos.append(_escribir(os.path.join(dir_tablas, nombre), texto))
    if carpeta_movilidad:
        mov = leer_resumen(carpeta_movilidad)
        escritos.append(_escribir(os.path.join(dir_tablas, "movilidad.tex"),
                                  tabla_movilidad(mov)))
        figura_movilidad(mov, os.path.join(dir_figuras, "movilidad.pdf"))
        escritos.append(os.path.join(dir_figuras, "movilidad.pdf"))

    for nombre, funcion, args in (
            ("despliegue.pdf", figura_despliegue, (ESCENARIO_DESPLIEGUE,)),
            ("fiabilidad.pdf", figura_fiabilidad, ())):
        ruta = os.path.join(dir_figuras, nombre)
        funcion(*args, ruta)
        escritos.append(ruta)

    # Plano de datos, robustez y generalidad, con diferencias pareadas.
    datos = leer_resumen(carpeta_datos) if carpeta_datos else None
    rob = leer_resumen(carpeta_robustez) if carpeta_robustez else None
    gen = leer_resumen(carpeta_generalidad) if carpeta_generalidad else None
    if datos:
        escritos.append(_escribir(os.path.join(dir_tablas, "movilidad_datos.tex"),
                                  tabla_movilidad_datos(datos)))
        ruta = os.path.join(dir_figuras, "paquetes_movilidad.pdf")
        figura_paquetes_movilidad(datos, ruta)
        escritos.append(ruta)
    if rob:
        escritos.append(_escribir(os.path.join(dir_tablas, "robustez.tex"),
                                  tabla_robustez(rob)))
    if gen:
        escritos.append(_escribir(os.path.join(dir_tablas, "generalidad.tex"),
                                  tabla_generalidad(gen)))
    if rob and gen:
        ruta = os.path.join(dir_figuras, "paquetes_comparacion.pdf")
        figura_paquetes_comparacion(rob, gen, ruta)
        escritos.append(ruta)
    if datos or rob or gen:
        escritos.append(_escribir(
            os.path.join(dir_tablas, "diferencias.tex"),
            tabla_diferencias(
                leer_corridas(carpeta_datos) if datos else None,
                leer_corridas(carpeta_robustez) if rob else None,
                leer_corridas(carpeta_generalidad) if gen else None)))
    return escritos


def _escribir(ruta, texto):
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)
    return ruta


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--fallos", help="salida de lotes/capitulo5_fallos.json "
                   "(por defecto, la última en reportes/)")
    p.add_argument("--fallos-movil", help="salida de lotes/"
                   "capitulo5_fallos_movil.json (por defecto, la última en "
                   "reportes/, si existe)")
    p.add_argument("--movilidad", help="salida de lotes/movilidad.json "
                   "(por defecto, la última en reportes/)")
    p.add_argument("--datos", help="salida de lotes/movilidad_datos.json")
    p.add_argument("--robustez", help="salida de lotes/robustez.json")
    p.add_argument("--generalidad", help="salida de lotes/generalidad.json")
    p.add_argument("--plantilla", default="Plantilla",
                   help="carpeta del documento (por defecto Plantilla/)")
    a = p.parse_args(argv)
    fallos = a.fallos or ultimo_lote("capitulo5_fallos")
    movilidad = a.movilidad or ultimo_lote("movilidad")
    movil = a.fallos_movil
    if movil is None and glob.glob(os.path.join(
            "reportes", "lote_capitulo5_fallos_movil_[0-9]*")):
        movil = ultimo_lote("capitulo5_fallos_movil")
    def opcional(valor, nombre):
        if valor is not None or not glob.glob(os.path.join(
                "reportes", f"lote_{nombre}_[0-9]*")):
            return valor
        return ultimo_lote(nombre)
    for ruta in generar(fallos, movilidad, a.plantilla, movil,
                        opcional(a.datos, "movilidad_datos"),
                        opcional(a.robustez, "robustez"),
                        opcional(a.generalidad, "generalidad")):
        print(f"  {ruta}")
    print(f"(desde {fallos}, {movilidad}" + (f" y {movil}" if movil else "")
          + ")")


if __name__ == "__main__":
    main()
