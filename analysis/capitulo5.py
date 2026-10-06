"""Tablas y figuras del Capítulo 5 a partir de los reportes de lote.

    python -m analysis.capitulo5                      # últimos lotes en reportes/
    python -m analysis.capitulo5 --fallos DIR --movilidad DIR --plantilla DIR

Lee la salida de `--batch` (resumen.json y, para la cobertura en el
tiempo, el reporte.csv de cada corrida) de `lotes/capitulo5_fallos.json`
y de `lotes/movilidad.json`, y escribe en la plantilla del documento:

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

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Paleta: un solo tono por panel donde hay una serie; dos tonos categóricos
# (validados para visión normal y daltonismo) donde se comparan seguir y
# repartir. El texto va siempre en tinta neutra, nunca en el color de la
# serie.
AZUL = "#2a78d6"
NARANJA = "#eb6834"
TINTA = "#222222"
TINTA_2 = "#5f5e5a"
GRILLA = "#e4e2dc"
CAIDA = "#d9d6cf"

ANCHO_TEXTO_IN = 6.1        # \textwidth de la plantilla (15.6 cm)

ETIQUETAS_FALLOS = {
    "cobertura_edificio": "Control (sin fallos)",
    "fallo_redundante": "Gateway redundante",
    "fallo_puente": "Gateway puente",
    "fallo_borde": "Gateway de borde",
    "fallo_cascada": "Cascada",
}
ESCENARIOS_MOVILIDAD = ["base", "colapso_progresivo", "particion",
                        "rescatista_perdido", "denso"]


# ── lectura ───────────────────────────────────────────────────────────────
def ultimo_lote(nombre, raiz="reportes"):
    carpetas = sorted(glob.glob(os.path.join(raiz, f"lote_{nombre}_*")))
    if not carpetas:
        raise SystemExit(f"No hay salida de lote '{nombre}' en {raiz}/: "
                         f"corre antes python main.py --batch lotes/{nombre}.json")
    return carpetas[-1]


def leer_resumen(carpeta):
    with open(os.path.join(carpeta, "resumen.json"), encoding="utf-8") as f:
        datos = json.load(f)
    return {e["etiqueta"]: e for e in datos["escenarios"]}


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
    col = "|" + "|".join(f">{{\\raggedright\\arraybackslash}}p{{{a}}}"
                         for a in anchos) + "|"
    lineas = [
        "% Generado por python -m analysis.capitulo5 (no editar a mano).",
        "\\begin{table}[htbp!]",
        "    \\centering",
        f"    \\caption{{{titulo}}}",
        f"    \\label{{{etiqueta}}}",
        "    \\footnotesize",
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
def tablas_fallos(fallos, n_semillas, duracion):
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
        "tab:cap5-fallos",
        "Respuesta de la malla a cada fallo",
        ["Experimento", "Malla partida (s)", "Reconvergencia de rutas (s)",
         "Alertas", "Cobertura media", "Nodos cubiertos al final"],
        filas, ["2.9cm", "1.7cm", "2.2cm", "1.9cm", "2.2cm", "1.7cm"],
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
        "tab:cap5-calidad",
        "Calidad de las rutas y del medio en los experimentos de fallo",
        ["Experimento", "TQ medio de rutas", "Saltos medios por ruta",
         "Tasa de entrega del radio"],
        filas, ["3.2cm", "2.8cm", "2.8cm", "2.8cm"])
    return principal, calidad


def tabla_movilidad(mov):
    filas = []
    for esc in ESCENARIOS_MOVILIDAD:
        s, r = mov[f"{esc}_seguir"], mov[f"{esc}_repartir"]
        def par(clave, dec):
            return (f"{fmt(metrica(s, clave), dec)} / "
                    f"{fmt(metrica(r, clave), dec)}")
        filas.append([esc.replace("_", "\\_"), par("cobertura_media", 2),
                      par("componentes_finales", 1),
                      par("tiempo_particionado_s", 0),
                      par("tasa_entrega", 2), par("tq_medio", 2)])
    return tabla_tex(
        "tab:cap5-movilidad",
        "Movilidad \\emph{seguir} / \\emph{repartir} (resultado secundario)",
        ["Escenario", "Cobertura media", "Componentes al final",
         "Malla partida (s)", "Entrega del radio", "TQ medio"],
        filas, ["2.4cm", "2.6cm", "2.4cm", "2.3cm", "2.2cm", "2.2cm"],
        nota=("En cada celda, \\emph{seguir} / \\emph{repartir}. "
              "Media $\\pm$ desviación estándar de 10 corridas de 200 s "
              "simulados (lote \\texttt{lotes/movilidad.json})."))


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
    """Cuatro paneles (uno por métrica) con seguir y repartir lado a lado
    por escenario."""
    paneles = [("cobertura_media", "Cobertura media"),
               ("tasa_entrega", "Tasa de entrega del radio"),
               ("tq_medio", "TQ medio de rutas"),
               ("tiempo_particionado_s", "Tiempo con la malla partida (s)")]
    y = list(range(len(ESCENARIOS_MOVILIDAD)))[::-1]
    alto_barra = 0.36
    fig, ejes = plt.subplots(2, 2, sharey=True,
                             figsize=(ANCHO_TEXTO_IN, 4.2))
    for ax, (clave, titulo) in zip(ejes.flat, paneles):
        _estilo(ax)
        ax.grid(axis="y", visible=False)
        for yi, esc in zip(y, ESCENARIOS_MOVILIDAD):
            for desp, modo, color in ((alto_barra / 2 + 0.02, "seguir", AZUL),
                                      (-alto_barra / 2 - 0.02, "repartir",
                                       NARANJA)):
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
               ncol=2, frameon=False, fontsize=7.5,
               bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.95), w_pad=1.0, h_pad=1.0)
    fig.savefig(salida)
    plt.close(fig)


# ── principal ─────────────────────────────────────────────────────────────
def generar(carpeta_fallos, carpeta_movilidad, plantilla):
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

    if carpeta_movilidad:
        mov = leer_resumen(carpeta_movilidad)
        escritos.append(_escribir(os.path.join(dir_tablas, "movilidad.tex"),
                                  tabla_movilidad(mov)))
        figura_movilidad(mov, os.path.join(dir_figuras, "movilidad.pdf"))
        escritos.append(os.path.join(dir_figuras, "movilidad.pdf"))
    return escritos


def _escribir(ruta, texto):
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)
    return ruta


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--fallos", help="salida de lotes/capitulo5_fallos.json "
                   "(por defecto, la última en reportes/)")
    p.add_argument("--movilidad", help="salida de lotes/movilidad.json "
                   "(por defecto, la última en reportes/)")
    p.add_argument("--plantilla", default="Plantilla",
                   help="carpeta del documento (por defecto Plantilla/)")
    a = p.parse_args(argv)
    fallos = a.fallos or ultimo_lote("capitulo5_fallos")
    movilidad = a.movilidad or ultimo_lote("movilidad")
    for ruta in generar(fallos, movilidad, a.plantilla):
        print(f"  {ruta}")
    print(f"(desde {fallos} y {movilidad})")


if __name__ == "__main__":
    main()
