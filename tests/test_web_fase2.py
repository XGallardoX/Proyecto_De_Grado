"""Pruebas del backend de la Fase 2 de la interfaz web: lente de
descentralización (matriz de conocimiento, vigilancia, rutas faltantes),
cobertura, series incrementales, contadores real/modelo y el editor de
escenarios (validar, guardar sin pisar predefinidos, y que lo guardado
corra con --config y --headless)."""
import contextlib
import io
import json
import math
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

import main as main_mod
from sim.radio import fiabilidad
from web import editor, estado
from web.sesion import construir_sesion


def _sim(nombre="base", pasos=40, **kw):
    main_mod.fijar_semilla(1)
    sim = main_mod.construir_simulacion(main_mod.ruta_escenario(nombre), **kw)[0]
    for _ in range(pasos):
        sim.step()
    return sim


class MatrizTests(unittest.TestCase):
    def test_forma_y_estados(self):
        sim = _sim("base", 80, static=True)
        m = estado.matriz_conocimiento(sim)
        json.dumps(m)
        n = len(sim.nodes)
        self.assertEqual(len(m["filas"]), n)
        validos = {"propio", "vigente", "obsoleta", "sin_converger",
                   "sin_conexion"}
        for i, fila in enumerate(m["filas"]):
            self.assertEqual(len(fila["celdas"]), n)
            self.assertEqual(fila["celdas"][i]["estado"], "propio")
            for c in fila["celdas"]:
                self.assertIn(c["estado"], validos)
        self.assertLessEqual(m["pares_con_ruta"], m["pares_conectados"])

    def test_vigente_coincide_con_la_tabla_de_rutas(self):
        sim = _sim("base", 80, static=True)
        m = estado.matriz_conocimiento(sim)
        ids = [c["id"] for c in m["nodos"]]
        for fila in m["filas"]:
            rutas = sim.nodes[fila["id"]].router.routes
            for destino, celda in zip(ids, fila["celdas"]):
                if celda["estado"] in ("vigente", "obsoleta"):
                    self.assertIn(destino, rutas)
                    self.assertEqual(celda["hops"], rutas[destino].hops)
                elif celda["estado"] != "propio":
                    self.assertNotIn(destino, rutas)

    def test_particion_sin_conexion_entre_grupos(self):
        sim = _sim("particion", 20, static=True)
        m = estado.matriz_conocimiento(sim)
        estados = {c["estado"] for f in m["filas"] for c in f["celdas"]}
        self.assertIn("sin_conexion", estados)

    def test_al_principio_nada_convergio(self):
        sim = _sim("base", 0)
        m = estado.matriz_conocimiento(sim)
        self.assertEqual(m["pares_con_ruta"], 0)


class NodoLenteTests(unittest.TestCase):
    def test_alcanzables_sin_ruta_al_arrancar(self):
        sim = _sim("base", 1, static=True)
        g = next(n for n in sim.nodes.values() if n.role == "G")
        d = estado.nodo_detalle(sim, g.id)
        alive, find, idx = sim._union_find()
        mismo_grupo = {n.id for n in alive if n.id != g.id
                       and find(idx[n.id]) == find(idx[g.id])}
        conocidos = set(g.router.routes)
        self.assertEqual({x["id"] for x in d["alcanzables_sin_ruta"]},
                         mismo_grupo - conocidos)

    def test_vigilancia_solo_gateways_y_contra_el_timeout(self):
        sim = _sim("colapso_progresivo", 220)
        f = estado.frame(sim)
        self.assertTrue(f["vigilancia"])
        for v in f["vigilancia"]:
            self.assertTrue(sim.is_gateway(v["observador"]))
            self.assertTrue(sim.is_gateway(v["observado"]))
            self.assertEqual(v["timeout"], sim.cfg["timeout"])
            self.assertEqual(
                v["cree_caido"],
                v["observado"] in sim.nodes[v["observador"]].fault.failed)


class FrameFase2Tests(unittest.TestCase):
    def test_paquetes_con_tipo_real_y_origen(self):
        sim = _sim("base", 3)
        f = estado.frame(sim)
        self.assertTrue(f["paquetes"])
        for x0, y0, x1, y1, prog, tipo, origen, ttl in f["paquetes"]:
            self.assertIn(tipo, ("OGM", "BCN"))
            self.assertIn(origen, sim.nodes)
            self.assertTrue(0 <= prog <= 1)
            if tipo == "OGM":
                self.assertTrue(1 <= ttl <= sim.cfg["ttl"])

    def test_contadores(self):
        sim = _sim("base", 40)
        c = estado.frame(sim)["contadores"]
        self.assertEqual(c["paquetes_intentados"], sim.medium.attempted)
        self.assertGreater(c["ogms_procesados"], 0)

    def test_eventos_con_nodos_implicados(self):
        sim = _sim("base", 5)
        g = next(n for n in sim.nodes.values() if n.role == "G")
        sim.fail_node(g.id)
        ev = estado.frame(sim)["eventos_nuevos"][-1]
        self.assertEqual(ev["tipo"], "FAIL")
        self.assertEqual(ev["nodos"], [g.id])

    def test_cfg_base(self):
        sim = _sim("particion", 1)
        sim.set_param("rango_comm", 30.0)
        f = estado.frame(sim)
        self.assertEqual(f["cfg"]["rango_comm"], 30.0)
        self.assertEqual(f["cfg_base"]["rango_comm"], 11)


class SeriesIncrementalesTests(unittest.TestCase):
    def test_desde(self):
        sim = _sim("colapso_progresivo", 400)
        completa = estado.series(sim)
        self.assertGreater(len(completa["eventos"]), 3)
        parte = estado.series(sim, desde=150, desde_evento=2)
        self.assertEqual(parte["total"], completa["total"])
        self.assertEqual(parte["series"]["t"], completa["series"]["t"][150:])
        self.assertEqual(parte["eventos"], completa["eventos"][2:])
        self.assertEqual(parte["eventos"][0]["indice"], 2)
        ultimas = estado.series(sim, ultimas=100)
        self.assertEqual(ultimas["desde"], completa["total"] - 100)
        self.assertEqual(ultimas["series"]["t"], completa["series"]["t"][-100:])
        self.assertEqual(ultimas["total"], completa["total"])


class CoberturaTests(unittest.TestCase):
    def test_misma_formula_que_el_medio(self):
        sim = _sim("base", 1)
        c = estado.cobertura(sim)
        self.assertEqual(len(c["valores"]), c["nx"] * c["ny"])
        gws = [n for n in sim.nodes.values() if n.role == "G" and n.alive]
        for j in (0, 7, c["ny"] - 1):
            for i in (0, 11, c["nx"] - 1):
                x, y = (i + 0.5) * c["paso"], (j + 0.5) * c["paso"]
                piso = max(1, min(sim.N_PISOS, int(y // sim.PISO_H) + 1))
                esperado = max(fiabilidad(math.hypot(g.x - x, g.y - y),
                                          abs(g.piso - piso), sim.cfg)
                               for g in gws)
                self.assertEqual(c["valores"][j * c["nx"] + i], esperado)

    def test_sin_gateways_vivos_es_cero(self):
        sim = _sim("dos_nodos", 1)
        for n in sim.nodes.values():
            n.alive = False
        self.assertEqual(set(estado.cobertura(sim)["valores"]), {0.0})


@contextlib.contextmanager
def escenarios_temporales():
    """El editor escribe en main.ESCENARIOS_DIR: aislarlo en un temporal
    con una copia de los escenarios de verdad."""
    tmp = tempfile.mkdtemp()
    destino = os.path.join(tmp, "escenarios")
    shutil.copytree(main_mod.ESCENARIOS_DIR, destino)
    try:
        with patch.object(main_mod, "ESCENARIOS_DIR", destino):
            yield destino
    finally:
        shutil.rmtree(tmp)


class EditorTests(unittest.TestCase):
    ESCENARIO = {
        "building": {"ancho": 40, "alto": 30, "piso_h": 10, "n_pisos": 3},
        "medium": {"rango_comm": 16},
        "protocol": {"timeout": 30, "movilidad": "repartir"},
        "nodes": [{"id": 1, "role": "G", "x": 5, "y": 5},
                  {"id": 2, "role": "G", "x": 15, "y": 5},
                  {"id": 3, "role": "N", "x": 25, "y": 15}],
        "events": [{"type": "wander", "node_id": 2, "until": 40}],
    }

    def test_validar(self):
        self.assertEqual(editor.validar(self.ESCENARIO),
                         {"nodos": 3, "gateways": 2})
        malo = dict(self.ESCENARIO, nodes=[{"id": 1, "role": "N", "x": 5, "y": 5}])
        with self.assertRaises(ValueError):
            editor.validar(malo)

    def test_no_pisa_predefinidos_ni_sale_de_la_carpeta(self):
        with escenarios_temporales():
            for nombre in ("base", "denso.json", "../fuera", "a/b", "", ".oculto"):
                with self.assertRaises(ValueError):
                    editor.guardar(self.ESCENARIO, nombre, sobrescribir=True)

    def test_no_sobrescribe_sin_permiso(self):
        with escenarios_temporales():
            editor.guardar(self.ESCENARIO, "mio")
            with self.assertRaises(ValueError):
                editor.guardar(self.ESCENARIO, "mio")
            editor.guardar(self.ESCENARIO, "mio", sobrescribir=True)

    def test_lo_guardado_corre_con_config_y_headless(self):
        cwd = os.getcwd()
        with escenarios_temporales() as carpeta:
            r = editor.guardar(self.ESCENARIO, "desde_editor")
            ruta = os.path.join(carpeta, r["archivo"])
            self.assertTrue(os.path.isfile(ruta))
            sim, info = main_mod.construir_simulacion(ruta)
            self.assertEqual(info["n_total"], 3)
            self.assertEqual(sim.escenario, "desde_editor")
            tmp = tempfile.mkdtemp()
            os.chdir(tmp)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    main_mod.main(["--headless", "--config", ruta,
                                   "--duracion", "5", "--seed", "1"])
                self.assertTrue(os.listdir(os.path.join(tmp, "reportes")))
            finally:
                os.chdir(cwd)
                shutil.rmtree(tmp)

    def test_ida_y_vuelta_desde_la_sesion(self):
        """El escenario actual de una sesión, guardado por el editor, se
        vuelve a cargar con la misma topología."""
        sesion = construir_sesion(main_mod.ruta_escenario("rescatista_perdido"),
                                  semilla=1)
        actual = estado.escenario_actual(sesion.sim)
        with escenarios_temporales() as carpeta:
            r = sesion.comando("guardar_escenario",
                               {"escenario": actual, "nombre": "copia"})
            sesion.comando("cargar", {"archivo": r["archivo"]})
            self.assertEqual(sesion.sim.escenario, "copia")
            self.assertEqual(len(sesion.sim.nodes), len(actual["nodes"]))
            self.assertIsNotNone(sesion.sim.wanderer)
            self.assertIn("--config", sesion.comando_equivalente())
            self.assertTrue(os.path.isfile(os.path.join(carpeta, "copia.json")))


class EscenarioActualTests(unittest.TestCase):
    def test_posiciones_iniciales_y_actuales(self):
        sim = _sim("base", 60)
        ini = estado.escenario_actual(sim)
        act = estado.escenario_actual(sim, posiciones="actuales")
        with open(main_mod.ruta_escenario("base"), encoding="utf-8") as f:
            original = json.load(f)
        self.assertEqual([(n["x"], n["y"]) for n in ini["nodes"]],
                         [(n["x"], n["y"]) for n in original["nodes"]])
        self.assertNotEqual(ini["nodes"], act["nodes"])
        editor.validar(ini)
        editor.validar(act)


if __name__ == "__main__":
    unittest.main()
