import logging
import threading
from collections import deque
from typing import Dict, List, Tuple


class FaultManager:
    """
    Detección y reconfiguración ante fallos. Sin coordinador.
    Cada nodo monitorea a sus pares de forma independiente.
    """
    def __init__(self, node_id: int):
        self.node_id = node_id
        self._lock   = threading.RLock()
        self.failed: set = set()
        self._hist:  Dict[int, List[float]] = {}
        self._log:   deque = deque(maxlen=100)
        self.log = logging.getLogger(f"Fault[N{node_id}]")

    def check(self, peers: List, now: float,TIMEOUT_ALERT) -> List[int]:
        """Retorna IDs de nodos recién detectados como caídos."""
        newly = []
        with self._lock:
            for p in peers:
                if p.node_id in self.failed: continue
                if p.is_lost(now,TIMEOUT_ALERT):
                    self.failed.add(p.node_id)
                    self._hist.setdefault(p.node_id,[]).append(now)
                    msg = f"Fallo N{p.node_id} (sin señal {now-p.last_seen:.0f}s)"
                    self._log.append((now, msg))
                    self.log.warning(msg)
                    newly.append(p.node_id)
        return newly

    def recover(self, nid: int, now: float):
        with self._lock:
            if nid in self.failed:
                self.failed.discard(nid)
                msg = f"Recuperación N{nid}"
                self._log.append((now, msg)); self.log.info(msg)

    def reassign(self, fid: int, sched,
                 peers: List, bat: float, now: float) -> int:
        count = 0
        with sched._lock:
            for t in sched.tasks.values():
                if (t.assigned_to == fid and
                        t.state in (sched.TaskState.ASSIGNED, sched.TaskState.RUNNING)):
                    t.state       = sched.TaskState.PENDING
                    t.assigned_to = sched.best_node(peers, bat)
                    t.state       = sched.TaskState.ASSIGNED
                    msg = f"Tarea {t.id}: N{fid}→N{t.assigned_to}"
                    self._log.append((now, msg))
                    self.log.info(msg); count += 1
        return count

    def repair_replicas(self, fid: int, mem, now: float):
        with mem._lock:
            for e in mem._store.values():
                if fid in e.replicas:
                    e.replicas.remove(fid)
                    self._log.append(
                        (now, f"Re-replicar '{e.key}' (pérdida en N{fid})"))

    def recent_log(self, n: int = 20) -> List[Tuple[float,str]]:
        with self._lock: return list(self._log)[-n:]