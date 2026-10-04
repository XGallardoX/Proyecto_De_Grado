"""Ventana propia para la interfaz web (Fase 3, parte 3): modo --app de un
navegador basado en Chromium, con el navegador por defecto de respaldo."""
import contextlib
import io
import unittest
from unittest.mock import patch

import main as main_mod
from web.ventana import abrir_en_ventana, buscar_navegador_app


class BuscarNavegadorTests(unittest.TestCase):
    def test_usa_el_primero_que_encuentra_en_el_path(self):
        rutas = {"brave-browser": "/usr/bin/brave-browser",
                 "chromium": "/usr/bin/chromium"}
        self.assertEqual(buscar_navegador_app(which=rutas.get,
                                              existe=lambda r: False),
                         "/usr/bin/chromium")

    def test_macos_busca_en_aplicaciones(self):
        ruta = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
        self.assertEqual(buscar_navegador_app(which=lambda n: None,
                                              existe=lambda r: r == ruta,
                                              plataforma="darwin"), ruta)

    def test_sin_navegador_con_modo_app(self):
        self.assertIsNone(buscar_navegador_app(which=lambda n: None,
                                               existe=lambda r: False,
                                               plataforma="linux"))


class AbrirEnVentanaTests(unittest.TestCase):
    def test_lanza_el_navegador_en_modo_app(self):
        lanzados, abiertos = [], []
        usado = abrir_en_ventana("http://127.0.0.1:1/",
                                 buscar=lambda: "/usr/bin/chromium",
                                 lanzar=lambda args, **kw: lanzados.append(args),
                                 abrir_navegador=abiertos.append)
        self.assertEqual(usado, "/usr/bin/chromium")
        self.assertEqual(lanzados, [["/usr/bin/chromium",
                                     "--app=http://127.0.0.1:1/", "--new-window"]])
        self.assertEqual(abiertos, [])

    def test_sin_navegador_abre_el_de_siempre(self):
        abiertos = []
        usado = abrir_en_ventana("http://127.0.0.1:1/", buscar=lambda: None,
                                 lanzar=None, abrir_navegador=abiertos.append)
        self.assertIsNone(usado)
        self.assertEqual(abiertos, ["http://127.0.0.1:1/"])

    def test_si_el_navegador_no_arranca_abre_el_de_siempre(self):
        def falla(args, **kw):
            raise OSError("no se pudo")
        abiertos = []
        usado = abrir_en_ventana("http://127.0.0.1:1/", buscar=lambda: "/x",
                                 lanzar=falla, abrir_navegador=abiertos.append)
        self.assertIsNone(usado)
        self.assertEqual(abiertos, ["http://127.0.0.1:1/"])


class FlagVentanaTests(unittest.TestCase):
    def _espera_salida(self, argv):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                main_mod.main(argv)

    def test_ventana_sin_web(self):
        self._espera_salida(["--ventana"])

    def test_ventana_con_no_abrir(self):
        self._espera_salida(["--web", "--ventana", "--no-abrir"])

    def test_web_ventana_llega_al_servidor(self):
        with patch("web.servidor.ejecutar_servidor") as ejecutar:
            main_mod.main(["--web", "--ventana", "--escenario", "base",
                           "--seed", "1"])
        self.assertTrue(ejecutar.call_args.kwargs["ventana"])
        self.assertTrue(ejecutar.call_args.kwargs["abrir"])


if __name__ == "__main__":
    unittest.main()
