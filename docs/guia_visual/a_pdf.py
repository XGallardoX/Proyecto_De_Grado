import sys, pathlib
if len(sys.argv) > 3:          # carpeta con playwright, si no está en el entorno
    sys.path.insert(0, sys.argv[3])
from playwright.sync_api import sync_playwright

html = pathlib.Path(sys.argv[1]).resolve()
out = sys.argv[2]
pie = ('<div style="width:100%;font-family:sans-serif;font-size:8px;color:#8891A3;'
       'padding:0 14mm;display:flex;justify-content:space-between">'
       '<span>Simulador BATMAN · Guía visual</span>'
       '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    pg = b.new_page()
    pg.goto(html.as_uri())
    pg.wait_for_load_state("networkidle")
    pg.evaluate("document.fonts.ready")
    pg.pdf(path=out, format="A4", print_background=True, prefer_css_page_size=True,
           display_header_footer=True, header_template="<span></span>", footer_template=pie)
    b.close()
print("ok", out)
