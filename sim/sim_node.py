
import math
import random

from mesh.router import BatmanRouter, PeerInfo
from mesh.fault_manager import FaultManager

class SimNode:
    """
    Un dispositivo de la malla. Toda la lógica de enrutamiento y de
    detección de fallos es de batman_node.py (código real). Esta clase
    sólo aporta: posición física, batería, movilidad y el reemplazo de
    los sockets por el RadioMedium.
    """

    def __init__(self, nid, role, x, y, piso, sim,DEFAULTS,N_PISOS,PISO_H,STAIR_XY,STAIR_HALF_W,DT):

        del piso
        self.id = nid
        self.role = role            # 'G' (Gateway) o 'N' (Nodo de Usuario)
        self.x, self.y = x, y
        self.sim = sim
        self.alive = True
        self.battery = 100.0
        self.ip = f"10.0.0.{nid}"
        self.DEFAULTS = DEFAULTS
        self.N_PISOS = N_PISOS
        self.PISO_H = PISO_H
        self.STAIR_XY = STAIR_XY
        self.STAIR_HALF_W = STAIR_HALF_W
        self.DT = DT
        # ── Estado del protocolo: clases REALES ──
        self.router = BatmanRouter(nid)
        self.fault = FaultManager(nid)

        self._ogm_seq = 0
        self._inbox = []            # (msg, from_ip) entregados por el medio


        self.t_beacon = -random.uniform(0, self.DEFAULTS['beacon_cada'])
        self.t_ogm = -random.uniform(0, self.DEFAULTS['batman_cada'])
        self.t_hb = -random.uniform(0, self.DEFAULTS['heartbeat_cada'])
        self.t_fault = 0.0


        self.my_survivors = []
        self.history = []
        self.last_msg = ""          

    @property
    def label(self):
        return f"{self.role}{self.sim.local_index[self.id]}"

    @property
    def piso(self):
        """Piso derivado de la coordenada y (1..N_PISOS)."""
        return max(1, min(self.N_PISOS, int(self.y // self.PISO_H) + 1))

    def color(self):
        if not self.alive:
            return self.sim.C_DEAD
        if self.role == 'N':
            return self.sim.C_SURV_OK if self.id in self.sim.found_ids else self.sim.C_SURV
        return self.sim.C_RESC[(self.sim.local_index[self.id] - 1) % len(self.sim.C_RESC)]

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
        drain = (self.sim.cfg['battery_drain'] if self.role == 'G'
                 else self.sim.cfg['battery_drain_surv'])
        self.battery = max(0.0, self.battery - drain * self.DT)
        if self.battery <= 0:
            self.alive = False
            self.sim.event('FAIL', f"{self.label} sin batería")
            self.sim.log(f"{self.label} se quedó sin batería", "error")
            return

        self._drain_inbox(now)

        if now - self.t_beacon >= self.sim.cfg['beacon_cada']:
            self.t_beacon = now
            if self.role == 'G':
                txt = f"Hola, soy el Gateway {self.label}"
            else:
                txt = f"Hola, soy el Nodo {self.label}"
            self.last_msg = txt
            self.sim.medium.broadcast(self, self._make_bcn(txt), self.sim.C_BCN)

        if now - self.t_ogm >= self.sim.cfg['batman_cada']:
            self.t_ogm = now
            self.sim.medium.broadcast(self, self._make_ogm(), self.sim.C_OGM)

        if now - self.t_fault >= 5.0 and self.role == 'G':
            self.t_fault = now
            peers = [p for p in self.router.peers.values()
                     if self.sim.is_gateway(p.node_id)]
            nuevos = self.fault.check(peers, now,self.sim.cfg['timeout'])
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
                if genuino and self.role == 'G' and \
                        self.sim.is_gateway(nid):
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
                    self.sim.medium.broadcast(self, fwd, self.sim.C_OGM)
                for sid in msg.get('survivors', []):
                    self.sim.register_found(sid, msg['origin_id'])
                for aid in msg.get('alerts', []):
                    self.router.mark_alert(aid)

    # ── movilidad con colisiones ──
    def move(self, now):
        if not self.alive:
            return

        if self.sim.cfg.get('move_speed', 0) <= 0:
            # move_speed=0: nodos estáticos, sin persecución ni jitter.
            self._record_history()
            return

        if self.role == 'N':
            # Nodos de usuario atrapados: micro-movimiento (sin chocar)
            for _ in range(3):
                dx, dy = random.gauss(0, 0.05), random.gauss(0, 0.05)
                if self._try_move(dx, dy):
                    break
        else:
            # destino: esquina (wanderer) o Nodo de Usuario más cercano
            if self is self.sim.wanderer and now < self.sim.wander_until:
                tx, ty = 38.0, 2.0
            else:
                objetivos = [s for s in self.sim.nodes.values()
                             if s.role == 'N'
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
            tgt_band = max(1, min(self.N_PISOS, int(ty // self.PISO_H) + 1))
            if my_band != tgt_band and \
                    abs(self.x - self.STAIR_XY[0]) > self.STAIR_HALF_W * 0.6:
                tx_eff, ty_eff = self.STAIR_XY[0], ty
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
        if not (1.0 <= nx <= self.sim.ANCHO - 1.0): return False
        if not (0.4 <= ny <= self.sim.ALTO - 0.4): return False
       
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
