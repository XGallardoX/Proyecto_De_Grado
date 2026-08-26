import os
import unittest

import main as main_mod
from sim.config_loader import load_scenario
from sim.engine import Simulation


def make_simulation(nodes, building=None, medium=None, protocol=None,
                     events=None, escenario="test"):
    building = building or {}
    ancho = building.get("ancho", main_mod.ANCHO)
    alto = building.get("alto", main_mod.ALTO)
    piso_h = building.get("piso_h", main_mod.PISO_H)
    n_pisos = building.get("n_pisos", main_mod.N_PISOS)
    stair_xy = tuple(building.get("stair_xy", main_mod.STAIR_XY))
    stair_half_w = building.get("stair_half_w", main_mod.STAIR_HALF_W)

    cfg = dict(main_mod.DEFAULTS)
    cfg.update(medium or {})
    cfg.update(protocol or {})
    cfg["nodes"] = nodes
    cfg["events"] = events or []
    cfg["n_nodes"] = len(nodes)
    cfg["n_gateways"] = sum(1 for n in nodes if n["role"] == "G")

    return Simulation(
        escenario=escenario, cfg=cfg, DEFAULTS=main_mod.DEFAULTS, DT=main_mod.DT,
        N_PISOS=n_pisos, PISO_H=piso_h, STAIR_XY=stair_xy, STAIR_HALF_W=stair_half_w,
        ANCHO=ancho, ALTO=alto, C_RESC=main_mod.C_RESC, C_SURV=main_mod.C_SURV,
        C_SURV_OK=main_mod.C_SURV_OK, C_DEAD=main_mod.C_DEAD, C_OGM=main_mod.C_OGM,
        C_BCN=main_mod.C_BCN, C_HB=main_mod.C_HB,
    )


def grid_nodes(n, n_gateways):
    """n nodos en grilla dentro de [0,40]x[0,30], los primeros n_gateways son 'G'."""
    nodes = []
    for i in range(n):
        x = 2.0 + (i % 8) * 4.5
        y = 2.0 + (i // 8) * 4.5
        role = "G" if i < n_gateways else "N"
        nodes.append({"id": i + 1, "role": role, "x": x, "y": y})
    return nodes


class BuildWorldExplicitConfigTests(unittest.TestCase):
    def test_tamanos_2_3_10_20(self):
        for n in (2, 3, 10, 20):
            n_gw = max(1, n // 4)
            nodes = grid_nodes(n, n_gw)
            sim = make_simulation(nodes)
            self.assertEqual(len(sim.nodes), n, f"n={n}")
            for spec in nodes:
                node = sim.nodes[spec["id"]]
                self.assertEqual(node.role, spec["role"])
                self.assertEqual(node.x, spec["x"])
                self.assertEqual(node.y, spec["y"])

    def test_posiciones_y_roles_exactos(self):
        nodes = [
            {"id": 1, "role": "G", "x": 7.0, "y": 27.0},
            {"id": 2, "role": "N", "x": 11.0, "y": 3.0},
        ]
        sim = make_simulation(nodes)
        self.assertEqual(sim.nodes[1].role, "G")
        self.assertEqual((sim.nodes[1].x, sim.nodes[1].y), (7.0, 27.0))
        self.assertEqual(sim.nodes[2].role, "N")
        self.assertEqual((sim.nodes[2].x, sim.nodes[2].y), (11.0, 3.0))

    def test_battery_inicial_explicita(self):
        nodes = [
            {"id": 1, "role": "G", "x": 1, "y": 1, "battery": 38.0},
            {"id": 2, "role": "N", "x": 2, "y": 2},
        ]
        sim = make_simulation(nodes)
        self.assertEqual(sim.nodes[1].battery, 38.0)
        self.assertEqual(sim.nodes[2].battery, 100.0)  # default de SimNode

    def test_evento_wander_se_aplica(self):
        nodes = [
            {"id": 1, "role": "G", "x": 1, "y": 1},
            {"id": 2, "role": "N", "x": 2, "y": 2},
        ]
        sim = make_simulation(nodes, events=[{"type": "wander", "node_id": 2, "until": 50.0}])
        self.assertIs(sim.wanderer, sim.nodes[2])
        self.assertEqual(sim.wander_until, 50.0)

    def test_random_fallback_sin_nodes_explicitos(self):
        cfg = dict(main_mod.DEFAULTS)
        cfg["n_nodes"] = 5
        cfg["n_gateways"] = 2
        sim = Simulation(
            escenario="aleatorio", cfg=cfg, DEFAULTS=main_mod.DEFAULTS, DT=main_mod.DT,
            N_PISOS=main_mod.N_PISOS, PISO_H=main_mod.PISO_H, STAIR_XY=main_mod.STAIR_XY,
            STAIR_HALF_W=main_mod.STAIR_HALF_W, ANCHO=main_mod.ANCHO, ALTO=main_mod.ALTO,
            C_RESC=main_mod.C_RESC, C_SURV=main_mod.C_SURV, C_SURV_OK=main_mod.C_SURV_OK,
            C_DEAD=main_mod.C_DEAD, C_OGM=main_mod.C_OGM, C_BCN=main_mod.C_BCN, C_HB=main_mod.C_HB,
        )
        self.assertEqual(len(sim.nodes), 5)
        self.assertEqual(sum(1 for n in sim.nodes.values() if n.role == "G"), 2)


class EngineBugFixRegressionTests(unittest.TestCase):
    """Regresión de los bugs de migración R/S -> G/N ya corregidos."""

    def test_register_found_solo_marca_nodos_rol_N(self):
        nodes = [
            {"id": 1, "role": "G", "x": 1, "y": 1},
            {"id": 2, "role": "N", "x": 2, "y": 2},
        ]
        sim = make_simulation(nodes)
        sim.register_found(2, 1)
        self.assertIn(2, sim.found_ids)

        sim2 = make_simulation(nodes)
        sim2.register_found(1, 2)  # 1 es 'G', no debe registrarse
        self.assertNotIn(1, sim2.found_ids)

    def test_gateway_drena_bateria_mas_rapido_que_nodo(self):
        nodes = [
            {"id": 1, "role": "G", "x": 1, "y": 1},
            {"id": 2, "role": "N", "x": 2, "y": 2},
        ]
        sim = make_simulation(nodes, medium={"battery_drain": 1.0, "battery_drain_surv": 0.1})
        for _ in range(5):
            sim.step()
        self.assertLess(sim.nodes[1].battery, sim.nodes[2].battery)

    def test_collides_point_no_explota_sin_escombros(self):
        nodes = [{"id": 1, "role": "G", "x": 1, "y": 1}]
        sim = make_simulation(nodes)
        self.assertFalse(sim.collides_point(20, 15))


class EscenariosMigradosRegressionTests(unittest.TestCase):
    """Corre los 5 escenarios migrados (parte 1.3) en modo headless (sin
    Visualizer/pygame) y verifica que el motor no explota y que cada
    escenario preserva el comportamiento que tenía en el repo madre."""

    def _load(self, name):
        path = os.path.join(main_mod.ESCENARIOS_DIR, f"{name}.json")
        scenario = load_scenario(path, default_building=dict(
            ancho=main_mod.ANCHO, alto=main_mod.ALTO,
            piso_h=main_mod.PISO_H, n_pisos=main_mod.N_PISOS))
        return make_simulation(
            scenario["nodes"], building=scenario["building"],
            medium=scenario.get("medium"), protocol=scenario.get("protocol"),
            events=scenario.get("events"), escenario=name,
        )

    def test_los_5_escenarios_corren_sin_excepciones(self):
        for name in main_mod.ESCENARIOS_DISPONIBLES:
            sim = self._load(name)
            n_inicial = len(sim.nodes)
            for _ in range(40):
                sim.step()
            self.assertEqual(len(sim.nodes), n_inicial, name)

    def test_particion_efectivamente_particiona(self):
        sim = self._load("particion")
        comps_vistos = set()
        for _ in range(40):
            sim.step()
            comps_vistos.add(sim.gateway_components())
        self.assertIn(2, comps_vistos, "particion debería partir la malla de gateways en algún punto")

    def test_colapso_progresivo_baterias_escalonadas(self):
        sim = self._load("colapso_progresivo")
        b = {nid: sim.nodes[nid].battery for nid in (1, 2, 3, 4)}
        self.assertGreater(b[1], b[2])
        self.assertGreater(b[2], b[3])
        self.assertGreater(b[3], b[4])

    def test_rescatista_perdido_configura_wanderer(self):
        sim = self._load("rescatista_perdido")
        self.assertIsNotNone(sim.wanderer)
        self.assertEqual(sim.wanderer.id, 4)
        self.assertEqual(sim.wander_until, 80.0)

    def test_base_y_denso_no_tienen_wanderer_ni_particion_forzada(self):
        for name in ("base", "denso"):
            sim = self._load(name)
            self.assertIsNone(sim.wanderer, name)


if __name__ == "__main__":
    unittest.main()
