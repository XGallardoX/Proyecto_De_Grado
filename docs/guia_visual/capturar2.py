"""Campo abierto (Fuerzas), editor, laboratorio y tema oscuro."""
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
    cmd("velocidad", valor=2)
    cmd("reanudar")
    while api("/api/estado")["t"] < hasta:
        time.sleep(0.05)
    cmd("pausar")
    cmd("velocidad", valor=1)
    print("t =", api("/api/estado")["t"])


def shot(pg, nombre, sel=None):
    ruta = f"{OUT}/{nombre}.png"
    (pg.locator(sel).screenshot if sel else pg.screenshot)(path=ruta)
    print("  ->", nombre)


with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    ctx = b.new_context(viewport={"width": 1600, "height": 950}, device_scale_factor=1.5,
                        color_scheme="light")
    pg = ctx.new_page()
    errores = []
    pg.on("pageerror", lambda e: errores.append(str(e)))

    # ── Campo abierto, Gateways que se mueven solos ──
    cmd("cargar", escenario="campo_abierto", semilla=3)
    cmd("pausar")
    pg.goto(BASE + "/")
    time.sleep(2)
    pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d => d.close())")
    avanzar(70)
    pg.focus("body")
    pg.keyboard.press("1")
    pg.click('#leyenda [data-capa="fuerzas"]')
    time.sleep(2.5)
    shot(pg, "30_campo_fuerzas")
    pg.click('#leyenda [data-capa="fuerzas"]')

    # ── Editor ──
    pg.click("#btn-editor")
    time.sleep(2)
    shot(pg, "31_editor")
    pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d => d.close())")

    # ── Laboratorio con lotes/robustez.json ──
    pg.click("#btn-laboratorio")
    time.sleep(1.5)
    opciones = pg.locator("#lab-cargar option").all_inner_texts()
    idx = next(i for i, t in enumerate(opciones) if "robustez" in t)
    pg.select_option("#lab-cargar", index=idx)
    time.sleep(1)
    shot(pg, "32_lab_armado")
    pg.click("#lab-correr")
    time.sleep(4)
    shot(pg, "33_lab_corriendo")
    t0 = time.time()
    while api("/api/laboratorio")["estado"] == "corriendo" and time.time() - t0 < 500:
        time.sleep(2)
    print("lab:", api("/api/laboratorio")["estado"], round(time.time() - t0), "s")
    time.sleep(3)
    shot(pg, "34_lab_resultado")
    pg.mouse.wheel(0, 1600)
    time.sleep(1)
    shot(pg, "35_lab_resultado_abajo")
    pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d => d.close())")

    # ── Tema oscuro, con el escenario base ──
    cmd("cargar", escenario="base", semilla=1)
    cmd("pausar")
    pg.click("#btn-tema")
    time.sleep(0.5)
    avanzar(40)
    pg.focus("body")
    pg.keyboard.press("2")
    time.sleep(2.5)
    shot(pg, "36_tema_oscuro")
    pg.click("#btn-tema")

    print("errores de página:", errores)
    b.close()
