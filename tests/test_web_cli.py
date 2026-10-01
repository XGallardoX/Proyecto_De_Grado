"""Pruebas de la integración de --web en main.py: validación de flags
incompatibles y que arranque sin bloquear la prueba (servidor real,
apagado enseguida), sin abrir navegador."""
import contextlib
import io
import threading
import time
import unittest
from unittest.mock import patch

import main as main_mod


def _correr_main_en_hilo(argv):
    hilo = threading.Thread(target=main_mod.main, args=(argv,), daemon=True)
    hilo.start()
    return hilo


class FlagsIncompatiblesTests(unittest.TestCase):
    def _espera_salida(self, argv):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                main_mod.main(argv)

    def test_web_con_headless(self):
        self._espera_salida(["--web", "--headless"])

    def test_web_con_inspect(self):
        self._espera_salida(["--web", "--inspect"])

    def test_web_con_batch(self):
        self._espera_salida(["--web", "--batch", "lotes/ejemplo.json"])

    def test_web_con_duracion(self):
        self._espera_salida(["--web", "--duracion", "50"])


class ArranqueRealTests(unittest.TestCase):
    def test_web_no_abrir_arranca_y_se_apaga(self):
        """--web --no-abrir arranca sin abrir el navegador; se verifica
        contra el puerto real y se apaga con el comando 'terminar' para no
        dejar la prueba (ni el hilo) colgados."""
        import http.client
        import json

        with patch("webbrowser.open") as abrir_navegador:
            hilo = _correr_main_en_hilo(
                ["--web", "--no-abrir", "--puerto", "8799",
                 "--escenario", "base"])
            try:
                conn = None
                for _ in range(50):
                    time.sleep(0.1)
                    try:
                        conn = http.client.HTTPConnection(
                            "127.0.0.1", 8799, timeout=2)
                        conn.request("GET", "/api/estado")
                        r = conn.getresponse()
                        datos = json.loads(r.read())
                        break
                    except (ConnectionRefusedError, OSError):
                        conn = None
                self.assertIsNotNone(conn, "el servidor --web no arrancó a tiempo")
                self.assertEqual(datos["escenario"], "base")
                abrir_navegador.assert_not_called()

                conn = http.client.HTTPConnection("127.0.0.1", 8799, timeout=2)
                conn.request("POST", "/api/comando",
                             body=json.dumps({"accion": "terminar"}).encode(),
                             headers={"Content-Type": "application/json"})
                conn.getresponse().read()
                conn.close()
            finally:
                hilo.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
