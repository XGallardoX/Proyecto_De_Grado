"""Pruebas del runner de lote: agregación (media ± desviación sobre datos
sintéticos), validación del archivo de lote y la corrida de punta a punta
desde main.py."""
import contextlib
import csv
import io
import json
import math
import os
import shutil
import tempfile
import unittest

import main as main_mod
from analysis import lote
from analysis.metrics import METRICAS_CORRIDA, resumen_corrida

CLAVES = [clave for clave, _, _ in METRICAS_CORRIDA]


def metricas(**valores):
    """Métricas de una corrida sintética: las no indicadas valen None."""
    return {clave: valores.get(clave) for clave in CLAVES}


def escribir_json(datos):
    fd, ruta = tempfile.mkstemp(suffix=".json", prefix="lote_prueba_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(datos, f)
    return ruta


class ResumirTests(unittest.TestCase):
    def test_media_y_desviacion_muestral(self):
        r = lote.resumir([1, 2, 3, 4])
        self.assertEqual(r["n"], 4)
        self.assertAlmostEqual(r["media"], 2.5)
        # desviación muestral: sqrt(sum((x - 2.5)^2) / (4 - 1)) = sqrt(5/3)
        self.assertAlmostEqual(r["desv"], math.sqrt(5 / 3))

    def test_valores_iguales_desviacion_cero(self):
        self.assertEqual(lote.resumir([3, 3, 3]),
                         {"media": 3, "desv": 0.0, "n": 3})

    def test_ignora_las_corridas_donde_no_aplica(self):
        r = lote.resumir([None, 2.0, None, 4.0])
        self.assertEqual(r["n"], 2)
        self.assertAlmostEqual(r["media"], 3.0)
        self.assertAlmostEqual(r["desv"], math.sqrt(2))

    def test_una_sola_corrida_no_tiene_desviacion(self):
        self.assertEqual(lote.resumir([5.0]), {"media": 5.0, "desv": None, "n": 1})

    def test_ninguna_corrida_aplica(self):
        self.assertEqual(lote.resumir([None, None]),
                         {"media": None, "desv": None, "n": 0})


class AgregarTests(unittest.TestCase):
    def test_agrupa_por_etiqueta_en_orden_de_aparicion(self):
        corridas = [
            {"etiqueta": "b", "semilla": 1, "metricas": metricas(tq_medio=0.5)},
            {"etiqueta": "a", "semilla": 1, "metricas": metricas(tq_medio=0.2)},
            {"etiqueta": "b", "semilla": 2, "metricas": metricas(tq_medio=0.7)},
            {"etiqueta": "a", "semilla": 2, "metricas": metricas(tq_medio=0.4)},
        ]
        agregado = lote.agregar(corridas)
        self.assertEqual(list(agregado), ["b", "a"])
        self.assertAlmostEqual(agregado["b"]["tq_medio"]["media"], 0.6)
        self.assertAlmostEqual(agregado["a"]["tq_medio"]["media"], 0.3)
        self.assertAlmostEqual(agregado["a"]["tq_medio"]["desv"],
                               math.sqrt(0.02))
        self.assertEqual(list(agregado["a"]), CLAVES)

    def test_metrica_que_aplica_en_parte_de_las_corridas(self):
        corridas = [
            {"etiqueta": "x", "semilla": s,
             "metricas": metricas(tiempo_reconvergencia_s=v)}
            for s, v in ((1, 10.0), (2, None), (3, 20.0))]
        r = lote.agregar(corridas)["x"]["tiempo_reconvergencia_s"]
        self.assertEqual(r["n"], 2)
        self.assertAlmostEqual(r["media"], 15.0)


class CargarLoteTests(unittest.TestCase):
    DISPONIBLES = main_mod.ESCENARIOS_DISPONIBLES

    def _cargar(self, datos):
        ruta = escribir_json(datos)
        self.addCleanup(os.unlink, ruta)
        return lote.cargar_lote(ruta, self.DISPONIBLES, 200.0, 1.0), ruta

    def _error(self, datos, patron):
        ruta = escribir_json(datos)
        self.addCleanup(os.unlink, ruta)
        with self.assertRaisesRegex(ValueError, patron):
            lote.cargar_lote(ruta, self.DISPONIBLES, 200.0, 1.0)

    def test_lote_minimo_con_defaults(self):
        spec, ruta = self._cargar({"semillas": 3,
                                   "escenarios": [{"escenario": "base"}]})
        self.assertEqual(spec["nombre"],
                         os.path.splitext(os.path.basename(ruta))[0])
        self.assertFalse(spec["figuras"])
        self.assertEqual(spec["escenarios"], [{
            "etiqueta": "base", "escenario": "base", "config": None,
            "static": False, "semillas": [1, 2, 3], "duracion": 200.0}])

    def test_la_entrada_pisa_los_defaults_del_lote(self):
        spec, _ = self._cargar({
            "nombre": "mi_lote", "duracion": 50, "semillas": 2,
            "figuras": True,
            "escenarios": [
                {"escenario": "base"},
                {"escenario": "base", "static": True},
                {"config": "otro/mi escenario.txt", "semillas": [7, 3],
                 "duracion": 10},
                {"escenario": "denso", "etiqueta": "denso_v2"},
            ]})
        self.assertEqual(spec["nombre"], "mi_lote")
        self.assertTrue(spec["figuras"])
        e = spec["escenarios"]
        self.assertEqual([x["etiqueta"] for x in e],
                         ["base", "base_static", "mi_escenario", "denso_v2"])
        self.assertEqual(e[1]["static"], True)
        self.assertEqual(e[2]["semillas"], [7, 3])
        self.assertEqual(e[2]["duracion"], 10.0)
        self.assertEqual(e[3]["duracion"], 50.0)
        self.assertEqual(e[3]["semillas"], [1, 2])

    def test_archivo_inexistente_o_json_invalido(self):
        with self.assertRaisesRegex(ValueError, "no encontrado"):
            lote.cargar_lote("/no/existe.json", self.DISPONIBLES, 200.0, 1.0)
        fd, ruta = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            f.write("{no es json")
        self.addCleanup(os.unlink, ruta)
        with self.assertRaisesRegex(ValueError, "JSON inválido"):
            lote.cargar_lote(ruta, self.DISPONIBLES, 200.0, 1.0)

    def test_errores_de_estructura(self):
        casos = [
            ([], "objeto JSON"),
            ({"semillas": 1}, "falta 'escenarios'"),
            ({"semillas": 1, "escenarios": []}, "falta 'escenarios'"),
            ({"semilla": 1, "escenarios": [{"escenario": "base"}]},
             "clave desconocida 'semilla'"),
            ({"semillas": 1, "escenarios": [{"escenario": "base", "x": 1}]},
             r"escenarios\[1\]: clave desconocida 'x'"),
            ({"semillas": 1, "escenarios": ["base"]}, "se esperaba un objeto"),
        ]
        for datos, patron in casos:
            with self.subTest(datos=datos):
                self._error(datos, patron)

    def test_errores_en_una_entrada(self):
        casos = [
            ({}, "exactamente uno de 'escenario'"),
            ({"escenario": "base", "config": "x.json"},
             "exactamente uno de 'escenario'"),
            ({"escenario": "no_existe"}, "escenario desconocido 'no_existe'"),
            ({"config": 5}, "'config' debe ser una ruta"),
            ({"escenario": "base", "static": "si"}, "'static' debe ser"),
            ({"escenario": "base", "etiqueta": "con espacio"}, "'etiqueta'"),
            ({"escenario": "base", "duracion": 0.5}, "'duracion'"),
            ({"escenario": "base", "duracion": "200"}, "'duracion'"),
        ]
        for entrada, patron in casos:
            with self.subTest(entrada=entrada):
                self._error({"semillas": 1, "escenarios": [entrada]}, patron)

    def test_semillas_invalidas_o_faltantes(self):
        for semillas in (0, -3, [], [1, 1], "10", True, [1, "2"], 2.5):
            with self.subTest(semillas=semillas):
                self._error({"semillas": semillas,
                             "escenarios": [{"escenario": "base"}]},
                            "'semillas'")
        self._error({"escenarios": [{"escenario": "base"}]},
                    "faltan 'semillas'")

    def test_etiquetas_repetidas(self):
        self._error({"semillas": 1, "escenarios": [{"escenario": "base"},
                                                   {"escenario": "base"}]},
                    "etiqueta repetida 'base'")

    def test_flags_de_lote_invalidos(self):
        self._error({"semillas": 1, "figuras": "no",
                     "escenarios": [{"escenario": "base"}]}, "'figuras'")
        self._error({"semillas": 1, "nombre": "con/barra",
                     "escenarios": [{"escenario": "base"}]}, "'nombre'")


class FormatoTests(unittest.TestCase):
    def test_formatear_estadistica(self):
        f = lote.formatear_estadistica
        self.assertTrue(f({"media": 0.41234, "desv": 0.0134, "n": 10}, 3, 10)
                        .startswith("0.412 ± 0.013"))
        self.assertIn("(n=10)", f({"media": 1.0, "desv": 0.0, "n": 10}, 2, 10))
        self.assertIn("(n=3 de 10)", f({"media": 1.0, "desv": 0.5, "n": 3}, 2, 10))
        self.assertTrue(f({"media": 5.0, "desv": None, "n": 1}, 1, 10)
                        .startswith("5.0 "))
        self.assertEqual(f({"media": None, "desv": None, "n": 0}, 1, 10),
                         "no aplica (0 de 10 corridas)")

    def test_describir_semillas(self):
        self.assertEqual(lote.describir_semillas([1, 2, 3, 4]), "1-4")
        self.assertEqual(lote.describir_semillas([7]), "7")
        self.assertEqual(lote.describir_semillas([5, 2, 9]), "5, 2, 9")


class EjecutarLoteTests(unittest.TestCase):
    """Un lote chico de punta a punta: 2 escenarios x 2 semillas x 5 s."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.ruta_lote = os.path.join(cls.tmp, "chico.json")
        with open(cls.ruta_lote, "w", encoding="utf-8") as f:
            json.dump({"duracion": 5, "semillas": 2, "escenarios": [
                {"escenario": "base"},
                {"escenario": "particion", "static": True},
            ]}, f)
        cls.out_dir = os.path.join(cls.tmp, "salida")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            main_mod.ejecutar_lote(cls.ruta_lote, cls.out_dir)
        cls.salida = out.getvalue()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def _csv(self, nombre):
        with open(os.path.join(self.out_dir, nombre), newline="",
                  encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_escribe_el_resumen_y_las_corridas(self):
        self.assertEqual(sorted(os.listdir(self.out_dir)),
                         ["base", "corridas.csv", "particion_static",
                          "resumen.csv", "resumen.json", "resumen.txt"])
        for etiqueta in ("base", "particion_static"):
            for semilla in (1, 2):
                carpeta = os.path.join(self.out_dir, etiqueta,
                                       f"semilla_{semilla}")
                self.assertEqual(sorted(os.listdir(carpeta)),
                                 ["reporte.csv", "reporte.json", "reporte.txt"])

    def test_corridas_csv_una_fila_por_corrida(self):
        filas = self._csv("corridas.csv")
        self.assertEqual([(f["etiqueta"], f["semilla"]) for f in filas],
                         [("base", "1"), ("base", "2"),
                          ("particion_static", "1"), ("particion_static", "2")])
        self.assertEqual(list(filas[0]), ["etiqueta", "semilla", "carpeta"] + CLAVES)

    def test_cada_corrida_es_igual_a_una_headless_con_la_misma_semilla(self):
        filas = {(f["etiqueta"], int(f["semilla"])): f
                 for f in self._csv("corridas.csv")}
        for etiqueta, nombre, static in (("base", "base", False),
                                         ("particion_static", "particion", True)):
            for semilla in (1, 2):
                main_mod.fijar_semilla(semilla)
                sim, _ = main_mod.construir_simulacion(
                    main_mod.ruta_escenario(nombre), static=static)
                main_mod.correr(sim, 5)
                esperado = resumen_corrida(sim)
                fila = filas[(etiqueta, semilla)]
                for clave in CLAVES:
                    if esperado[clave] is None:
                        self.assertEqual(fila[clave], "", clave)
                    else:
                        self.assertAlmostEqual(float(fila[clave]),
                                               esperado[clave], msg=clave)

    def test_resumen_csv_es_la_agregacion_de_las_corridas(self):
        corridas = self._csv("corridas.csv")
        resumen = {f["etiqueta"]: f for f in self._csv("resumen.csv")}
        self.assertEqual(list(resumen), ["base", "particion_static"])
        for etiqueta, fila in resumen.items():
            valores = [float(c["tasa_entrega"]) for c in corridas
                       if c["etiqueta"] == etiqueta]
            esperado = lote.resumir(valores)
            self.assertAlmostEqual(float(fila["tasa_entrega_media"]),
                                   esperado["media"])
            self.assertAlmostEqual(float(fila["tasa_entrega_desv"]),
                                   esperado["desv"])
            self.assertEqual(int(fila["tasa_entrega_n"]), 2)
        self.assertEqual(resumen["particion_static"]["static"], "True")

    def test_resumen_json_y_txt(self):
        with open(os.path.join(self.out_dir, "resumen.json"),
                  encoding="utf-8") as f:
            datos = json.load(f)
        self.assertEqual(set(datos), {"metadatos", "escenarios", "corridas"})
        self.assertEqual(datos["metadatos"]["nombre"], "chico")
        self.assertEqual(len(datos["corridas"]), 4)
        self.assertEqual(set(datos["escenarios"][0]["metricas"]), set(CLAVES))
        with open(os.path.join(self.out_dir, "resumen.txt"),
                  encoding="utf-8") as f:
            txt = f.read()
        self.assertIn("RESUMEN DEL LOTE 'chico'", txt)
        self.assertIn("particion_static  (particion, nodos fijos", txt)
        self.assertIn(txt.strip(), self.salida)     # también va a stdout

    def test_escenario_invalido_falla_antes_de_correr(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        ruta = os.path.join(tmp, "malo.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump({"semillas": 1, "escenarios": [
                {"escenario": "base"}, {"config": "/no/existe.json"}]}, f)
        with self.assertRaisesRegex(ValueError, "escenario 'existe'.*no encontrado"):
            main_mod.ejecutar_lote(ruta, os.path.join(tmp, "salida"))
        self.assertFalse(os.path.exists(os.path.join(tmp, "salida")))


class MainBatchTests(unittest.TestCase):
    def test_batch_desde_la_linea_de_comandos(self):
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        self.addCleanup(os.chdir, cwd)
        os.chdir(tmp)
        with open("mini.json", "w", encoding="utf-8") as f:
            json.dump({"duracion": 2, "semillas": 1,
                       "escenarios": [{"escenario": "base"}]}, f)
        with contextlib.redirect_stdout(io.StringIO()):
            main_mod.main(["--batch", "mini.json"])
        carpetas = os.listdir("reportes")
        self.assertEqual(len(carpetas), 1)
        self.assertTrue(carpetas[0].startswith("lote_mini_"))
        self.assertIn("resumen.txt", os.listdir(os.path.join("reportes",
                                                             carpetas[0])))

    def test_batch_no_se_combina_con_flags_del_lote(self):
        for extra in (["--escenario", "base"], ["--seed", "3"],
                      ["--duracion", "50"], ["--static"], ["-n", "5"]):
            with self.subTest(extra=extra), \
                    contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit) as cm:
                main_mod.main(["--batch", "x.json"] + extra)
            self.assertEqual(cm.exception.code, 2)

    def test_lote_invalido_termina_con_error(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                self.assertRaises(SystemExit) as cm:
            main_mod.main(["--batch", "/no/existe.json"])
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("Error en archivo de lote", out.getvalue())


if __name__ == "__main__":
    unittest.main()
