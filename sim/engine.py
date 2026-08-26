import math
import random
from collections import deque

from analysis.metrics import Recorder
from sim.radio import RadioMedium
from sim.sim_node import SimNode


class Simulation:
    def __init__(self, escenario='base', cfg=None,DEFAULTS=None,DT=None,N_PISOS=None,PISO_H=None,STAIR_XY=None,STAIR_HALF_W=None,ANCHO=None,ALTO=None,C_RESC=None,C_SURV=None,C_SURV_OK=None,C_DEAD=None,C_OGM=None,C_BCN=None,C_HB=None):
        self.escenario = escenario
        self.cfg = dict(DEFAULTS)
        self.DEFAULTS = DEFAULTS
        self.DT = DT
        self.N_PISOS = N_PISOS
        self.PISO_H = PISO_H
        self.STAIR_XY = STAIR_XY
        self.STAIR_HALF_W = STAIR_HALF_W
        self.ANCHO = ANCHO
        self.ALTO = ALTO
        self.C_RESC=C_RESC
        self.C_SURV=C_SURV
        self.C_SURV_OK=C_SURV_OK
        self.C_DEAD=C_DEAD
        self.C_OGM=C_OGM
        self.C_BCN=C_BCN
        self.C_HB=C_HB
        if cfg:
            self.cfg.update(cfg)
        self._base_cfg = dict(self.cfg)
        self._build_world()

    # ── construir el mundo según el escenario ──
    def _build_world(self):

        self.cfg = dict(self._base_cfg)

        # aplicar el timeout pedido al CÓDIGO REAL (lo lee PeerInfo.is_lost
        # y FaultManager.check desde el espacio de nombres de batman_node)
        # bn.TIMEOUT_ALERT = self.cfg['timeout']

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
        self.debris = []


        explicit_nodes = self.cfg.get("nodes")
        gi = ni = 0
        if explicit_nodes:
            # posiciones a voluntad, ya validadas por sim.config_loader
            for spec in explicit_nodes:
                nid, role = spec["id"], spec["role"]
                n = SimNode(nid, role, float(spec["x"]), float(spec["y"]), 1, self,
                            self.DEFAULTS, self.N_PISOS, self.PISO_H, self.STAIR_XY,
                            self.STAIR_HALF_W, self.DT)
                if "battery" in spec:
                    n.battery = float(spec["battery"])
                if role == 'G':
                    gi += 1
                    self.local_index[nid] = gi
                else:
                    ni += 1
                    self.local_index[nid] = ni
                self.nodes[nid] = n

            for ev in self.cfg.get("events", []):
                if ev["type"] == "wander" and ev["node_id"] in self.nodes:
                    self.wanderer = self.nodes[ev["node_id"]]
                    self.wander_until = float(ev["until"])
                    self.log(f"Escenario: {self.label_of(ev['node_id'])} se "
                             f"internará lejos (hasta t={ev['until']:.0f}) y "
                             f"dejará de dar señal.", "warn")
        else:
            n_gateways = self.cfg.get("n_gateways", 1)
            n_nodes = self.cfg.get("n_nodes", 10)

            gateways = []
            for i in range(n_gateways):
                gateways.append((i + 1, random.uniform(5, 35), random.uniform(5, 25), 1))

            nodes = []
            for i in range(n_nodes - n_gateways):
                nodes.append((i + 1 + n_gateways, random.uniform(5, 35), random.uniform(5, 25), 1))

            for nid, x, y, p in gateways:
                gi += 1
                n = SimNode(nid, 'G', float(x), float(y), p, self,self.DEFAULTS,self.N_PISOS,self.PISO_H,self.STAIR_XY,self.STAIR_HALF_W,self.DT)
                self.local_index[nid] = gi
                self.nodes[nid] = n
            for nid, x, y, p in nodes:
                ni += 1
                n = SimNode(nid, 'N', float(x), float(y), p, self,self.DEFAULTS,self.N_PISOS,self.PISO_H,self.STAIR_XY,self.STAIR_HALF_W,self.DT)
                self.local_index[nid] = ni
                self.nodes[nid] = n

        self.log(f"Escenario '{self.escenario}' iniciado · {gi} gateways, "
                 f"{ni} nodos · timeout={self.cfg['timeout']:.0f}s",
                 "info")
        self.log("Protocolo BATMAN: clases reales de batman "
                 "(BatmanRouter + FaultManager).", "info")

    # ── utilidades ──
    def label_of(self, nid):
        n = self.nodes.get(nid)
        return n.label if n else f"?{nid}"

    def is_gateway(self, nid):
        n = self.nodes.get(nid)
        return bool(n and n.role == 'G')

    

    def collides_point(self, x, y):
        """¿El punto (x,y) está dentro de un escombro?"""
        for (cx, cy, r) in self.debris:
            if (x - cx) ** 2 + (y - cy) ** 2 < r * r:
                return True
        return False

    

    def register_found(self, sid, by_id):
        if sid in self.nodes and self.nodes[sid].role == 'N' \
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

     
        hops = len(path) - 1
        via = " → ".join(self.label_of(i) for i in path)
    
        converged = a.router.routes.get(to_id) is not None
        modo = ("ruta BATMAN convergida" if converged
                else "entregado por la malla (BATMAN aún converge)")
        self.event('MSG_OK', f"{a.label}→{b.label} ({hops} "
                   f"salto{'s' if hops != 1 else ''}): {texto[:60]}")
 
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

    def gateway_components(self):
        """Nº de componentes conexas considerando SÓLO gateways.
        1 = el equipo está totalmente conectado; >1 = malla partida."""
        alive, find, idx = self._union_find()
        roots = {find(idx[n.id]) for n in alive if n.role == 'G'}
        return len(roots) if roots else 0

    def nodes_in_mesh(self):
        """Cuántos nodos de usuario vivos comparten componente con algún
        gateway (la malla puede enrutar hasta ellos)."""
        alive, find, idx = self._union_find()
        gateway_roots = {find(idx[n.id]) for n in alive if n.role == 'G'}
        return sum(1 for n in alive if n.role == 'N'
                   and find(idx[n.id]) in gateway_roots)

    # ── paso principal ──
    def step(self):
        if self.paused:
            return
        self.t += self.DT
        self.medium.reset_step_counters()

        for n in self.nodes.values():
            n.move(self.t)
        for n in self.nodes.values():
            n.tick(self.t)

        # detectar particiones / reunificaciones de la malla de
        # gateways (esto es lo que BATMAN "ve" y reorganiza)
        comps = self.gateway_components()
        # anti-rebote: no registrar transiciones más seguido que cada 6 s
        if self.t - self._last_part_evt >= 6.0:
            if comps > self._prev_components and comps > 1:
                self._last_part_evt = self.t
                self.event('PARTITION',
                           f"Malla de gateways partida en {comps} grupos")
                self.log(f"⚠ La malla de gateways se partió "
                         f"en {comps} grupos", "error")
            elif comps < self._prev_components and comps == 1:
                self._last_part_evt = self.t
                self.event('HEAL', "Malla de gateways reunificada")
                self.log("La malla de gateways se reunificó "
                         "(BATMAN reconvergió)", "ok")
        self._prev_components = comps

        # envejecer paquetes visuales
        pv = self.medium.packets_visual
        for p in pv:
            p.age += self.DT
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
        # if clave == 'timeout':
        #     bn.TIMEOUT_ALERT = valor
        self.event('PARAM', f"{clave} = {valor}")
        self.log(f"Parámetro {clave} = {valor}", "warn")

    def event(self, tipo, texto):
        self.recorder.event(self.t, tipo, texto)

    def log(self, msg, tipo="info"):
        self.log_lines.append((self.t, msg, tipo))
        if len(self.log_lines) > 300:
            self.log_lines.pop(0)

    def summary(self):
        aliveG = sum(1 for n in self.nodes.values()
                     if n.role == 'G' and n.alive)
        totG = sum(1 for n in self.nodes.values() if n.role == 'G')
        aliveN = sum(1 for n in self.nodes.values()
                        if n.role == 'N' and n.alive)
        totN = sum(1 for n in self.nodes.values() if n.role == 'N')
        return dict(t=self.t, aliveG=aliveG, totG=totG,
                    aliveN=aliveN, totN=totN,
                    comps=self._prev_components)

    def add_node(self):
        new_id = max(self.nodes.keys()) + 1
        x = random.uniform(5, 35)
        y = random.uniform(5, 25)
        n = SimNode(new_id, 'N', float(x), float(y), 1, self,self.DEFAULTS,self.N_PISOS,self.PISO_H,self.STAIR_XY,self.STAIR_HALF_W,self.DT)
        self.local_index[new_id] = len([n for n in self.nodes.values() if n.role == 'N']) + 1
        self.nodes[new_id] = n
        self.log(f"Nodo {n.label} añadido", "info")

    def remove_node(self, nid):
        if nid in self.nodes:
            n = self.nodes[nid]
            if n.role == 'G':
                gateways = [node for node in self.nodes.values() if node.role == 'G']
                if len(gateways) <= 1:
                    self.log(f"No se puede eliminar {n.label}. Es el unico Gateway.", "warn")
                    return
            lbl = n.label  
            del self.nodes[nid]
            del self.local_index[nid]
            self.log(f"Nodo {lbl} eliminado", "info")