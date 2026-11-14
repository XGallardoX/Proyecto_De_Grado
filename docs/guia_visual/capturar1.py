"""Capturas de la interfaz web con el escenario fallo_puente (+6 flujos).

Uso: capturar1.py <carpeta_salida> [carpeta_con_playwright]
Repite las de la guía del 4 de noviembre en los mismos instantes (55, 123 y
206 s) y agrega las de la pestaña Tráfico."""
import json, sys, time, urllib.request

if len(sys.argv) > 2:          # carpeta con playwright, si no está en el entorno
    sys.path.insert(0, sys.argv[2])
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8771"
OUT = sys.argv[1]


def api(ruta, datos=None):
    req = urllib.request.Request(BASE + ruta, method="POST" if datos is not None else "GET",
                                 data=json.dumps(datos).encode() if datos is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def cmd(accion, **kw):
    r = api("/api/comando", {"accion": accion, **kw})
    if not r.get("ok"):
        print("FALLO", accion, r)
    return r


def avanzar(hasta):
    """Llega exactamente a `hasta`: rápido hasta 12 s antes y luego paso a paso."""
    if api("/api/estado")["t"] < hasta - 12:
        cmd("velocidad", valor=8)
        cmd("reanudar")
        while api("/api/estado")["t"] < hasta - 12:
            time.sleep(0.01)
        cmd("pausar")
        cmd("velocidad", valor=1)
    while api("/api/estado")["t"] < hasta - 0.01:
        cmd("paso")
    print("t =", api("/api/estado")["t"])


def shot(pg, nombre, sel=None):
    ruta = f"{OUT}/{nombre}.png"
    if sel:
        pg.locator(sel).screenshot(path=ruta)
    else:
        pg.screenshot(path=ruta)
    print("  ->", nombre)


def pestana(pg, p):
    pg.click(f'.pestana[data-panel="{p}"]')
    time.sleep(1.6)


def capa(pg, k):
    pg.click(f'#leyenda [data-capa="{k}"]')
    time.sleep(1.2)


with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    pg = b.new_page(viewport={"width": 1600, "height": 950}, device_scale_factor=1.5,
                    color_scheme="light")
    errores = []
    pg.on("pageerror", lambda e: errores.append(str(e)))

    cmd("pausar")
    cmd("reiniciar")
    cmd("pausar")
    pg.goto(BASE + "/")
    time.sleep(2.5)
    shot(pg, "01_dialogo_inicio")
    pg.click("#dialogo-inicio .cerrar-dialogo")
    time.sleep(0.5)

    # ── Antes de la caída (t = 55 s) ──
    avanzar(55)
    pg.focus("body")
    pg.keyboard.press("5")          # selecciona G5
    time.sleep(2.5)
    shot(pg, "02_vista_general")
    shot(pg, "03_barra_superior", "#barra-superior")
    shot(pg, "04_riel", "#riel")
    shot(pg, "05_leyenda", "#leyenda")
    shot(pg, "06_barra_inferior", "#barra-inferior")
    shot(pg, "07_barra_mapa", "#barra-mapa")
    shot(pg, "08_panel_nodo", "#panel-lateral")

    capa(pg, "alcance")
    shot(pg, "09_capa_alcance", "#contenedor-canvas")
    capa(pg, "alcance")
    capa(pg, "vigilancia")
    shot(pg, "10_capa_vigilancia", "#contenedor-canvas")
    capa(pg, "vigilancia")
    capa(pg, "cobertura")
    time.sleep(2.5)
    shot(pg, "11_capa_cobertura", "#contenedor-canvas")
    capa(pg, "cobertura")
    capa(pg, "burbujas")
    shot(pg, "12_capa_beacons", "#contenedor-canvas")
    capa(pg, "burbujas")

    pg.click("#btn-lente")
    time.sleep(2)
    shot(pg, "13_lente", "#contenedor-canvas")
    pg.click("#btn-lente")
    time.sleep(0.5)

    pg.select_option("#sel-filtro-ogm", value="6")
    time.sleep(1.5)
    shot(pg, "14_filtro_ogm", "#contenedor-canvas")
    pg.select_option("#sel-filtro-ogm", value="")

    pestana(pg, "red")
    time.sleep(1.5)
    shot(pg, "15_panel_red", "#panel-lateral")
    pestana(pg, "real")
    shot(pg, "16_panel_real", "#panel-lateral")
    pestana(pg, "inspector")
    time.sleep(1.5)
    shot(pg, "17_panel_inspector", "#panel-lateral")
    pestana(pg, "parametros")
    shot(pg, "18_panel_parametros", "#panel-lateral")
    pestana(pg, "nodo")

    # Menú contextual en un lugar vacío del mapa
    caja = pg.locator("#mapa").bounding_box()
    pg.mouse.click(caja["x"] + caja["width"] * 0.62, caja["y"] + caja["height"] * 0.55, button="right")
    time.sleep(0.6)
    shot(pg, "19_menu_contextual", "#contenedor-canvas")
    pg.keyboard.press("Escape")

    # Mensaje N1 -> N6 por el plano de datos
    pg.focus("body")
    pg.keyboard.press("m")
    time.sleep(0.4)
    pg.select_option("#msg-origen", value="101")
    pg.select_option("#msg-destino", value="106")
    pg.fill("#msg-texto", "hola desde el piso 1")
    pg.click("#compositor button[type=submit]")
    time.sleep(1.5)
    shot(pg, "20_mensaje", "#contenedor-canvas")
    pg.keyboard.press("Escape")

    # ── Durante la caída de G6 (t = 123 s) ──
    avanzar(123)
    pg.focus("body")
    pg.keyboard.press("1")          # G1
    capa(pg, "criticos")
    time.sleep(2.5)
    shot(pg, "21_particion_general")
    shot(pg, "22_particion_nodo", "#panel-lateral")
    capa(pg, "criticos")
    pestana(pg, "red")
    time.sleep(1.5)
    shot(pg, "23_particion_red", "#panel-lateral")
    pestana(pg, "nodo")

    # ── Después de que vuelve G6 (t = 206 s): métricas ──
    avanzar(206)
    pestana(pg, "metricas")
    pg.select_option("#sel-ventana", value="0")
    time.sleep(2.5)
    shot(pg, "24_panel_metricas", "#panel-lateral")
    graf = pg.locator("#graficas .grafica")
    for i in range(graf.count()):
        g = graf.nth(i)
        if g.is_visible():
            g.scroll_into_view_if_needed()
            time.sleep(0.6)
            g.screenshot(path=f"{OUT}/graf_{i + 1}.png")
            print("  -> graf", i + 1)
    shot(pg, "25_final_general")

    # Ayuda
    pg.keyboard.press("Escape")
    pg.click("#btn-ayuda")
    time.sleep(0.6)
    shot(pg, "26_atajos", "#dialogo-ayuda")
    pg.click("#dialogo-ayuda .cerrar-dialogo")

    # ── Pestaña Tráfico (t = 206 s): una ráfaga de ICMP y otra de TCP, N1 -> N6 ──
    pestana(pg, "trafico")
    shot(pg, "39_panel_trafico_antes", "#panel-lateral")
    form = "#form-trafico"
    pg.select_option(f"{form} [name=origen]", value="101")
    pg.select_option(f"{form} [name=destino]", value="106")
    pg.fill(f"{form} [name=cantidad]", "10")
    pg.fill(f"{form} [name=cada]", "0")
    for tipo in ("icmp", "tcp"):
        pg.select_option(f"{form} [name=tipo]", value=tipo)
        pg.click(f"{form} button[type=submit]")
        time.sleep(1.5)
    shot(pg, "40_panel_trafico", "#panel-lateral")
    shot(pg, "41_trafico_general")
    pg.locator("#panel-trafico .tr-recientes").scroll_into_view_if_needed()
    time.sleep(0.8)
    shot(pg, "42_panel_trafico_abajo", "#panel-lateral")
    tr = api("/api/estado")["trafico"]
    print("por_tipo:", json.dumps(tr["por_tipo"]))
    print("totales:", tr["enviados"], tr["entregados"], tr["transmisiones"])
    for r in tr["recientes"][-4:]:
        print("  ", r["t"], r["tipo"], r["entregado"], r["intentos"], r["camino"], r["vuelta"], r["motivo"])

    print("errores de página:", errores)
    b.close()
