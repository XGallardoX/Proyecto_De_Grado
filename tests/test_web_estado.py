"""Pruebas de web/estado.py: forma del frame, serializable a JSON, y que
coincida con el modelo (enlaces = pares con fiabilidad > 0, grupos =
_union_find)."""
import json
import unittest

import main as main_mod
from web import estado


def _sim(nombre="dos_nodos", pasos=20):
    sim, _ = main_mod.construir_simulacion(main_mod.ruta_escenario(nombre))
    for _ in range(pasos):
        sim.step()
    return sim


class FrameTests(unittest.TestCase):
    def test_json_serializable(self):
        sim = _sim()
        json.dumps(estado.frame(sim, velocidad=1.0, semilla=7))

    def test_claves_de_alto_nivel(self):
        sim = _sim()
        f = estado.frame(sim, velocidad=2.0, semilla=42)
        for clave in ("esquema", "t", "pausado", "velocidad", "escenario",
                     "semilla", "edificio", "cfg", "colores", "nodos",
                     "enlaces", "paquetes", "resumen", "grupos",
                     "nodos_alcanzables", "eventos_nuevos", "log",
                     "ultima_muestra"):
            self.assertIn(clave, f)
        self.assertEqual(f["velocidad"], 2.0)
        self.assertEqual(f["semilla"], 42)

    def test_etiquetas_g_n(self):
        sim = _sim("base")
        f = estado.frame(sim)
        etiquetas = {n["etiqueta"] for n in f["nodos"]}
        self.assertTrue(any(e.startswith("G") for e in etiquetas))
        self.assertTrue(any(e.startswith("N") for e in etiquetas))
        for n in f["nodos"]:
            self.assertIn(n["rol"], ("G", "N"))
            self.assertEqual(n["etiqueta"][0], n["rol"])

    def test_enlaces_coinciden_con_reliability(self):
        sim = _sim("base", pasos=30)
        f = estado.frame(sim)
        vivos = [n for n in sim.nodes.values() if n.alive]
        esperados = set()
        for i, a in enumerate(vivos):
            for b in vivos[i + 1:]:
                if sim.medium.reliability(a, b) > 0.0:
                    esperados.add(frozenset((a.id, b.id)))
        obtenidos = {frozenset((e["a"], e["b"])) for e in f["enlaces"]}
        self.assertEqual(esperados, obtenidos)

    def test_grupos_coinciden_con_union_find(self):
        sim = _sim("particion", pasos=30)
        f = estado.frame(sim)
        alive, find, idx = sim._union_find()
        esperados = {}
        for n in alive:
            esperados.setdefault(find(idx[n.id]), set()).add(n.id)
        obtenidos = {frozenset(g) for g in f["grupos"]}
        self.assertEqual({frozenset(g) for g in esperados.values()}, obtenidos)

    def test_sin_eventos_nuevos_no_rompe(self):
        sim, _ = main_mod.construir_simulacion(
            main_mod.ruta_escenario("dos_nodos"))
        f = estado.frame(sim)
        self.assertEqual(f["eventos_nuevos"], [])
        self.assertIsNone(f["ultima_muestra"])


class NodoDetalleTests(unittest.TestCase):
    def test_nodo_inexistente_es_none(self):
        sim = _sim()
        self.assertIsNone(estado.nodo_detalle(sim, 999))

    def test_nodo_existente(self):
        sim = _sim("base", pasos=60)
        gid = next(n.id for n in sim.nodes.values() if n.role == "G")
        detalle = estado.nodo_detalle(sim, gid)
        json.dumps(detalle)
        self.assertEqual(detalle["id"], gid)
        self.assertIn("rutas", detalle)
        self.assertIn("vecinos", detalle)
        self.assertIn("cree_caidos", detalle)


class SeriesTests(unittest.TestCase):
    def test_series_y_eventos(self):
        sim = _sim("colapso_progresivo", pasos=200)
        datos = estado.series(sim)
        json.dumps(datos)
        self.assertEqual(len(datos["series"]["t"]), len(sim.recorder.t))
        self.assertEqual(len(datos["eventos"]), len(sim.recorder.events))
        if datos["eventos"]:
            self.assertEqual(datos["eventos"][0]["indice"], 0)


class InspectorTests(unittest.TestCase):
    def test_devuelve_texto(self):
        sim = _sim()
        texto = estado.inspector_texto(sim)
        self.assertIn("RED AD-HOC", texto)


if __name__ == "__main__":
    unittest.main()
