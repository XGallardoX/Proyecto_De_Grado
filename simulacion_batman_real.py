import argparse
import math
import os
import random
import sys
import time
from collections import defaultdict, deque


import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import batman_node as bn
from batman_node import BatmanRouter, FaultManager, PeerInfo 


# ══════════════════════════════════════════════════════════════════════════
#  PARÁMETROS (todos modificables por CLI o en caliente)
# ══════════════════════════════════════════════════════════════════════════

# Edificio
ANCHO  = 40.0
ALTO   = 30.0
PISO_H = 10.0
N_PISOS = 3
STAIR_XY = (20.0, 15.0)   # hueco de escalera (presente en todos los pisos)
STAIR_HALF_W = 1.7        # mitad del ancho del hueco de escalera (m)

# Tiempo de simulación
DT = 0.5  # segundos de tiempo simulado por paso

# Radio / medio (valores por defecto; el escenario y el CLI los ajustan)
DEFAULTS = dict(
    rango_comm=16.0,     # m: alcance máximo de radio
    perdida_base=0.02,   # prob. de pérdida incluso a 0 m
    falloff=0.85,        # cuánto degrada la fiabilidad con la distancia
    floor_atten=0.55,    # factor de atenuación extra por piso de diferencia
    timeout=30.0,        # s sin señal de un compañero -> caído (regla pedida)
    beacon_cada=2.0,     # s entre beacons de identificación
    batman_cada=4.0,     # s entre OGMs propios (BATMAN)
    heartbeat_cada=8.0,  # s entre "estoy bien" de un rescatista
    ttl=bn.BATMAN_TTL,   # saltos máximos de un OGM (del código real)
    battery_drain=0.030,      # % por segundo (rescatistas)
    battery_drain_surv=0.012, # % por segundo (celular de superviviente)
    rango_deteccion=7.0, # m: contacto físico con un superviviente
    move_speed=0.32,     # m por paso de un rescatista
)

# Colores
C_RESC   = ["#378ADD", "#1D9E75", "#9B59B6", "#E8A838",
            "#2E86C1", "#16A085", "#8E44AD", "#D4AC0D"]
C_SURV   = "#E24B4A"
C_SURV_OK = "#1D9E75"
C_DEAD   = "#8C8B85"
C_ALERT  = "#C0392B"
C_OGM    = "#F0A500"
C_BCN    = "#5DADE2"
C_HB     = "#27AE60"
C_HELP   = "#E74C3C"
C_MSG    = "#9B59B6"   # mensaje personalizado entre nodos (R o S)
C_BG     = "#F8F7F4"
C_WALL   = "#D3D1C7"
C_FLOOR  = "#E8E6E0"


# ══════════════════════════════════════════════════════════════════════════
#  MEDIO RADIO SIMULADO  (reemplaza los sockets UDP broadcast reales)
# ══════════════════════════════════════════════════════════════════════════
class RadioMedium:
    """
    Único componente "no real": entrega los mensajes broadcast entre
    nodos según la distancia 3D y el piso. La pérdida de paquetes hace
    que la calidad de enlace y el TQ de BATMAN se comporten como en la
    realidad.  Lleva la cuenta de paquetes intentados/entregados para
    el análisis posterior.
    """

    def __init__(self, sim, cfg):
        self.sim = sim
        self.cfg = cfg
        self.attempted = 0      # acumulado total
        self.delivered = 0
        self._step_attempt = 0  # contadores del paso actual
        self._step_deliver = 0
        self.packets_visual = []  # animación

    def reset_step_counters(self):
        self._step_attempt = 0
        self._step_deliver = 0

    def reliability(self, a, b):
        """Probabilidad de que un paquete de a llegue a b (0 si fuera de rango)."""
        d = a.dist_to(b)
        rango = self.cfg['rango_comm']
        if d > rango:
            return 0.0
        # fiabilidad cae con la distancia normalizada
        rel = 1.0 - self.cfg['falloff'] * (d / rango)
        rel -= self.cfg['perdida_base']
        # atenuación adicional si están en pisos distintos
        df = abs(a.piso - b.piso)
        if df:
            rel *= self.cfg['floor_atten'] ** df
        return max(0.0, min(1.0, rel))

    def broadcast(self, sender, msg, visual_color=None):
        """
        Difunde msg a todos los nodos vivos en rango (como un broadcast
        UDP en la red ad-hoc real). Devuelve la lista de receptores que
        sí recibieron el paquete.
        """
        recibidos = []
        for node in self.sim.nodes.values():
            if node is sender or not node.alive:
                continue
            rel = self.reliability(sender, node)
            if rel <= 0.0:
                continue
            self.attempted += 1
            self._step_attempt += 1
            if random.random() <= rel:
                self.delivered += 1
                self._step_deliver += 1
                recibidos.append(node)
                node._inbox.append((dict(msg), sender.ip))
        if recibidos and visual_color:
            for r in recibidos:
                self.packets_visual.append(
                    _Packet(sender.x, sender.y, r.x, r.y, visual_color))
        return recibidos


class _Packet:
    """Paquete sólo para la animación (no afecta al protocolo)."""
    __slots__ = ('x', 'y', 'tx', 'ty', 'color', 'age', 'life')

    def __init__(self, x, y, tx, ty, color):
        self.x, self.y, self.tx, self.ty = x, y, tx, ty
        self.color = color
        self.age = 0.0
        self.life = 1.4

    @property
    def progress(self):
        return min(self.age / self.life, 1.0)

    @property
    def pos(self):
        t = self.progress
        return (self.x + (self.tx - self.x) * t,
                self.y + (self.ty - self.y) * t)


# ══════════════════════════════════════════════════════════════════════════
#  NODO SIMULADO  (envuelve el BatmanRouter / FaultManager REALES)
# ══════════════════════════════════════════════════════════════════════════
class SimNode:
    """
    Un dispositivo de la malla. Toda la lógica de enrutamiento y de
    detección de fallos es de batman_node.py (código real). Esta clase
    sólo aporta: posición física, batería, movilidad y el reemplazo de
    los sockets por el RadioMedium.
    """

    def __init__(self, nid, role, x, y, piso, sim):
        # piso ya no se almacena: se deriva de y (los pisos son bandas
        # contiguas en y), así un cambio de piso = mover y a través de
        # la escalera atravesando un muro intermedio.
        del piso
        self.id = nid
        self.role = role            # 'R' (rescatista) o 'S' (superviviente)
        self.x, self.y = x, y
        self.sim = sim
        self.alive = True
        self.battery = 100.0
        self.ip = f"10.0.0.{nid}"

        # ── Estado del protocolo: clases REALES ──
        self.router = BatmanRouter(nid)
        self.fault = FaultManager(nid)

        self._ogm_seq = 0
        self._inbox = []            # (msg, from_ip) entregados por el medio

        # temporizadores escalonados
        self.t_beacon = -random.uniform(0, DEFAULTS['beacon_cada'])
        self.t_ogm = -random.uniform(0, DEFAULTS['batman_cada'])
        self.t_hb = -random.uniform(0, DEFAULTS['heartbeat_cada'])
        self.t_fault = 0.0

        # supervivientes que ESTE nodo encontró físicamente
        self.my_survivors = []
        self.history = []
        self.last_msg = ""          # último texto humano emitido (para UI)

    @property
    def label(self):
        return f"{self.role}{self.sim.local_index[self.id]}"

    @property
    def piso(self):
        """Piso derivado de la coordenada y (1..N_PISOS)."""
        return max(1, min(N_PISOS, int(self.y // PISO_H) + 1))

    def color(self):
        if not self.alive:
            return C_DEAD
        if self.role == 'S':
            return C_SURV_OK if self.id in self.sim.found_ids else C_SURV
        return C_RESC[(self.sim.local_index[self.id] - 1) % len(C_RESC)]

    def dist_to(self, other):
        return math.hypot(self.x - other.x, self.y - other.y)

    def dist_xy(self, x, y, piso=None):
        return math.hypot(self.x - x, self.y - y)

    def _make_ogm(self):
        self._ogm_seq += 1
        return {
            'type': 'OGM', 'origin_id': self.id, 'seq': self._ogm_seq,
            'ttl': self.sim.cfg['ttl'], 'path': [self.id],
            'battery': self.battery, 'load': 0,
            'reputation': 1.0, 'tq': 1.0,
            'survivors': list(self.my_survivors),
            'alerts': list(self.fault.failed),
            'ts': self.sim.t,
        }

    def _make_bcn(self, texto):
        return {
            'type': 'BCN', 'node_id': self.id, 'battery': self.battery,
            'load': 0, 'rep': 1.0, 'role': self.role,
            'msg': texto, 'ts': self.sim.t,
        }

    # ── un paso de tiempo ──
    def tick(self, now):
        if not self.alive:
            return
        drain = (self.sim.cfg['battery_drain'] if self.role == 'R'
                 else self.sim.cfg['battery_drain_surv'])
        self.battery = max(0.0, self.battery - drain * DT)
        if self.battery <= 0:
            self.alive = False
            self.sim.event('FAIL', f"{self.label} sin batería")
            self.sim.log(f"{self.label} se quedó sin batería", "error")
            return

        self._drain_inbox(now)

        if now - self.t_beacon >= self.sim.cfg['beacon_cada']:
            self.t_beacon = now
            if self.role == 'R':
                txt = f"Hola, soy el rescatista {self.label}"
            else:
                txt = f"AYUDA, soy superviviente {self.label}"
            self.last_msg = txt
            self.sim.medium.broadcast(self, self._make_bcn(txt), C_BCN)

        if self.role == 'R' and now - self.t_hb >= self.sim.cfg['heartbeat_cada']:
            self.t_hb = now
            self.sim.medium.broadcast(
                self, self._make_bcn("estoy bien"), C_HB)

        if now - self.t_ogm >= self.sim.cfg['batman_cada']:
            self.t_ogm = now
            self.sim.medium.broadcast(self, self._make_ogm(), C_OGM)

        if now - self.t_fault >= 5.0 and self.role == 'R':
            self.t_fault = now
            peers = [p for p in self.router.peers.values()
                     if self.sim.is_rescuer(p.node_id)]
            nuevos = self.fault.check(peers, now)
            for fid in nuevos:
                self.router.mark_alert(fid)
                lbl = self.sim.label_of(fid)
                self.sim.event('ALERT_ON', f"{self.label} no oye a {lbl}")
                self.sim.log(
                    f"⚠ {self.label}: sin señal de {lbl} > "
                    f"{self.sim.cfg['timeout']:.0f}s — ¿necesita ayuda?",
                    "error")

    def _drain_inbox(self, now):
        """Procesa los mensajes entregados por el medio.

        Réplica fiel de MeshNode._handle_bcast de batman_node.py:
        usa router.receive_ogm(), reenvía si es nuevo y ttl>1, y
        actualiza/recupera pares con los beacons.
        """
        inbox, self._inbox = self._inbox, []
        for msg, from_ip in inbox:
            mt = msg.get('type')
            src = msg.get('node_id') or msg.get('origin_id')
            if src == self.id:
                continue

            if mt == 'BCN':
                nid = msg['node_id']
                with self.router._lock:
                    if nid not in self.router.peers:
                        self.router.peers[nid] = PeerInfo(
                            node_id=nid, ip=from_ip, last_seen=now)
                    p = self.router.peers[nid]
                    p.last_seen = now
                    p.ip = from_ip
                    p.battery = msg.get('battery', 100.0)
                    p.load = msg.get('load', 0)
                    p.reputation = msg.get('rep', 1.0)
                    if p.in_alert:
                        p.in_alert = False


                genuino = nid in self.fault.failed
                self.fault.recover(nid, now)
                if genuino and self.role == 'R' and \
                        self.sim.is_rescuer(nid):
                    lbl = self.sim.label_of(nid)
                    self.sim.event('ALERT_OFF',
                                   f"{self.label} recuperó señal de {lbl}")
                    self.sim.log(
                        f"{self.label}: señal de {lbl} recuperada", "ok")

            elif mt == 'OGM':
                is_new = self.router.receive_ogm(msg, from_ip, now)
                if is_new and msg.get('ttl', 0) > 1:
                    fwd = dict(msg)
                    fwd['ttl'] = msg['ttl'] - 1
                    fwd['path'] = msg['path'] + [self.id]
                    fwd['tq'] = msg.get('tq', 1.0) * \
                        self.router.link_quality(from_ip)
                    self.sim.medium.broadcast(self, fwd, C_OGM)
                for sid in msg.get('survivors', []):
                    self.sim.register_found(sid, msg['origin_id'])
                for aid in msg.get('alerts', []):
                    self.router.mark_alert(aid)

    # ── movilidad con colisiones ──
    def move(self, now):
        if not self.alive:
            return

        if self.role == 'S':
            # supervivientes atrapados: micro-movimiento (sin chocar)
            for _ in range(3):
                dx, dy = random.gauss(0, 0.05), random.gauss(0, 0.05)
                if self._try_move(dx, dy):
                    break
        else:
            # destino: esquina (wanderer) o superviviente más cercano
            if self is self.sim.wanderer and now < self.sim.wander_until:
                tx, ty = 38.0, 2.0
            else:
                objetivos = [s for s in self.sim.nodes.values()
                             if s.role == 'S'
                             and s.id not in self.sim.found_ids]
                if objetivos:
                    tgt = min(objetivos,
                              key=lambda s: self.dist_xy(s.x, s.y))
                    tx, ty = tgt.x, tgt.y
                else:
                    # patrullar: pequeño paso aleatorio sin chocar
                    for _ in range(4):
                        ang = random.uniform(0, 2 * math.pi)
                        sp = self.sim.cfg['move_speed'] * 0.6
                        if self._try_move(sp * math.cos(ang),
                                          sp * math.sin(ang)):
                            break
                    self._record_history()
                    return

            my_band = self.piso
            tgt_band = max(1, min(N_PISOS, int(ty // PISO_H) + 1))
            if my_band != tgt_band and \
                    abs(self.x - STAIR_XY[0]) > STAIR_HALF_W * 0.6:
                tx_eff, ty_eff = STAIR_XY[0], ty
            else:
                tx_eff, ty_eff = tx, ty
            self._move_avoiding(tx_eff, ty_eff)

        self._record_history()

    def _record_history(self):
        self.history.append((self.x, self.y))
        if len(self.history) > 80:
            self.history.pop(0)

    def _try_move(self, dx, dy):
        """Intenta un paso: rechaza si sale del edificio o colisiona."""
        nx = self.x + dx
        ny = self.y + dy
        if not (1.0 <= nx <= ANCHO - 1.0): return False
        if not (0.4 <= ny <= ALTO - 0.4): return False
        if self.sim.segment_blocked(self.x, self.y, nx, ny):
            return False
        self.x, self.y = nx, ny
        return True

    def _move_avoiding(self, tx, ty):
        """Mueve hacia (tx,ty) sorteando muros/escombros.

        Si el paso recto no es válido se prueban ángulos de desvío;
        si nada funciona el rescatista se queda quieto (atascado)."""
        sp = self.sim.cfg['move_speed']
        base = math.atan2(ty - self.y, tx - self.x)
        for k_deg in (0, 20, -20, 45, -45, 75, -75,
                      110, -110, 150, -150, 180):
            a = base + math.radians(k_deg)
            jx = random.gauss(0, 0.04)
            jy = random.gauss(0, 0.04)
            if self._try_move(sp * math.cos(a) + jx,
                              sp * math.sin(a) + jy):
                return True
        return False


# ══════════════════════════════════════════════════════════════════════════
#  REGISTRADOR DE MÉTRICAS  (para el análisis posterior)
# ══════════════════════════════════════════════════════════════════════════
class Recorder:
    def __init__(self):
        self.t = []
        self.alive_R = []
        self.alive_S = []
        self.comp_R = []            
        self.surv_reach = []        
        self.avg_tq = []
        self.avg_hops = []
        self.max_silence = []       
        self.deliver_ratio = []     
        self.alerts_active = []
        self.found_cum = []
        self.events = []            

    def event(self, t, tipo, texto):
        self.events.append((t, tipo, texto))

    def sample(self, sim, medium):
        self.t.append(sim.t)
        rescuers = [n for n in sim.nodes.values() if n.role == 'R']
        survs = [n for n in sim.nodes.values() if n.role == 'S']
        self.alive_R.append(sum(1 for n in rescuers if n.alive))
        self.alive_S.append(sum(1 for n in survs if n.alive))
        self.comp_R.append(sim.rescuer_components())
        self.surv_reach.append(sim.survivors_in_mesh())

        tqs, hops = [], []
        for n in rescuers:
            if not n.alive:
                continue
            with n.router._lock:
                for r in n.router.routes.values():
                    tqs.append(r.tq)
                    hops.append(r.hops)
        self.avg_tq.append(sum(tqs) / len(tqs) if tqs else 0.0)
        self.avg_hops.append(sum(hops) / len(hops) if hops else 0.0)

        # cuánto lleva el rescatista más "callado" sin que otro lo oiga
        sil = 0.0
        for n in rescuers:
            if not n.alive:
                continue
            for m in rescuers:
                if m is n or not m.alive:
                    continue
                p = m.router.peers.get(n.id)
                if p is not None:
                    sil = max(sil, sim.t - p.last_seen)
        self.max_silence.append(sil)

        at, dl = medium._step_attempt, medium._step_deliver
        self.deliver_ratio.append(dl / at if at else 1.0)

        self.alerts_active.append(sum(
            1 for n in rescuers if n.alive
            for p in n.router.peers.values() if p.in_alert))
        self.found_cum.append(len(sim.found_ids))


# ══════════════════════════════════════════════════════════════════════════
#  SIMULACIÓN
# ══════════════════════════════════════════════════════════════════════════
SCENARIOS = ['base', 'colapso_progresivo', 'particion',
             'rescatista_perdido', 'denso']


class Simulation:
    def __init__(self, escenario='base', cfg=None):
        self.escenario = escenario
        self.cfg = dict(DEFAULTS)
        if cfg:
            self.cfg.update(cfg)
        self._base_cfg = dict(self.cfg)
        self._build_world()

    # ── construir el mundo según el escenario ──
    def _build_world(self):

        self.cfg = dict(self._base_cfg)

        # aplicar el timeout pedido al CÓDIGO REAL (lo lee PeerInfo.is_lost
        # y FaultManager.check desde el espacio de nombres de batman_node)
        bn.TIMEOUT_ALERT = self.cfg['timeout']

        self.t = 0.0
        self.paused = False
        self.nodes = {}
        self.local_index = {}     # id global -> índice local por rol (1..n)
        self.found_ids = set()    # ids de supervivientes ya hallados
        self.found_by = {}
        self.log_lines = []
        self.recorder = Recorder()
        self.medium = RadioMedium(self, self.cfg)
        self.wanderer = None
        self.wander_until = -1.0
        self._prev_components = 1
        self._last_part_evt = -100.0


        esc = self.escenario
        if esc == 'base':
            R = [(1, 7, 27, 3), (2, 11, 27, 3), (3, 9, 24, 3), (4, 13, 25, 3)]
            S = [(101, 34, 3, 1), (102, 5, 5, 1), (103, 33, 15, 2)]
        elif esc == 'colapso_progresivo':
            R = [(1, 7, 27, 3), (2, 11, 27, 3), (3, 9, 24, 3), (4, 13, 25, 3)]
            S = [(101, 34, 3, 1), (102, 5, 5, 1), (103, 33, 15, 2)]
            self.cfg['battery_drain'] = 0.45   # baterías caen rápido
        elif esc == 'particion':
            # dos equipos lejos; sólo se unen si un rescatista hace puente
            R = [(1, 6, 27, 3), (2, 9, 24, 3), (3, 34, 5, 1), (4, 31, 4, 1)]
            S = [(101, 5, 22, 3), (102, 37, 7, 1), (103, 20, 14, 2)]
            self.cfg['rango_comm'] = 11.0
        elif esc == 'rescatista_perdido':
            R = [(1, 7, 27, 3), (2, 11, 27, 3), (3, 9, 24, 3), (4, 13, 25, 3)]
            S = [(101, 34, 3, 1), (102, 5, 5, 1), (103, 33, 15, 2)]
        elif esc == 'denso':
            R = [(1, 6, 27, 3), (2, 11, 27, 3), (3, 16, 26, 3),
                 (4, 9, 24, 3), (5, 14, 23, 3), (6, 8, 20, 3),
                 (7, 13, 19, 3), (8, 11, 16, 3)]
            S = [(101, 4, 4, 1), (102, 36, 4, 1), (103, 35, 26, 3),
                 (104, 33, 14, 2), (105, 6, 13, 2), (106, 20, 4, 1)]
        else:
            raise ValueError(f"Escenario desconocido: {esc}")

        ri = si = 0
        for nid, x, y, p in R:
            ri += 1
            n = SimNode(nid, 'R', float(x), float(y), p, self)
            self.local_index[nid] = ri
            self.nodes[nid] = n
        for nid, x, y, p in S:
            si += 1
            n = SimNode(nid, 'S', float(x), float(y), p, self)
            self.local_index[nid] = si
            self.nodes[nid] = n

        if esc == 'colapso_progresivo':
            # baterías escalonadas -> los rescatistas caen uno a uno y
            # se ve a BATMAN reconvergiendo tras cada pérdida
            for nid, bat in [(1, 100.0), (2, 78.0), (3, 56.0), (4, 38.0)]:
                self.nodes[nid].battery = bat
            self.log("Escenario: baterías desiguales; los rescatistas "
                     "caerán de forma escalonada.", "warn")

        if esc == 'rescatista_perdido':
            # el rescatista 4 se interna lejos entre t=20 y t=80
            self.wanderer = self.nodes[4]
            self.wander_until = 80.0
            self.log("Escenario: el rescatista R4 se internará lejos "
                     "(t=20..80) y dejará de dar señal.", "warn")


        self._init_obstacles(esc)

        self.log(f"Escenario '{esc}' iniciado · {ri} rescatistas, "
                 f"{si} supervivientes · timeout={self.cfg['timeout']:.0f}s",
                 "info")
        self.log("Protocolo BATMAN: clases reales de batman_node.py "
                 "(BatmanRouter + FaultManager).", "info")

    # ── utilidades ──
    def label_of(self, nid):
        n = self.nodes.get(nid)
        return n.label if n else f"?{nid}"

    def is_rescuer(self, nid):
        n = self.nodes.get(nid)
        return bool(n and n.role == 'R')

    # ── Obstáculos físicos (losas con escalera + escombros) ──────────────
    def _init_obstacles(self, esc):
        """Coloca losas inter-piso con hueco de escalera + escombros
        aleatorios pero reproducibles. Los escombros nunca se generan
        encima de un nodo, del hueco de escalera o de un superviviente."""
        sx, _sy = STAIR_XY

        self.walls = []
        for y_losa in [PISO_H, 2 * PISO_H]:
            self.walls.append((y_losa, 0.0, sx - STAIR_HALF_W))
            self.walls.append((y_losa, sx + STAIR_HALF_W, ANCHO))

        # Escombros: círculos con (cx, cy, r). Cantidad por escenario.
        cantidad = {'base': 22, 'rescatista_perdido': 22,
                    'colapso_progresivo': 22, 'particion': 26,
                    'denso': 28}.get(esc, 22)
        rng = random.Random(hash(('debris', esc)) & 0xFFFFFFFF)
        self.debris = []
        # zonas a respetar: posiciones iniciales de los nodos + escalera
        bloqueadas = [(n.x, n.y, 2.4) for n in self.nodes.values()]
        bloqueadas.append((sx, PISO_H, 2.2))
        bloqueadas.append((sx, 2 * PISO_H, 2.2))
        intentos = 0
        while len(self.debris) < cantidad and intentos < cantidad * 25:
            intentos += 1
            cx = rng.uniform(2.5, ANCHO - 2.5)
            cy = rng.uniform(1.0, ALTO - 1.0)
            r = rng.uniform(0.7, 1.5)
            # no pegado a una losa ni dentro de la escalera
            if min(abs(cy - PISO_H), abs(cy - 2 * PISO_H)) < r + 0.4:
                continue
            if abs(cx - sx) < STAIR_HALF_W + r + 0.3:
                continue
            ok = True
            for (bx, by, br) in bloqueadas:
                if math.hypot(cx - bx, cy - by) < r + br:
                    ok = False
                    break
            if not ok:
                continue
            for (ox, oy, orad) in self.debris:
                if math.hypot(cx - ox, cy - oy) < r + orad + 0.2:
                    ok = False
                    break
            if ok:
                self.debris.append((cx, cy, r))

    def collides_point(self, x, y):
        """¿El punto (x,y) está dentro de un escombro?"""
        for (cx, cy, r) in self.debris:
            if (x - cx) ** 2 + (y - cy) ** 2 < r * r:
                return True
        return False

    def segment_blocked(self, x0, y0, x1, y1):
        """¿El segmento (x0,y0)→(x1,y1) cruza un muro o un escombro?"""
        # 1) muros horizontales con hueco de escalera
        for (yw, xa, xb) in self.walls:
            if (y0 - yw) * (y1 - yw) < 0:    # cruzan el nivel del muro
                t = (yw - y0) / (y1 - y0)
                xi = x0 + t * (x1 - x0)
                if xa <= xi <= xb:
                    return True
        # 2) escombros (distancia punto-segmento < radio)
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        for (cx, cy, r) in self.debris:
            if L2 < 1e-9:
                d2 = (cx - x0) ** 2 + (cy - y0) ** 2
            else:
                t = max(0.0, min(1.0,
                        ((cx - x0) * dx + (cy - y0) * dy) / L2))
                px = x0 + t * dx
                py = y0 + t * dy
                d2 = (cx - px) ** 2 + (cy - py) ** 2
            if d2 < r * r:
                return True
        return False

    def register_found(self, sid, by_id):
        if sid in self.nodes and self.nodes[sid].role == 'S' \
                and sid not in self.found_ids:
            self.found_ids.add(sid)
            self.found_by[sid] = by_id
            self.event('FOUND',
                       f"{self.label_of(sid)} hallado por "
                       f"{self.label_of(by_id)}")
            self.log(f"Superviviente {self.label_of(sid)} hallado por "
                     f"{self.label_of(by_id)} — propagado por OGM", "ok")

    # ── Mensajes personalizados entre cualquier par de nodos ──────────
    def send_unicast(self, from_id, to_id, texto):
        """Envía un mensaje libre de un nodo a otro (rescatista o
        superviviente). GARANTÍA: si existe ALGÚN camino por la malla
        —directo o multi-salto a través de nodos intermedios— el mensaje
        llega. El camino se calcula con BFS sobre el grafo de conectividad
        actual (mismos enlaces que cuentan para el panel de conectividad),
        así que "se ve conectado" ⟺ "el mensaje llega". Sólo falla si el
        destino está caído o la malla está realmente partida."""
        a = self.nodes.get(from_id)
        b = self.nodes.get(to_id)
        if a is None or b is None:
            self.log(f"Mensaje: id inválido ({from_id}→{to_id})", "error")
            return
        if from_id == to_id:
            self.log("Mensaje a sí mismo, ignorado.", "warn")
            return
        if not a.alive:
            self.log(f"{a.label} no puede enviar (caído).", "error")
            return
        if not b.alive:
            self.event('MSG_FAIL', f"{a.label}→{b.label}: destino caído")
            self.log(f"Mensaje {a.label}→{b.label} no entregado: "
                     f"{b.label} está caído.", "error")
            return

        path = self._shortest_path(from_id, to_id)
        if path is None:
            self.event('MSG_FAIL',
                       f"{a.label}→{b.label}: sin camino (malla partida)")
            self.log(f"Mensaje {a.label}→{b.label} no entregado: no existe "
                     f"ningún camino en la malla (partición de red).",
                     "error")
            return

        # Hay camino físico → el mensaje SIEMPRE llega. La animación
        # visible (que viaja salto a salto y deja el texto en el destino)
        # la dibuja el Visualizer con reloj de pared; aquí sólo registramos
        # el evento/log y devolvemos el camino para que lo anime.
        hops = len(path) - 1
        via = " → ".join(self.label_of(i) for i in path)
        # Nota didáctica: ¿la tabla BATMAN del origen ya tenía esta ruta?
        converged = a.router.routes.get(to_id) is not None
        modo = ("ruta BATMAN convergida" if converged
                else "entregado por la malla (BATMAN aún converge)")
        self.event('MSG_OK', f"{a.label}→{b.label} ({hops} "
                   f"salto{'s' if hops != 1 else ''}): {texto[:60]}")
        # El TEXTO va primero (justo tras de→a) para que se vea aunque el
        # panel recorte la línea; el detalle de ruta va al final. Marcador
        # "»" en vez de emoji (Consolas no tiene glifo para 📨 → cuadro tofu).
        self.log(f"» {a.label}→{b.label}: \"{texto}\"  "
                 f"({hops} salto{'s' if hops != 1 else ''} vía {via}; {modo})",
                 "ok")
        return path

    def _shortest_path(self, src_id, dst_id):
        """BFS de menor nº de saltos sobre el grafo de conectividad actual:
        nodos vivos, enlaces con reliability > 0 (idéntico criterio que
        _union_find / el panel de conectividad). Devuelve la lista de ids
        [src, ..., dst] o None si no hay ningún camino."""
        src = self.nodes.get(src_id)
        dst = self.nodes.get(dst_id)
        if (src is None or dst is None or not src.alive or not dst.alive):
            return None
        if src_id == dst_id:
            return [src_id]
        alive = [n for n in self.nodes.values() if n.alive]
        prev = {src_id: None}
        q = deque([src])
        while q:
            cur = q.popleft()
            if cur.id == dst_id:
                break
            for nb in alive:
                if nb.id in prev:
                    continue
                if self.medium.reliability(cur, nb) > 0.0:
                    prev[nb.id] = cur.id
                    q.append(nb)
        if dst_id not in prev:
            return None
        path = []
        node = dst_id
        while node is not None:
            path.append(node)
            node = prev[node]
        path.reverse()
        return path

    def _union_find(self):
        """Union-find sobre TODOS los nodos vivos según los enlaces de
        radio utilizables. Devuelve (nodos_vivos, función find, idx)."""
        alive = [n for n in self.nodes.values() if n.alive]
        idx = {n.id: i for i, n in enumerate(alive)}
        parent = list(range(len(alive)))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        for i, a in enumerate(alive):
            for b in alive[i + 1:]:
                if self.medium.reliability(a, b) > 0.0:
                    ra, rb = find(idx[a.id]), find(idx[b.id])
                    if ra != rb:
                        parent[ra] = rb
        return alive, find, idx

    def rescuer_components(self):
        """Nº de componentes conexas considerando SÓLO rescatistas.
        1 = el equipo está totalmente conectado; >1 = malla partida."""
        alive, find, idx = self._union_find()
        roots = {find(idx[n.id]) for n in alive if n.role == 'R'}
        return len(roots) if roots else 0

    def survivors_in_mesh(self):
        """Cuántos supervivientes vivos comparten componente con algún
        rescatista (la malla puede enrutar hasta ellos)."""
        alive, find, idx = self._union_find()
        resc_roots = {find(idx[n.id]) for n in alive if n.role == 'R'}
        return sum(1 for n in alive if n.role == 'S'
                   and find(idx[n.id]) in resc_roots)

    # ── paso principal ──
    def step(self):
        if self.paused:
            return
        self.t += DT
        self.medium.reset_step_counters()

        for n in self.nodes.values():
            n.move(self.t)
        for n in self.nodes.values():
            n.tick(self.t)

        # detección física de supervivientes por proximidad
        for r in self.nodes.values():
            if r.role != 'R' or not r.alive:
                continue
            for s in self.nodes.values():
                # un superviviente con el móvil caído no emite señal: no
                # puede ser hallado por proximidad hasta que reviva
                if s.role != 'S' or not s.alive or s.id in self.found_ids:
                    continue
                if r.dist_to(s) <= self.cfg['rango_deteccion']:
                    if s.id not in r.my_survivors:
                        r.my_survivors.append(s.id)
                    self.register_found(s.id, r.id)

        # detectar particiones / reunificaciones de la malla de
        # rescatistas (esto es lo que BATMAN "ve" y reorganiza)
        comps = self.rescuer_components()
        # anti-rebote: no registrar transiciones más seguido que cada 6 s
        if self.t - self._last_part_evt >= 6.0:
            if comps > self._prev_components and comps > 1:
                self._last_part_evt = self.t
                self.event('PARTITION',
                           f"Malla de rescatistas partida en {comps} grupos")
                self.log(f"⚠ La malla de rescatistas se partió "
                         f"en {comps} grupos", "error")
            elif comps < self._prev_components and comps == 1:
                self._last_part_evt = self.t
                self.event('HEAL', "Malla de rescatistas reunificada")
                self.log("La malla de rescatistas se reunificó "
                         "(BATMAN reconvergió)", "ok")
        self._prev_components = comps

        # envejecer paquetes visuales
        pv = self.medium.packets_visual
        for p in pv:
            p.age += DT
        self.medium.packets_visual = [p for p in pv if p.age < p.life]

        self.recorder.sample(self, self.medium)

    # ── operaciones interactivas ──
    def fail_node(self, nid):
        n = self.nodes.get(nid)
        if not n or not n.alive:
            return
        n.alive = False
        n.battery = 0.0
        self.event('FAIL', f"{n.label} caído (manual)")
        self.log(f"ACCIDENTE: {n.label} dejó de responder", "error")

    def recover_node(self, nid):
        n = self.nodes.get(nid)
        if not n or n.alive:
            return
        n.alive = True
        n.battery = max(n.battery, 60.0)
        n._ogm_seq = 0
        n.router.seen_ogms.clear()
        self.event('RECOVER', f"{n.label} recuperado (manual)")
        self.log(f"{n.label} vuelve a la red — BATMAN reconverge", "ok")

    def set_param(self, clave, valor):
        self.cfg[clave] = valor
        if clave == 'timeout':
            bn.TIMEOUT_ALERT = valor
        self.event('PARAM', f"{clave} = {valor}")
        self.log(f"Parámetro {clave} = {valor}", "warn")

    def event(self, tipo, texto):
        self.recorder.event(self.t, tipo, texto)

    def log(self, msg, tipo="info"):
        self.log_lines.append((self.t, msg, tipo))
        if len(self.log_lines) > 300:
            self.log_lines.pop(0)

    def summary(self):
        aliveR = sum(1 for n in self.nodes.values()
                     if n.role == 'R' and n.alive)
        totR = sum(1 for n in self.nodes.values() if n.role == 'R')
        totS = sum(1 for n in self.nodes.values() if n.role == 'S')
        return dict(t=self.t, aliveR=aliveR, totR=totR,
                    found=len(self.found_ids), totS=totS,
                    comps=self._prev_components)


# ══════════════════════════════════════════════════════════════════════════
#  FIGURA DE ANÁLISIS  (post-ejecución, lo que pide el profe)
# ══════════════════════════════════════════════════════════════════════════
EVENT_STYLE = {
    'FAIL':      ('#C0392B', '-'),
    'RECOVER':   ('#1D9E75', '-'),
    'ALERT_ON':  ('#E67E22', ':'),
    'ALERT_OFF': ('#2ECC71', ':'),
    'FOUND':     ('#2980B9', '--'),
    'PARTITION': ('#8E44AD', '-.'),
    'HEAL':      ('#16A085', '-.'),
    'SCENARIO':  ('#555', '-'),
    'PARAM':     ('#999', ':'),
}


def _mark_events(ax, events, tipos):
    for (t, tipo, _txt) in events:
        if tipo in tipos:
            col, ls = EVENT_STYLE.get(tipo, ('#888', ':'))
            ax.axvline(t, color=col, linestyle=ls, linewidth=1.0, alpha=0.55)


def build_analysis_figure(sim):
    """Construye la figura de 6 paneles que explica el comportamiento de
    la red a lo largo del tiempo y la guarda como PNG."""
    rec = sim.recorder
    t = np.array(rec.t)
    if len(t) < 2:
        return None

    fig = plt.figure(figsize=(16, 10), facecolor=C_BG)
    fig.suptitle(
        f"Análisis de la red ad-hoc BATMAN · escenario '{sim.escenario}' · "
        f"timeout={sim.cfg['timeout']:.0f}s  rango={sim.cfg['rango_comm']:.0f}m  "
        f"falloff={sim.cfg['falloff']:.2f}",
        fontsize=13, y=0.985)
    gs = fig.add_gridspec(3, 2, hspace=0.42, wspace=0.20,
                          left=0.07, right=0.97, top=0.92, bottom=0.06)

    # 1) Nodos vivos en el tiempo
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.step(t, rec.alive_R, where='post', color='#378ADD',
             label='Rescatistas vivos', linewidth=1.8)
    ax1.step(t, rec.alive_S, where='post', color='#E24B4A',
             label='Supervivientes (nodo) vivos', linewidth=1.4)
    _mark_events(ax1, rec.events, {'FAIL', 'RECOVER'})
    ax1.set_title("1 · Nodos activos en el tiempo "
                  "(líneas: caída roja / recuperación verde)")
    ax1.set_ylabel("nº de nodos")
    ax1.set_xlabel("tiempo (s)")
    ax1.legend(fontsize=8, loc='lower left')
    ax1.grid(alpha=0.25)

    # 2) Conectividad de la malla de rescatistas + supervivientes
    #    alcanzables por la red
    ax2 = fig.add_subplot(gs[0, 1])
    comp = np.array(rec.comp_R)
    ax2.step(t, comp, where='post', color='#8E44AD', linewidth=1.8,
             label='Componentes de la malla de rescatistas')
    ax2.fill_between(t, 1, comp, step='post', where=comp > 1,
                     color='#8E44AD', alpha=0.18, label='Malla partida')
    ax2.axhline(1, color='#16A085', linestyle='--', linewidth=1,
                label='Malla unida (1 grupo)')
    ax2.step(t, rec.surv_reach, where='post', color='#E24B4A',
             linewidth=1.3, label='Supervivientes alcanzables por la malla')
    _mark_events(ax2, rec.events, {'PARTITION', 'HEAL'})
    ax2.set_title("2 · Auto-reorganización de la malla "
                  "(1 = equipo conectado; >1 = partición BATMAN)")
    ax2.set_ylabel("nº")
    ax2.set_xlabel("tiempo (s)")
    ax2.legend(fontsize=7, loc='upper left')
    ax2.grid(alpha=0.25)

    # 3) Calidad de enrutamiento BATMAN: TQ medio y saltos medios
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.plot(t, rec.avg_tq, color='#1D9E75', linewidth=1.6,
             label='TQ medio de rutas')
    ax3.set_ylabel("TQ medio", color='#1D9E75')
    ax3.tick_params(axis='y', labelcolor='#1D9E75')
    ax3.set_xlabel("tiempo (s)")
    ax3b = ax3.twinx()
    ax3b.plot(t, rec.avg_hops, color='#E8A838', linewidth=1.4,
              linestyle='--', label='Saltos medios')
    ax3b.set_ylabel("saltos medios", color='#E8A838')
    ax3b.tick_params(axis='y', labelcolor='#E8A838')
    _mark_events(ax3, rec.events, {'FAIL', 'RECOVER', 'PARTITION', 'HEAL'})
    ax3.set_title("3 · Enrutamiento BATMAN: calidad (TQ) y longitud de ruta")
    ax3.grid(alpha=0.25)

    # 4) Silencio máximo entre rescatistas vs umbral de timeout
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.plot(t, rec.max_silence, color='#C0392B', linewidth=1.5,
             label='Máx. s sin oír a un rescatista')
    ax4.axhline(sim.cfg['timeout'], color='#000', linestyle='--',
                linewidth=1.2,
                label=f"Umbral caída ({sim.cfg['timeout']:.0f}s)")
    alerts = np.array(rec.alerts_active)
    ax4.fill_between(t, 0, ax4.get_ylim()[1], where=alerts > 0,
                     color='#E67E22', alpha=0.15,
                     label='Alerta activa', step='post')
    ax4.set_title("4 · Detección de rescatista perdido (regla del heartbeat)")
    ax4.set_ylabel("segundos")
    ax4.set_xlabel("tiempo (s)")
    ax4.legend(fontsize=8, loc='upper left')
    ax4.grid(alpha=0.25)

    # 5) Calidad del medio: ratio de entrega de paquetes
    ax5 = fig.add_subplot(gs[2, 0])
    dr = np.array(rec.deliver_ratio)
    ax5.plot(t, dr, color='#888', linewidth=0.7, alpha=0.5,
             label='Ratio entrega (por paso)')
    if len(dr) >= 9:
        k = 9
        mov = np.convolve(dr, np.ones(k) / k, mode='same')
        ax5.plot(t, mov, color='#2980B9', linewidth=1.8,
                 label='Media móvil')
    ax5.set_ylim(-0.02, 1.05)
    ax5.set_title("5 · Calidad del medio radio "
                  "(paquetes entregados / intentados)")
    ax5.set_ylabel("ratio de entrega")
    ax5.set_xlabel("tiempo (s)")
    ax5.legend(fontsize=8, loc='lower left')
    ax5.grid(alpha=0.25)

    # 6) Supervivientes hallados (acumulado) + eventos
    ax6 = fig.add_subplot(gs[2, 1])
    ax6.step(t, rec.found_cum, where='post', color='#1D9E75',
             linewidth=2.0, label='Supervivientes hallados')
    _mark_events(ax6, rec.events,
                 {'FOUND', 'FAIL', 'RECOVER', 'SCENARIO'})
    for (et, tipo, txt) in rec.events:
        if tipo == 'FOUND':
            ax6.annotate(txt.split(' hallado')[0], (et, 0),
                         rotation=90, fontsize=6, color='#2980B9',
                         va='bottom', ha='right')
    ax6.set_title("6 · Progreso del rescate (líneas: hallazgo / caídas)")
    ax6.set_ylabel("nº hallados")
    ax6.set_xlabel("tiempo (s)")
    ax6.legend(fontsize=8, loc='upper left')
    ax6.grid(alpha=0.25)

    ts = time.strftime('%Y%m%d_%H%M%S')
    fname = f"analisis_red_{sim.escenario}_{ts}.png"
    fig.savefig(fname, dpi=110)
    return fname


# ══════════════════════════════════════════════════════════════════════════
#  INSPECTOR DE TEXTO  (volcado de las partes internas de la red ad-hoc)
# ══════════════════════════════════════════════════════════════════════════
def snapshot_red(sim):
    """Devuelve, en TEXTO, una instantánea del estado interno de la red
    ad-hoc tal como lo 've' el protocolo: conectividad de la malla, enlaces
    de radio, y por cada nodo sus vecinos (PeerInfo), su tabla de rutas
    BATMAN (RouteEntry), sus alertas (FaultManager.failed) y los
    supervivientes que encontró. Todo sale de las estructuras REALES
    (router.peers, router.routes, fault.failed).

    Salida en ASCII puro a propósito: así se imprime/redirige sin romperse
    en consolas Windows (cp1252) — útil con `--inspect > red.txt`.
    """
    nodes = sim.nodes
    lbl = sim.label_of
    R = [n for n in nodes.values() if n.role == 'R']
    S = [n for n in nodes.values() if n.role == 'S']
    aliveR = sum(1 for n in R if n.alive)
    aliveS = sum(1 for n in S if n.alive)
    deliv, att = sim.medium.delivered, sim.medium.attempted
    pct = (100.0 * deliv / att) if att else 100.0

    out = []
    w = out.append

    def tabla(headers, rows, indent="    "):
        cols = len(headers)
        wid = [len(str(h)) for h in headers]
        for r in rows:
            for i in range(cols):
                wid[i] = max(wid[i], len(str(r[i])))
        ls = [indent + "  ".join(str(headers[i]).ljust(wid[i]) for i in range(cols)),
              indent + "  ".join("-" * wid[i] for i in range(cols))]
        for r in rows:
            ls.append(indent + "  ".join(str(r[i]).ljust(wid[i]) for i in range(cols)))
        return ls

    w("=" * 72)
    w(f" RED AD-HOC - INSTANTANEA  .  escenario '{sim.escenario}'  .  t = {sim.t:.1f} s")
    w(f" Rescatistas vivos: {aliveR}/{len(R)}   "
      f"Supervivientes vivos: {aliveS}/{len(S)}   "
      f"Hallados: {len(sim.found_ids)}/{len(S)}")
    w(f" Paquetes de radio (acumulado): {deliv}/{att} entregados ({pct:.0f}%)")
    w("=" * 72)
    w("")

    # ── conectividad de la malla ──
    w("[ CONECTIVIDAD DE LA MALLA ]")
    w(f"  Componentes de rescatistas : {sim.rescuer_components()}   "
      f"(1 = malla entera, >1 = partida)")
    w(f"  Supervivientes alcanzables : {sim.survivors_in_mesh()}/{len(S)}")
    alive, find, idx = sim._union_find()
    groups = {}
    for n in alive:
        groups.setdefault(find(idx[n.id]), []).append(n)
    glist = sorted(groups.values(), key=lambda g: (-len(g), min(x.id for x in g)))
    w("  Grupos conexos (se alcanzan entre si por radio):")
    for gi, g in enumerate(glist, 1):
        ids = sorted(g, key=lambda n: (n.role, sim.local_index[n.id]))
        w(f"    grupo {gi}: " + ", ".join(lbl(n.id) for n in ids))
    w("")

    # ── enlaces de radio (verdad fisica) ──
    w("[ ENLACES DE RADIO - verdad fisica (fiabilidad %) ]")
    al = sorted((n for n in nodes.values() if n.alive),
                key=lambda n: (n.role, sim.local_index[n.id]))
    pares = []
    for i, a in enumerate(al):
        for b in al[i + 1:]:
            rel = sim.medium.reliability(a, b)
            if rel > 0:
                pares.append((lbl(a.id), lbl(b.id), rel))
    if pares:
        for (la, lb, rel) in pares:
            w(f"    {la:>3} <-> {lb:<3} : {rel * 100:3.0f}%")
    else:
        w("    (no hay enlaces; todos fuera de rango)")
    w("")

    # ── detalle por nodo ──
    for n in sorted(nodes.values(), key=lambda n: (n.role, sim.local_index[n.id])):
        w("-" * 72)
        w(f" {lbl(n.id)}   ip {n.ip}   piso {n.piso}   "
          f"bateria {n.battery:.0f}%   {'VIVO' if n.alive else 'CAIDO'}")
        w("-" * 72)
        if not n.alive:
            w("  (nodo caido - no participa en la malla)")
            w("")
            continue
        with n.router._lock:
            peers = list(n.router.peers.values())
            routes = list(n.router.routes.values())
            failed = set(n.fault.failed)
        # vecinos aprendidos por el protocolo
        w("  Vecinos conocidos por el protocolo (PeerInfo):")
        if peers:
            rows = [[lbl(p.node_id), f"{sim.t - p.last_seen:.1f}s",
                     f"{p.tq:.2f}", p.hops, f"{p.battery:.0f}%",
                     "ALERTA" if p.in_alert else "-"]
                    for p in sorted(peers, key=lambda p: p.node_id)]
            out.extend(tabla(["vecino", "ult.visto", "TQ", "hops", "bat%", "estado"], rows))
        else:
            w("    (ninguno todavia)")
        # tabla de rutas BATMAN (la pieza estrella)
        w("  Tabla de rutas BATMAN (a quien / por quien / con que calidad):")
        if routes:
            rows = [[lbl(rt.dest), lbl(rt.via_id), rt.hops, f"{rt.tq:.2f}",
                     rt.seq, f"{sim.t - rt.last_seen:.1f}s"]
                    for rt in sorted(routes, key=lambda r: r.dest)]
            out.extend(tabla(["destino", "via(sig.salto)", "hops", "TQ", "seq", "edad"], rows))
        else:
            w("    (sin rutas todavia)")
        w("  Cree caidos (FaultManager.failed): " +
          (", ".join(lbl(i) for i in sorted(failed)) if failed else "(ninguno)"))
        w("  Supervivientes que encontro: " +
          (", ".join(lbl(i) for i in n.my_survivors) if n.my_survivors else "(ninguno)"))
        w("")

    w("Leyenda: TQ = calidad de ruta (mayor mejor) . via = siguiente salto .")
    w("hops = saltos . edad/ult.visto = hace cuanto se supo del nodo.")
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════
#  VISUALIZADOR EN VIVO
# ══════════════════════════════════════════════════════════════════════════
class Visualizer:
    """Vista EN VIVO con pygame (fluida, ~60 fps). Dibuja el edificio, la
    malla, los paquetes en vuelo y los paneles laterales (tabla de rutas
    BATMAN, calidad de red y log). matplotlib sólo se usa para el PNG de
    análisis (tecla A / al salir)."""

    W, H = 1400, 800
    # ventana del mundo (deja sitio a las etiquetas P1/P2/P3 y márgenes)
    WX0, WX1 = -3.0, 44.0
    WY0, WY1 = -3.0, 35.0
    STEP_DT = 1.0 / 18.0      # ritmo de simulación (independiente del fps)

    def __init__(self, sim):
        global pygame
        import pygame as _pg
        pygame = _pg
        self.sim = sim
        self.sel_idx = 0
        self._refresh_sel_ids()
        self._acc = 0.0
        self._running = True
        self.input_active = False
        self.input_text = ""
        self.messages = []          # animaciones de mensajes en vuelo (M)

        # zonas de pantalla
        self.map_rect = pygame.Rect(10, 40, 850, self.H - 90)
        px = 870
        pw = self.W - px - 12
        self.tab_rect = pygame.Rect(px, 10, pw, 250)
        self.q_rect = pygame.Rect(px, 270, pw, 230)
        self.log_rect = pygame.Rect(px, 510, pw, self.H - 510 - 34)

        # escala mundo→pantalla uniforme (equivalente a aspect='equal')
        sx = self.map_rect.w / (self.WX1 - self.WX0)
        sy = self.map_rect.h / (self.WY1 - self.WY0)
        self.scale = min(sx, sy)
        self._xoff = (self.map_rect.w - (self.WX1 - self.WX0) * self.scale) / 2
        self._yoff = (self.map_rect.h - (self.WY1 - self.WY0) * self.scale) / 2

        # colores RGB precomputados
        self.c_bg = self._rgb(C_BG)
        self.c_wall = self._rgb(C_WALL)
        self.c_floor = self._rgb(C_FLOOR)
        self.c_slab = self._rgb('#5F5E5A')
        self.c_stair = self._rgb('#1D9E75')
        self.c_debris = self._rgb('#9C9A8E')
        self.c_alert = self._rgb(C_ALERT)
        self.c_ink = self._rgb('#2C2C2A')
        self.c_dim = self._rgb('#888780')

    # ── color: hex→RGB y mezcla con el fondo (simula alpha) ──
    @staticmethod
    def _rgb(h):
        h = h.lstrip('#')
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    def _blend(self, rgb, a, bg=None):
        bg = bg if bg is not None else self.c_bg
        a = max(0.0, min(1.0, a))
        return (int(rgb[0] * a + bg[0] * (1 - a)),
                int(rgb[1] * a + bg[1] * (1 - a)),
                int(rgb[2] * a + bg[2] * (1 - a)))

    # ── selección de nodos ──
    def _refresh_sel_ids(self):
        self.sel_ids = [n.id for n in self.sim.nodes.values()
                        if n.role == 'R'] + \
                       [n.id for n in self.sim.nodes.values()
                        if n.role == 'S']
        if self.sel_ids:
            self.sel_idx = min(self.sel_idx, len(self.sel_ids) - 1)
        else:
            self.sel_idx = 0

    @property
    def sel_node(self):
        if not self.sel_ids:
            return None
        return self.sim.nodes.get(self.sel_ids[self.sel_idx])

    # ── transformación mundo→pantalla (y invertida: pygame crece hacia abajo)
    def _w2s(self, wx, wy):
        x = self.map_rect.x + self._xoff + (wx - self.WX0) * self.scale
        y = self.map_rect.y + self._yoff + (self.WY1 - wy) * self.scale
        return (int(x), int(y))

    def _text(self, surf, font, s, x, y, color,
              center=False, right=False):
        img = font.render(s, True, color)
        r = img.get_rect()
        if center:
            r.midtop = (x, y)
        elif right:
            r.topright = (x, y)
        else:
            r.topleft = (x, y)
        surf.blit(img, r)
        return r

    # ── formas auxiliares ──
    def _diamond(self, surf, c, r, col, border):
        cx, cy = c
        pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, border, pts, 2)

    def _dashed_line(self, surf, col, a, b, width, dash=6):
        x1, y1 = a
        x2, y2 = b
        dist = math.hypot(x2 - x1, y2 - y1)
        if dist == 0:
            return
        ux, uy = (x2 - x1) / dist, (y2 - y1) / dist
        n = int(dist // dash)
        for i in range(0, n + 1, 2):
            sa = (x1 + ux * dash * i, y1 + uy * dash * i)
            sb = (x1 + ux * dash * (i + 1), y1 + uy * dash * (i + 1))
            pygame.draw.line(surf, col, sa, sb, width)

    def _bubble(self, surf, s, x, y):
        img = self.f_ital.render(s, True, self._rgb('#555555'))
        r = img.get_rect(topleft=(x, y))
        pygame.draw.rect(surf, (255, 255, 255), r.inflate(8, 4),
                         border_radius=4)
        surf.blit(img, r)

    # ── dibujo del edificio + malla ──
    def _draw_map(self, surf):
        surf.set_clip(self.map_rect)
        # pisos
        for piso in range(N_PISOS):
            y0 = piso * PISO_H
            tl = self._w2s(0, y0 + PISO_H)
            br = self._w2s(ANCHO, y0)
            rect = pygame.Rect(tl[0], tl[1], br[0] - tl[0], br[1] - tl[1])
            pygame.draw.rect(surf, self._blend(self.c_floor, 0.5), rect)
            pygame.draw.rect(surf, self.c_wall, rect, 1)
            lx, ly = self._w2s(-1.4, y0 + PISO_H / 2)
            self._text(surf, self.f_sm, f"P{piso + 1}", lx, ly,
                       self.c_slab, center=True)
        # losas inter-piso (impenetrables) con hueco de escalera
        for (yw, xa, xb) in self.sim.walls:
            pygame.draw.line(surf, self.c_slab,
                             self._w2s(xa, yw), self._w2s(xb, yw), 3)
        sx0, _ = STAIR_XY
        for yw in (PISO_H, 2 * PISO_H):
            self._dashed_line(surf, self.c_stair,
                              self._w2s(sx0 - STAIR_HALF_W, yw),
                              self._w2s(sx0 + STAIR_HALF_W, yw), 3, dash=6)
        # escombros
        for (cx, cy, r) in self.sim.debris:
            c = self._w2s(cx, cy)
            rr = max(2, int(r * self.scale))
            pygame.draw.circle(surf, self.c_debris, c, rr)
            pygame.draw.circle(surf, self.c_slab, c, rr, 1)

        nodes = [n for n in self.sim.nodes.values() if n.alive]
        sel = self.sel_node

        # anillo de rango del nodo seleccionado
        if sel and sel.alive:
            c = self._w2s(sel.x, sel.y)
            rr = int(self.sim.cfg['rango_comm'] * self.scale)
            pygame.draw.circle(surf, self._blend(self._rgb(sel.color()), 0.30),
                               c, rr, 1)

        # enlaces de radio coloreados por fiabilidad
        for i, a in enumerate(nodes):
            for b in nodes[i + 1:]:
                rel = self.sim.medium.reliability(a, b)
                if rel <= 0:
                    continue
                base = (29, 158, 117) if rel > 0.66 else (
                    (232, 168, 56) if rel > 0.33 else (226, 75, 74))
                col = self._blend(base, 0.30 + 0.4 * rel)
                w = max(1, int(round(1 + 2 * rel)))
                pygame.draw.line(surf, col, self._w2s(a.x, a.y),
                                 self._w2s(b.x, b.y), w)

        # estelas (historial reciente)
        for n in self.sim.nodes.values():
            h = n.history[-40:]
            if len(h) > 1:
                col = self._blend(self._rgb(n.color()), 0.28)
                pygame.draw.lines(surf, col, False,
                                  [self._w2s(hx, hy) for (hx, hy) in h], 1)

        # paquetes en vuelo (se desvanecen con la edad)
        for p in self.sim.medium.packets_visual:
            pos = p.pos
            col = self._blend(self._rgb(p.color), max(0.05, 1 - p.progress))
            pygame.draw.circle(surf, col, self._w2s(pos[0], pos[1]), 4)

        # nodos + etiquetas
        for n in self.sim.nodes.values():
            in_alert = (n.role == 'R' and n.alive and any(
                pp.in_alert for pp in n.router.peers.values()))
            col = self.c_alert if in_alert else self._rgb(n.color())
            c = self._w2s(n.x, n.y)
            if n.role == 'R':
                pygame.draw.circle(surf, col, c, 9)
                pygame.draw.circle(surf, (255, 255, 255), c, 9, 2)
            else:
                self._diamond(surf, c, 9, col, (255, 255, 255))
            if n is sel and n.alive:
                pygame.draw.circle(surf, self._rgb(n.color()), c, 14, 2)
            tag = n.label
            if not n.alive:
                tag += " X"
            elif in_alert:
                tag += " !"
            tag += f" {n.battery:.0f}%"
            self._text(surf, self.f_xs, tag, c[0], c[1] - 26, col,
                       center=True)
            if n.alive and n.last_msg and (self.sim.t - n.t_beacon) < 1.4:
                self._bubble(surf, f'"{n.last_msg}"', c[0] + 12, c[1] + 6)

        # mensajes personalizados (M) viajando por la malla
        self._draw_messages(surf)

        surf.set_clip(None)
        self._draw_legend(surf)
        self._draw_map_title(surf)

    def _draw_legend(self, surf):
        items = [
            ('o', '#378ADD', 'Rescatista'),
            ('d', C_SURV, 'Superviviente'),
            ('d', C_SURV_OK, 'Superv. hallado'),
            ('o', C_ALERT, 'Alerta'),
            ('l', '#1D9E75', 'Enlace bueno'),
            ('l', '#E24B4A', 'Enlace débil'),
            ('l', C_OGM, 'OGM'),
            ('l', C_HB, '"estoy bien"'),
            ('l', C_MSG, 'Mensaje (M)'),
        ]
        pad, lh, cols = 6, 16, 2
        rows = (len(items) + cols - 1) // cols
        bw, bh = 256, rows * lh + 2 * pad
        bx = self.map_rect.right - bw - 6
        by = self.map_rect.top + 6
        s = pygame.Surface((bw, bh), pygame.SRCALPHA)
        s.fill((255, 255, 255, 220))
        surf.blit(s, (bx, by))
        pygame.draw.rect(surf, self.c_wall, pygame.Rect(bx, by, bw, bh), 1)
        colw = bw // cols
        for idx, (kind, color, label) in enumerate(items):
            ix = bx + pad + (idx % cols) * colw
            iy = by + pad + (idx // cols) * lh + lh // 2
            rgb = self._rgb(color)
            if kind == 'o':
                pygame.draw.circle(surf, rgb, (ix + 5, iy), 5)
            elif kind == 'd':
                self._diamond(surf, (ix + 5, iy), 5, rgb, (255, 255, 255))
            else:
                pygame.draw.line(surf, rgb, (ix, iy), (ix + 12, iy), 3)
            self._text(surf, self.f_xs, label, ix + 18, iy - 7, self.c_ink)

    def _draw_map_title(self, surf):
        s = self.sim.summary()
        estado = "PAUSADO" if self.sim.paused else f"T+{s['t']:.0f}s"
        part = "" if s['comps'] <= 1 else f"   ·   RED PARTIDA ({s['comps']})"
        txt = (f"{estado}   ·   Rescatistas {s['aliveR']}/{s['totR']}"
               f"   ·   Hallados {s['found']}/{s['totS']}"
               f"   ·   escenario: {self.sim.escenario}{part}")
        col = self.c_alert if s['comps'] > 1 else self.c_ink
        self._text(surf, self.f_title, txt, self.map_rect.x, 10, col)

    # ── marco común de los paneles ──
    def _panel_bg(self, surf, rect, title, title_col=None):
        pygame.draw.rect(surf, (255, 255, 255), rect)
        pygame.draw.rect(surf, self.c_wall, rect, 1)
        self._text(surf, self.f_bold, title, rect.x + 8, rect.y + 6,
                   title_col or self.c_ink)

    # ── panel: tabla de rutas BATMAN del nodo seleccionado ──
    def _draw_table(self, surf):
        rect = self.tab_rect
        self._panel_bg(surf, rect, "Tabla de rutas BATMAN")
        n = self.sel_node
        if not n:
            return
        self._text(surf, self.f_sm,
                   f"{n.label} ({'activo' if n.alive else 'INACTIVO'})",
                   rect.x + 8, rect.y + 26, self._rgb(n.color()))
        cols = [("Dest", 0.03), ("Via", 0.26), ("Hops", 0.46),
                ("TQ", 0.62), ("Visto", 0.80)]
        hy = rect.y + 48
        for label, fx in cols:
            self._text(surf, self.f_xs, label,
                       rect.x + int(fx * rect.w), hy, self.c_ink)
        with n.router._lock:
            rutas = sorted(n.router.routes.values(), key=lambda r: r.dest)
            peers = dict(n.router.peers)
        if not rutas:
            self._text(surf, self.f_sm, "Sin rutas todavía (esperando OGMs)",
                       rect.x + 8, rect.y + 72, self._rgb('#888888'))
            return
        c444 = self._rgb('#444444')
        for i, r in enumerate(rutas[:9]):
            y = rect.y + 66 + i * 17
            p = peers.get(r.dest)
            alert = p.in_alert if p else False
            lost = p.is_lost(self.sim.t) if p else False
            col = self.c_alert if (alert or lost) else self.c_ink
            ago = self.sim.t - r.last_seen
            row = [(self.sim.label_of(r.dest), 0.03, col),
                   (self.sim.label_of(r.via_id), 0.26, c444),
                   (str(r.hops), 0.46, c444),
                   (f"{r.tq:.2f}", 0.62, c444),
                   (f"{ago:.0f}s", 0.80, col)]
            for txt, fx, cc in row:
                self._text(surf, self.f_mono_sm, txt,
                           rect.x + int(fx * rect.w), y, cc)

    # ── panel: calidad de enlace y métricas (sparklines) ──
    def _draw_quality(self, surf):
        rect = self.q_rect
        self._panel_bg(surf, rect, "Calidad de red (ventana reciente)")
        rec = self.sim.recorder
        plot = pygame.Rect(rect.x + 34, rect.y + 30, rect.w - 44, rect.h - 56)
        pygame.draw.rect(surf, self._rgb('#DDDDDD'), plot, 1)
        self._text(surf, self.f_xs, "1", plot.x - 16, plot.y - 6, self.c_dim)
        self._text(surf, self.f_xs, "0", plot.x - 16, plot.bottom - 8,
                   self.c_dim)
        dr = rec.deliver_ratio[-160:]
        tq = rec.avg_tq[-160:]
        comp = rec.comp_R[-160:]
        nP = len(dr)
        if nP >= 2:
            def X(i):
                return plot.x + int(i / (nP - 1) * plot.w)

            def Y(v):
                return plot.bottom - int(max(0, min(1, v)) * plot.h)
            # sombreado de particiones
            for i, cc in enumerate(comp):
                if cc and cc > 1:
                    x0 = X(i)
                    x1 = X(min(i + 1, nP - 1))
                    band = pygame.Surface((max(1, x1 - x0), plot.h),
                                          pygame.SRCALPHA)
                    band.fill((142, 68, 173, 45))
                    surf.blit(band, (x0, plot.y))
            pygame.draw.lines(surf, self._rgb('#2980B9'), False,
                              [(X(i), Y(v)) for i, v in enumerate(dr)], 2)
            pygame.draw.lines(surf, self._rgb('#1D9E75'), False,
                              [(X(i), Y(v)) for i, v in enumerate(tq)], 2)
        self._text(surf, self.f_xs, "Entrega", plot.x + 2, rect.bottom - 18,
                   self._rgb('#2980B9'))
        self._text(surf, self.f_xs, "TQ", plot.x + 66, rect.bottom - 18,
                   self._rgb('#1D9E75'))
        self._text(surf, self.f_xs, "Partición", plot.x + 100,
                   rect.bottom - 18, self._rgb('#8E44AD'))

    # ── panel: log ──
    def _fit(self, font, s, maxpx):
        """Recorta s con '…' para que quepa en maxpx px con la fuente dada
        (usa el ancho real del texto, no un nº fijo de caracteres)."""
        if maxpx <= 0 or font.size(s)[0] <= maxpx:
            return s
        while s and font.size(s + "…")[0] > maxpx:
            s = s[:-1]
        return s + "…"

    def _draw_log(self, surf):
        rect = self.log_rect
        self._panel_bg(surf, rect, "Log de eventos de la red")
        cmap = {"info": self._rgb('#5F5E5A'), "ok": self._rgb('#0F6E56'),
                "warn": self._rgb('#854F0B'), "error": self._rgb('#A32D2D')}
        maxlines = max(1, (rect.h - 34) // 16)
        maxpx = rect.w - 78          # de rect.x+70 hasta rect.right-8
        y = rect.y + 30
        for (tt, msg, tipo) in self.sim.log_lines[-maxlines:]:
            self._text(surf, self.f_mono_sm, f"[{tt:5.0f}s]",
                       rect.x + 8, y, self._rgb('#888888'))
            self._text(surf, self.f_mono_sm, self._fit(self.f_mono_sm, msg,
                       maxpx), rect.x + 70, y,
                       cmap.get(tipo, self._rgb('#5F5E5A')))
            y += 16

    def _draw_help(self, surf):
        txt = ("ESPACIO pausa · TAB/←→ o clic seleccionar · 1-9 rescatista · "
               "F caer · G revivir · M mensaje · I inspeccionar (terminal) · "
               "S escenario · +/- rango · [ ] pérdida · A análisis · "
               "R reinicia · Q salir")
        self._text(surf, self.f_sm, txt, self.W // 2, self.H - 26,
                   self.c_dim, center=True)

    # ── tipografías ──
    def _setup_fonts(self):
        def mk(name, size, bold=False, italic=False):
            try:
                f = pygame.font.SysFont(name, size, bold=bold, italic=italic)
                if f:
                    return f
            except Exception:
                pass
            return pygame.font.Font(None, size)
        self.f_title = mk("segoeui", 20, bold=True)
        self.f = mk("segoeui", 15)
        self.f_sm = mk("segoeui", 13)
        self.f_xs = mk("segoeui", 11)
        self.f_bold = mk("segoeui", 14, bold=True)
        self.f_ital = mk("segoeui", 12, italic=True)
        self.f_mono = mk("consolas", 14)
        self.f_mono_sm = mk("consolas", 12)

    # ── bucle principal ──
    def run(self):
        pygame.init()
        pygame.display.set_caption(
            "Red Ad-Hoc BATMAN (código real) · Rescate en edificio")
        screen = pygame.display.set_mode((self.W, self.H))
        clock = pygame.time.Clock()
        self._setup_fonts()
        while self._running:
            dt = clock.tick(60) / 1000.0
            self._handle_events()
            # avanzar la simulación a ritmo fijo, sea cual sea el fps
            if not self.sim.paused and not self.input_active:
                self._acc += dt
                steps = 0
                while self._acc >= self.STEP_DT and steps < 6:
                    self.sim.step()
                    self._acc -= self.STEP_DT
                    steps += 1
            else:
                self._acc = 0.0
            self._render(screen)
            pygame.display.flip()
        try:
            fn = build_analysis_figure(self.sim)
            if fn:
                print(f"[análisis] figura guardada al salir: {fn}")
        except Exception as e:
            print(f"[análisis] no se pudo guardar la figura: {e}")
        pygame.quit()

    def _render(self, screen):
        screen.fill(self.c_bg)
        self._draw_map(screen)
        self._draw_table(screen)
        self._draw_quality(screen)
        self._draw_log(screen)
        self._draw_help(screen)
        if self.input_active:
            self._draw_input(screen)

    # ── eventos ──
    def _handle_events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self._running = False
            elif e.type == pygame.KEYDOWN:
                if self.input_active:
                    self._key_input(e)
                else:
                    self._key_control(e)
            elif (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1
                  and not self.input_active):
                self._click_select(e.pos)

    def _click_select(self, pos):
        best, bestd = None, 20 ** 2
        for i, nid in enumerate(self.sel_ids):
            n = self.sim.nodes.get(nid)
            if not n:
                continue
            sx, sy = self._w2s(n.x, n.y)
            d = (sx - pos[0]) ** 2 + (sy - pos[1]) ** 2
            if d < bestd:
                bestd, best = d, i
        if best is not None:
            self.sel_idx = best

    def _key_control(self, e):
        sim = self.sim
        k, u = e.key, e.unicode
        if k == pygame.K_SPACE:
            sim.paused = not sim.paused
            sim.log("Simulación " +
                    ("PAUSADA" if sim.paused else "REANUDADA"), "warn")
        elif k in (pygame.K_TAB, pygame.K_RIGHT):
            if self.sel_ids:
                self.sel_idx = (self.sel_idx + 1) % len(self.sel_ids)
        elif k == pygame.K_LEFT:
            if self.sel_ids:
                self.sel_idx = (self.sel_idx - 1) % len(self.sel_ids)
        elif k == pygame.K_f:
            n = self.sel_node
            if n:
                sim.fail_node(n.id)
        elif k == pygame.K_g:
            n = self.sel_node
            if n:
                sim.recover_node(n.id)
        elif k == pygame.K_s:
            i = SCENARIOS.index(sim.escenario)
            sim.escenario = SCENARIOS[(i + 1) % len(SCENARIOS)]
            sim._build_world()
            self._refresh_sel_ids()
            self.messages.clear()
        elif k == pygame.K_m:
            self._open_input()
        elif k == pygame.K_a:
            fn = build_analysis_figure(sim)
            sim.log(f"Análisis guardado: {fn}", "ok")
            print(f"[análisis] figura guardada: {fn}")
        elif k == pygame.K_i:
            print(snapshot_red(sim))
            sim.log("Instantánea de la red impresa en la terminal "
                    "(tabla de rutas, vecinos, conectividad)", "info")
        elif k == pygame.K_r:
            sim._build_world()
            self._refresh_sel_ids()
            self.messages.clear()
        elif k in (pygame.K_q, pygame.K_ESCAPE):
            self._running = False
        elif u in ('+', '='):
            sim.set_param('rango_comm',
                          round(sim.cfg['rango_comm'] + 1.0, 1))
        elif u == '-':
            sim.set_param('rango_comm',
                          max(4.0, round(sim.cfg['rango_comm'] - 1.0, 1)))
        elif u == ']':
            sim.set_param('falloff',
                          min(1.5, round(sim.cfg['falloff'] + 0.05, 2)))
        elif u == '[':
            sim.set_param('falloff',
                          max(0.0, round(sim.cfg['falloff'] - 0.05, 2)))
        elif u and u in '123456789':
            i = int(u) - 1
            rs = [n.id for n in sim.nodes.values() if n.role == 'R']
            if i < len(rs):
                self.sel_idx = self.sel_ids.index(rs[i])

    # ── composición de mensajes (entrada de texto en la propia ventana) ──
    def _open_input(self):
        if len(self.sim.nodes) < 2:
            self.sim.log("Hacen falta al menos 2 nodos.", "warn")
            return
        self.input_active = True
        self.input_text = ""

    def _key_input(self, e):
        if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            raw = self.input_text.strip()
            self.input_active = False
            self.input_text = ""
            if raw:
                self._resolve_and_send(raw)
        elif e.key == pygame.K_ESCAPE:
            self.input_active = False
            self.input_text = ""
        elif e.key == pygame.K_BACKSPACE:
            self.input_text = self.input_text[:-1]
        else:
            ch = e.unicode
            if ch and ch.isprintable() and len(self.input_text) < 120:
                self.input_text += ch

    def _resolve_and_send(self, raw):
        """Interpreta 'R1 > R3 texto' / 'S2 > R1 texto' / '1>3 texto' y
        manda el mensaje por la malla BATMAN."""
        import re
        resc_ids = sorted(n.id for n in self.sim.nodes.values()
                          if n.role == 'R')
        surv_ids = sorted(n.id for n in self.sim.nodes.values()
                          if n.role == 'S')
        m = re.match(r"\s*([rRsS]?)(\d+)\s*>\s*([rRsS]?)(\d+)\s+(.+)", raw)
        if not m:
            self.sim.log(f"Formato inválido: '{raw}'. Usa "
                         f"R1>R3 texto  o  S2>R1 texto", "warn")
            return
        rol_from, idx_from = m.group(1).upper() or 'R', int(m.group(2))
        rol_to = m.group(3).upper() or 'R'
        idx_to, texto = int(m.group(4)), m.group(5)

        def resolver(rol, idx):
            lista = resc_ids if rol == 'R' else surv_ids
            if not (1 <= idx <= len(lista)):
                return None
            return lista[idx - 1]

        from_id = resolver(rol_from, idx_from)
        to_id = resolver(rol_to, idx_to)
        if from_id is None or to_id is None:
            self.sim.log(f"Índice fuera de rango (R: {len(resc_ids)}, "
                         f"S: {len(surv_ids)}).", "warn")
            return
        path = self.sim.send_unicast(from_id, to_id, texto.strip())
        if path and len(path) >= 2:
            self._enqueue_message(path, texto.strip(),
                                  self.sim.label_of(from_id),
                                  self.sim.label_of(to_id))

    def _enqueue_message(self, path_ids, text, src_label, dst_label):
        """Registra una animación de mensaje con reloj de pared (independiente
        del paso de simulación) para que SE VEA viajar salto a salto y el
        texto quede visible varios segundos al llegar al destino."""
        now = pygame.time.get_ticks() / 1000.0
        segs = max(1, len(path_ids) - 1)
        pts0 = [(self.sim.nodes[i].x, self.sim.nodes[i].y)
                for i in path_ids]                 # snapshot por si un nodo cae
        self.messages.append({
            'ids': list(path_ids),
            'pts0': pts0,
            'text': text,
            'src': src_label,
            'dst': dst_label,
            'start': now,
            'dur': max(1.3, 0.7 * segs),           # ~0.7 s por salto
            'hold': 3.2,                           # texto fijo en el destino
        })
        self.messages = self.messages[-4:]         # a lo sumo 4 en vuelo

    def _msg_point(self, msg, i):
        """Posición en pantalla del i-ésimo nodo del camino (sigue al nodo
        vivo; si cayó, usa la posición capturada al enviar)."""
        n = self.sim.nodes.get(msg['ids'][i])
        if n is not None and n.alive:
            return self._w2s(n.x, n.y)
        wx, wy = msg['pts0'][i]
        return self._w2s(wx, wy)

    def _draw_messages(self, surf):
        """Dibuja los mensajes en vuelo: ruta resaltada, marcador que viaja
        salto a salto y un globo con el texto que se fija en el destino."""
        if not self.messages:
            return
        now = pygame.time.get_ticks() / 1000.0
        pulse = 3 if (pygame.time.get_ticks() // 250) % 2 == 0 else 0
        alive = []
        for msg in self.messages:
            el = now - msg['start']
            dur, hold = msg['dur'], msg['hold']
            if el >= dur + hold:
                continue
            alive.append(msg)
            pts = [self._msg_point(msg, i) for i in range(len(msg['ids']))]
            if len(pts) >= 2:                      # ruta resaltada
                pygame.draw.lines(surf, self._blend(self._rgb(C_MSG), 0.55),
                                  False, pts, 3)
            segs = len(pts) - 1
            if el <= dur:                          # viajando
                seg_f = (el / dur) * segs
                i = min(int(seg_f), segs - 1)
                local = seg_f - i
                ax, ay = pts[i]
                bx, by = pts[i + 1]
                mx = int(ax + (bx - ax) * local)
                my = int(ay + (by - ay) * local)
            else:                                  # llegó: fijo en destino
                mx, my = pts[-1]
            pygame.draw.circle(surf, self._blend(self._rgb(C_MSG), 0.35),
                               (mx, my), 11 + pulse)
            pygame.draw.circle(surf, self._rgb(C_MSG), (mx, my), 6)
            pygame.draw.circle(surf, (255, 255, 255), (mx, my), 6, 2)
            label = f"{msg['src']}→{msg['dst']}: {msg['text']}"
            if len(label) > 46:
                label = label[:45] + "…"
            self._msg_bubble(surf, label, mx + 12, my - 10)
        self.messages = alive

    def _msg_bubble(self, surf, s, x, y):
        """Globo prominente (relleno color mensaje, texto blanco) que se
        mantiene dentro del mapa."""
        img = self.f_bold.render(s, True, (255, 255, 255))
        r = img.get_rect(topleft=(x + 6, y + 3))
        bg = r.inflate(14, 8)
        if bg.right > self.map_rect.right - 4:
            d = bg.right - (self.map_rect.right - 4)
            bg.move_ip(-d, 0)
            r.move_ip(-d, 0)
        if bg.left < self.map_rect.left + 4:
            d = (self.map_rect.left + 4) - bg.left
            bg.move_ip(d, 0)
            r.move_ip(d, 0)
        if bg.top < self.map_rect.top + 4:
            d = (self.map_rect.top + 4) - bg.top
            bg.move_ip(0, d)
            r.move_ip(0, d)
        pygame.draw.rect(surf, self._rgb(C_MSG), bg, border_radius=5)
        pygame.draw.rect(surf, (255, 255, 255), bg, 1, border_radius=5)
        surf.blit(img, r)

    def _draw_input(self, surf):
        dim = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        dim.fill((20, 20, 25, 150))
        surf.blit(dim, (0, 0))
        bw, bh = 740, 236
        bx, by = (self.W - bw) // 2, (self.H - bh) // 2
        box = pygame.Rect(bx, by, bw, bh)
        pygame.draw.rect(surf, (255, 255, 255), box, border_radius=8)
        pygame.draw.rect(surf, self.c_slab, box, 2, border_radius=8)
        self._text(surf, self.f_title, "Mensaje personalizado (R o S)",
                   bx + 20, by + 16, self.c_ink)
        resc = ", ".join(self.sim.label_of(i) for i in sorted(
            n.id for n in self.sim.nodes.values() if n.role == 'R'))
        surv = ", ".join(self.sim.label_of(i) for i in sorted(
            n.id for n in self.sim.nodes.values() if n.role == 'S'))
        info = [f"Rescatistas: {resc}",
                f"Supervivientes: {surv}",
                "Formato:  R1 > R3 cuidado con los escombros",
                "          S2 > R1 estoy atrapado en el piso 2",
                "(emisor > destino, espacio, texto)"]
        yy = by + 52
        for ln in info:
            self._text(surf, self.f_sm, ln, bx + 20, yy, self._rgb('#555555'))
            yy += 20
        inp = pygame.Rect(bx + 20, by + bh - 46, bw - 40, 30)
        pygame.draw.rect(surf, self._rgb('#F2F1EC'), inp)
        pygame.draw.rect(surf, self.c_dim, inp, 1)
        cur = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
        self._text(surf, self.f_mono, self.input_text + cur,
                   inp.x + 6, inp.y + 6, self.c_ink)
        self._text(surf, self.f_xs, "Enter envía · Esc cancela",
                   inp.right, inp.bottom + 4, self.c_dim, right=True)


# ══════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════
def main():
    p = argparse.ArgumentParser(
        description="Simulación de red ad-hoc con BATMAN real (rescate).")
    p.add_argument('--escenario', default='base', choices=SCENARIOS)
    p.add_argument('--headless', action='store_true',
                   help="Sin ventana: corre y guarda el análisis en PNG")
    p.add_argument('--duracion', type=float, default=200.0,
                   help="Segundos simulados en modo headless")
    p.add_argument('--timeout', type=float, default=DEFAULTS['timeout'],
                   help="Segundos sin señal para marcar rescatista caído")
    p.add_argument('--rango', type=float, default=DEFAULTS['rango_comm'],
                   help="Alcance de radio en metros")
    p.add_argument('--falloff', type=float, default=DEFAULTS['falloff'],
                   help="Degradación de fiabilidad con la distancia (0-1.5)")
    p.add_argument('--seed', type=int, default=None,
                   help="Semilla aleatoria (reproducibilidad)")
    p.add_argument('--inspect', action='store_true',
                   help="Imprime en TEXTO el estado interno de la red "
                        "(tabla de rutas, vecinos, conectividad) y sale. "
                        "Corre --duracion segundos antes del volcado.")
    args = p.parse_args()

    if args.seed is not None:
        random.seed(args.seed)
        np.random.seed(args.seed)

    cfg = dict(timeout=args.timeout, rango_comm=args.rango,
               falloff=args.falloff)
    sim = Simulation(escenario=args.escenario, cfg=cfg)

    print("=" * 68)
    print("  Red Ad-Hoc · BATMAN REAL (batman_node.py) en simulación")
    print(f"  Escenario: {args.escenario}  ·  timeout={args.timeout:.0f}s  "
          f"·  rango={args.rango:.0f}m")
    print("=" * 68)

    if args.inspect:
        pasos = int(args.duracion / DT)
        for _ in range(pasos):
            sim.step()
        print(snapshot_red(sim))
        return

    if args.headless:
        pasos = int(args.duracion / DT)
        for _ in range(pasos):
            sim.step()
        fn = build_analysis_figure(sim)
        s = sim.summary()
        print(f"\n  Tiempo simulado     : {s['t']:.0f} s")
        print(f"  Rescatistas activos : {s['aliveR']}/{s['totR']}")
        print(f"  Supervivientes      : {s['found']}/{s['totS']} hallados")
        print(f"  Componentes finales : {s['comps']}")
        print(f"  Eventos registrados : {len(sim.recorder.events)}")
        print(f"  Paquetes radio      : {sim.medium.delivered}/"
              f"{sim.medium.attempted} entregados")
        print(f"\n  Figura de análisis  : {fn}\n")
        for (et, tipo, txt) in sim.recorder.events:
            print(f"    [{et:6.1f}s] {tipo:10s} {txt}")
    else:
        viz = Visualizer(sim)
        viz.run()
        s = sim.summary()
        print(f"\n  Resumen: t={s['t']:.0f}s · "
              f"rescatistas {s['aliveR']}/{s['totR']} · "
              f"hallados {s['found']}/{s['totS']}")


if __name__ == "__main__":
    main()
