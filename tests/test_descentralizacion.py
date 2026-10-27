"""Métricas de descentralización (paso 10 de contexto/PLAN_SIGUIENTE.md):
exactitud del conocimiento de rutas, nodos críticos (puntos de
articulación) y caídas al azar contra caídas dirigidas."""
import os
import tempfile
import unittest

import main as main_mod
from analysis.metrics import (conocimiento, nodos_cortados,
                              puntos_articulacion, resumen_corrida)
from sim.config_loader import load_scenario, validar_escenario
from test_datos import LINEA, MEDIO_PERFECTO, ROMBO, _sim
from test_engine import make_simulation


def _hasta(sim, t):
    while sim.t < t:
        sim.step()


def _grafo(posiciones, rango=10):
    nodes = [{"id": i + 1, "role": "G", "x": x, "y": y}
             for i, (x, y) in enumerate(posiciones)]
    return make_simulation(nodes, medium=dict(MEDIO_PERFECTO, rango_comm=rango),
                           protocol={"move_speed": 0})


class ArticulacionTests(unittest.TestCase):
    def test_linea_el_del_medio_es_critico(self):
        sim = _grafo([(5, 5), (13, 5), (21, 5)])
        self.assertEqual(puntos_articulacion(sim), [2])
        self.assertEqual(nodos_cortados(sim, 2), 1)
        self.assertEqual(nodos_cortados(sim, 1), 0)

    def test_un_ciclo_no_tiene_criticos(self):
        sim = make_simulation(ROMBO, medium=MEDIO_PERFECTO,
                              protocol={"move_speed": 0})
        self.assertEqual(puntos_articulacion(sim), [])

    def test_cadena_de_cuatro_y_nodo_caido(self):
        sim = _grafo([(2, 5), (10, 5), (18, 5), (26, 5)])
        self.assertEqual(puntos_articulacion(sim), [2, 3])
        sim.fail_node(4)
        self.assertEqual(puntos_articulacion(sim), [2])

    def test_estrella_el_centro_es_critico(self):
        sim = _grafo([(15, 5), (7, 5), (23, 5), (15, 13)])
        self.assertEqual(puntos_articulacion(sim), [1])
        self.assertEqual(nodos_cortados(sim, 1), 2)


class ConocimientoTests(unittest.TestCase):
    def test_al_arrancar_todo_falta(self):
        sim = _sim(LINEA)
        self.assertEqual(conocimiento(sim), (0.0, 0.0, 1.0))

    def test_convergido_es_exacto(self):
        sim = _sim(LINEA)
        _hasta(sim, 30)
        self.assertEqual(conocimiento(sim), (1.0, 0.0, 0.0))

    def test_tras_partirse_quedan_rutas_fantasma(self):
        # cae el del medio: 1 y 3 siguen con la ruta vigente hasta el
        # timeout, aunque la radio ya no los conecta
        sim = _sim(LINEA)
        _hasta(sim, 30)
        sim.fail_node(2)
        exacto, fantasma, faltante = conocimiento(sim)
        self.assertEqual((exacto, fantasma, faltante), (0.0, 1.0, 0.0))
        _hasta(sim, 30 + sim.cfg["timeout"] + 5)
        self.assertEqual(conocimiento(sim), (1.0, 0.0, 0.0))

    def test_resumen_y_series(self):
        sim = _sim(LINEA)
        _hasta(sim, 30)
        r = resumen_corrida(sim)
        rec = sim.recorder
        self.assertAlmostEqual(r["exactitud_conocimiento"],
                               sum(rec.exactitud) / len(rec.exactitud))
        self.assertEqual(r["nodos_criticos_medio"], 1.0)
        self.assertEqual(rec.nodos_criticos[-1], 1)


def _escenario_txt(eventos):
    lineas = ["[medium]", "rango_comm=10", "falloff=0", "perdida_base=0",
              "[protocol]", "static=true", "[nodes]",
              "1 G 5 5", "2 G 13 5", "3 G 21 5", "4 N 13 8", "[events]"] + eventos
    fd, ruta = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")
    return ruta


class CaidasElegidasTests(unittest.TestCase):
    def _correr(self, eventos, semilla=1, hasta=12):
        ruta = _escenario_txt(eventos)
        self.addCleanup(os.remove, ruta)
        main_mod.fijar_semilla(semilla)
        sim, _ = main_mod.construir_simulacion(ruta)
        _hasta(sim, hasta)
        return sim

    def test_la_dirigida_tumba_al_mas_critico(self):
        sim = self._correr(["fail_critico G 10"])
        caidos = [n.id for n in sim.nodes.values() if not n.alive]
        self.assertEqual(caidos, [2])
        self.assertTrue(any("G2 caído (dirigido)" in txt
                            for _t, tipo, txt in sim.recorder.events if tipo == "FAIL"))

    def test_al_azar_respeta_el_rol(self):
        for semilla in range(1, 6):
            sim = self._correr(["fail_azar N 10"], semilla=semilla)
            self.assertEqual([n.id for n in sim.nodes.values() if not n.alive], [4])

    def test_al_azar_varia_con_la_semilla(self):
        caidos = {tuple(n.id for n in self._correr(["fail_azar G 10"], semilla=s)
                        .nodes.values() if not n.alive) for s in range(1, 9)}
        self.assertGreater(len(caidos), 1)

    def test_formato_y_validacion(self):
        ruta = _escenario_txt(["fail_critico G 60", "fail_azar * 90"])
        self.addCleanup(os.remove, ruta)
        eventos = load_scenario(ruta)["events"]
        self.assertEqual(eventos, [{"type": "fail_critico", "rol": "G", "t": 60.0},
                                   {"type": "fail_azar", "rol": "*", "t": 90.0}])
        base = {"nodes": LINEA}
        with self.assertRaisesRegex(ValueError, "rol"):
            validar_escenario(dict(base, events=[{"type": "fail_azar", "rol": "X", "t": 1}]))
        with self.assertRaisesRegex(ValueError, "'t'"):
            validar_escenario(dict(base, events=[{"type": "fail_critico"}]))
        self.assertEqual(validar_escenario(dict(base, events=[
            {"type": "fail_critico", "t": 5}]))["events"][0]["rol"], "G")
        with self.assertRaisesRegex(ValueError, "modo random"):
            validar_escenario({"random": {"n_nodes": 4, "n_gateways": 1},
                               "events": [{"type": "fail_azar", "t": 5}]})


if __name__ == "__main__":
    unittest.main()
