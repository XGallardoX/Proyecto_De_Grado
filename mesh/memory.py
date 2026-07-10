import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class MemEntry:
    key: str; value: object; version: int
    vector_clk: dict; author: int; timestamp: float
    replicas: list = field(default_factory=list)

class DistributedMemory:
    """
    Clave-valor con vector clocks para consistencia causal (CRDT-like).
    Persiste en JSON para sobrevivir reinicios.
    Thread-safe.
    """
    def __init__(self, node_id: int, path: Optional[str] = None):
        self.node_id = node_id
        self._lock   = threading.RLock()
        self._store: Dict[str, MemEntry] = {}
        self._clock: Dict[str, int]      = {str(node_id): 0}
        self._wc     = 0
        self._path   = path
        self.log = logging.getLogger(f"Mem[N{node_id}]")
        if path and os.path.exists(path): self._load()

    def write(self, key: str, value: object) -> MemEntry:
        with self._lock:
            self._clock[str(self.node_id)] = \
                self._clock.get(str(self.node_id), 0) + 1
            self._wc += 1
            e = MemEntry(key=key, value=value, version=self._wc,
                         vector_clk=dict(self._clock), author=self.node_id,
                         timestamp=time.time(), replicas=[self.node_id])
            self._store[key] = e; self._save(); return e

    def read(self, key: str) -> Optional[object]:
        with self._lock:
            e = self._store.get(key); return e.value if e else None

    def merge(self, ed: dict) -> bool:
        with self._lock:
            e   = self._d2e(ed)
            loc = self._store.get(e.key)
            if loc is None:
                self._store[e.key] = e
                self._mclk(e.vector_clk); self._save(); return True
            ln = self._dom(loc.vector_clk, e.vector_clk)
            rn = self._dom(e.vector_clk, loc.vector_clk)
            if rn:
                self._store[e.key] = e
                self._mclk(e.vector_clk); self._save(); return True
            elif not ln and e.timestamp > loc.timestamp:
                self._store[e.key] = e
                self._mclk(e.vector_clk); self._save(); return True
            return False

    def digest(self) -> dict:
        with self._lock: return {k: e.version for k,e in self._store.items()}

    def newer_than(self, rd: dict) -> List[dict]:
        with self._lock:
            return [self._e2d(e) for k,e in self._store.items()
                    if k not in rd or e.version > rd[k]]

    def all_entries(self) -> List[dict]:
        with self._lock: return [self._e2d(e) for e in self._store.values()]

    def size(self) -> int:
        with self._lock: return len(self._store)

    def _dom(self, a, b) -> bool:
        ks = set(a)|set(b)
        return (all(a.get(k,0) >= b.get(k,0) for k in ks) and
                any(a.get(k,0) >  b.get(k,0) for k in ks))

    def _mclk(self, r):
        for k,v in r.items():
            self._clock[k] = max(self._clock.get(k,0), v)

    def _e2d(self, e) -> dict:
        return {'key':e.key,'value':e.value,'version':e.version,
                'vector_clk':e.vector_clk,'author':e.author,
                'timestamp':e.timestamp,'replicas':e.replicas}

    def _d2e(self, d) -> MemEntry:
        return MemEntry(key=d['key'],value=d['value'],version=d['version'],
                        vector_clk=d['vector_clk'],author=d['author'],
                        timestamp=d['timestamp'],replicas=d.get('replicas',[]))

    def _save(self):
        if not self._path: return
        try:
            tmp = self._path + ".tmp"
            with open(tmp,'w') as f:
                json.dump({'clock':self._clock,'wc':self._wc,
                           'store':{k:self._e2d(e) for k,e in self._store.items()}},f)
            os.replace(tmp, self._path)
        except Exception as ex:
            self.log.warning(f"Persist: {ex}")

    def _load(self):
        try:
            with open(self._path) as f: d = json.load(f)
            self._clock = d.get('clock', {str(self.node_id): 0})
            self._wc    = d.get('wc', 0)
            for k,ed in d.get('store',{}).items():
                self._store[k] = self._d2e(ed)
            self.log.info(f"Memoria restaurada: {len(self._store)} entradas")
        except Exception as ex:
            self.log.warning(f"Load: {ex}")