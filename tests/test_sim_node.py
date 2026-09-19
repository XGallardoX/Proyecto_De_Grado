"""Pruebas directas de sim/sim_node.py: ciclo de vida de un nodo (tick,
drenaje de inbox, drenaje de batería), detección de caídas y movilidad.
Sin Visualizer/pygame."""
import math
import unittest

from tests.test_engine import make_simulation

# Medio sin pérdidas: todo paquete en rango llega (fiabilidad 1.0), así
# lo que se verifica no depende del azar del medio radio.
SIN_PERDIDAS = {"perdida_base": 0.0, "falloff": 0.0}


def simulacion(roles=("G", "G"), separacion=3.0, **medium):
    """Nodos en fila sobre el piso 1, a `separacion` metros entre sí."""
    nodes = [{"id": i + 1, "role": rol, "x": 5.0 + i * separacion, "y": 5.0}
             for i, rol in enumerate(roles)]
    return make_simulation(nodes, medium={**SIN_PERDIDAS, **medium})


def silenciar_timers(nodo, now):
    """Que el próximo tick(now) no emita beacon ni OGM."""
    nodo.t_beacon = now
    nodo.t_ogm = now


def ogm(origen, seq, ttl=3, path=None, alerts=()):
    return {"type": "OGM", "origin_id": origen, "seq": seq, "ttl": ttl,
            "path": list(path or [origen]), "battery": 90.0, "load": 0,
            "reputation": 1.0, "tq": 1.0, "alerts": list(alerts), "ts": 0.0}


def eventos(sim, tipo):
    return [txt for (_t, tp, txt) in sim.recorder.events if tp == tipo]


class TickBateriaTests(unittest.TestCase):
    def test_descuenta_bateria_segun_rol(self):
        sim = simulacion(roles=("G", "N"), battery_drain=2.0,
                         battery_drain_nodo=0.5)
        g, n = sim.nodes[1], sim.nodes[2]
        for nodo in (g, n):
            silenciar_timers(nodo, 1.0)
            nodo.tick(1.0)
        self.assertAlmostEqual(g.battery, 100.0 - 2.0 * sim.DT)
        self.assertAlmostEqual(n.battery, 100.0 - 0.5 * sim.DT)

    def test_bateria_agotada_mata_al_nodo_y_registra_fail(self):
        sim = simulacion(battery_drain=1.0)
        g = sim.nodes[1]
        g.battery = 0.2
        g.t_beacon = g.t_ogm = -100.0      # le tocaría emitir...
        g.tick(1.0)
        self.assertFalse(g.alive)
        self.assertEqual(g.battery, 0.0)
        self.assertEqual(eventos(sim, "FAIL"), ["G1 sin batería"])
        self.assertEqual(sim.medium.attempted, 0)  # ...pero ya no emite

    def test_nodo_caido_no_hace_nada(self):
        sim = simulacion()
        g = sim.nodes[1]
        g.alive = False
        g.t_beacon = g.t_ogm = -100.0
        g._inbox.append((ogm(2, 1), sim.nodes[2].ip))
        g.tick(1.0)
        self.assertEqual(g.battery, 100.0)
        self.assertEqual(sim.medium.attempted, 0)
        self.assertNotIn(2, g.router.routes)


class TickEmisionTests(unittest.TestCase):
    def test_emite_beacon_y_ogm_cuando_toca(self):
        sim = simulacion()
        emisor, receptor = sim.nodes[1], sim.nodes[2]
        emisor.t_beacon = emisor.t_ogm = -100.0
        emisor.tick(1.0)

        tipos = [msg["type"] for msg, _ip in receptor._inbox]
        self.assertEqual(sorted(tipos), ["BCN", "OGM"])
        ogm_recibido = next(m for m, _ in receptor._inbox if m["type"] == "OGM")
        self.assertEqual(ogm_recibido["origin_id"], 1)
        self.assertEqual(ogm_recibido["seq"], 1)
        self.assertEqual(ogm_recibido["ttl"], sim.cfg["ttl"])
        self.assertEqual(ogm_recibido["path"], [1])
        self.assertNotIn("survivors", ogm_recibido)
        self.assertEqual((emisor.t_beacon, emisor.t_ogm), (1.0, 1.0))

    def test_no_emite_antes_de_tiempo(self):
        sim = simulacion()
        emisor = sim.nodes[1]
        silenciar_timers(emisor, 1.0)
        emisor.tick(1.5)          # 0.5 s después: ni beacon (2 s) ni OGM (4 s)
        self.assertEqual(sim.medium.attempted, 0)

    def test_seq_del_ogm_propio_crece(self):
        sim = simulacion()
        emisor, receptor = sim.nodes[1], sim.nodes[2]
        emisor.t_ogm = -100.0
        emisor.tick(1.0)
        emisor.tick(1.0 + sim.cfg["batman_cada"])
        seqs = [m["seq"] for m, _ in receptor._inbox if m["type"] == "OGM"]
        self.assertEqual(seqs, [1, 2])


class DrenajeInboxTests(unittest.TestCase):
    def test_beacon_crea_vecino_con_sus_datos(self):
        sim = simulacion()
        g1, g2 = sim.nodes[1], sim.nodes[2]
        bcn = {"type": "BCN", "node_id": 2, "battery": 42.0, "load": 0,
               "rep": 1.0, "role": "G", "msg": "hola", "ts": 0.0}
        g1._inbox.append((bcn, g2.ip))
        g1._drain_inbox(3.0)
        peer = g1.router.peers[2]
        self.assertEqual(peer.last_seen, 3.0)
        self.assertEqual(peer.battery, 42.0)
        self.assertEqual(peer.ip, g2.ip)
        self.assertEqual(g1._inbox, [])

    def test_beacon_de_gateway_dado_por_caido_emite_alert_off(self):
        sim = simulacion()
        g1, g2 = sim.nodes[1], sim.nodes[2]
        g1.fault.failed.add(2)
        g1._inbox.append(({"type": "BCN", "node_id": 2}, g2.ip))
        g1._drain_inbox(3.0)
        self.assertNotIn(2, g1.fault.failed)
        self.assertEqual(eventos(sim, "ALERT_OFF"), ["G1 recuperó señal de G2"])

    def test_ogm_nuevo_crea_ruta_y_se_reenvia(self):
        sim = simulacion(roles=("G", "G", "G"))
        g1, g2, g3 = (sim.nodes[i] for i in (1, 2, 3))
        g1._inbox.append((ogm(3, seq=1, ttl=3, path=[3]), g3.ip))
        g1._drain_inbox(1.0)

        ruta = g1.router.routes[3]
        self.assertEqual((ruta.dest, ruta.via_ip, ruta.seq), (3, g3.ip, 1))
        reenviado = [m for m, ip in g2._inbox if ip == g1.ip]
        self.assertEqual(len(reenviado), 1)
        self.assertEqual(reenviado[0]["ttl"], 2)
        self.assertEqual(reenviado[0]["path"], [3, 1])
        self.assertAlmostEqual(reenviado[0]["tq"],
                               g1.router.link_quality(g3.ip))

    def test_ogm_con_ttl_1_no_se_reenvia(self):
        sim = simulacion()
        g1, g2 = sim.nodes[1], sim.nodes[2]
        g1._inbox.append((ogm(2, seq=1, ttl=1), g2.ip))
        g1._drain_inbox(1.0)
        self.assertIn(2, g1.router.routes)
        self.assertEqual(sim.medium.attempted, 0)

    def test_ogm_repetido_se_reenvia_una_sola_vez(self):
        sim = simulacion()
        g1, g2 = sim.nodes[1], sim.nodes[2]
        g1._inbox.append((ogm(2, seq=5), g2.ip))
        g1._inbox.append((ogm(2, seq=5), g2.ip))
        g1._drain_inbox(1.0)
        self.assertEqual(sim.medium.attempted, 1)

    def test_ignora_sus_propios_mensajes(self):
        sim = simulacion()
        g1 = sim.nodes[1]
        g1._inbox.append((ogm(1, seq=1), g1.ip))
        g1._drain_inbox(1.0)
        self.assertEqual(g1.router.routes, {})
        self.assertEqual(sim.medium.attempted, 0)

    def test_alertas_del_ogm_marcan_al_vecino(self):
        sim = simulacion(roles=("G", "G", "G"))
        g1, g2, g3 = (sim.nodes[i] for i in (1, 2, 3))
        g1._inbox.append((ogm(3, seq=1, ttl=1), g3.ip))
        g1._inbox.append((ogm(2, seq=1, ttl=1, alerts=[3]), g2.ip))
        g1._drain_inbox(1.0)
        self.assertTrue(g1.router.peers[3].in_alert)
        self.assertFalse(g1.router.peers[2].in_alert)


class DeteccionCaidasTests(unittest.TestCase):
    def test_gateway_detecta_a_otro_gateway_callado(self):
        sim = simulacion()
        g1, g2 = sim.nodes[1], sim.nodes[2]
        g1._inbox.append(({"type": "BCN", "node_id": 2}, g2.ip))
        g1._drain_inbox(0.0)                      # último contacto en t=0
        now = sim.cfg["timeout"] + 1.0
        silenciar_timers(g1, now)
        g1.tick(now)
        self.assertIn(2, g1.fault.failed)
        self.assertTrue(g1.router.peers[2].in_alert)
        self.assertEqual(eventos(sim, "ALERT_ON"), ["G1 no oye a G2"])

    def test_no_alerta_antes_del_timeout(self):
        sim = simulacion()
        g1, g2 = sim.nodes[1], sim.nodes[2]
        g1._inbox.append(({"type": "BCN", "node_id": 2}, g2.ip))
        g1._drain_inbox(0.0)
        now = sim.cfg["timeout"] - 1.0
        silenciar_timers(g1, now)
        g1.tick(now)
        self.assertEqual(g1.fault.failed, set())
        self.assertEqual(eventos(sim, "ALERT_ON"), [])

    def test_nodo_de_usuario_no_vigila_caidas(self):
        sim = simulacion(roles=("N", "G"))
        n1, g2 = sim.nodes[1], sim.nodes[2]
        n1._inbox.append(({"type": "BCN", "node_id": 2}, g2.ip))
        n1._drain_inbox(0.0)
        now = sim.cfg["timeout"] + 10.0
        silenciar_timers(n1, now)
        n1.tick(now)
        self.assertEqual(n1.fault.failed, set())
        self.assertEqual(eventos(sim, "ALERT_ON"), [])


class MovilidadTests(unittest.TestCase):
    def test_move_speed_0_deja_a_todos_fijos(self):
        sim = simulacion(roles=("G", "N"), separacion=20.0, move_speed=0)
        for _ in range(20):
            for nodo in sim.nodes.values():
                nodo.move(1.0)
        self.assertEqual((sim.nodes[1].x, sim.nodes[1].y), (5.0, 5.0))
        self.assertEqual((sim.nodes[2].x, sim.nodes[2].y), (25.0, 5.0))

    def test_gateway_se_acerca_al_nodo_de_usuario_mas_cercano(self):
        sim = make_simulation([
            {"id": 1, "role": "G", "x": 10.0, "y": 5.0},
            {"id": 2, "role": "N", "x": 30.0, "y": 5.0},   # el más cercano
            {"id": 3, "role": "N", "x": 10.0, "y": 29.0},
        ])
        g, cerca = sim.nodes[1], sim.nodes[2]
        antes = g.dist_to(cerca)
        for _ in range(10):
            g.move(1.0)
        # 10 pasos de 0.32 m hacia N1 (a la derecha), no hacia N2 (arriba)
        self.assertLess(g.dist_to(cerca), antes - 2.0)
        self.assertGreater(g.x, 12.0)
        self.assertLess(abs(g.y - 5.0), 1.0)

    def test_wanderer_va_hacia_la_esquina_hasta_until(self):
        sim = make_simulation(
            [{"id": 1, "role": "G", "x": 10.0, "y": 25.0},
             {"id": 2, "role": "N", "x": 5.0, "y": 25.0}],
            events=[{"type": "wander", "node_id": 1, "until": 50.0}])
        g = sim.nodes[1]
        esquina = (38.0, 2.0)
        antes = math.dist((g.x, g.y), esquina)
        for _ in range(10):
            g.move(1.0)
        self.assertLess(math.dist((g.x, g.y), esquina), antes - 2.0)

    def test_nodo_de_usuario_no_sale_del_edificio(self):
        sim = make_simulation([
            {"id": 1, "role": "G", "x": 20.0, "y": 15.0},
            {"id": 2, "role": "N", "x": 1.0, "y": 0.4},   # en la esquina
        ])
        n = sim.nodes[2]
        for _ in range(300):
            n.move(1.0)
            self.assertTrue(1.0 <= n.x <= sim.ANCHO - 1.0)
            self.assertTrue(0.4 <= n.y <= sim.ALTO - 0.4)

    def test_nodo_caido_no_se_mueve(self):
        sim = simulacion(roles=("G", "N"), separacion=20.0)
        g = sim.nodes[1]
        g.alive = False
        g.move(1.0)
        self.assertEqual((g.x, g.y), (5.0, 5.0))


class IdentidadTests(unittest.TestCase):
    def test_etiqueta_por_rol_e_indice_local(self):
        sim = simulacion(roles=("G", "N", "G", "N"))
        etiquetas = [sim.nodes[i].label for i in (1, 2, 3, 4)]
        self.assertEqual(etiquetas, ["G1", "N1", "G2", "N2"])

    def test_piso_se_deriva_de_y(self):
        sim = simulacion()
        g = sim.nodes[1]
        for y, piso in ((0.0, 1), (9.9, 1), (10.0, 2), (25.0, 3), (30.0, 3)):
            g.y = y
            self.assertEqual(g.piso, piso, f"y={y}")


if __name__ == "__main__":
    unittest.main()
