"""Pasa las capturas PNG a los JPG que usa guia.html (con dos recortes).

Uso: a_jpg.py <capturas> <guia/img>"""
import pathlib, sys
from PIL import Image

src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
dst.mkdir(parents=True, exist_ok=True)
MAX_ANCHO = 2000


def guardar(im, nombre):
    im = im.convert("RGB")
    if im.width > MAX_ANCHO:
        im = im.resize((MAX_ANCHO, round(im.height * MAX_ANCHO / im.width)), Image.LANCZOS)
    im.save(dst / (nombre + ".jpg"), quality=86, optimize=True)


def recorte(im, x0, y0, x1, y1):
    """Recorte en fracciones del ancho y del alto."""
    return im.crop((round(x0 * im.width), round(y0 * im.height),
                    round(x1 * im.width), round(y1 * im.height)))


n = 0
for png in sorted(src.glob("*.png")):
    if png.stem.startswith("_"):      # recortes de revisión, no van a la guía
        continue
    im = Image.open(png)
    if png.stem in ("15_panel_red", "23_particion_red"):
        # la matriz y su leyenda: debajo el panel queda en blanco
        im = recorte(im, 0, 0, 1, 0.72)
    guardar(im, png.stem)
    n += 1
    if png.stem == "04_riel":
        # el riel es muy alto: sólo los cuatro botones de arriba
        guardar(recorte(im, 0, 0, 1, 0.33), "04_riel_corto")
    if png.stem == "34_lab_resultado":
        # sólo la mitad derecha del diálogo: el resultado del lote
        guardar(recorte(im, 0.42, 0.10, 0.98, 0.96), "34_lab_resultado_rec")
print("ok", n, "capturas")
