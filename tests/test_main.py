"""Pruebas de main.py sin ventana (construir_simulacion, --seed,
--headless, --inspect) y del resumen por corrida de analysis/metrics.py."""
import contextlib
import io
import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace

import main as main_mod
from analysis.metrics import (METRICAS_CORRIDA, episodios_particion,
                              resumen_corrida)

ARCHIVOS_DE_UNA_CORRIDA = ["analisis_red.png", "reporte.csv",
                           "reporte.json", "reporte.txt"]


def silencioso(f, *args, **kwargs):
    """Llama a f sin ensuciar la salida del test; devuelve (resultado, stdout)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        resultado = f(*args, **kwargs)
    return resultado, out.getvalue()


@contextlib.contextmanager
def en_directorio_temporal():
    """reportes/ se crea relativo al directorio actual: aislarlo."""
    cwd = os.getcwd()
    tmp = tempfile.mkdtemp()
    os.chdir(tmp)
    try:
        yield tmp
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp)


def escenario(nombre, static=False):
    return main_mod.construir_simulacion(main_mod.ruta_escenario(nombre),
                                         static=static)[0]


class EpisodiosParticionTests(unittest.TestCase):
    def test_sin_particiones(self):
        self.assertEqual(episodios_particion([0.5, 1.0, 1.5], [1, 1, 1]), [])

    def test_episodio_que_se_cierra(self):
        t = [0.5, 1.0, 1.5, 2.0, 2.5]
        self.assertEqual(episodios_particion(t, [1, 2, 3, 1, 1]), [(1.0, 2.0)])

    def test_episodio_abierto_al_final(self):
        self.assertEqual(episodios_particion([0.5, 1.0, 1.5], [2, 2, 2]),
                         [(0.5, None)])

    def test_quedarse_sin_gateways_no_cuenta_como_reunificacion(self):
        self.assertEqual(episodios_particion([0.5, 1.0, 1.5], [1, 2, 0]),
                         [(1.0, None)])

    def test_varios_episodios(self):
        t = [1, 2, 3, 4, 5, 6, 7]
        comps = [2, 1, 1, 3, 2, 1, 2]
        self.assertEqual(episodios_particion(t, comps),
                         [(1, 2), (4, 6), (7, None)])


class ResumenCorridaTests(unittest.TestCase):
    def _sim(self, t, delivered=3, attempted=4, **series):
        rec = SimpleNamespace(t=t, events=series.pop("events", []), **series)
        medio = SimpleNamespace(delivered=delivered, attempted=attempted)
        return SimpleNamespace(recorder=rec, medium=medio, DT=0.5)

    def test_valores_derivados_de_la_serie_y_los_eventos(self):
        sim = self._sim(
            t=[0.5, 1.0, 1.5, 2.0],
            avg_tq=[0.0, 1.0, 1.0, 1.0], avg_hops=[0, 1, 2, 1],
            comp_G=[1, 2, 1, 2], node_reach=[0, 1, 2, 3],
            alive_G=[4, 4, 3, 3],
            events=[(1.0, "ALERT_ON", "G1 no oye a G4"),
                    (1.5, "FAIL", "G4 sin batería"),
                    (2.0, "ALERT_ON", "G2 no oye a G4")])
        r = resumen_corrida(sim)
        self.assertEqual(r, {
            "tq_medio": 0.75, "saltos_medio": 1.0, "tasa_entrega": 0.75,
            "componentes_finales": 2, "nodos_alcanzables_finales": 3,
            "gateways_vivos_finales": 3, "particiones": 2,
            "tiempo_particionado_s": 1.0,      # 2 muestras partidas x 0.5 s
            "tiempo_reconvergencia_s": 0.5,    # sólo se cerró 1.0 -> 1.5
            "alertas_gateway": 2, "t_primera_alerta_s": 1.0,
        })

    def test_sin_datos_las_metricas_no_aplican(self):
        sim = self._sim(t=[], delivered=0, attempted=0, avg_tq=[],
                        avg_hops=[], comp_G=[], node_reach=[], alive_G=[])
        r = resumen_corrida(sim)
        for clave in ("tq_medio", "tasa_entrega", "componentes_finales",
                      "tiempo_reconvergencia_s", "t_primera_alerta_s"):
            self.assertIsNone(r[clave], clave)
        self.assertEqual(r["particiones"], 0)

    def test_claves_coinciden_con_metricas_corrida(self):
        sim = escenario("base")
        main_mod.correr(sim, 2)
        self.assertEqual(list(resumen_corrida(sim)),
                         [clave for clave, _, _ in METRICAS_CORRIDA])


class ConstruirSimulacionTests(unittest.TestCase):
    def test_escenario_sin_name_toma_el_nombre_del_archivo(self):
        fd, ruta = tempfile.mkstemp(suffix=".txt", prefix="sin_nombre_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("[nodes]\n1 G 5 5\n2 N 9 5\n")
        self.addCleanup(os.unlink, ruta)
        sim, info = main_mod.construir_simulacion(ruta)
        esperado = os.path.splitext(os.path.basename(ruta))[0]
        self.assertEqual(sim.escenario, esperado)
        self.assertEqual(info["escenario"], esperado)

    def test_parametros_invalidos_lanzan_value_error(self):
        for kwargs in (dict(n_nodes=1), dict(n_nodes=3, n_gateways=3),
                       dict(config_path="/no/existe.json")):
            with self.assertRaises(ValueError, msg=kwargs):
                main_mod.construir_simulacion(**kwargs)

    def test_static_deja_move_speed_en_0(self):
        self.assertEqual(escenario("base", static=True).cfg["move_speed"], 0)
        self.assertGreater(escenario("base").cfg["move_speed"], 0)


class SemillaTests(unittest.TestCase):
    def _corrida(self, semilla):
        main_mod.fijar_semilla(semilla)
        sim = escenario("base")
        main_mod.correr(sim, 30)
        rec = sim.recorder
        return (rec.deliver_ratio, rec.comp_G, rec.node_reach,
                [(n.x, n.y) for n in sim.nodes.values()],
                sim.medium.delivered)

    def test_misma_semilla_misma_corrida(self):
        self.assertEqual(self._corrida(5), self._corrida(5))

    def test_semillas_distintas_dan_corridas_distintas(self):
        self.assertNotEqual(self._corrida(5), self._corrida(6))

    def test_correr_avanza_la_duracion_pedida(self):
        sim = escenario("base")
        main_mod.correr(sim, 12.5)
        self.assertEqual(sim.t, 12.5)
        self.assertEqual(len(sim.recorder.t), 25)


class ModosSinVentanaTests(unittest.TestCase):
    def test_modo_headless_exporta_figura_y_reportes(self):
        out_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out_dir)
        main_mod.fijar_semilla(1)
        carpeta, salida = silencioso(main_mod.modo_headless,
                                     escenario("base"), 5, out_dir=out_dir)
        self.assertEqual(carpeta, out_dir)
        self.assertEqual(sorted(os.listdir(out_dir)), ARCHIVOS_DE_UNA_CORRIDA)
        for _, etiqueta, _ in METRICAS_CORRIDA:
            self.assertIn(etiqueta, salida)

    def test_main_headless_crea_su_carpeta_en_reportes(self):
        with en_directorio_temporal():
            silencioso(main_mod.main, ["--headless", "--escenario", "base",
                                       "--duracion", "5", "--seed", "1"])
            carpetas = os.listdir("reportes")
            self.assertEqual(len(carpetas), 1)
            self.assertTrue(carpetas[0].startswith("base_"))
            self.assertEqual(sorted(os.listdir(os.path.join("reportes",
                                                            carpetas[0]))),
                             ARCHIVOS_DE_UNA_CORRIDA)

    def test_main_inspect_imprime_el_estado_sin_generar_archivos(self):
        with en_directorio_temporal() as tmp:
            _, salida = silencioso(main_mod.main,
                                   ["--inspect", "--escenario", "particion",
                                    "--duracion", "5"])
            self.assertIn("RED AD-HOC - INSTANTANEA", salida)
            self.assertIn("Tabla de rutas BATMAN", salida)
            self.assertEqual(os.listdir(tmp), [])

    def test_flags_invalidos_terminan_con_error_de_uso(self):
        for argv in (["--duracion", "50"],                  # sin --headless
                     ["--headless", "--duracion", "0.5"]):  # < 2 pasos
            with contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit) as cm:
                main_mod.main(argv)
            self.assertEqual(cm.exception.code, 2, argv)


if __name__ == "__main__":
    unittest.main()
