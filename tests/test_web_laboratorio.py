"""Laboratorio de experimentos (Fase 3, parte 2): validación del lote,
ejecución en un subproceso `--batch` y sus rutas HTTP."""
import glob
import http.client
import json
import os
import random
import shutil
import threading
import unittest

import main as main_mod
from web import laboratorio as lab_mod
from web.laboratorio import Laboratorio, validar_lote
from web.servidor import crear_servidor
from web.sesion import construir_sesion

RAIZ = lab_mod.RAIZ


def _lote(nombre="prueba_lab", **extra):
    datos = {"nombre": nombre, "duracion": 5, "semillas": 2,
             "escenarios": [{"escenario": "base"},
                            {"config": "casos/puente.txt", "etiqueta": "puente"}]}
    datos.update(extra)
    return datos


def _limpiar(nombre):
    for ruta in glob.glob(os.path.join(RAIZ, "reportes", f"lote_{nombre}_*")):
        shutil.rmtree(ruta, ignore_errors=True)
    for ruta in glob.glob(os.path.join(lab_mod.LAB_DIR, f"lote_{nombre}_*.json")):
        os.remove(ruta)


class ValidarLoteTests(unittest.TestCase):
    def test_normaliza_las_rutas_de_escenario(self):
        lote, spec = validar_lote(_lote())
        self.assertEqual(lote["escenarios"][1]["config"],
                         os.path.join("escenarios", "casos", "puente.txt"))
        self.assertEqual([e["etiqueta"] for e in spec["escenarios"]],
                         ["base", "puente"])

    def test_nombre_por_defecto(self):
        lote, _ = validar_lote({"semillas": 1, "duracion": 5,
                                "escenarios": [{"escenario": "base"}]})
        self.assertEqual(lote["nombre"], "laboratorio")

    def test_errores(self):
        casos = [
            (_lote(escenarios=[{"config": "../main.py"}]), "fuera de escenarios/"),
            (_lote(escenarios=[{"config": "no_existe.json"}]), "no encontrado"),
            (_lote(escenarios=[{"escenario": "inexistente"}]), "escenario desconocido"),
            (_lote(semillas=400), "admite hasta"),
            (_lote(duracion=5000), "duración máxima"),
            (_lote(escenarios=[]), "al menos una entrada"),
            ("no es un lote", "se esperaba un lote"),
        ]
        for lote, mensaje in casos:
            with self.subTest(mensaje=mensaje):
                with self.assertRaises(ValueError) as cm:
                    validar_lote(lote)
                self.assertIn(mensaje, str(cm.exception))

    def test_validar_no_consume_random(self):
        # el servidor comparte `random` con la sesión en vivo
        random.seed(5)
        antes = random.getstate()
        validar_lote(_lote())
        self.assertEqual(random.getstate(), antes)


class LaboratorioTests(unittest.TestCase):
    def tearDown(self):
        _limpiar("prueba_lab")
        _limpiar("prueba_lab_largo")

    def test_corre_el_lote_en_un_subproceso_igual_que_la_terminal(self):
        lab = Laboratorio()
        estado = lab.iniciar(_lote())
        self.assertEqual(estado["estado"], "corriendo")
        self.assertEqual(estado["total"], 4)
        self.assertTrue(lab.esperar(timeout=120))
        final = lab.estado()
        self.assertEqual(final["estado"], "terminado", final["error"])
        self.assertEqual(final["hechas"], 4)
        resultado = final["resultado"]
        self.assertEqual([e["etiqueta"] for e in resultado["escenarios"]],
                         ["base", "puente"])
        self.assertIn("resumen.csv", resultado["archivos"])

        # el mismo archivo de lote, corrido como en terminal, da lo mismo
        terminal = main_mod.ejecutar_lote(os.path.join(RAIZ, final["archivo"]))
        try:
            with open(os.path.join(terminal, "resumen.json"), encoding="utf-8") as f:
                esperado = json.load(f)["escenarios"]
            self.assertEqual(resultado["escenarios"], esperado)
        finally:
            shutil.rmtree(terminal, ignore_errors=True)

    def test_un_lote_a_la_vez_y_cancelar(self):
        lab = Laboratorio()
        lab.iniciar(_lote("prueba_lab_largo", duracion=600, semillas=20))
        with self.assertRaises(ValueError) as cm:
            lab.iniciar(_lote())
        self.assertIn("ya hay un lote corriendo", str(cm.exception))
        lab.cancelar()
        self.assertTrue(lab.esperar(timeout=30))
        self.assertEqual(lab.estado()["estado"], "cancelado")
        with self.assertRaises(ValueError):
            lab.cancelar()

    def test_error_del_subproceso(self):
        lab = Laboratorio(python=os.path.join(RAIZ, "no_existe_python"))
        with self.assertRaises(ValueError) as cm:
            lab.iniciar(_lote())
        self.assertIn("no se pudo lanzar el lote", str(cm.exception))
        self.assertEqual(lab.estado()["estado"], "inactivo")


class RutasLaboratorioTests(unittest.TestCase):
    def setUp(self):
        self.sesion = construir_sesion(main_mod.ruta_escenario("base"), semilla=1)
        self.httpd = crear_servidor(self.sesion, puerto=0)
        self.puerto = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def _pedir(self, metodo, ruta, cuerpo=None):
        c = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=10)
        try:
            datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
            c.request(metodo, ruta, body=datos,
                      headers={"Content-Type": "application/json"})
            r = c.getresponse()
            return r.status, json.loads(r.read())
        finally:
            c.close()

    def test_estado_inicial(self):
        status, datos = self._pedir("GET", "/api/laboratorio")
        self.assertEqual(status, 200)
        self.assertEqual(datos["estado"], "inactivo")

    def test_lotes_existentes(self):
        status, datos = self._pedir("GET", "/api/lotes")
        self.assertEqual(status, 200)
        archivos = [l["archivo"] for l in datos["lotes"]]
        self.assertIn("lotes/fallos.json", archivos)

    def test_lote_invalido_da_error_legible(self):
        status, datos = self._pedir("POST", "/api/laboratorio",
                                    {"accion": "iniciar",
                                     "lote": {"escenarios": [{"config": "../x"}]}})
        self.assertEqual(status, 400)
        self.assertFalse(datos["ok"])
        self.assertIn("escenarios/", datos["error"])

    def test_accion_desconocida(self):
        status, datos = self._pedir("POST", "/api/laboratorio", {"accion": "x"})
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
