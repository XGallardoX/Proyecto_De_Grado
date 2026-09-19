"""Pruebas de las funciones puras de analysis/visualizer.py (las que no
necesitan abrir la ventana: importar el módulo no carga pygame)."""
import unittest

from analysis.visualizer import interpretar_mensaje, siguiente_escenario

ESCENARIOS = ["base", "colapso_progresivo", "particion",
              "rescatista_perdido", "denso"]


class InterpretarMensajeTests(unittest.TestCase):
    def test_prefijos_g_y_n(self):
        self.assertEqual(interpretar_mensaje("G1 > G3 prueba de enlace"),
                         ("G1", "G3", "prueba de enlace"))
        self.assertEqual(interpretar_mensaje("N2>G1 hola"), ("N2", "G1", "hola"))

    def test_sin_prefijo_es_gateway(self):
        self.assertEqual(interpretar_mensaje("1>3 hola"), ("G1", "G3", "hola"))

    def test_minusculas_y_ceros_a_la_izquierda(self):
        self.assertEqual(interpretar_mensaje("  g01 >n002   texto  "),
                         ("G1", "N2", "texto"))

    def test_formatos_invalidos(self):
        for raw in ("R1>R3 x",      # vocabulario viejo de rescate
                    "S2>R1 x",
                    "G1 G3 x",      # falta '>'
                    "G1>G3",        # falta el texto
                    "G>G3 x",       # falta el índice
                    ""):
            self.assertIsNone(interpretar_mensaje(raw), raw)


class SiguienteEscenarioTests(unittest.TestCase):
    def test_avanza_en_orden(self):
        self.assertEqual(siguiente_escenario("base", ESCENARIOS),
                         "colapso_progresivo")

    def test_vuelve_al_primero_al_final(self):
        self.assertEqual(siguiente_escenario("denso", ESCENARIOS), "base")

    def test_escenario_fuera_de_la_lista_arranca_por_el_primero(self):
        self.assertEqual(siguiente_escenario("mi_config", ESCENARIOS), "base")
        self.assertEqual(siguiente_escenario("aleatorio", ESCENARIOS), "base")


if __name__ == "__main__":
    unittest.main()
