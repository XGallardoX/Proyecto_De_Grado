"""Tipos de paquete del plano de datos (sim/datos.py): UDP, ICMP (eco) y
TCP (con confirmación y retransmisión), y su control desde la interfaz."""
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))

import main as main_mod
from sim.config_loader import load_scenario, validar_escenario
from sim.datos import RETRANSMISIONES_TCP
from test_datos import LINEA, _hasta, _sim
from web import estado
from web.sesion import construir_sesion


class TiposTests(unittest.TestCase):
    def setUp(self):
        self.sim = _sim(LINEA)
        _hasta(self.sim, 30)

    def test_udp_es_el_tipo_por_defecto_y_no_tiene_vuelta(self):
        r = self.sim.datos.enviar(1, 3)
        self.assertEqual((r["tipo"], r["vuelta"], r["confirmado"]),
                         ("udp", None, False))
        self.assertTrue(r["entregado"])

    def test_icmp_va_y_vuelve_por_las_tablas(self):
        r = self.sim.datos.enviar(1, 3, "icmp")
        self.assertTrue(r["entregado"] and r["confirmado"])
        self.assertEqual((r["camino"], r["vuelta"]), ([1, 2, 3], [3, 2, 1]))

    def test_icmp_no_cuenta_si_la_respuesta_no_vuelve(self):
        # 3 pierde su ruta hacia 1: la petición llega, la respuesta no
        self.sim.nodes[3].router.routes.pop(1, None)
        r = self.sim.datos.enviar(1, 3, "icmp")
        self.assertFalse(r["entregado"])
        self.assertEqual((r["causa"], r["tramo"]), ("sin_ruta", "vuelta"))
        self.assertEqual(self.sim.datos.por_tipo["icmp"]["sin_respuesta"], 1)

    def test_tcp_entrega_y_confirma(self):
        r = self.sim.datos.enviar(1, 3, "tcp")
        self.assertTrue(r["entregado"] and r["confirmado"])
        self.assertEqual(r["intentos"], 1)

    def test_tcp_entregado_sin_confirmar_si_el_ack_no_tiene_ruta(self):
        self.sim.nodes[3].router.routes.pop(1, None)
        r = self.sim.datos.enviar(1, 3, "tcp")
        self.assertTrue(r["entregado"])
        self.assertFalse(r["confirmado"])
        self.assertEqual(r["intentos"], 1)   # no es una pérdida de la radio

    def test_tcp_no_retransmite_si_no_hay_ruta(self):
        self.sim.nodes[1].router.routes.pop(3, None)
        r = self.sim.datos.enviar(1, 3, "tcp")
        self.assertEqual((r["entregado"], r["causa"], r["intentos"]),
                         (False, "sin_ruta", 1))

    def test_tipo_desconocido(self):
        with self.assertRaisesRegex(ValueError, "tipo de paquete"):
            self.sim.datos.enviar(1, 3, "sctp")

    def test_las_cuentas_por_tipo_suman_el_total(self):
        d = self.sim.datos
        for tipo in ("udp", "icmp", "tcp", "tcp"):
            d.enviar(1, 3, tipo)
        self.assertEqual(sum(c["enviados"] for c in d.por_tipo.values()), d.enviados)
        self.assertEqual(sum(c["entregados"] for c in d.por_tipo.values()), d.entregados)
        self.assertEqual([h["tipo"] for h in d.historial], ["udp", "icmp", "tcp", "tcp"])


class TcpConPerdidasTests(unittest.TestCase):
    def test_tcp_retransmite_y_entrega_mas_que_udp(self):
        """Sobre un enlace con pérdidas, TCP recupera con retransmisiones lo
        que UDP pierde, a cambio de más transmisiones."""
        nodos = [{"id": 1, "role": "G", "x": 5, "y": 5},
                 {"id": 2, "role": "G", "x": 14, "y": 5}]
        medio = {"rango_comm": 10, "falloff": 0.85, "perdida_base": 0.02}
        entrega = {}
        for tipo in ("udp", "tcp"):
            import test_datos
            ruta = test_datos._archivo(nodos, None, medio)
            try:
                main_mod.fijar_semilla(4)
                sim = main_mod.construir_simulacion(ruta)[0]
            finally:
                os.remove(ruta)
            _hasta(sim, 60)
            for _ in range(300):
                sim.datos.enviar(1, 2, tipo)
            entrega[tipo] = sim.datos.entregados / sim.datos.enviados
            if tipo == "tcp":
                self.assertGreater(sim.datos.por_tipo["tcp"]["retransmisiones"], 0)
                self.assertLessEqual(max(h["intentos"] for h in sim.datos.historial),
                                     1 + RETRANSMISIONES_TCP)
        self.assertGreater(entrega["tcp"], entrega["udp"])


class FlujosTests(unittest.TestCase):
    def test_flujo_con_cantidad_termina_solo(self):
        sim = _sim(LINEA)
        _hasta(sim, 30)
        f = sim.datos.agregar_flujo(1, 3, "icmp", cada=1.0, cantidad=5)
        _hasta(sim, 60)
        self.assertEqual((f["enviados"], f["entregados"]), (5, 5))
        self.assertFalse(sim.datos.flujo_activo(f, sim.t))
        self.assertEqual(sim.datos.por_tipo["icmp"]["enviados"], 5)

    def test_quitar_flujo(self):
        sim = _sim(LINEA)
        f = sim.datos.agregar_flujo(1, 3, "udp", cada=1.0)
        self.assertTrue(sim.datos.quitar_flujo(f["id"]))
        self.assertFalse(sim.datos.quitar_flujo(f["id"]))

    def test_escenario_con_tipo_y_cantidad(self):
        sim = _sim(LINEA, {"tipo": "tcp", "flujos": [
            {"src": 1, "dst": 3},
            {"src": 3, "dst": 1, "tipo": "icmp", "cantidad": 2}]})
        self.assertEqual([sim.datos.tipo_de(f) for f in sim.datos.flujos], ["tcp", "icmp"])
        _hasta(sim, 40)
        self.assertEqual(sim.datos.flujos[1]["enviados"], 2)
        self.assertEqual(sim.datos.descripcion_flujos()[1]["cantidad"], 2)

    def test_validacion(self):
        base = {"name": "x", "nodes": LINEA}
        for traffic in ({"tipo": "sctp"},
                        {"flujos": [{"src": 1, "dst": 3, "tipo": "x"}]},
                        {"flujos": [{"src": 1, "dst": 3, "cantidad": 0}]}):
            with self.assertRaises(ValueError):
                validar_escenario(dict(base, traffic=traffic), "prueba")

    def test_formato_txt(self):
        texto = ("[nodes]\n1 G 5 5\n2 G 13 5\n3 G 21 5\n"
                 "[traffic]\ntipo=tcp\n1 3\n3 1 1 tipo=icmp cantidad=4\n")
        fd, ruta = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(texto)
        try:
            t = load_scenario(ruta)["traffic"]
        finally:
            os.remove(ruta)
        self.assertEqual(t["tipo"], "tcp")
        self.assertEqual(t["flujos"][1], {"src": 3, "dst": 1, "cada": 1.0,
                                          "tipo": "icmp", "cantidad": 4})

    def test_udp_no_cambia_el_azar_respecto_del_defecto(self):
        """Un flujo "udp" explícito da la misma corrida que uno sin tipo."""
        estados = []
        for traffic in ({"flujos": [{"src": 1, "dst": 3}]},
                        {"flujos": [{"src": 1, "dst": 3, "tipo": "udp"}]}):
            sim = _sim(LINEA, traffic, semilla=9)
            _hasta(sim, 50)
            estados.append((sim.datos.enviados, sim.datos.entregados,
                            sim.datos.transmisiones, random.random()))
        self.assertEqual(estados[0], estados[1])


class SesionTests(unittest.TestCase):
    def setUp(self):
        self.sesion = construir_sesion(main_mod.ruta_escenario("base"),
                                       semilla=3, static=True)
        _hasta(self.sesion.sim, 40)
        ids = sorted(self.sesion.sim.nodes)
        self.a, self.b = ids[0], ids[1]

    def test_rafaga(self):
        r = self.sesion.comando("enviar_paquetes", {
            "origen": self.a, "destino": self.b, "tipo": "icmp", "cantidad": 5})
        self.assertEqual((r["modo"], r["enviados"]), ("rafaga", 5))
        self.assertEqual(self.sesion.sim.datos.por_tipo["icmp"]["enviados"], 5)

    def test_flujo_y_quitarlo(self):
        r = self.sesion.comando("enviar_paquetes", {
            "origen": self.a, "destino": self.b, "tipo": "tcp",
            "cantidad": 3, "cada": 2})
        self.assertEqual(r["modo"], "flujo")
        f = estado.frame(self.sesion.sim)["trafico"]
        self.assertEqual([x["tipo"] for x in f["flujos"]], ["tcp"])
        self.sesion.comando("quitar_flujo", {"flujo": r["flujo"]})
        self.assertEqual(self.sesion.sim.datos.flujos, [])

    def test_errores(self):
        for datos in ({"origen": self.a, "destino": self.a},
                      {"origen": self.a, "destino": self.b, "tipo": "x"},
                      {"origen": self.a, "destino": self.b, "cantidad": 0},
                      {"origen": self.a, "destino": 9999},
                      {"destino": self.b}):
            with self.assertRaises(ValueError):
                self.sesion.comando("enviar_paquetes", datos)

    def test_el_frame_lleva_los_ultimos_paquetes_con_etiquetas(self):
        self.sesion.comando("enviar_paquetes", {
            "origen": self.a, "destino": self.b, "tipo": "icmp", "cantidad": 2})
        t = estado.frame(self.sesion.sim)["trafico"]
        self.assertEqual(len(t["recientes"]), 2)
        self.assertEqual(t["recientes"][0]["origen"],
                         self.sesion.sim.label_of(self.a))
        self.assertEqual({x["clave"] for x in t["tipos"]}, {"udp", "icmp", "tcp"})


if __name__ == "__main__":
    unittest.main()
