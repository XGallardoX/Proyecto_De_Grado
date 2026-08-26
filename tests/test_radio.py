import math
import unittest

from sim.radio import RadioMedium


class _StubNode:
    def __init__(self, x, y, piso):
        self.x, self.y, self.piso = x, y, piso

    def dist_to(self, other):
        return math.hypot(self.x - other.x, self.y - other.y)


CFG = dict(rango_comm=16.0, falloff=0.85, perdida_base=0.02, floor_atten=0.55)


class RadioReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.medium = RadioMedium(sim=None, cfg=CFG)

    def test_distancia_cero_mismo_piso(self):
        a = _StubNode(0, 0, 1)
        b = _StubNode(0, 0, 1)
        rel = self.medium.reliability(a, b)
        self.assertAlmostEqual(rel, 1.0 - CFG["perdida_base"], places=6)

    def test_fuera_de_rango_es_cero(self):
        a = _StubNode(0, 0, 1)
        b = _StubNode(0, CFG["rango_comm"] + 1, 1)
        self.assertEqual(self.medium.reliability(a, b), 0.0)

    def test_en_el_borde_del_rango(self):
        a = _StubNode(0, 0, 1)
        b = _StubNode(0, CFG["rango_comm"], 1)
        rel = self.medium.reliability(a, b)
        esperado = max(0.0, 1.0 - CFG["falloff"] - CFG["perdida_base"])
        self.assertAlmostEqual(rel, esperado, places=6)

    def test_diferencia_de_piso_atenua(self):
        a = _StubNode(0, 0, 1)
        b_mismo_piso = _StubNode(5, 0, 1)
        b_otro_piso = _StubNode(5, 0, 2)
        rel_mismo = self.medium.reliability(a, b_mismo_piso)
        rel_otro = self.medium.reliability(a, b_otro_piso)
        self.assertAlmostEqual(rel_otro, rel_mismo * CFG["floor_atten"], places=6)
        self.assertLess(rel_otro, rel_mismo)

    def test_dos_pisos_de_diferencia_atenua_al_cuadrado(self):
        a = _StubNode(0, 0, 1)
        b1 = _StubNode(5, 0, 2)
        b2 = _StubNode(5, 0, 3)
        rel1 = self.medium.reliability(a, b1)
        rel2 = self.medium.reliability(a, b2)
        # b2 está 2 pisos más lejos que a -> atenuación al cuadrado
        # respecto a la fiabilidad sin atenuar por piso
        a_mismo_piso = _StubNode(5, 0, 1)
        rel_base = self.medium.reliability(a, a_mismo_piso)
        self.assertAlmostEqual(rel2, rel_base * CFG["floor_atten"] ** 2, places=6)

    def test_resultado_siempre_acotado_0_1(self):
        cfg_extremo = dict(rango_comm=16.0, falloff=5.0, perdida_base=2.0, floor_atten=0.55)
        medium = RadioMedium(sim=None, cfg=cfg_extremo)
        a = _StubNode(0, 0, 1)
        b = _StubNode(1, 0, 1)
        self.assertEqual(medium.reliability(a, b), 0.0)


if __name__ == "__main__":
    unittest.main()
