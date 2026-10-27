
import logging
import math
import random

from mesh.router import BatmanRouter, PeerInfo
from mesh.fault_manager import FaultManager

class SimNode:
    """
    Un dispositivo de la malla. Toda la lógica de enrutamiento y de
    detección de fallos es de mesh/router.py y mesh/fault_manager.py
    (código real). Esta clase sólo aporta: posición física, batería,
    movilidad y el reemplazo de los sockets por el RadioMedium.
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
        # FaultManager avisa por logging con el id crudo ("Fallo N4"), que
        # en el simulador se confunde con el rol N. Esas caídas ya quedan
        # como eventos ALERT_ON/ALERT_OFF con etiquetas G/N, así que el
        # aviso interno se silencia para no duplicarlo en la terminal.
        self.fault.log.setLevel(logging.ERROR)

        self._ogm_seq = 0
        self._inbox = []            # (msg, from_ip) entregados por el medio


        self.t_beacon = -random.uniform(0, self.DEFAULTS['beacon_cada'])
        self.t_ogm = -random.uniform(0, self.DEFAULTS['batman_cada'])
        self.t_fault = 0.0

        self.history = []
        self.last_msg = ""
        # Lo que este nodo sabe de sus vecinos por los beacons que oyó:
        # id -> (x, y, rol, instante). Es la única información que usa la
        # movilidad "descentralizada" (nunca mira sim.nodes).
        self.oidos = {}

        # contadores de uso del código real (sólo informativos)
        self.ogms_procesados = 0    # llamadas a BatmanRouter.receive_ogm()
        self.ogms_nuevos = 0        # de ésas, las que devolvieron True
        self.beacons_procesados = 0
        self.chequeos_fallo = 0     # llamadas a FaultManager.check()

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
            return self.sim.C_NODO
        return self.sim.C_GATEWAY[(self.sim.local_index[self.id] - 1) % len(self.sim.C_GATEWAY)]

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
            'alerts': list(self.fault.failed),
            'ts': self.sim.t,
        }

    def _make_bcn(self, texto):
        # El beacon lleva la posición del emisor (supuesto: GPS o UWB de
        # interiores), como en los algoritmos de cobertura por fuerzas
        # virtuales. Sólo la usa la movilidad "descentralizada".
        return {
            'type': 'BCN', 'node_id': self.id, 'battery': self.battery,
            'load': 0, 'rep': 1.0, 'role': self.role,
            'msg': texto, 'ts': self.sim.t,
            'x': round(self.x, 2), 'y': round(self.y, 2),
        }

    # ── un paso de tiempo ──
    def tick(self, now):
        if not self.alive:
            return
        drain = (self.sim.cfg['battery_drain'] if self.role == 'G'
                 else self.sim.cfg['battery_drain_nodo'])
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
            self.chequeos_fallo += 1
            for fid in nuevos:
                self.router.mark_alert(fid)
                lbl = self.sim.label_of(fid)
                self.sim.event('ALERT_ON', f"{self.label} no oye a {lbl}")
                self.sim.log(
                    f"⚠ {self.label}: sin señal de {lbl} > "
                    f"{self.sim.cfg['timeout']:.0f}s — se marca caído",
                    "error")

    def _drain_inbox(self, now):
        """Procesa los mensajes entregados por el medio.

        Réplica fiel de MeshNode._handle_bcast de mesh/node.py:
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
                self.beacons_procesados += 1
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
                if 'x' in msg:
                    self.oidos[nid] = (msg['x'], msg['y'], msg.get('role'), now)


                self._recuperar(nid, now)

            elif mt == 'OGM':
                is_new = self.router.receive_ogm(msg, from_ip, now)
                self.ogms_procesados += 1
                if is_new:
                    self.ogms_nuevos += 1
                    # un OGM nuevo prueba que el origen está vivo: apaga su
                    # alerta, con el mismo criterio con que se detectó (el
                    # last_seen que refrescan los OGM). Sin esto, un
                    # Gateway a varios saltos quedaba caído para siempre.
                    self._recuperar(msg['origin_id'], now)
                if is_new and msg.get('ttl', 0) > 1:
                    fwd = dict(msg)
                    fwd['ttl'] = msg['ttl'] - 1
                    fwd['path'] = msg['path'] + [self.id]
                    fwd['tq'] = msg.get('tq', 1.0) * \
                        self.router.link_quality(from_ip)
                    self.sim.medium.broadcast(self, fwd, self.sim.C_OGM)
                for aid in msg.get('alerts', []):
                    self.router.mark_alert(aid)

    def _recuperar(self, nid, now):
        """FaultManager.recover() y, si `nid` estaba de verdad marcado
        caído, el evento ALERT_OFF."""
        genuino = nid in self.fault.failed
        self.fault.recover(nid, now)
        if genuino and self.role == 'G' and self.sim.is_gateway(nid):
            lbl = self.sim.label_of(nid)
            self.sim.event('ALERT_OFF', f"{self.label} recuperó señal de {lbl}")
            self.sim.log(f"{self.label}: señal de {lbl} recuperada", "ok")

    # ── movilidad ──
    def move(self, now):
        if not self.alive:
            return

        if self.sim.cfg.get('move_speed', 0) <= 0:
            # move_speed=0: nodos estáticos, sin persecución ni jitter.
            self._record_history()
            return

        if self.role == 'N':
            # Nodos de usuario: casi estáticos, micro-movimiento aleatorio
            for _ in range(3):
                dx, dy = random.gauss(0, 0.05), random.gauss(0, 0.05)
                if self._try_move(dx, dy):
                    break
        else:
            # destino: esquina (wanderer), el que deciden las fuerzas
            # locales ("descentralizada"), el Nodo de usuario asignado
            # ("repartir") o el más cercano ("seguir")
            modo = self.sim.cfg.get('movilidad', 'seguir')
            if self is self.sim.wanderer and now < self.sim.wander_until:
                tx, ty = 38.0, 2.0
            elif modo == 'descentralizada':
                self._mover_descentralizado(now)
                self._record_history()
                return
            elif modo == 'repartir':
                tgt = self.sim.objetivo_repartido(self)
                if tgt is None:
                    # sobra (más Gateway que Nodos de usuario): se queda
                    # quieto, de relevo
                    self._record_history()
                    return
                tx, ty = tgt.x, tgt.y
            else:
                objetivos = [s for s in self.sim.nodes.values()
                             if s.role == 'N']
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

    # ── movilidad descentralizada ──
    # Distancias de las fuerzas, como fracción del alcance de radio.
    D_USUARIO = 0.4     # un Nodo de usuario más lejos que esto atrae
    # (elegidas en una grilla sobre base, denso, colapso_progresivo y
    # rescatista_perdido, 5 semillas: ver contexto/PLAN_SIGUIENTE.md, paso 9)
    D_REPULSION = 0.55  # un Gateway más cerca que esto repele
    D_EXPANSION = 0.75  # ...o que esto, si el Gateway está ocioso
    D_ENLACE = 0.9      # un Gateway más cerca que esto cuenta como enlace
    MEMORIA_BEACONS = 3  # se olvida a un vecino tras 3 beacons sin oírlo

    def fuerza_descentralizada(self, now):
        """Vector (fx, fy, motivo) que el Gateway quiere seguir, calculado
        sólo con lo que oyó (self.oidos):
        - atracción hacia los Nodos de usuario que oye y de los que es el
          Gateway más cercano entre los que conoce ("a su cargo"), si están
          más lejos que D_USUARIO;
        - repulsión de los Gateway que oye más cerca que D_REPULSION, o que
          D_EXPANSION si no tiene ningún usuario a su cargo (ocioso): así
          la malla se estira y explora hasta oír usuarios nuevos, sin
          perder el enlace (ver _conserva_enlace);
        - sin ningún Gateway oído, vuelve hacia el último que oyó
          (reconexión)."""
        rango = self.sim.cfg['rango_comm']
        memoria = self.MEMORIA_BEACONS * self.sim.cfg['beacon_cada']
        recientes = {nid: v for nid, v in self.oidos.items()
                     if now - v[3] <= memoria}
        gws = {nid: (x, y) for nid, (x, y, rol, _t) in recientes.items()
               if rol == 'G'}
        fx = fy = 0.0
        d_usr = self.D_USUARIO * rango
        a_cargo = 0
        for nid, (ux, uy, rol, _t) in recientes.items():
            if rol != 'N':
                continue
            d = math.hypot(ux - self.x, uy - self.y)
            # ¿otro Gateway que conozco está más cerca de ese usuario?
            if any(math.hypot(ux - gx, uy - gy) < d for gx, gy in gws.values()):
                continue
            a_cargo += 1
            if d > d_usr:
                fx += (ux - self.x) / d * (d - d_usr)
                fy += (uy - self.y) / d * (d - d_usr)
        d_rep = (self.D_REPULSION if a_cargo else self.D_EXPANSION) * rango
        for nid, (gx, gy) in gws.items():
            d = math.hypot(self.x - gx, self.y - gy)
            if d >= d_rep:
                continue
            if d < 1e-6:
                # apilados: se separan en direcciones opuestas según el id
                ux, uy = (1.0, 0.0) if self.id < nid else (-1.0, 0.0)
            else:
                ux, uy = (self.x - gx) / d, (self.y - gy) / d
            fx += ux * (d_rep - d)
            fy += uy * (d_rep - d)
        if not gws:
            gateways_vistos = [(t, x, y) for nid, (x, y, rol, t)
                               in self.oidos.items() if rol == 'G']
            if gateways_vistos:
                _t, x, y = max(gateways_vistos)
                return x - self.x, y - self.y, "reconexion"
        return fx, fy, ("cobertura" if a_cargo else "expansion")

    def _mover_descentralizado(self, now):
        fx, fy, _motivo = self.fuerza_descentralizada(now)
        norma = math.hypot(fx, fy)
        if norma < 0.1:
            return      # equilibrio: se queda
        tx, ty = self.x + fx, self.y + fy
        if self.piso != max(1, min(self.N_PISOS, int(ty // self.PISO_H) + 1)) \
                and abs(self.x - self.STAIR_XY[0]) > self.STAIR_HALF_W * 0.6:
            tx = self.STAIR_XY[0]     # cambiar de piso: por la escalera
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        paso = min(self.sim.cfg['move_speed'], dist)
        nx, ny = self.x + dx / dist * paso, self.y + dy / dist * paso
        if not self._conserva_enlace(now, nx, ny):
            return
        if paso < self.sim.cfg['move_speed']:
            self._try_move(nx - self.x, ny - self.y)
        else:
            self._move_avoiding(tx, ty)

    def _conserva_enlace(self, now, nx, ny):
        """¿Ir a (nx, ny) conserva la conexión con la malla? Un enlace con
        un Gateway oído (a menos de D_ENLACE) sólo se puede romper si
        queda un rodeo de dos saltos: otro Gateway oído que siga enlazado
        con los dos. Se decide con las posiciones de los beacons, que
        pueden tener segundos: un vecino oído hace `a` s pudo moverse hasta
        velocidad·a metros, así que un enlace cuenta como seguro sólo si lo
        es en el peor caso, y como posible si lo es en el mejor."""
        memoria = self.MEMORIA_BEACONS * self.sim.cfg['beacon_cada']
        d_enl = self.D_ENLACE * self.sim.cfg['rango_comm']
        vel = self.sim.cfg['move_speed'] / self.DT      # m/s de un Gateway
        gws = [(x, y, vel * (now - t)) for (x, y, rol, t) in self.oidos.values()
               if rol == 'G' and now - t <= memoria]
        d = lambda a, b: math.hypot(a[0] - b[0], a[1] - b[1])
        yo, nuevo = (self.x, self.y), (nx, ny)
        for h in gws:
            if d(yo, h) - h[2] > d_enl:          # ni siquiera es un enlace
                continue
            if d(nuevo, h) + h[2] <= d_enl:      # lo conserva seguro
                continue
            if not any(k is not h and d(nuevo, k) + k[2] <= d_enl
                       and d(h, k) + h[2] + k[2] <= d_enl for k in gws):
                return False
        return True

    def _record_history(self):
        self.history.append((self.x, self.y))
        if len(self.history) > 80:
            self.history.pop(0)

    def _try_move(self, dx, dy):
        """Intenta un paso: lo rechaza si sale del edificio."""
        nx = self.x + dx
        ny = self.y + dy
        if not (1.0 <= nx <= self.sim.ANCHO - 1.0): return False
        if not (0.4 <= ny <= self.sim.ALTO - 0.4): return False
       
        self.x, self.y = nx, ny
        return True

    def _move_avoiding(self, tx, ty):
        """Mueve hacia (tx,ty) sin salir del edificio.

        Si el paso recto no es válido se prueban ángulos de desvío;
        si nada funciona el nodo se queda quieto (atascado)."""
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
