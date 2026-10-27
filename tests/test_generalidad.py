"""Generalidad (paso 11 de contexto/PLAN_SIGUIENTE.md): campo abierto,
movilidad de los Nodos de usuario (random waypoint y grupos), inundación
como protocolo de datos de comparación y --param."""
import math
import unittest

import main as main_mod
from analysis import lote
from sim.config_loader import validar_escenario
from test_datos import LINEA, _hasta, _sim
from test_engine import make_simulation
from web import estado
from web.sesion import construir_sesion


class CampoAbiertoTests(unittest.TestCase):
    def test_campo_es_un_solo_piso_sin_escalera(self):
        main_mod.fijar_semilla(1)
        sim, _ = main_mod.construir_simulacion(main_mod.ruta_escenario("campo_abierto"))
        self.assertEqual((sim.TIPO_MAPA, sim.N_PISOS, sim.PISO_H), ("campo", 1, 80))
        self.assertEqual({n.piso for n in sim.nodes.values()}, {1})
        self.assertEqual(estado.frame(sim)["edificio"]["tipo"], "campo")
        self.assertEqual(estado.escenario_actual(sim)["building"]["tipo"], "campo")

    def test_tipo_invalido(self):
        with self.assertRaisesRegex(ValueError, "tipo"):
            validar_escenario({"building": {"tipo": "cueva"}, "nodes": LINEA})

    def test_modo_aleatorio_sigue_igual_en_el_edificio(self):
        # mismas posiciones que antes de usar las dimensiones del mapa
        main_mod.fijar_semilla(4)
        sim, _ = main_mod.construir_simulacion(None, n_nodes=6, n_gateways=2)
        for n in sim.nodes.values():
            self.assertTrue(5 <= n.x <= 35 and 5 <= n.y <= 25)


def _usuarios(modo, static=False, **protocol):
    nodes = [{"id": 1, "role": "G", "x": 5, "y": 5}] + [
        {"id": 100 + i, "role": "N", "x": 10 + 3 * i, "y": 5} for i in range(6)]
    protocol = dict({"movilidad_usuarios": modo, "velocidad_usuarios": 0.5}, **protocol)
    if static:
        protocol["move_speed"] = 0
    return make_simulation(nodes, protocol=protocol)


def _caminar(sim, pasos):
    for _ in range(pasos):
        sim.t += sim.DT
        for n in list(sim.nodes.values()):
            n.move(sim.t)


class MovilidadUsuariosTests(unittest.TestCase):
    def test_random_waypoint_camina_aunque_los_gateway_esten_fijos(self):
        sim = _usuarios("random_waypoint", static=True)
        antes = {n.id: (n.x, n.y) for n in sim.nodes.values()}
        _caminar(sim, 40)
        self.assertEqual((sim.nodes[1].x, sim.nodes[1].y), antes[1])
        movidos = [i for i, (x, y) in antes.items()
                   if i != 1 and math.hypot(sim.nodes[i].x - x, sim.nodes[i].y - y) > 3]
        self.assertGreaterEqual(len(movidos), 4)

    def test_quietos_con_static_no_se_mueven(self):
        sim = _usuarios("quietos", static=True)
        antes = {n.id: (n.x, n.y) for n in sim.nodes.values()}
        _caminar(sim, 40)
        self.assertEqual(antes, {n.id: (n.x, n.y) for n in sim.nodes.values()})

    def test_random_waypoint_espera_al_llegar(self):
        sim = _usuarios("random_waypoint")
        u = sim.nodes[100]
        u._wp = (u.x + 0.1, u.y)
        u.move(1.0)
        self.assertIsNotNone(u._pausa_hasta)
        quieto = (u.x, u.y)
        if u._pausa_hasta > 1.5:
            u.move(1.5)
            self.assertEqual((u.x, u.y), quieto)

    def test_grupos_siguen_a_su_lider(self):
        sim = _usuarios("grupos")
        ids = sorted(n.id for n in sim.nodes.values() if n.role == "N")
        self.assertIs(sim.lider_de_grupo(sim.nodes[ids[1]]), sim.nodes[ids[0]])
        self.assertIs(sim.lider_de_grupo(sim.nodes[ids[4]]), sim.nodes[ids[3]])
        _caminar(sim, 200)
        for lider, miembros in ((ids[0], ids[1:3]), (ids[3], ids[4:6])):
            for m in miembros:
                d = math.hypot(sim.nodes[m].x - sim.nodes[lider].x,
                               sim.nodes[m].y - sim.nodes[lider].y)
                self.assertLess(d, 6.0)

    def test_si_cae_el_lider_lo_reemplaza_el_siguiente(self):
        sim = _usuarios("grupos")
        ids = sorted(n.id for n in sim.nodes.values() if n.role == "N")
        sim.fail_node(ids[0])
        self.assertIs(sim.lider_de_grupo(sim.nodes[ids[2]]), sim.nodes[ids[1]])


class InundacionTests(unittest.TestCase):
    def test_entrega_sin_tablas(self):
        # al arrancar BATMAN no tiene rutas, la inundación no las necesita
        sim = _sim(LINEA)
        sim.cfg["protocolo_datos"] = "inundacion"
        r = sim.datos.enviar(1, 3)
        self.assertTrue(r["entregado"])
        self.assertEqual(r["camino"], [1, 2, 3])
        # difunden 1 y 2; el destino no reenvía
        self.assertEqual(sim.datos.transmisiones, 2)

    def test_batman_cuenta_sus_transmisiones(self):
        sim = _sim(LINEA)
        _hasta(sim, 30)
        sim.datos.enviar(1, 3)
        self.assertEqual(sim.datos.transmisiones, 2)   # dos saltos sin pérdidas

    def test_sin_camino_no_inunda(self):
        sim = _sim(LINEA)
        sim.cfg["protocolo_datos"] = "inundacion"
        sim.fail_node(2)
        self.assertEqual(sim.datos.enviar(1, 3)["causa"], "sin_camino")
        self.assertEqual(sim.datos.transmisiones, 0)


class ParamTests(unittest.TestCase):
    def test_leer_parametros(self):
        self.assertEqual(main_mod.leer_parametros(
            ["protocolo_datos=inundacion", "rango_comm=20", "ttl=3"]),
            {"protocolo_datos": "inundacion", "rango_comm": 20.0, "ttl": 3})
        for malo in (["rango_comm"], ["nada=1"], ["rango_comm=999"],
                     ["movilidad_usuarios=volar"]):
            with self.assertRaises(ValueError):
                main_mod.leer_parametros(malo)

    def test_parametros_pisan_el_escenario(self):
        main_mod.fijar_semilla(1)
        sim, _ = main_mod.construir_simulacion(
            main_mod.ruta_escenario("base"),
            parametros={"protocolo_datos": "inundacion", "rango_comm": 20})
        self.assertEqual((sim.cfg["protocolo_datos"], sim.cfg["rango_comm"]),
                         ("inundacion", 20.0))

    def test_lote_y_comando_equivalente(self):
        e = lote._entrada({"escenario": "base", "parametros": {"protocolo_datos": "inundacion"}},
                          "x", main_mod.ESCENARIOS_DISPONIBLES, 200, [1], 1)
        self.assertEqual(e["etiqueta"], "base_inundacion")
        with self.assertRaisesRegex(ValueError, "protocolo_datos"):
            lote._entrada({"escenario": "base", "parametros": {"protocolo_datos": "x"}},
                          "x", main_mod.ESCENARIOS_DISPONIBLES, 200, [1], 1)
        sesion = construir_sesion(main_mod.ruta_escenario("base"), semilla=1,
                                  parametros={"movilidad_usuarios": "grupos"})
        self.assertIn("--param movilidad_usuarios=grupos", sesion.comando_equivalente())


if __name__ == "__main__":
    unittest.main()
