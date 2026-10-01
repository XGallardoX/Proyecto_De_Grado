"""Pruebas del servidor HTTP/SSE de web/servidor.py: se levanta en un
puerto efímero (0), en un hilo, y se prueba con http.client. Cubre las
rutas principales, un comando, un evento SSE y los intentos de path
traversal."""
import http.client
import json
import threading
import time
import unittest

import main as main_mod
from web.servidor import crear_servidor
from web.sesion import construir_sesion


class ServidorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sesion = construir_sesion(main_mod.ruta_escenario("base"), semilla=3)
        cls.sesion.avanzar_sincrono(5)
        cls.httpd = crear_servidor(cls.sesion, puerto=0)
        cls.puerto = cls.httpd.server_address[1]
        cls.hilo = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.hilo.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.hilo.join(timeout=2)
        cls.httpd.server_close()

    def _conn(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=5)
        self.addCleanup(conn.close)
        return conn

    def test_index(self):
        conn = self._conn()
        conn.request("GET", "/")
        r = conn.getresponse()
        self.assertEqual(r.status, 200)
        self.assertIn(b"<!doctype html>", r.read().lower())

    def test_estado(self):
        conn = self._conn()
        conn.request("GET", "/api/estado")
        r = conn.getresponse()
        self.assertEqual(r.status, 200)
        datos = json.loads(r.read())
        self.assertEqual(datos["escenario"], "base")

    def test_nodo_existente_e_inexistente(self):
        gid = next(n.id for n in self.sesion.sim.nodes.values() if n.role == "G")
        conn = self._conn()
        conn.request("GET", f"/api/nodo/{gid}")
        r = conn.getresponse()
        self.assertEqual(r.status, 200)
        json.loads(r.read())

        conn = self._conn()
        conn.request("GET", "/api/nodo/99999")
        r = conn.getresponse()
        self.assertEqual(r.status, 404)
        r.read()

    def test_series_e_inspector(self):
        conn = self._conn()
        conn.request("GET", "/api/series")
        r = conn.getresponse()
        self.assertEqual(r.status, 200)
        json.loads(r.read())

        conn = self._conn()
        conn.request("GET", "/api/inspector")
        r = conn.getresponse()
        self.assertEqual(r.status, 200)
        self.assertIn(b"RED AD-HOC", r.read())

    def test_escenarios(self):
        conn = self._conn()
        conn.request("GET", "/api/escenarios")
        r = conn.getresponse()
        self.assertEqual(r.status, 200)
        datos = json.loads(r.read())
        nombres = {e["nombre"] for e in datos["predefinidos"]}
        self.assertIn("base", nombres)
        self.assertIn("denso", nombres)

    def test_comando_valido_e_invalido(self):
        conn = self._conn()
        cuerpo = json.dumps({"accion": "pausar"}).encode()
        conn.request("POST", "/api/comando", body=cuerpo,
                     headers={"Content-Type": "application/json"})
        r = conn.getresponse()
        self.assertEqual(r.status, 200)
        self.assertTrue(json.loads(r.read())["ok"])

        conn = self._conn()
        cuerpo = json.dumps({"accion": "inexistente"}).encode()
        conn.request("POST", "/api/comando", body=cuerpo,
                     headers={"Content-Type": "application/json"})
        r = conn.getresponse()
        self.assertEqual(r.status, 400)
        self.assertFalse(json.loads(r.read())["ok"])

        conn = self._conn()
        cuerpo = json.dumps({"accion": "reanudar"}).encode()
        conn.request("POST", "/api/comando", body=cuerpo,
                     headers={"Content-Type": "application/json"})
        conn.getresponse().read()

    def test_comando_sin_accion(self):
        conn = self._conn()
        conn.request("POST", "/api/comando", body=b"{}",
                     headers={"Content-Type": "application/json"})
        r = conn.getresponse()
        self.assertEqual(r.status, 400)
        r.read()

    def test_sse_entrega_un_frame(self):
        self.sesion._publicar()
        conn = self._conn()
        conn.request("GET", "/api/stream")
        r = conn.getresponse()
        self.assertEqual(r.status, 200)
        self.assertEqual(r.getheader("Content-Type"), "text/event-stream")
        recibido = []
        limite = time.monotonic() + 3.0
        buffer = b""
        while time.monotonic() < limite and not recibido:
            chunk = r.read(4096)
            if not chunk:
                break
            buffer += chunk
            if b"event: frame" in buffer:
                recibido.append(buffer)
        conn.close()
        self.assertTrue(recibido, "no llegó ningún evento 'frame' por SSE")

    def test_path_traversal_static(self):
        conn = self._conn()
        conn.request("GET", "/static/../main.py")
        r = conn.getresponse()
        self.assertIn(r.status, (403, 404))
        r.read()

    def test_path_traversal_reportes(self):
        conn = self._conn()
        conn.request("GET", "/api/reportes/../../main.py")
        r = conn.getresponse()
        self.assertIn(r.status, (403, 404))
        r.read()

    def test_ruta_desconocida(self):
        conn = self._conn()
        conn.request("GET", "/no/existe")
        r = conn.getresponse()
        self.assertEqual(r.status, 404)
        r.read()


if __name__ == "__main__":
    unittest.main()
