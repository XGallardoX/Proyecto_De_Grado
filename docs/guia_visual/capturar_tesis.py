"""Capturas de la interfaz para la tesis (Plantilla/Images/Cap4/), con semilla fija.

Con el servidor ya corriendo (ver LEEME.md):

    python main.py --web --config escenarios/base.json --seed 1 --puerto 8771 --no-abrir
    python docs/guia_visual/capturar_tesis.py CARPETA [CARPETA_PLAYWRIGHT]

Escribe en CARPETA:

- fuerzas_cobertura.png: escenario `base`, semilla 2, a los 45 s, con las
  capas de cobertura, nodos críticos y fuerzas, y G2 seleccionado.
- trafico.png: despliegue de referencia (`cobertura_edificio`), semilla 1,
  a los 50 s, con 20 paquetes de cada tipo de N1 a N4 y dos flujos.

La misma semilla da siempre la misma imagen: si cambia la interfaz, se
vuelve a correr y las cifras de los pies de figura siguen siendo las de
la corrida (el guion las imprime).
"""
import json
import sys
import time
import urllib.request

if len(sys.argv) > 2:          # carpeta con playwright, si no está en el entorno
    sys.path.insert(0, sys.argv[2])
from playwright.sync_api import sync_playwright  # noqa: E402

BASE = "http://127.0.0.1:8771"
OUT = sys.argv[1]


def api(ruta, datos=None):
    req = urllib.request.Request(
        BASE + ruta, method="POST" if datos is not None else "GET",
        data=json.dumps(datos).encode() if datos is not None else None,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def cmd(accion, **kw):
    r = api("/api/comando", {"accion": accion, **kw})
    if not r.get("ok"):
        raise SystemExit(f"Falló {accion}: {r}")
    return r


def avanzar(hasta):
    """Avanza paso a paso hasta `hasta` s: igual en cualquier máquina."""
    while api("/api/estado")["t"] < hasta - 1e-9:
        cmd("paso")
    print("  t =", api("/api/estado")["t"])


def cargar(pg, semilla, **cual):
    cmd("cargar", semilla=semilla, **cual)
    cmd("pausar")
    pg.goto(BASE + "/")
    time.sleep(2)
    pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d => d.close())")


def capa(pg, k, encendida=True):
    """Deja la capa `k` encendida o apagada (el botón alterna)."""
    boton = pg.locator(f'#leyenda [data-capa="{k}"]')
    if (boton.get_attribute("aria-pressed") == "true") != encendida:
        boton.click()
        time.sleep(0.4)


def shot(pg, nombre):
    pg.screenshot(path=f"{OUT}/{nombre}.png")
    print("  ->", nombre)


with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    ctx = b.new_context(viewport={"width": 1600, "height": 1013},
                        device_scale_factor=1.5, color_scheme="light")
    pg = ctx.new_page()
    errores = []
    pg.on("pageerror", lambda e: errores.append(str(e)))

    # ── Capas del mapa: cobertura, críticos y fuerzas ──
    print("fuerzas_cobertura")
    cargar(pg, 2, escenario="base")
    avanzar(45)
    pg.focus("body")
    pg.keyboard.press("2")          # G2
    for k in ("cobertura", "criticos", "fuerzas", "alcance"):
        capa(pg, k, True)
    time.sleep(2.5)
    shot(pg, "fuerzas_cobertura")
    for k in ("cobertura", "criticos", "fuerzas"):
        capa(pg, k, False)

    # ── Panel Tráfico ──
    print("trafico")
    cargar(pg, 1, archivo="fallos/cobertura_edificio.txt")
    avanzar(40)
    ids = {n["etiqueta"]: n["id"] for n in api("/api/estado")["nodos"]}
    for tipo in ("udp", "icmp", "tcp"):
        cmd("enviar_paquetes", origen=ids["N1"], destino=ids["N4"],
            tipo=tipo, cantidad=20, cada=0)
    cmd("enviar_paquetes", origen=ids["N2"], destino=ids["N3"],
        tipo="icmp", cantidad=10, cada=1)
    cmd("enviar_paquetes", origen=ids["N3"], destino=ids["N1"],
        tipo="tcp", cantidad=10, cada=1)
    avanzar(50)
    pg.focus("body")
    pg.click('.pestana[data-panel="trafico"]')
    time.sleep(1.5)
    # el formulario queda arriba, fuera de la imagen: se ven la tabla, el
    # retardo y los últimos paquetes con su línea de tiempo
    pg.evaluate("document.querySelector('#panel-trafico .tr-tipos')"
                ".previousElementSibling.scrollIntoView({block: 'start'})")
    time.sleep(1)
    shot(pg, "trafico")
    t = api("/api/estado")["trafico"]
    for k, c in t["por_tipo"].items():
        print(f"  {k}: {c['entregados']}/{c['enviados']}, "
              f"retransm. {c['retransmisiones']}, sin respuesta {c['sin_respuesta']}, "
              f"retardo medio {c['retardo_medio']}")

    b.close()
    if errores:
        raise SystemExit("Errores de la página: " + "; ".join(errores))
