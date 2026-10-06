"""D1 (contexto/PLAN_SIGUIENTE.md): el TQ de BatmanRouter es la fracción
de OGM recibidos de las últimas secuencias de cada vecino. Antes la ventana
sólo recibía unos y el TQ valía siempre 1.0."""
import unittest

from mesh.router import BatmanRouter

A, B = "10.0.0.2", "10.0.0.3"     # IP de dos vecinos


def ogm(seq, origen=9, tq=1.0, path=None):
    return {"type": "OGM", "origin_id": origen, "seq": seq, "ttl": 5,
            "tq": tq, "path": path or [origen]}


class VentanaTqTests(unittest.TestCase):
    def setUp(self):
        self.r = BatmanRouter(1)

    def test_enlace_sin_perdidas_sigue_en_1(self):
        for seq in range(1, 30):
            self.r.receive_ogm(ogm(seq), A, float(seq))
        self.assertEqual(self.r.routes[9].tq, 1.0)
        self.assertEqual(self.r.link_quality(A), 1.0)

    def test_ogm_salteados_bajan_el_tq(self):
        for seq in (1, 2, 5):          # se perdieron la 3 y la 4
            self.r.receive_ogm(ogm(seq), A, float(seq))
        self.assertAlmostEqual(self.r.routes[9].tq, 3 / 5)
        self.assertAlmostEqual(self.r.link_quality(A), 3 / 5)

    def test_la_ventana_tiene_tope(self):
        self.r.receive_ogm(ogm(1), A, 1.0)
        self.r.receive_ogm(ogm(100), A, 2.0)
        # 16 lugares: a lo sumo 15 ceros y el 1 de la secuencia 100
        self.assertAlmostEqual(self.r.routes[9].tq, 1 / 16)

    def test_duplicados_y_viejos_no_tocan_la_ventana(self):
        for seq in (1, 3):
            self.r.receive_ogm(ogm(seq), A, float(seq))
        self.assertFalse(self.r.receive_ogm(ogm(3), A, 4.0))   # duplicado
        self.assertFalse(self.r.receive_ogm(ogm(2), A, 5.0))   # viejo
        self.assertEqual(list(self.r._windows[(9, A)]), [1, 0, 1])

    def test_el_tq_acumulado_multiplica_el_del_ogm(self):
        for seq in (1, 3):
            self.r.receive_ogm(ogm(seq, tq=0.5), A, float(seq))
        self.assertAlmostEqual(self.r.routes[9].tq, 0.5 * 2 / 3)

    def test_se_reenvia_solo_la_primera_copia(self):
        self.assertTrue(self.r.receive_ogm(ogm(1), A, 1.0))
        self.assertFalse(self.r.receive_ogm(ogm(1), B, 1.0))


class EleccionDeRutaTests(unittest.TestCase):
    def setUp(self):
        self.r = BatmanRouter(1)

    def test_gana_el_vecino_de_mejor_tq_aunque_llegue_segundo(self):
        # por A se pierde una de cada dos; por B, ninguna. La copia de A
        # llega siempre primero.
        for seq in range(1, 21):
            if seq % 2:
                self.r.receive_ogm(ogm(seq), A, float(seq))
            self.r.receive_ogm(ogm(seq), B, float(seq))
        ruta = self.r.routes[9]
        self.assertEqual(ruta.via_ip, B)
        self.assertEqual(ruta.tq, 1.0)
        self.assertEqual(ruta.seq, 20)

    def test_el_vecino_actual_refresca_su_ruta_aunque_baje_el_tq(self):
        for seq in (1, 2, 4):
            self.r.receive_ogm(ogm(seq), A, float(seq))
        ruta = self.r.routes[9]
        self.assertEqual((ruta.via_ip, ruta.seq, ruta.last_seen), (A, 4, 4.0))

    def test_otro_vecino_peor_no_reemplaza_a_uno_mejor(self):
        self.r.receive_ogm(ogm(1), A, 1.0)
        self.r.receive_ogm(ogm(2, tq=0.5), B, 2.0)
        self.r.receive_ogm(ogm(2), A, 2.0)
        self.assertEqual(self.r.routes[9].via_ip, A)

    def test_una_copia_por_un_vecino_peor_mantiene_vigente_la_ruta(self):
        self.r.receive_ogm(ogm(1), A, 1.0)
        self.r.receive_ogm(ogm(2, tq=0.5), B, 5.0)   # la de A se perdió
        ruta = self.r.routes[9]
        self.assertEqual((ruta.via_ip, ruta.last_seen), (A, 5.0))

    def test_si_el_vecino_actual_desaparece_la_ruta_pasa_a_otro(self):
        for seq in range(1, 6):
            self.r.receive_ogm(ogm(seq), A, float(seq))
            self.r.receive_ogm(ogm(seq, tq=0.6), B, float(seq))
        self.assertEqual(self.r.routes[9].via_ip, A)
        # A deja de entregar; B sigue, con TQ 0.6
        for seq in range(6, 20):
            self.r.receive_ogm(ogm(seq, tq=0.6), B, float(seq))
        ruta = self.r.routes[9]
        self.assertEqual((ruta.via_ip, ruta.seq), (B, 19))


if __name__ == "__main__":
    unittest.main()
