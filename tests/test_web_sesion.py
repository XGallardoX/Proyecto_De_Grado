"""Pruebas de web/sesion.py: paridad con --headless (misma semilla, mismas
series) y validación de comandos, sin servidor HTTP ni hilos."""
import random
import unittest

import numpy as np

import main as main_mod
from analysis.metrics import resumen_corrida
from web.sesion import Sesion, construir_sesion


def _reset_aleatoriedad():
    random.seed()
    np.random.seed()


class ParidadTests(unittest.TestCase):
    """Con la misma semilla, k pasos por la Sesion (API síncrona) dan
    exactamente la misma serie y el mismo resumen_corrida que correr()."""

    def _comparar(self, config_path, pasos, **kwargs):
        main_mod.fijar_semilla(7)
        sim_term, _ = main_mod.construir_simulacion(config_path, **kwargs)
        main_mod.correr(sim_term, pasos * main_mod.DT)

        sesion = construir_sesion(config_path, semilla=7, **kwargs)
        sesion.avanzar_sincrono(pasos)

        self.assertEqual(sim_term.recorder.t, sesion.sim.recorder.t)
        self.assertEqual(sim_term.recorder.avg_tq, sesion.sim.recorder.avg_tq)
        self.assertEqual(sim_term.recorder.comp_G, sesion.sim.recorder.comp_G)
        self.assertEqual(sim_term.recorder.deliver_ratio,
                         sesion.sim.recorder.deliver_ratio)
        self.assertEqual(resumen_corrida(sim_term), resumen_corrida(sesion.sim))

    def test_paridad_base(self):
        self._comparar(main_mod.ruta_escenario("base"), 100)

    def test_paridad_denso_repartir(self):
        self._comparar(main_mod.ruta_escenario("denso"), 100, movilidad="repartir")

    def test_paridad_static(self):
        self._comparar(main_mod.ruta_escenario("base"), 60, static=True)

    def test_paridad_aleatorio(self):
        self._comparar(None, 60, n_nodes=6, n_gateways=2)


class ComandosTests(unittest.TestCase):
    def setUp(self):
        self.sesion = construir_sesion(main_mod.ruta_escenario("base"), semilla=1)

    def test_pausar_y_reanudar(self):
        self.sesion.comando("pausar", {})
        self.assertTrue(self.sesion.sim.paused)
        self.sesion.comando("reanudar", {})
        self.assertFalse(self.sesion.sim.paused)

    def test_paso_requiere_pausa(self):
        with self.assertRaises(ValueError):
            self.sesion.comando("paso", {})
        self.sesion.comando("pausar", {})
        t0 = self.sesion.sim.t
        self.sesion.comando("paso", {})
        self.assertGreater(self.sesion.sim.t, t0)

    def test_velocidad_valida_e_invalida(self):
        self.sesion.comando("velocidad", {"valor": 4})
        self.assertEqual(self.sesion.velocidad, 4.0)
        self.sesion.comando("velocidad", {"valor": "maxima"})
        self.assertEqual(self.sesion.velocidad, "maxima")
        with self.assertRaises(ValueError):
            self.sesion.comando("velocidad", {"valor": 99})
        with self.assertRaises(ValueError):
            self.sesion.comando("velocidad", {"valor": "rapido"})

    def test_accion_desconocida(self):
        with self.assertRaises(ValueError):
            self.sesion.comando("teletransportar", {})

    def test_caer_y_recuperar(self):
        gid = next(n.id for n in self.sesion.sim.nodes.values() if n.role == "G")
        self.sesion.comando("caer", {"id": gid})
        self.assertFalse(self.sesion.sim.nodes[gid].alive)
        self.assertEqual(len(self.sesion.intervenciones), 1)
        self.sesion.comando("recuperar", {"id": gid})
        self.assertTrue(self.sesion.sim.nodes[gid].alive)

    def test_caer_id_inexistente(self):
        with self.assertRaises(ValueError):
            self.sesion.comando("caer", {"id": 9999})

    def test_eliminar_unico_gateway_falla(self):
        sesion = construir_sesion(main_mod.ruta_escenario("dos_nodos"), semilla=1)
        gid = next(n.id for n in sesion.sim.nodes.values() if n.role == "G")
        with self.assertRaises(ValueError):
            sesion.comando("eliminar_nodo", {"id": gid})

    def test_agregar_nodo(self):
        antes = len(self.sesion.sim.nodes)
        r = self.sesion.comando("agregar_nodo", {})
        self.assertEqual(len(self.sesion.sim.nodes), antes + 1)
        self.assertIn(r["id"], self.sesion.sim.nodes)

    def test_mensaje_malla_partida_no_entrega(self):
        sesion = construir_sesion(main_mod.ruta_escenario("particion"),
                                  semilla=1, static=True)
        sesion.avanzar_sincrono(20)
        self.assertEqual(sesion.sim.gateway_components(), 2)
        alive, find, idx = sesion.sim._union_find()
        gateways = [n for n in alive if n.role == "G"]
        g1 = gateways[0]
        g2 = next(n for n in gateways[1:] if find(idx[n.id]) != find(idx[g1.id]))
        r = sesion.comando(
            "mensaje", {"texto": f"{g1.label}>{g2.label} hola"})
        self.assertFalse(r["entregado"])

    def test_mensaje_formato_invalido(self):
        with self.assertRaises(ValueError):
            self.sesion.comando("mensaje", {"texto": "texto sin formato"})

    def test_parametro_en_lista_blanca(self):
        self.sesion.comando("parametro", {"clave": "rango_comm", "valor": 20})
        self.assertEqual(self.sesion.sim.cfg["rango_comm"], 20)

    def test_parametro_fuera_de_lista_blanca(self):
        with self.assertRaises(ValueError):
            self.sesion.comando("parametro", {"clave": "timeout", "valor": 5})

    def test_reiniciar_refija_semilla(self):
        self.sesion.avanzar_sincrono(10)
        t_antes = self.sesion.sim.t
        self.sesion.comando("reiniciar", {})
        self.assertEqual(self.sesion.sim.t, 0.0)
        self.assertNotEqual(t_antes, self.sesion.sim.t)

    def test_cargar_otro_escenario(self):
        self.sesion.comando("cargar", {"escenario": "denso"})
        self.assertEqual(self.sesion.sim.escenario, "denso")

    def test_cargar_escenario_desconocido(self):
        with self.assertRaises(ValueError):
            self.sesion.comando("cargar", {"escenario": "no_existe"})

    def test_cargar_archivo_fuera_de_escenarios_falla(self):
        with self.assertRaises(ValueError):
            self.sesion.comando("cargar", {"archivo": "../main.py"})

    def tearDown(self):
        _reset_aleatoriedad()


class ComandoEquivalenteTests(unittest.TestCase):
    def test_sin_intervenciones(self):
        sesion = construir_sesion(main_mod.ruta_escenario("base"), semilla=5)
        sesion.avanzar_sincrono(10)
        cmd = sesion.comando_equivalente()
        self.assertIn("--escenario base", cmd)
        self.assertIn("--seed 5", cmd)

    def test_con_intervenciones_no_hay_comando(self):
        sesion = construir_sesion(main_mod.ruta_escenario("base"), semilla=5)
        gid = next(n.id for n in sesion.sim.nodes.values() if n.role == "G")
        sesion.comando("caer", {"id": gid})
        self.assertIsNone(sesion.comando_equivalente())

    def tearDown(self):
        _reset_aleatoriedad()


if __name__ == "__main__":
    unittest.main()
