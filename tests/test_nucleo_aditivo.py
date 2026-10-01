"""Cambios aditivos al núcleo para la interfaz web (Fase 2): que no
cambien el comportamiento de siempre (consumo de `random`, fórmula de la
fiabilidad) y que lo nuevo respete sus límites."""
import json
import os
import random
import tempfile
import unittest

import main as main_mod
from sim.config_loader import load_scenario, validar_escenario
from sim.radio import fiabilidad


def _sim(nombre="base", **kw):
    return main_mod.construir_simulacion(main_mod.ruta_escenario(nombre), **kw)[0]


def _fiabilidad_original(a, b, cfg):
    """La fórmula tal como estaba en RadioMedium.reliability() antes de
    extraerla a sim.radio.fiabilidad()."""
    d = a.dist_to(b)
    rango = cfg['rango_comm']
    if d > rango:
        return 0.0
    rel = 1.0 - cfg['falloff'] * (d / rango)
    rel -= cfg['perdida_base']
    df = abs(a.piso - b.piso)
    if df:
        rel *= cfg['floor_atten'] ** df
    return max(0.0, min(1.0, rel))


class AddNodeTests(unittest.TestCase):
    def test_sin_argumentos_consume_random_igual_que_antes(self):
        main_mod.fijar_semilla(11)
        sim = _sim()
        sim.add_node()
        nuevo = sim.nodes[max(sim.nodes)]
        siguiente = random.random()

        # el camino de antes: uniform(5,35), uniform(5,25) y los dos
        # desfases de temporizador de SimNode.__init__
        main_mod.fijar_semilla(11)
        sim2 = _sim()
        x = random.uniform(5, 35)
        y = random.uniform(5, 25)
        random.uniform(0, sim2.DEFAULTS['beacon_cada'])
        random.uniform(0, sim2.DEFAULTS['batman_cada'])
        self.assertEqual((nuevo.x, nuevo.y), (x, y))
        self.assertEqual(nuevo.role, 'N')
        self.assertEqual(random.random(), siguiente)

    def test_gateway_en_posicion(self):
        sim = _sim()
        gs_antes = [n for n in sim.nodes.values() if n.role == 'G']
        nid = sim.add_node('G', 10.0, 12.0)
        n = sim.nodes[nid]
        self.assertEqual(n.role, 'G')
        self.assertEqual((n.x, n.y), (10.0, 12.0))
        self.assertEqual(n.label, f"G{len(gs_antes) + 1}")
        self.assertIn(n.color(), sim.C_GATEWAY)

    def test_posicion_recortada(self):
        sim = _sim()
        nid = sim.add_node('N', -10, 999)
        n = sim.nodes[nid]
        self.assertEqual((n.x, n.y), (1.0, sim.ALTO - 0.4))

    def test_rol_invalido(self):
        with self.assertRaises(ValueError):
            _sim().add_node('X')


class MoverNodoTests(unittest.TestCase):
    def test_dentro_de_limites(self):
        sim = _sim()
        self.assertEqual(sim.mover_nodo(1, 20.0, 15.0), (20.0, 15.0))
        self.assertEqual(sim.recorder.events[-1][1], 'MOVE')

    def test_recorta_a_los_limites_de_try_move(self):
        sim = _sim()
        self.assertEqual(sim.mover_nodo(1, -5, -5), (1.0, 0.4))
        self.assertEqual(sim.mover_nodo(1, 500, 500),
                         (sim.ANCHO - 1.0, sim.ALTO - 0.4))

    def test_nodo_inexistente(self):
        self.assertIsNone(_sim().mover_nodo(999, 1, 1))


class FiabilidadTests(unittest.TestCase):
    def test_refactor_da_identico(self):
        rnd = random.Random(3)
        for nombre in ("base", "particion", "denso"):
            sim = _sim(nombre)
            nodos = list(sim.nodes.values())
            for _ in range(300):
                a, b = rnd.sample(nodos, 2)
                a.x, a.y = rnd.uniform(0, 40), rnd.uniform(0, 30)
                b.x, b.y = rnd.uniform(0, 40), rnd.uniform(0, 30)
                self.assertEqual(sim.medium.reliability(a, b),
                                 _fiabilidad_original(a, b, sim.cfg))

    def test_fuera_de_rango(self):
        cfg = dict(main_mod.DEFAULTS)
        self.assertEqual(fiabilidad(cfg['rango_comm'] + 0.1, 0, cfg), 0.0)


class PaqueteTests(unittest.TestCase):
    def test_paquetes_llevan_tipo_origen_y_ttl(self):
        main_mod.fijar_semilla(1)
        sim = _sim("base", static=True)
        tipos = set()
        for _ in range(20):
            sim.step()
            for p in sim.medium.packets_visual:
                tipos.add(p.tipo)
                self.assertIn(p.origen, sim.nodes)
                self.assertIn(p.emisor, sim.nodes)
                self.assertIn(p.receptor, sim.nodes)
                if p.tipo == 'OGM':
                    self.assertIsNotNone(p.ttl)
                    self.assertEqual(p.color, sim.C_OGM)
                else:
                    self.assertEqual(p.color, sim.C_BCN)
        self.assertEqual(tipos, {'OGM', 'BCN'})


class ContadoresTests(unittest.TestCase):
    def test_cuentan_uso_del_codigo_real(self):
        main_mod.fijar_semilla(1)
        sim = _sim("base", static=True)
        for _ in range(40):
            sim.step()
        g = next(n for n in sim.nodes.values() if n.role == 'G')
        self.assertGreater(g.ogms_procesados, 0)
        self.assertGreaterEqual(g.ogms_procesados, g.ogms_nuevos)
        self.assertGreater(g.beacons_procesados, 0)
        self.assertGreater(g.chequeos_fallo, 0)


class ValidarEscenarioTests(unittest.TestCase):
    def test_igual_que_load_scenario(self):
        ruta = main_mod.ruta_escenario("base")
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        self.assertEqual(validar_escenario(datos, ruta), load_scenario(ruta))

    def test_no_modifica_la_entrada(self):
        datos = {"nodes": [{"id": 1, "role": "G", "x": 5, "y": 5}],
                 "protocol": {"battery_drain_surv": 0.1}}
        copia = json.loads(json.dumps(datos))
        validar_escenario(datos)
        self.assertEqual(datos, copia)

    def test_errores(self):
        for datos in ({"nodes": []},
                      {"nodes": [{"id": 1, "role": "N", "x": 5, "y": 5}]},
                      {"nodes": [{"id": 1, "role": "G", "x": 99, "y": 5}]},
                      {"nodes": [{"id": 1, "role": "G", "x": "a", "y": 5}]},
                      "no es un objeto"):
            with self.assertRaises(ValueError):
                validar_escenario(datos)

    def test_un_json_validado_carga_con_load_scenario(self):
        datos = {"name": "x", "nodes": [{"id": 1, "role": "G", "x": 5, "y": 5},
                                        {"id": 2, "role": "N", "x": 9, "y": 5}]}
        validar_escenario(datos)
        with tempfile.TemporaryDirectory() as tmp:
            ruta = os.path.join(tmp, "x.json")
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump(datos, f)
            self.assertEqual(len(load_scenario(ruta)["nodes"]), 2)


if __name__ == "__main__":
    unittest.main()
