"""Fase 3, parte 1 (contexto/DECISIONES_FASE3.md): recuperar un nodo sin
reiniciar su secuencia de OGM (1b), tiempo de reconvergencia de rutas
(1a) y eventos de caída y recuperación programables en el escenario (1c)."""
import unittest

import main as main_mod
from analysis.metrics import resumen_corrida, ruta_vigente


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


class RutaVigenteTests(unittest.TestCase):
    """1a: el criterio de ruta vigente usa el last_seen de la ruta, no el
    del vecino."""

    def setUp(self):
        self.sim = _sim()
        _hasta(self.sim, 30)
        self.g1 = self.sim.nodes[1]

    def test_ruta_reciente_es_vigente(self):
        self.assertTrue(ruta_vigente(self.sim, self.g1, 2))

    def test_sin_ruta_no_es_vigente(self):
        self.assertFalse(ruta_vigente(self.sim, self.g1, 999))

    def test_ruta_vieja_no_es_vigente_aunque_el_vecino_se_oiga(self):
        ruta = self.g1.router.routes[2]
        ruta.last_seen = self.sim.t - self.sim.cfg["timeout"] - 1
        self.g1.router.peers[2].last_seen = self.sim.t   # un beacon reciente
        self.assertFalse(ruta_vigente(self.sim, self.g1, 2))

    def test_las_alertas_no_cuentan(self):
        # in_alert se contagia por los OGM de terceros: no decide si la
        # ruta está vigente (ver el docstring de ruta_vigente)
        self.g1.router.mark_alert(2)
        self.assertTrue(ruta_vigente(self.sim, self.g1, 2))

    def test_reconvergencia_se_cierra_con_la_malla_densa_y_repartida(self):
        # Con el criterio que miraba las alertas, ningún episodio de
        # `denso` con `repartir` se cerraba en 200 s.
        sim = _sim("denso", static=False, movilidad="repartir")
        _hasta(sim, 200)
        cerrados = [e for e in sim.recorder.reconv_rutas if e[1] is not None]
        self.assertTrue(cerrados)


class ReconvergenciaRutasTests(unittest.TestCase):
    """1a: tiempo_reconvergencia_rutas_s."""

    def _caida_y_vuelta(self, caida, vuelta, fin):
        sim = _sim()
        _hasta(sim, caida)
        sim.fail_node(2)
        _hasta(sim, vuelta)
        sim.recover_node(2)
        _hasta(sim, fin)
        return sim

    def test_sin_recuperaciones_ni_reunificaciones_no_aplica(self):
        sim = _sim()
        _hasta(sim, 60)
        self.assertEqual(sim.recorder.reconv_rutas, [])
        self.assertIsNone(resumen_corrida(sim)["tiempo_reconvergencia_rutas_s"])

    def test_recuperar_un_gateway_abre_y_cierra_un_episodio(self):
        sim = self._caida_y_vuelta(60, 90, 150)
        [(inicio, fin, causa)] = sim.recorder.reconv_rutas
        self.assertEqual((inicio, causa), (90.0, "RECOVER G2"))
        self.assertIsNotNone(fin)
        duracion = fin - inicio
        # del orden del intervalo de OGM, no del tiempo que estuvo vivo
        # antes de caer (60 s) como pasaba con la secuencia reiniciada
        self.assertGreater(duracion, 0)
        self.assertLessEqual(duracion, 3 * sim.cfg["batman_cada"])
        self.assertEqual(resumen_corrida(sim)["tiempo_reconvergencia_rutas_s"],
                         duracion)

    def test_caida_mas_corta_que_el_timeout_converge_al_instante(self):
        # Las rutas hacia G2 nunca llegaron a vencer: para BATMAN no hay
        # nada que reconverger. El episodio dura una muestra.
        sim = self._caida_y_vuelta(60, 70, 100)
        [(inicio, fin, _)] = sim.recorder.reconv_rutas
        self.assertEqual(fin - inicio, sim.DT)

    def test_recuperar_un_nodo_de_usuario_no_abre_episodio(self):
        sim = _sim()
        _hasta(sim, 30)
        sim.fail_node(101)
        _hasta(sim, 70)
        sim.recover_node(101)
        _hasta(sim, 80)
        self.assertEqual(sim.recorder.reconv_rutas, [])

    def test_una_reunificacion_abre_un_episodio(self):
        # Dos Gateway fuera de alcance; al acercar uno, la malla se
        # reunifica (HEAL) y las rutas entre los dos tardan en aparecer.
        sim = _sim("particion")
        _hasta(sim, 10)
        self.assertGreater(sim.gateway_components(), 1)
        destino = next(n for n in sim.nodes.values() if n.role == "G")
        for n in [n for n in sim.nodes.values() if n.role == "G"]:
            sim.mover_nodo(n.id, destino.x, destino.y)
        _hasta(sim, 60)
        heals = [e for e in sim.recorder.events if e[1] == "HEAL"]
        self.assertTrue(heals)
        causas = [c for _, _, c in sim.recorder.reconv_rutas]
        self.assertIn("HEAL", causas)
        self.assertTrue(all(fin is not None
                            for _, fin, _ in sim.recorder.reconv_rutas))

    def test_episodio_abierto_al_final_no_cuenta(self):
        sim = _sim()
        _hasta(sim, 60)
        sim.fail_node(2)
        _hasta(sim, 95)
        sim.recover_node(2)
        sim.step()      # una sola muestra: todavía no llegó ningún OGM
        [(_, fin, _)] = sim.recorder.reconv_rutas
        self.assertIsNone(fin)
        self.assertIsNone(resumen_corrida(sim)["tiempo_reconvergencia_rutas_s"])


if __name__ == "__main__":
    unittest.main()
