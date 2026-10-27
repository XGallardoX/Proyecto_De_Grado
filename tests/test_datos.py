"""Plano de datos sobre BATMAN (sim/datos.py, paso 8 de
contexto/PLAN_SIGUIENTE.md): cada paquete avanza salto a salto con
BatmanRouter.next_hop() del nodo que lo tiene, y se clasifica por qué se
pierde."""
import json
import os
import random
import tempfile
import unittest

import main as main_mod
from analysis import lote
from analysis.metrics import resumen_corrida
from mesh.router import BatmanRouter, RouteEntry
from sim.config_loader import load_scenario, validar_escenario
from web.sesion import construir_sesion

# Medio sin pérdidas (fiabilidad 1 hasta el alcance): los resultados no
# dependen del azar.
MEDIO_PERFECTO = {"rango_comm": 10, "falloff": 0, "perdida_base": 0}

# 1 — 2 — 3 en línea: 1 y 3 no se oyen.
LINEA = [{"id": 1, "role": "G", "x": 5, "y": 5},
         {"id": 2, "role": "G", "x": 13, "y": 5},
         {"id": 3, "role": "G", "x": 21, "y": 5}]

# Rombo: 1 llega a 4 por 2 o por 3; 1 y 4 no se oyen.
ROMBO = [{"id": 1, "role": "G", "x": 2, "y": 5},
         {"id": 2, "role": "G", "x": 9, "y": 8},
         {"id": 3, "role": "G", "x": 9, "y": 2},
         {"id": 4, "role": "G", "x": 16, "y": 5}]


def _archivo(nodos, traffic=None, medio=MEDIO_PERFECTO):
    datos = {"name": "prueba_datos", "medium": dict(medio),
             "protocol": {"move_speed": 0}, "nodes": nodos}
    if traffic is not None:
        datos["traffic"] = traffic
    fd, ruta = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(datos, f)
    return ruta


def _sim(nodos, traffic=None, semilla=1, **kw):
    """`traffic`: la sección del escenario; `kw` va a construir_simulacion
    (p. ej. trafico=K, como --trafico)."""
    ruta = _archivo(nodos, traffic)
    try:
        main_mod.fijar_semilla(semilla)
        return main_mod.construir_simulacion(ruta, **kw)[0]
    finally:
        os.remove(ruta)


def _hasta(sim, t):
    while sim.t < t:
        sim.step()


class NextHopTests(unittest.TestCase):
    def test_sin_ruta_es_none(self):
        self.assertIsNone(BatmanRouter(1).next_hop(9))

    def test_devuelve_el_vecino_de_la_ruta(self):
        r = BatmanRouter(1)
        r.routes[9] = RouteEntry(dest=9, via_ip="10.0.0.4", via_id=4, hops=3,
                                 tq=0.5, last_seen=0.0, seq=1)
        self.assertEqual(r.next_hop(9), (4, "10.0.0.4"))


class ReenvioTests(unittest.TestCase):
    def test_sigue_la_tabla_de_cada_nodo(self):
        sim = _sim(LINEA)
        _hasta(sim, 30)
        r = sim.datos.enviar(1, 3)
        self.assertTrue(r["entregado"])
        self.assertEqual(r["camino"], [1, 2, 3])
        self.assertEqual(r["optimo"], [1, 2, 3])
        self.assertEqual(sim.datos.estiramientos, [1.0])

    def test_antes_de_converger_no_hay_ruta(self):
        sim = _sim(LINEA)
        r = sim.datos.enviar(1, 3)
        self.assertEqual((r["entregado"], r["causa"]), (False, "sin_ruta"))
        self.assertEqual(sim.datos.perdidas["sin_ruta"], 1)

    def test_destino_caido_y_sin_camino_son_fisicos(self):
        sim = _sim(LINEA)
        _hasta(sim, 30)
        sim.fail_node(2)
        r = sim.datos.enviar(1, 3)
        self.assertEqual(r["causa"], "sin_camino")
        self.assertIsNone(r["optimo"])
        sim.fail_node(3)
        self.assertEqual(sim.datos.enviar(1, 3)["causa"], "destino_caido")

    def test_origen_caido_no_envia(self):
        sim = _sim(LINEA)
        _hasta(sim, 30)
        sim.fail_node(1)
        r = sim.datos.enviar(1, 3)
        self.assertEqual(r["causa"], "origen_caido")
        self.assertEqual(sim.datos.enviados, 0)

    def test_ruta_vieja_por_un_vecino_caido(self):
        # hay otro camino por radio, pero la tabla de 1 sigue apuntando al
        # vecino que cayó: BATMAN todavía no se enteró
        sim = _sim(ROMBO)
        _hasta(sim, 30)
        via = sim.nodes[1].router.next_hop(4)[0]
        sim.fail_node(via)
        r = sim.datos.enviar(1, 4)
        self.assertEqual(r["causa"], "ruta_vieja")
        self.assertIsNotNone(r["optimo"])

    def test_bucle_se_corta_por_ttl(self):
        sim = _sim(LINEA)
        _hasta(sim, 30)
        # 2 cree que a 3 se llega por 1, y 1 que por 2
        sim.nodes[2].router.routes[3] = RouteEntry(
            dest=3, via_ip=sim.nodes[1].ip, via_id=1, hops=2, tq=1.0,
            last_seen=sim.t, seq=10 ** 6)
        r = sim.datos.enviar(1, 3)
        self.assertEqual(r["causa"], "bucle")
        self.assertEqual(len(r["camino"]) - 1, 50)


class FlujosTests(unittest.TestCase):
    def test_flujo_explicito_respeta_desde_hasta(self):
        sim = _sim(LINEA, {"flujos": [{"src": 1, "dst": 3, "cada": 2,
                                       "desde": 0, "hasta": 10}]})
        _hasta(sim, 30)
        self.assertEqual(sim.datos.enviados, 6)     # t = 0, 2, 4, 6, 8, 10

    def test_aleatorios_entre_nodos_de_usuario(self):
        nodos = LINEA + [{"id": 101, "role": "N", "x": 3, "y": 3},
                         {"id": 102, "role": "N", "x": 23, "y": 3}]
        sim = _sim(nodos, {"aleatorios": 3})
        self.assertEqual(len(sim.datos.flujos), 3)
        for f in sim.datos.flujos:
            self.assertEqual({f["src"], f["dst"]}, {101, 102})

    def test_trafico_por_parametro_reemplaza_los_aleatorios(self):
        sim = _sim(LINEA, {"aleatorios": 5, "flujos": [{"src": 1, "dst": 3}]},
                   trafico=1)
        self.assertEqual(len(sim.datos.flujos), 2)  # el explícito + 1

    def test_sin_trafico_no_consume_azar(self):
        # una corrida sin tráfico tiene que dar lo mismo que antes del
        # plano de datos: el tick no toca `random`
        sim = _sim(LINEA)
        estado = random.getstate()
        sim.datos.tick(100.0)
        self.assertEqual(random.getstate(), estado)

    def test_resumen_con_trafico(self):
        sim = _sim(LINEA, {"flujos": [{"src": 1, "dst": 3, "cada": 1}]})
        _hasta(sim, 60)
        r = resumen_corrida(sim)
        d = sim.datos
        self.assertAlmostEqual(r["entrega_datos"], d.entregados / d.enviados)
        self.assertGreater(r["entrega_datos"], 0.5)
        self.assertEqual(r["saltos_datos"], 2.0)
        self.assertEqual(r["estiramiento_datos"], 1.0)
        perdidas = sum(r[f"perdida_{c}"] for c in
                       ("destino_caido", "sin_camino", "sin_ruta",
                        "ruta_vieja", "enlace", "bucle"))
        self.assertAlmostEqual(perdidas, 1 - r["entrega_datos"])
        self.assertEqual(r["entrega_datos_con_camino"], r["entrega_datos"])
        self.assertEqual(sim.recorder.datos_enviados[-1], d.enviados)


class EscenarioTraficoTests(unittest.TestCase):
    def _txt(self, cuerpo):
        fd, ruta = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(cuerpo)
        self.addCleanup(os.remove, ruta)
        return ruta

    def test_seccion_traffic_en_txt(self):
        ruta = self._txt("[nodes]\n1 G 5 5\n2 N 9 5\n3 N 13 5\n"
                         "[traffic]\naleatorios=2\ncada=1.5\n"
                         "2 3\n3 2 4 10 50\n")
        t = load_scenario(ruta)["traffic"]
        self.assertEqual(t["aleatorios"], 2)
        self.assertEqual(t["cada"], 1.5)
        self.assertEqual(t["flujos"], [
            {"src": 2, "dst": 3},
            {"src": 3, "dst": 2, "cada": 4.0, "desde": 10.0, "hasta": 50.0}])

    def test_validaciones(self):
        base = {"nodes": LINEA}
        malos = [
            ({"flujos": [{"src": 1, "dst": 9}]}, "no existe"),
            ({"flujos": [{"src": 1, "dst": 1}]}, "mismo origen"),
            ({"flujos": [{"src": 1, "dst": 2, "cada": 0}]}, "cada"),
            ({"flujos": [{"src": 1, "dst": 2, "desde": 5, "hasta": 1}]}, "hasta"),
            ({"aleatorios": -1}, "aleatorios"),
            ({"rafaga": 3}, "desconocida"),
        ]
        for trafico, texto in malos:
            with self.subTest(trafico=trafico):
                with self.assertRaisesRegex(ValueError, texto):
                    validar_escenario(dict(base, traffic=trafico))

    def test_modo_random_sólo_admite_aleatorios(self):
        rnd = {"random": {"n_nodes": 5, "n_gateways": 1}}
        validar_escenario(dict(rnd, traffic={"aleatorios": 2}))
        with self.assertRaisesRegex(ValueError, "nodos explícitos"):
            validar_escenario(dict(rnd, traffic={"flujos": [{"src": 1, "dst": 2}]}))


class LoteYSesionTests(unittest.TestCase):
    def test_lote_acepta_trafico_y_lo_pone_en_la_etiqueta(self):
        e = lote._entrada({"escenario": "base", "trafico": 3}, "x",
                          main_mod.ESCENARIOS_DISPONIBLES, 200, [1], 1)
        self.assertEqual((e["trafico"], e["etiqueta"]), (3, "base_trafico3"))
        with self.assertRaisesRegex(ValueError, "trafico"):
            lote._entrada({"escenario": "base", "trafico": -2}, "x",
                          main_mod.ESCENARIOS_DISPONIBLES, 200, [1], 1)

    def test_sesion_con_trafico_y_su_comando(self):
        sesion = construir_sesion(main_mod.ruta_escenario("base"), semilla=3,
                                  trafico=2)
        self.assertEqual(len(sesion.sim.datos.flujos), 2)
        self.assertIn("--trafico 2", sesion.comando_equivalente())
        sesion.comando("cargar", {"escenario": "denso"})
        self.assertEqual(len(sesion.sim.datos.flujos), 2)   # se conserva

    def test_paridad_web_terminal_con_trafico(self):
        ruta = main_mod.ruta_escenario("base")
        main_mod.fijar_semilla(5)
        sim, _ = main_mod.construir_simulacion(ruta, trafico=3)
        main_mod.correr(sim, 60 * main_mod.DT)
        sesion = construir_sesion(ruta, semilla=5, trafico=3)
        sesion.avanzar_sincrono(60)
        self.assertEqual(sim.recorder.entrega_datos,
                         sesion.sim.recorder.entrega_datos)
        self.assertEqual(resumen_corrida(sim), resumen_corrida(sesion.sim))


if __name__ == "__main__":
    unittest.main()
