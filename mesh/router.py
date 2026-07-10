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
        # sliding window de OGMs recibidos por (origin, via_ip)
        self._windows: Dict[Tuple[int,str], deque] = \
            defaultdict(lambda: deque(maxlen=16))
        self.log = logging.getLogger(f"Router[N{node_id}]")

    def receive_ogm(self, ogm: dict, from_ip: str, now: float) -> bool:
        """Procesa OGM. True = es nuevo, debe reenviarse."""
        origin = ogm['origin_id']; seq = ogm['seq']
        with self._lock:
            if self.seen_ogms.get(origin, -1) >= seq: return False
            self.seen_ogms[origin] = seq
            key = (origin, from_ip)
            self._windows[key].append(1)
            lq     = sum(self._windows[key]) / len(self._windows[key])
            acc_tq = ogm.get('tq', 1.0) * lq
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
            path = ogm.get('path', [origin])
            if (origin not in self.routes or
                    acc_tq > self.routes[origin].tq or
                    seq    > self.routes[origin].seq):
                self.routes[origin] = RouteEntry(
                    dest=origin, via_ip=from_ip,
                    via_id=path[-1] if path else origin,
                    hops=len(path), tq=acc_tq,
                    last_seen=now, seq=seq)
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