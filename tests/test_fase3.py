"""Fase 3, parte 1 (contexto/DECISIONES_FASE3.md): recuperar un nodo sin
reiniciar su secuencia de OGM (1b), tiempo de reconvergencia de rutas
(1a) y eventos de caída y recuperación programables en el escenario (1c)."""
import unittest

import main as main_mod


def _sim(nombre="base", semilla=1, static=True, **kw):
    main_mod.fijar_semilla(semilla)
    return main_mod.construir_simulacion(main_mod.ruta_escenario(nombre),
                                         static=static, **kw)[0]


def _hasta(sim, t):
    while sim.t < t:
        sim.step()


class RecuperarConservaSecuenciaTests(unittest.TestCase):
    """1b: al recuperar un nodo, los demás vuelven a aceptar sus OGM en el
    siguiente ciclo, en vez de esperar a que su secuencia supere la de
    antes de caer."""

    def test_la_secuencia_no_vuelve_a_cero(self):
        sim = _sim()
        _hasta(sim, 60)
        g2 = sim.nodes[2]
        seq_al_caer = g2._ogm_seq
        self.assertGreater(seq_al_caer, 0)
        sim.fail_node(2)
        _hasta(sim, 90)
        sim.recover_node(2)
        self.assertEqual(g2._ogm_seq, seq_al_caer)

    def test_las_rutas_hacia_el_recuperado_se_refrescan_en_un_ciclo(self):
        # El caso medido en la revisión del 3 de octubre: G2 cae a los
        # 60 s y vuelve a los 90 s. Con la secuencia reiniciada, las rutas
        # de G1, G3 y G4 hacia G2 seguían sin refrescarse hasta t ~ 150 s.
        sim = _sim()
        _hasta(sim, 60)
        sim.fail_node(2)
        _hasta(sim, 90)
        sim.recover_node(2)
        _hasta(sim, 90 + sim.cfg["batman_cada"] + 1.0)
        for gid in (1, 3, 4):
            ruta = sim.nodes[gid].router.routes[2]
            self.assertLessEqual(sim.t - ruta.last_seen,
                                 sim.cfg["batman_cada"] + 1.0,
                                 f"G{gid} no refrescó su ruta hacia G2")


if __name__ == "__main__":
    unittest.main()
