import logging
import threading
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# ══════════════════════════════════════════════════════════════════════
#  BATMAN ROUTER
# ══════════════════════════════════════════════════════════════════════
@dataclass
class RouteEntry:
    dest: int; via_ip: str; via_id: int; hops: int
    tq: float; last_seen: float; seq: int

@dataclass
class PeerInfo:
    node_id: int; ip: str; last_seen: float
    battery: float = 100.0; load: int = 0; reputation: float = 1.0
    hops: int = 1; tq: float = 1.0
    survivors: list = field(default_factory=list)
    in_alert: bool = False

    def is_lost(self, now: float, TIMEOUT_ALERT) -> bool:
        return (now - self.last_seen) > TIMEOUT_ALERT


class BatmanRouter:
    """
    Enrutador B.A.T.M.A.N. con Transmit Quality (TQ).
    Cada nodo emite sus propios OGMs y reenvía los ajenos.
    La tabla de rutas se actualiza eligiendo siempre la ruta con mayor TQ.
    Thread-safe.
    """
    def __init__(self, node_id: int):
        self.node_id = node_id
        self._lock   = threading.RLock()
        self.peers:     Dict[int, PeerInfo]   = {}
        self.routes:    Dict[int, RouteEntry] = {}
        self.seen_ogms: Dict[int, int]        = {}
        # sliding window de OGMs recibidos por (origin, via_ip): 1 por
        # secuencia recibida, 0 por secuencia salteada
        self._windows: Dict[Tuple[int,str], deque] = \
            defaultdict(lambda: deque(maxlen=self.WINDOW))
        self._last_seq: Dict[Tuple[int,str], int] = {}
        self.log = logging.getLogger(f"Router[N{node_id}]")

    WINDOW = 16

    def _window_update(self, key, seq: int):
        """Desliza la ventana de `key` con la secuencia `seq`: un 0 por
        cada secuencia salteada desde la última vista por ese vecino (hasta
        el tamaño de la ventana) y un 1 por ésta. Las copias duplicadas o
        viejas no la tocan."""
        last = self._last_seq.get(key)
        if last is not None and seq <= last:
            return
        dq = self._windows[key]
        if last is not None:
            for _ in range(min(seq - last - 1, self.WINDOW)):
                dq.append(0)
        dq.append(1)
        self._last_seq[key] = seq

    def _route_tq_now(self, route: RouteEntry, seq: int) -> float:
        """TQ de la ruta vigente si su vecino se perdió las secuencias
        entre la de la ruta y `seq` (sin contar `seq`, que todavía puede
        llegar por él)."""
        dq = self._windows.get((route.dest, route.via_ip))
        missed = seq - route.seq - 1
        if not dq or missed <= 0:
            return route.tq
        lq_now = sum(dq) / len(dq)
        vals = (list(dq) + [0] * min(missed, self.WINDOW))[-self.WINDOW:]
        return route.tq * (sum(vals) / len(vals)) / lq_now

    def receive_ogm(self, ogm: dict, from_ip: str, now: float) -> bool:
        """Procesa OGM. True = es nuevo, debe reenviarse.

        La ventana del vecino se actualiza con toda copia, aunque la
        secuencia ya haya llegado por otro vecino, y la ruta se queda con
        el vecino de mayor TQ: el actual la refresca, otro la reemplaza
        sólo si su TQ es mayor que el del actual, descontadas las
        secuencias que el actual se perdió. Cualquier copia que no sea
        vieja refresca el last_seen de la ruta: la ruta hacia un origen
        sigue vigente mientras lleguen sus OGM, por el vecino que sea."""
        origin = ogm['origin_id']; seq = ogm['seq']
        with self._lock:
            key = (origin, from_ip)
            self._window_update(key, seq)
            lq     = sum(self._windows[key]) / len(self._windows[key])
            acc_tq = ogm.get('tq', 1.0) * lq
            path = ogm.get('path', [origin])
            route = self.routes.get(origin)
            if route is None or route.via_ip == from_ip:
                mejor = route is None or seq >= route.seq
            else:
                mejor = seq >= route.seq and \
                    acc_tq > self._route_tq_now(route, seq)
            if mejor:
                self.routes[origin] = RouteEntry(
                    dest=origin, via_ip=from_ip,
                    via_id=path[-1] if path else origin,
                    hops=len(path), tq=acc_tq,
                    last_seen=now, seq=seq)
            elif seq >= route.seq:
                # el origen sigue vivo y alcanzable, aunque esta copia no
                # llegó por el mejor vecino: la ruta se mantiene vigente
                route.last_seen = now
            if self.seen_ogms.get(origin, -1) >= seq: return False
            self.seen_ogms[origin] = seq
            if origin not in self.peers:
                self.peers[origin] = PeerInfo(node_id=origin, ip=from_ip, last_seen=now)
            p = self.peers[origin]
            p.last_seen  = now;  p.ip         = from_ip
            p.battery    = ogm.get('battery',   100.0)
            p.load       = ogm.get('load',       0)
            p.reputation = ogm.get('reputation', 1.0)
            p.hops       = len(ogm.get('path',  []))
            p.tq         = acc_tq
            p.survivors  = ogm.get('survivors',  [])
            p.in_alert   = False
            return True

    def link_quality(self, from_ip: str) -> float:
        with self._lock:
            vals = [v for (o,ip),dq in self._windows.items()
                    if ip == from_ip for v in dq]
            return sum(vals)/len(vals) if vals else 0.8

    def alive_peers(self, now: float,TIMEOUT_ALERT) -> List[PeerInfo]:
        with self._lock:
            return [p for p in self.peers.values() if not p.is_lost(now,TIMEOUT_ALERT)]

    def mark_alert(self, pid: int):
        with self._lock:
            if pid in self.peers: self.peers[pid].in_alert = True

    def mark_recovered(self, pid: int, now: float):
        with self._lock:
            if pid in self.peers: self.peers[pid].in_alert = False