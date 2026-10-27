"""Movilidad descentralizada de los Gateway (paso 9 de
contexto/PLAN_SIGUIENTE.md): cada Gateway decide con lo que oyó en los
beacons de sus vecinos (SimNode.oidos), nunca con sim.nodes."""
import math
import unittest

import main as main_mod
from test_engine import make_simulation

R = main_mod.DEFAULTS["rango_comm"]     # 16 m


def _sim(nodes, **protocol):
    return make_simulation(nodes, protocol={"movilidad": "descentralizada",
                                            **protocol})


def _oir(nodo, otro, t=0.0):
    """`nodo` oyó un beacon de `otro` en el instante t."""
    nodo.oidos[otro.id] = (otro.x, otro.y, otro.role, t)


class BeaconsTests(unittest.TestCase):
    def test_el_beacon_lleva_la_posicion_y_el_receptor_la_guarda(self):
        sim = _sim([{"id": 1, "role": "G", "x": 5, "y": 5},
                    {"id": 2, "role": "N", "x": 9, "y": 5}],
                   move_speed=0)
        g, n = sim.nodes[1], sim.nodes[2]
        bcn = n._make_bcn("hola")
        self.assertEqual((bcn["x"], bcn["y"]), (9.0, 5.0))
        g._inbox.append((bcn, n.ip))
        g._drain_inbox(3.0)
        self.assertEqual(g.oidos[2], (9.0, 5.0, "N", 3.0))


class FuerzaTests(unittest.TestCase):
    def test_sin_oir_nada_no_se_mueve(self):
        # el usuario está ahí, pero el Gateway no lo oyó: no lo sabe
        sim = _sim([{"id": 1, "role": "G", "x": 5, "y": 5},
                    {"id": 2, "role": "N", "x": 12, "y": 5}])
        g = sim.nodes[1]
        fx, fy, _ = g.fuerza_descentralizada(0.0)
        self.assertEqual((fx, fy), (0.0, 0.0))
        g.move(0.0)
        self.assertEqual((g.x, g.y), (5.0, 5.0))

    def test_atrae_al_usuario_lejano_a_su_cargo(self):
        sim = _sim([{"id": 1, "role": "G", "x": 5, "y": 5},
                    {"id": 2, "role": "N", "x": 18, "y": 5}])
        g = sim.nodes[1]
        _oir(g, sim.nodes[2])
        fx, fy, motivo = g.fuerza_descentralizada(0.0)
        self.assertAlmostEqual(fx, 13 - 0.4 * R)
        self.assertAlmostEqual(fy, 0.0)
        self.assertEqual(motivo, "cobertura")

    def test_un_usuario_cercano_no_atrae(self):
        sim = _sim([{"id": 1, "role": "G", "x": 5, "y": 5},
                    {"id": 2, "role": "N", "x": 8, "y": 5}])
        g = sim.nodes[1]
        _oir(g, sim.nodes[2])
        self.assertEqual(g.fuerza_descentralizada(0.0)[:2], (0.0, 0.0))

    def test_el_usuario_de_otro_gateway_mas_cercano_no_atrae(self):
        # G2 está más cerca del usuario: G1 no lo tiene a su cargo, y como
        # queda ocioso se aleja de G2 (expansión)
        sim = _sim([{"id": 1, "role": "G", "x": 5, "y": 5},
                    {"id": 2, "role": "G", "x": 12, "y": 5},
                    {"id": 3, "role": "N", "x": 20, "y": 5}])
        g1 = sim.nodes[1]
        _oir(g1, sim.nodes[2])
        _oir(g1, sim.nodes[3])
        fx, fy, motivo = g1.fuerza_descentralizada(0.0)
        self.assertEqual(motivo, "expansion")
        self.assertAlmostEqual(fx, -(0.75 * R - 7))
        self.assertAlmostEqual(fy, 0.0)

    def test_apilados_se_separan_en_direcciones_opuestas(self):
        sim = _sim([{"id": 1, "role": "G", "x": 10, "y": 5},
                    {"id": 2, "role": "G", "x": 10, "y": 5}])
        g1, g2 = sim.nodes[1], sim.nodes[2]
        _oir(g1, g2)
        _oir(g2, g1)
        f1, f2 = g1.fuerza_descentralizada(0.0), g2.fuerza_descentralizada(0.0)
        self.assertGreater(f1[0], 0)
        self.assertLess(f2[0], 0)

    def test_olvida_a_los_vecinos_que_no_oye_hace_rato(self):
        sim = _sim([{"id": 1, "role": "G", "x": 5, "y": 5},
                    {"id": 2, "role": "N", "x": 18, "y": 5}])
        g = sim.nodes[1]
        _oir(g, sim.nodes[2], t=0.0)
        memoria = g.MEMORIA_BEACONS * sim.cfg["beacon_cada"]
        self.assertNotEqual(g.fuerza_descentralizada(memoria)[:2], (0.0, 0.0))
        self.assertEqual(g.fuerza_descentralizada(memoria + 0.5)[:2], (0.0, 0.0))

    def test_sin_gateways_oidos_vuelve_al_ultimo_conocido(self):
        sim = _sim([{"id": 1, "role": "G", "x": 5, "y": 5},
                    {"id": 2, "role": "G", "x": 30, "y": 5}])
        g = sim.nodes[1]
        _oir(g, sim.nodes[2], t=0.0)
        fx, fy, motivo = g.fuerza_descentralizada(100.0)
        self.assertEqual(motivo, "reconexion")
        self.assertEqual((fx, fy), (25.0, 0.0))


class EnlaceTests(unittest.TestCase):
    def _g(self, otros):
        nodes = [{"id": 1, "role": "G", "x": 10, "y": 5}] + otros
        sim = _sim(nodes)
        g = sim.nodes[1]
        for n in sim.nodes.values():
            if n is not g:
                _oir(g, n, t=0.0)
        return g

    def test_no_rompe_su_unico_enlace(self):
        g = self._g([{"id": 2, "role": "G", "x": 20, "y": 5}])
        lejos = 20 - 0.9 * R - 1          # queda fuera de D_ENLACE de G2
        self.assertFalse(g._conserva_enlace(0.0, lejos, 5))
        self.assertTrue(g._conserva_enlace(0.0, 11, 5))

    def test_rompe_un_enlace_si_queda_un_rodeo(self):
        # G3 sigue enlazado con G1 (en su nueva posición) y con G2
        g = self._g([{"id": 2, "role": "G", "x": 20, "y": 5},
                     {"id": 3, "role": "G", "x": 10, "y": 9}])
        self.assertTrue(g._conserva_enlace(0.0, 4, 5))

    def test_un_vecino_oido_hace_rato_cuenta_con_incertidumbre(self):
        # oído hace 4 s: pudo moverse 4 · 0.64 m; el paso que parecía
        # seguro con la posición vieja ya no lo es en el peor caso
        g = self._g([{"id": 2, "role": "G", "x": 20, "y": 5}])
        borde = 20 - 0.9 * R + 0.5
        self.assertTrue(g._conserva_enlace(0.0, borde, 5))
        self.assertFalse(g._conserva_enlace(4.0, borde, 5))


class IntegracionTests(unittest.TestCase):
    def _correr(self, nombre, movilidad, segundos=150, semilla=1):
        main_mod.fijar_semilla(semilla)
        sim, _ = main_mod.construir_simulacion(main_mod.ruta_escenario(nombre),
                                               movilidad=movilidad)
        main_mod.correr(sim, segundos)
        return sim

    def _min_dist_gateways(self, sim):
        gws = [n for n in sim.nodes.values() if n.role == "G" and n.alive]
        return min(math.hypot(a.x - b.x, a.y - b.y)
                   for i, a in enumerate(gws) for b in gws[i + 1:])

    def test_denso_no_se_apilan_y_la_malla_sigue_unida(self):
        desc = self._correr("denso", "descentralizada")
        seguir = self._correr("denso", "seguir")
        self.assertLess(self._min_dist_gateways(seguir), 1.0)    # apilados
        self.assertGreater(self._min_dist_gateways(desc), 3.0)
        self.assertEqual(desc.gateway_components(), 1)

    def test_base_descubre_a_los_usuarios(self):
        # los Gateway arrancan juntos sin oír a nadie: la expansión los
        # lleva hasta los Nodos de usuario sin partir la malla
        sim = self._correr("base", "descentralizada", segundos=200)
        self.assertEqual(sim.recorder.comp_G.count(2), 0)
        self.assertGreaterEqual(sim.recorder.node_reach[-1], 2)


if __name__ == "__main__":
    unittest.main()
