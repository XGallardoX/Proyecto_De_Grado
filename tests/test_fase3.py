"""Fase 3, parte 1 (contexto/DECISIONES_FASE3.md): recuperar un nodo sin
reiniciar su secuencia de OGM (1b), tiempo de reconvergencia de rutas
(1a) y eventos de caída y recuperación programables en el escenario (1c)."""
import json
import os
import tempfile
import unittest

import main as main_mod
from sim.config_loader import load_scenario, validar_escenario
from analysis.metrics import resumen_corrida, ruta_vigente


def _sim(nombre="base", semilla=1, static=True, **kw):
    main_mod.fijar_semilla(semilla)
    return main_mod.construir_simulacion(main_mod.ruta_escenario(nombre),
                                         static=static, **kw)[0]


def _hasta(sim, t):
    while sim.t < t:
        sim.step()


def _escenario_con_eventos(eventos, nombre="base", ext=".json"):
    """Escribe en un archivo temporal el escenario predefinido `nombre`
    con `eventos` agregados. Devuelve la ruta (el llamador la borra)."""
    with open(main_mod.ruta_escenario(nombre), encoding="utf-8") as f:
        datos = json.load(f)
    datos["events"] = list(datos.get("events", [])) + eventos
    fd, ruta = tempfile.mkstemp(suffix=ext)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(datos, f)
    return ruta


def _series(sim):
    rec = sim.recorder
    return {k: list(getattr(rec, k)) for k in (
        "t", "alive_G", "alive_N", "comp_G", "node_reach", "avg_tq",
        "avg_hops", "max_silence", "deliver_ratio", "alerts_active",
        "bandwidth")}


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

    def test_volver_de_un_puente_es_un_solo_episodio(self):
        # RECOVER de G2 y, medio paso después, el HEAL que provoca: un
        # solo episodio, medido desde el RECOVER.
        main_mod.fijar_semilla(1)
        sim, _ = main_mod.construir_simulacion(
            os.path.join(main_mod.ESCENARIOS_DIR, "casos", "puente.txt"))
        _hasta(sim, 160)
        tipos = [tipo for _, tipo, _ in sim.recorder.events]
        self.assertIn("HEAL", tipos)
        [(inicio, fin, causa)] = sim.recorder.reconv_rutas
        self.assertEqual((inicio, causa), (100.0, "RECOVER G2"))
        self.assertIsNotNone(fin)

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


class CriterioWebTests(unittest.TestCase):
    """La tabla de rutas y la matriz de la interfaz usan ruta_vigente: una
    ruta que ningún OGM refrescó sale obsoleta aunque el vecino se oiga
    por beacons (el caso de la revisión del 3 de octubre)."""

    def test_tabla_y_matriz_marcan_la_ruta_vieja(self):
        from web import estado
        sim = _sim()
        _hasta(sim, 30)
        g1 = sim.nodes[1]
        g1.router.routes[2].last_seen = sim.t - sim.cfg["timeout"] - 1
        g1.router.peers[2].last_seen = sim.t
        detalle = estado.nodo_detalle(sim, 1)
        [ruta] = [r for r in detalle["rutas"] if r["destino"] == 2]
        self.assertTrue(ruta["obsoleta"])
        matriz = estado.matriz_conocimiento(sim)
        col = [n["id"] for n in matriz["nodos"]].index(2)
        [fila] = [f for f in matriz["filas"] if f["id"] == 1]
        self.assertEqual(fila["celdas"][col]["estado"], "obsoleta")


class EventosEnElCargadorTests(unittest.TestCase):
    """1c: validación de los eventos fail/recover."""

    def _validar(self, eventos, **extra):
        datos = {"nodes": [{"id": 1, "role": "G", "x": 5, "y": 5},
                           {"id": 2, "role": "N", "x": 9, "y": 5}],
                 "events": eventos}
        datos.update(extra)
        return validar_escenario(datos, "prueba")

    def test_fail_y_recover_validos(self):
        datos = self._validar([{"type": "fail", "node_id": 1, "t": 60},
                               {"type": "recover", "node_id": 1, "t": 90.5}])
        self.assertEqual([e["type"] for e in datos["events"]],
                         ["fail", "recover"])

    def test_errores(self):
        casos = [
            ([{"type": "fail", "node_id": 1}], "instante 't'"),
            ([{"type": "fail", "node_id": 1, "t": "60"}], "instante 't'"),
            ([{"type": "recover", "node_id": 1, "t": -1}], "debe ser >= 0"),
            ([{"type": "fail", "node_id": 7, "t": 1}], "no existe"),
            ([{"type": "explotar", "node_id": 1, "t": 1}],
             "válidos: wander, fail, recover"),
        ]
        for eventos, mensaje in casos:
            with self.subTest(eventos=eventos):
                with self.assertRaises(ValueError) as cm:
                    self._validar(eventos)
                self.assertIn(mensaje, str(cm.exception))

    def test_modo_random_no_admite_fail(self):
        with self.assertRaises(ValueError) as cm:
            validar_escenario({"random": {"n_nodes": 4, "n_gateways": 1},
                               "events": [{"type": "fail", "node_id": 1,
                                           "t": 5}]}, "prueba")
        self.assertIn("nodos explícitos", str(cm.exception))

    def test_formato_txt(self):
        fd, ruta = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("name: t\n[nodes]\n1 G 5 5\n2 G 9 5\n"
                    "[events]\nwander 2 40\nfail 1 60\nrecover 1 90\n")
        try:
            datos = load_scenario(ruta)
        finally:
            os.remove(ruta)
        self.assertEqual(datos["events"], [
            {"type": "wander", "node_id": 2, "until": 40.0},
            {"type": "fail", "node_id": 1, "t": 60.0},
            {"type": "recover", "node_id": 1, "t": 90.0}])


class EventosEnElMotorTests(unittest.TestCase):
    """1c: el motor aplica los eventos en el mismo punto del ciclo que la
    interfaz web aplica una intervención."""

    def _correr(self, eventos, fin=150, static=True):
        ruta = _escenario_con_eventos(eventos)
        try:
            main_mod.fijar_semilla(1)
            sim, _ = main_mod.construir_simulacion(ruta, static=static)
        finally:
            os.remove(ruta)
        _hasta(sim, fin)
        return sim

    def test_aplica_la_caida_y_la_vuelta_en_su_instante(self):
        sim = self._correr([{"type": "fail", "node_id": 2, "t": 60},
                            {"type": "recover", "node_id": 2, "t": 90}])
        eventos = [(t, tipo, txt) for t, tipo, txt in sim.recorder.events
                   if tipo in ("FAIL", "RECOVER")]
        self.assertEqual(eventos, [(60.0, "FAIL", "G2 caído (programado)"),
                                   (90.0, "RECOVER",
                                    "G2 recuperado (programado)")])
        self.assertTrue(sim.nodes[2].alive)
        self.assertIsNotNone(
            resumen_corrida(sim)["tiempo_reconvergencia_rutas_s"])

    def test_igual_que_hacerlo_a_mano_entre_pasos(self):
        for static in (True, False):
            with self.subTest(static=static):
                programada = self._correr(
                    [{"type": "fail", "node_id": 2, "t": 60},
                     {"type": "recover", "node_id": 2, "t": 90}],
                    static=static)
                main_mod.fijar_semilla(1)
                manual = _sim(static=static)
                _hasta(manual, 60)
                manual.fail_node(2)
                _hasta(manual, 90)
                manual.recover_node(2)
                _hasta(manual, 150)
                self.assertEqual(_series(programada), _series(manual))
                self.assertEqual(resumen_corrida(programada),
                                 resumen_corrida(manual))

    def test_instante_entre_dos_pasos_se_aplica_en_el_siguiente(self):
        sim = self._correr([{"type": "fail", "node_id": 2, "t": 60.2}],
                           fin=70)
        [t] = [t for t, tipo, _ in sim.recorder.events if tipo == "FAIL"]
        self.assertEqual(t, 60.5)

    def test_reiniciar_vuelve_a_programarlos(self):
        sim = self._correr([{"type": "fail", "node_id": 2, "t": 10}], fin=20)
        sim._build_world()
        _hasta(sim, 20)
        fallas = [e for e in sim.recorder.events if e[1] == "FAIL"]
        self.assertEqual(len(fallas), 1)

    def test_sin_eventos_programados_nada_cambia(self):
        main_mod.fijar_semilla(1)
        a = _sim()
        _hasta(a, 80)
        b = self._correr([], fin=80)
        self.assertEqual(_series(a), _series(b))


class ExportarSesionComoEscenarioTests(unittest.TestCase):
    """1c en la web: una sesión cuyas únicas intervenciones son caer y
    recuperar se exporta como escenario, y su comando de terminal
    reproduce la misma corrida."""

    def setUp(self):
        from web.sesion import construir_sesion
        self.construir_sesion = construir_sesion
        self.carpetas = []

    def tearDown(self):
        import shutil
        for c in self.carpetas:
            shutil.rmtree(c, ignore_errors=True)

    def _exportar(self, sesion):
        carpeta = sesion.exportar()
        self.carpetas.append(carpeta)
        return carpeta, sesion.ultima_exportacion

    def test_paridad_con_la_terminal(self):
        for static in (False, True):
            with self.subTest(static=static):
                sesion = self.construir_sesion(main_mod.ruta_escenario("base"),
                                               semilla=7, static=static)
                sesion.avanzar_sincrono(120)            # t = 60
                sesion.comando("caer", {"id": 2})
                sesion.avanzar_sincrono(60)             # t = 90
                sesion.comando("recuperar", {"id": 2})
                sesion.avanzar_sincrono(120)            # t = 150
                carpeta, export = self._exportar(sesion)

                self.assertEqual(export["escenario_sesion"],
                                 "escenario_sesion.json")
                comando = export["comando_equivalente"]
                self.assertIn("--config", comando)
                self.assertIn("escenario_sesion.json", comando)
                self.assertIn("--seed 7", comando)
                self.assertIn("--duracion 150.0", comando)
                self.assertEqual("--static" in comando, static)

                ruta = os.path.join(carpeta, "escenario_sesion.json")
                with open(ruta, encoding="utf-8") as f:
                    eventos = json.load(f)["events"]
                self.assertEqual(eventos, [
                    {"type": "fail", "node_id": 2, "t": 60.0},
                    {"type": "recover", "node_id": 2, "t": 90.0}])

                # lo mismo que hace --headless con ese comando
                main_mod.fijar_semilla(7)
                sim, _ = main_mod.construir_simulacion(ruta, static=static)
                main_mod.correr(sim, 150.0)
                self.assertEqual(_series(sim), _series(sesion.sim))
                self.assertEqual(resumen_corrida(sim),
                                 resumen_corrida(sesion.sim))

    def test_otras_intervenciones_no_se_exportan(self):
        sesion = self.construir_sesion(main_mod.ruta_escenario("base"),
                                       semilla=7, static=True)
        sesion.avanzar_sincrono(10)
        sesion.comando("caer", {"id": 2})
        sesion.comando("mover_nodo", {"id": 1, "x": 10, "y": 20})
        sesion.avanzar_sincrono(10)
        self.assertIsNone(sesion.escenario_de_sesion())
        _, export = self._exportar(sesion)
        self.assertIsNone(export["escenario_sesion"])
        self.assertIsNone(export["comando_equivalente"])

    def test_modo_aleatorio_no_se_exporta(self):
        sesion = self.construir_sesion(None, n_nodes=5, n_gateways=2,
                                       semilla=7)
        sesion.avanzar_sincrono(10)
        sesion.comando("caer", {"id": 1})
        self.assertIsNone(sesion.escenario_de_sesion())

    def test_sin_intervenciones_sigue_el_comando_de_siempre(self):
        sesion = self.construir_sesion(main_mod.ruta_escenario("base"),
                                       semilla=7)
        sesion.avanzar_sincrono(10)
        _, export = self._exportar(sesion)
        self.assertIsNone(export["escenario_sesion"])
        self.assertIn("--escenario base", export["comando_equivalente"])


if __name__ == "__main__":
    unittest.main()
