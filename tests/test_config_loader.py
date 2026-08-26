import json
import os
import tempfile
import unittest

from sim.config_loader import load_scenario


class ConfigLoaderTests(unittest.TestCase):
    def _write(self, data):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
        self.addCleanup(os.unlink, path)
        return path

    def test_config_valido_minimo(self):
        path = self._write({
            "nodes": [
                {"id": 1, "role": "G", "x": 5, "y": 5},
                {"id": 2, "role": "N", "x": 10, "y": 10},
            ]
        })
        scenario = load_scenario(path, default_building=dict(ancho=40, alto=30))
        self.assertEqual(len(scenario["nodes"]), 2)
        self.assertEqual(scenario["building"]["ancho"], 40)

    def test_config_valido_con_building_medium_protocol_events(self):
        path = self._write({
            "name": "completo",
            "building": {"ancho": 50, "alto": 20},
            "medium": {"rango_comm": 12.0},
            "protocol": {"timeout": 45},
            "nodes": [
                {"id": 1, "role": "G", "x": 1, "y": 1},
                {"id": 2, "role": "N", "x": 2, "y": 2},
            ],
            "events": [{"type": "wander", "node_id": 2, "until": 30.0}],
        })
        scenario = load_scenario(path)
        self.assertEqual(scenario["building"]["ancho"], 50)
        self.assertEqual(scenario["medium"]["rango_comm"], 12.0)
        self.assertEqual(scenario["events"][0]["node_id"], 2)

    def test_archivo_inexistente(self):
        with self.assertRaisesRegex(ValueError, "no encontrado"):
            load_scenario("/no/existe/escenario.json")

    def test_json_invalido(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("{esto no es json")
        self.addCleanup(os.unlink, path)
        with self.assertRaisesRegex(ValueError, "JSON inválido"):
            load_scenario(path)

    def test_sin_nodes(self):
        path = self._write({"nodes": []})
        with self.assertRaisesRegex(ValueError, "falta 'nodes'"):
            load_scenario(path)

    def test_id_duplicado(self):
        path = self._write({"nodes": [
            {"id": 1, "role": "G", "x": 1, "y": 1},
            {"id": 1, "role": "N", "x": 2, "y": 2},
        ]})
        with self.assertRaisesRegex(ValueError, "duplicado"):
            load_scenario(path)

    def test_rol_invalido(self):
        path = self._write({"nodes": [{"id": 1, "role": "X", "x": 1, "y": 1}]})
        with self.assertRaisesRegex(ValueError, "rol inválido"):
            load_scenario(path)

    def test_sin_gateway(self):
        path = self._write({"nodes": [{"id": 1, "role": "N", "x": 1, "y": 1}]})
        with self.assertRaisesRegex(ValueError, "al menos un nodo con role 'G'"):
            load_scenario(path)

    def test_fuera_de_edificio(self):
        path = self._write({
            "building": {"ancho": 40, "alto": 30},
            "nodes": [{"id": 1, "role": "G", "x": 999, "y": 1}],
        })
        with self.assertRaisesRegex(ValueError, "fuera del"):
            load_scenario(path)

    def test_campo_faltante(self):
        path = self._write({"nodes": [{"id": 1, "role": "G"}]})
        with self.assertRaisesRegex(ValueError, "campo obligatorio"):
            load_scenario(path)

    def test_battery_fuera_de_rango(self):
        path = self._write({"nodes": [
            {"id": 1, "role": "G", "x": 1, "y": 1, "battery": 150},
        ]})
        with self.assertRaisesRegex(ValueError, "battery"):
            load_scenario(path)

    def test_evento_tipo_desconocido(self):
        path = self._write({
            "nodes": [{"id": 1, "role": "G", "x": 1, "y": 1}],
            "events": [{"type": "teleport", "node_id": 1}],
        })
        with self.assertRaisesRegex(ValueError, "tipo de evento desconocido"):
            load_scenario(path)

    def test_evento_referencia_nodo_inexistente(self):
        path = self._write({
            "nodes": [{"id": 1, "role": "G", "x": 1, "y": 1}],
            "events": [{"type": "wander", "node_id": 99, "until": 10}],
        })
        with self.assertRaisesRegex(ValueError, "no existe"):
            load_scenario(path)


if __name__ == "__main__":
    unittest.main()
