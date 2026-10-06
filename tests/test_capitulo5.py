"""analysis/capitulo5.py: tablas y figuras del Capítulo 5."""
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest

import main as main_mod
from analysis import capitulo5 as c5


class VentanasCaidaTests(unittest.TestCase):
    def test_caida_y_vuelta(self):
        self.assertEqual(
            c5.ventanas_caida([(60.0, "FAIL", "G7"), (150.0, "RECOVER", "G7")],
                              240),
            [(60.0, 150.0, "G7")])

    def test_sin_vuelta_queda_caido_hasta_el_final(self):
        self.assertEqual(
            c5.ventanas_caida([(60.0, "FAIL", "G6"), (100.0, "FAIL", "G7")],
                              240),
            [(60.0, 240, "G6"), (100.0, 240, "G7")])


class FormatoTests(unittest.TestCase):
    def test_media_desv_y_no_aplica(self):
        self.assertEqual(c5.fmt({"media": 7.65, "desv": 3.74, "n": 10}, 1),
                         "7.7 $\\pm$ 3.7")
        self.assertEqual(c5.fmt({"media": 6.0, "desv": 0.0, "n": 10}, 0), "6")
        self.assertEqual(c5.fmt({"media": None, "desv": None, "n": 0}, 1),
                         "no aplica")


class GenerarTests(unittest.TestCase):
    """De punta a punta con un lote chico del Capítulo 5 y otro de
    movilidad (pocos segundos simulados, una semilla)."""

    def test_escribe_tablas_y_figuras(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        carpetas = {}
        for nombre, entradas in (
                ("capitulo5_fallos",
                 [{"config": os.path.join(main_mod.ESCENARIOS_DIR, "fallos",
                                          f"{e}.txt"), "etiqueta": e}
                  for e in c5.ETIQUETAS_FALLOS]),
                ("movilidad",
                 [{"escenario": e, "movilidad": m, "etiqueta": f"{e}_{m}"}
                  for e in c5.ESCENARIOS_MOVILIDAD
                  for m in ("seguir", "repartir")])):
            ruta = os.path.join(tmp, f"{nombre}.json")
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump({"nombre": nombre, "duracion": 5, "semillas": 1,
                           "escenarios": entradas}, f)
            with contextlib.redirect_stdout(io.StringIO()):
                carpetas[nombre] = main_mod.ejecutar_lote(
                    ruta, os.path.join(tmp, nombre))
        escritos = c5.generar(carpetas["capitulo5_fallos"],
                              carpetas["movilidad"],
                              os.path.join(tmp, "Plantilla"))
        nombres = sorted(os.path.basename(r) for r in escritos)
        self.assertEqual(nombres, [
            "calidad.tex", "cobertura_tiempo.pdf", "comparacion_fallos.pdf",
            "fallos.tex", "movilidad.pdf", "movilidad.tex"])
        for ruta in escritos:
            self.assertGreater(os.path.getsize(ruta), 0, ruta)
        with open(escritos[0], encoding="utf-8") as f:
            self.assertIn("\\label{tab:cap5-fallos}", f.read())


if __name__ == "__main__":
    unittest.main()
