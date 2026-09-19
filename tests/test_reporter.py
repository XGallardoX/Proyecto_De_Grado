"""Pruebas de analysis/reporter.py: que reporte.csv/json/txt tengan las
columnas y campos esperados y que coincidan con lo que registró la
simulación. Sin Visualizer/pygame."""
import contextlib
import csv
import io
import json
import os
import random
import shutil
import tempfile
import unittest

from analysis.reporter import export_simulation_reports
from tests.test_engine import make_simulation

COLUMNAS_CSV = [
    "tiempo_s", "gateways_activos", "nodos_activos", "componentes_malla",
    "nodos_alcanzables", "calidad_ruta_promedio_tq", "saltos_promedio",
    "silencio_maximo_s", "tasa_entrega_paquetes", "alertas_activas",
    "ancho_banda_total_mbps", "tipo_evento", "descripcion_evento",
]
CAMPOS_RESUMEN = {
    "tiempo_final_s", "nodos_por_rol", "componentes_finales",
    "total_eventos", "paquetes_transmitidos", "paquetes_recibidos",
    "tasa_entrega_paquetes",
}


def exportar(sim, out_dir):
    with contextlib.redirect_stdout(io.StringIO()):
        return export_simulation_reports(sim, out_dir)


class ReporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        random.seed(7)
        cls.sim = make_simulation([
            {"id": 1, "role": "G", "x": 5, "y": 5},
            {"id": 2, "role": "G", "x": 12, "y": 5},
            {"id": 3, "role": "N", "x": 9, "y": 8},
        ], escenario="prueba_reporter")
        for _ in range(10):
            cls.sim.step()
        cls.t_fallo = cls.sim.t
        cls.sim.fail_node(2)            # evento FAIL en t = 5.0
        for _ in range(10):
            cls.sim.step()
        cls.dir = tempfile.mkdtemp()
        cls.rutas = exportar(cls.sim, cls.dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir)

    def _csv(self):
        with open(self.rutas["csv"], newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def _json(self):
        with open(self.rutas["json"], encoding="utf-8") as f:
            return json.load(f)

    def _txt(self):
        with open(self.rutas["text"], encoding="utf-8") as f:
            return f.read()

    def test_devuelve_las_tres_rutas_dentro_de_out_dir(self):
        self.assertEqual(set(self.rutas), {"csv", "json", "text"})
        for ruta in self.rutas.values():
            self.assertTrue(os.path.isfile(ruta), ruta)
            self.assertEqual(os.path.dirname(ruta), self.dir)

    def test_csv_tiene_las_columnas_esperadas(self):
        with open(self.rutas["csv"], newline="", encoding="utf-8") as f:
            self.assertEqual(next(csv.reader(f)), COLUMNAS_CSV)

    def test_csv_una_fila_por_muestra_con_los_valores_del_recorder(self):
        rec = self.sim.recorder
        filas = self._csv()
        self.assertEqual(len(filas), len(rec.t))
        for i, fila in enumerate(filas):
            self.assertAlmostEqual(float(fila["tiempo_s"]), rec.t[i])
            self.assertEqual(int(fila["gateways_activos"]), rec.alive_G[i])
            self.assertEqual(int(fila["componentes_malla"]), rec.comp_G[i])
            self.assertAlmostEqual(float(fila["calidad_ruta_promedio_tq"]),
                                   rec.avg_tq[i])
            self.assertAlmostEqual(float(fila["tasa_entrega_paquetes"]),
                                   rec.deliver_ratio[i])

    def test_csv_marca_el_evento_en_su_instante(self):
        filas = self._csv()
        con_fallo = [f for f in filas if "FAIL" in f["tipo_evento"]]
        self.assertEqual(len(con_fallo), 1)
        self.assertAlmostEqual(float(con_fallo[0]["tiempo_s"]), self.t_fallo)
        self.assertIn("G2", con_fallo[0]["descripcion_evento"])

    def test_json_tiene_la_estructura_esperada(self):
        data = self._json()
        self.assertEqual(set(data), {"metadatos", "resumen",
                                     "serie_temporal_metricas", "eventos"})
        self.assertEqual(set(data["metadatos"]),
                         {"escenario", "fecha_ejecucion", "configuracion"})
        self.assertEqual(data["metadatos"]["escenario"], "prueba_reporter")
        self.assertEqual(set(data["resumen"]), CAMPOS_RESUMEN)
        serie = data["serie_temporal_metricas"]
        self.assertEqual(len(serie), len(self.sim.recorder.t))
        self.assertEqual(list(serie[0]), COLUMNAS_CSV[:-2])
        for ev in data["eventos"]:
            self.assertEqual(set(ev), {"tiempo_s", "tipo_evento", "descripcion"})

    def test_json_resumen_coincide_con_la_simulacion(self):
        resumen = self._json()["resumen"]
        medio = self.sim.medium
        self.assertEqual(resumen["tiempo_final_s"], self.sim.t)
        self.assertEqual(resumen["nodos_por_rol"],
                         {"G": {"total": 2, "activos": 1},
                          "N": {"total": 1, "activos": 1}})
        self.assertEqual(resumen["componentes_finales"],
                         self.sim.recorder.comp_G[-1])
        self.assertEqual(resumen["paquetes_transmitidos"], medio.attempted)
        self.assertEqual(resumen["paquetes_recibidos"], medio.delivered)
        self.assertAlmostEqual(resumen["tasa_entrega_paquetes"],
                               medio.delivered / medio.attempted)
        self.assertEqual(resumen["total_eventos"],
                         len(self.sim.recorder.events))

    def test_json_guarda_la_configuracion_usada(self):
        cfg = self._json()["metadatos"]["configuracion"]
        for clave in ("rango_comm", "timeout", "battery_drain_nodo", "nodes"):
            self.assertIn(clave, cfg)
        self.assertEqual(cfg["timeout"], self.sim.cfg["timeout"])

    def test_txt_tiene_todas_las_secciones(self):
        txt = self._txt()
        for texto in ("REPORTE DE SIMULACIÓN AD-HOC BATMAN",
                      "PRUEBA_REPORTER",
                      "PARÁMETROS DE CONFIGURACIÓN DE LA RED:",
                      "ESTADÍSTICAS FINALES:",
                      "Gateway (G)", "Nodo de Usuario (N)",
                      "PROMEDIOS DE RENDIMIENTO:",
                      "CRONOLOGÍA DE EVENTOS REGISTRADOS:",
                      "G2 caído (manual)"):
            self.assertIn(texto, txt)

    def test_sin_vocabulario_de_rescate(self):
        for ruta in self.rutas.values():
            with open(ruta, encoding="utf-8") as f:
                contenido = f.read().lower()
            for palabra in ("rescat", "superviv", "hallad"):
                self.assertNotIn(palabra, contenido, ruta)


class ReporterCasosBordeTests(unittest.TestCase):
    def test_sin_muestras_no_escribe_reportes(self):
        sim = make_simulation([{"id": 1, "role": "G", "x": 5, "y": 5}])
        out_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out_dir)
        self.assertEqual(exportar(sim, out_dir), {})
        self.assertEqual(os.listdir(out_dir), [])

    def test_sin_out_dir_crea_una_carpeta_por_ejecucion_en_reportes(self):
        sim = make_simulation([{"id": 1, "role": "G", "x": 5, "y": 5},
                               {"id": 2, "role": "N", "x": 8, "y": 5}],
                              escenario="mi_escenario")
        sim.step()
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        self.addCleanup(os.chdir, cwd)
        os.chdir(tmp)
        rutas = exportar(sim, None)
        carpeta = os.path.dirname(rutas["csv"])
        self.assertEqual(os.path.dirname(carpeta), "reportes")
        self.assertTrue(os.path.basename(carpeta).startswith("mi_escenario_"))
        self.assertEqual(sorted(os.listdir(carpeta)),
                         ["reporte.csv", "reporte.json", "reporte.txt"])


if __name__ == "__main__":
    unittest.main()
