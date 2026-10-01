"""Prueba de ejecución del frontend (web/static/js) sin navegador.

Genera datos reales con web/estado.py (una corrida de 'base' con un
Gateway caído) y ejecuta los módulos ES del frontend en JavaScriptCore
(`jsc`, que trae macOS) con un DOM mínimo simulado (tests/frontend/).
Detecta errores en tiempo de ejecución con datos reales: un campo que no
existe, un `undefined` o `NaN` que llega al canvas o al HTML, una
interacción que no responde. No reemplaza mirar la interfaz en un
navegador (ver docs/interfaz_web.md), y se salta si no hay `jsc`."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

import main as main_mod
from web import estado
from web.servidor import listar_escenarios

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
AQUI = os.path.dirname(os.path.abspath(__file__))
JS = os.path.join(os.path.dirname(AQUI), "web", "static", "js") + os.sep


def _datos(carpeta):
    main_mod.fijar_semilla(4)
    sim, _ = main_mod.construir_simulacion(main_mod.ruta_escenario("base"))
    for _ in range(200):
        sim.step()
    sim.fail_node(4)
    for _ in range(820):
        sim.step()
    archivos = {"frame.json": estado.frame(sim, semilla=4, generacion=1)}
    sim.step()
    archivos.update({
        "frame2.json": estado.frame(sim, semilla=4, generacion=1),
        "series.json": dict(estado.series(sim), generacion=1),
        "matriz.json": estado.matriz_conocimiento(sim),
        "nodo.json": estado.nodo_detalle(sim, 1),
        "cobertura.json": estado.cobertura(sim),
        "escenario.json": estado.escenario_actual(sim),
        "escenarios.json": listar_escenarios(),
        "paquetes.json": {"origen": 1, "paquetes": estado.paquetes_de_origen(sim, 1)},
    })
    for nombre, contenido in archivos.items():
        with open(os.path.join(carpeta, nombre), "w", encoding="utf-8") as f:
            json.dump(contenido, f)
    with open(os.path.join(carpeta, "inspector.txt"), "w", encoding="utf-8") as f:
        f.write(estado.inspector_texto(sim))


@unittest.skipUnless(os.path.exists(JSC), "sin JavaScriptCore (jsc)")
class FrontendTests(unittest.TestCase):
    def test_modulos_corren_con_datos_reales(self):
        tmp = tempfile.mkdtemp()
        try:
            datos = os.path.join(tmp, "datos") + os.sep
            os.makedirs(datos)
            _datos(datos)
            for nombre in ("stub.js", "arnes.js"):
                shutil.copy(os.path.join(AQUI, "frontend", nombre), tmp)
            with open(os.path.join(tmp, "rutas.js"), "w", encoding="utf-8") as f:
                f.write(f"globalThis.__RUTAS = {json.dumps({'datos': datos, 'js': JS})};\n")
            r = subprocess.run([JSC, "-m", os.path.join(tmp, "arnes.js")],
                               capture_output=True, text=True, timeout=120)
            salida = r.stdout + r.stderr
            self.assertIn("✓ errores: 0", salida, salida)
            self.assertIn("comprobaciones", salida, salida)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
