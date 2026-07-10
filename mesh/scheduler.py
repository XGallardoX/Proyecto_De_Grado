import logging
import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List
import heapq
import threading

# ══════════════════════════════════════════════════════════════════════
#  MMODELOS ML 
# ══════════════════════════════════════════════════════════════════════
class TaskType(str, Enum):
    LINEAR_REGRESSION   = "LinReg"
    LOGISTIC_REGRESSION = "LogReg"
    SVM                 = "SVM"
    DECISION_TREE       = "DecTree"
    MLP                 = "MLP"
    SENSOR_FUSION       = "SensorFusion"
    PATH_PLANNING       = "PathPlan"

class TaskState(str, Enum):
    PENDING  = "pending";  ASSIGNED = "assigned"
    RUNNING  = "running";  DONE     = "done";  FAILED = "failed"

@dataclass
class Task:
    id:          str
    task_type:   str
    origin_id:   int
    priority:    int
    payload:     dict
    created_at:  float
    deadline:    float
    state:       str  = TaskState.PENDING
    assigned_to: int  = -1
    result:      dict = field(default_factory=dict)


def run_model(task_type: str, payload: dict) -> dict:
    """Ejecuta el modelo ML indicado. Solo usa stdlib."""

    # ── Regresión Lineal (gradiente descendente) ──────────────────
    if task_type == TaskType.LINEAR_REGRESSION:
        X  = payload.get('X', [[1],[2],[3],[4],[5]])
        y  = payload.get('y', [1, 2, 3, 4, 5])
        lr = payload.get('lr', 0.01)
        ep = payload.get('epochs', 500)
        n, m = len(X), len(X[0])
        w = [0.0] * m; b = 0.0
        for _ in range(ep):
            pr = [sum(X[i][j]*w[j] for j in range(m))+b for i in range(n)]
            er = [pr[i]-y[i] for i in range(n)]
            dw = [sum(er[i]*X[i][j] for i in range(n))/n for j in range(m)]
            w  = [w[j]-lr*dw[j] for j in range(m)]
            b -= lr * sum(er)/n
        pr  = [sum(X[i][j]*w[j] for j in range(m))+b for i in range(n)]
        mse = sum((pr[i]-y[i])**2 for i in range(n))/n
        return {'weights': [round(v,6) for v in w],
                'bias': round(b,6), 'mse': round(mse,8)}

    # ── Regresión Logística ────────────────────────────────────────
    elif task_type == TaskType.LOGISTIC_REGRESSION:
        def sig(x): return 1/(1+math.exp(-max(-500,min(500,x))))
        X  = payload.get('X', [])
        y  = payload.get('y', [])
        lr = payload.get('lr', 0.1)
        ep = payload.get('epochs', 300)
        n, m = len(X), len(X[0])
        w = [0.0]*m; b = 0.0
        for _ in range(ep):
            pr = [sig(sum(X[i][j]*w[j] for j in range(m))+b) for i in range(n)]
            er = [pr[i]-y[i] for i in range(n)]
            dw = [sum(er[i]*X[i][j] for i in range(n))/n for j in range(m)]
            w  = [w[j]-lr*dw[j] for j in range(m)]; b -= lr*sum(er)/n
        pr  = [sig(sum(X[i][j]*w[j] for j in range(m))+b) for i in range(n)]
        acc = sum(1 for i in range(n) if (pr[i]>0.5)==bool(y[i]))/n if n else 0
        return {'weights': [round(v,6) for v in w],
                'bias': round(b,6), 'accuracy': round(acc,4)}

    # ── SVM lineal (SGD, kernel lineal) ───────────────────────────
    elif task_type == TaskType.SVM:
        X  = payload.get('X', [])
        y  = payload.get('y', [])   # labels en {-1, 1}
        lr = payload.get('lr', 0.01)
        C  = payload.get('C',  1.0)
        ep = payload.get('epochs', 200)
        n, m = len(X), (len(X[0]) if X else 1)
        w = [0.0]*m; b = 0.0
        for _ in range(ep):
            for i in range(n):
                dot = sum(X[i][j]*w[j] for j in range(m))+b
                if y[i]*dot < 1:
                    w = [w[j]-lr*(w[j]-C*y[i]*X[i][j]) for j in range(m)]
                    b += lr*C*y[i]
                else:
                    w = [w[j]-lr*w[j] for j in range(m)]
        pr  = [1 if sum(X[i][j]*w[j] for j in range(m))+b>=0 else -1 for i in range(n)]
        acc = sum(1 for i in range(n) if pr[i]==y[i])/n if n else 0
        return {'weights': [round(v,6) for v in w],
                'bias': round(b,6), 'accuracy': round(acc,4)}

    # ── Árbol de Decisión (GINI, recursivo) ───────────────────────
    elif task_type == TaskType.DECISION_TREE:
        X  = payload.get('X', [])
        y  = payload.get('y', [])
        md = payload.get('max_depth', 4)
        def gini(lb):
            if not lb: return 0
            n = len(lb); c = {}
            for l in lb: c[l] = c.get(l,0)+1
            return 1 - sum((v/n)**2 for v in c.values())
        def best_split(X, y):
            best=None; bg=1.0
            for f in range(len(X[0])):
                for t in sorted(set(r[f] for r in X)):
                    l=[y[i] for i in range(len(X)) if X[i][f]<=t]
                    r=[y[i] for i in range(len(X)) if X[i][f]>t]
                    if not l or not r: continue
                    g=(len(l)*gini(l)+len(r)*gini(r))/len(y)
                    if g<bg: bg=g; best=(f,t)
            return best, bg
        def build(X, y, d):
            if not X or d==0 or len(set(y))==1:
                return {'leaf':True,'label':max(set(y),key=y.count) if y else 0}
            s, g = best_split(X, y)
            if s is None:
                return {'leaf':True,'label':max(set(y),key=y.count)}
            f, t = s
            lX=[X[i] for i in range(len(X)) if X[i][f]<=t]
            ly=[y[i] for i in range(len(X)) if X[i][f]<=t]
            rX=[X[i] for i in range(len(X)) if X[i][f]>t]
            ry=[y[i] for i in range(len(X)) if X[i][f]>t]
            return {'leaf':False,'feature':f,'threshold':t,'gini':round(g,4),
                    'left':build(lX,ly,d-1),'right':build(rX,ry,d-1)}
        return {'tree': build(X,y,md), 'root_gini': round(gini(y),4)}

    # ── MLP — Perceptrón Multicapa (1 capa oculta, ReLU + Sigmoid) ─
    elif task_type == TaskType.MLP:
        def relu(x): return max(0.0, x)
        def drelu(x): return 1.0 if x>0 else 0.0
        def sig(x): return 1/(1+math.exp(-max(-500,min(500,x))))
        X  = payload.get('X', [])
        y  = payload.get('y', [])
        hd = payload.get('hidden', 4)
        lr = payload.get('lr', 0.05)
        ep = payload.get('epochs', 500)
        n, idim = len(X), (len(X[0]) if X else 1)
        rng = random.Random(42)
        sc1 = math.sqrt(2/idim); sc2 = math.sqrt(2/hd)
        W1 = [[rng.gauss(0,sc1) for _ in range(idim)] for _ in range(hd)]
        b1 = [0.0]*hd
        W2 = [rng.gauss(0,sc2) for _ in range(hd)]; b2 = 0.0
        for _ in range(ep):
            for i in range(n):
                # Forward
                hv = [relu(sum(W1[k][j]*X[i][j] for j in range(idim))+b1[k])
                      for k in range(hd)]
                o  = sig(sum(W2[k]*hv[k] for k in range(hd))+b2)
                # Backward
                do = o - y[i]
                dW2= [do*hv[k] for k in range(hd)]; db2 = do
                dh = [W2[k]*do*drelu(hv[k]) for k in range(hd)]
                for k in range(hd):
                    for j in range(idim): W1[k][j] -= lr*dh[k]*X[i][j]
                    b1[k] -= lr*dh[k]
                for k in range(hd): W2[k] -= lr*dW2[k]
                b2 -= lr*db2
        preds = [sig(sum(W2[k]*relu(sum(W1[k][j]*X[i][j]
                 for j in range(idim))+b1[k]) for k in range(hd))+b2)
                 for i in range(n)]
        mse = sum((preds[i]-y[i])**2 for i in range(n))/n if n else 0
        return {'mse': round(mse,8), 'hidden': hd, 'epochs': ep}

    # ── Fusión de sensores (promedio ponderado por varianza) ───────
    elif task_type == TaskType.SENSOR_FUSION:
        readings = payload.get('readings', {})
        fused = {}
        for sid, vals in readings.items():
            if not vals: continue
            mean = sum(vals)/len(vals)
            var  = sum((v-mean)**2 for v in vals)/len(vals) if len(vals)>1 else 1.0
            fused[sid] = {'mean':round(mean,4),'var':round(var,6),
                          'weight':round(1/(var+1e-9),4)}
        tw  = sum(f['weight'] for f in fused.values())
        est = sum(f['mean']*f['weight'] for f in fused.values())/tw if tw else 0
        return {'fused_estimate': round(est,4), 'per_sensor': fused}

    # ── A* sobre grid ──────────────────────────────────────────────
    elif task_type == TaskType.PATH_PLANNING:
        grid  = payload.get('grid', [[0]*5]*5)
        start = tuple(payload.get('start', [0,0]))
        goal  = tuple(payload.get('goal',  [4,4]))
        rows, cols = len(grid), len(grid[0])
        def h(a,b): return abs(a[0]-b[0])+abs(a[1]-b[1])
        open_set = [(h(start,goal), 0, start, [start])]
        visited  = set()
        while open_set:
            _, cost, cur, path = heapq.heappop(open_set)
            if cur == goal:
                return {'path':[list(p) for p in path],
                        'cost':cost, 'length':len(path)}
            if cur in visited: continue
            visited.add(cur)
            for dr,dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                nr,nc = cur[0]+dr, cur[1]+dc
                if 0<=nr<rows and 0<=nc<cols and grid[nr][nc]==0:
                    nxt = (nr,nc)
                    heapq.heappush(open_set,
                        (cost+1+h(nxt,goal), cost+1, nxt, path+[nxt]))
        return {'path':[], 'cost':-1, 'length':0}

    else:
        raise ValueError(f"Tipo desconocido: {task_type}")


class DistributedScheduler:
    """
    Scheduler sin maestro.
    score(n) = reputacion * (1 - carga/MAX) * (bateria/100)
    El nodo con mayor score recibe la tarea.
    """
    def __init__(self, node_id: int,MAX_LOAD):
        self.node_id    = node_id
        self._lock      = threading.RLock()
        self.tasks:     Dict[str, Task] = {}
        self.my_tasks:  List[str]       = []
        self.reputation = 1.0
        self._done      = 0
        self._failed    = 0
        self.log = logging.getLogger(f"Sched[N{node_id}]")
        self.MAX_LOAD = MAX_LOAD

    @property
    def load(self) -> int:
        with self._lock: return len(self.my_tasks)

    def score(self, battery: float) -> float:
        lf = max(0.0, 1.0 - self.load / self.MAX_LOAD)
        return self.reputation * lf * (battery / 100.0)

    def best_node(self, peers: List, battery: float) -> int:
        cands = {self.node_id: self.score(battery)}
        for p in peers:
            s = p.reputation * max(0.0,1-p.load/self.MAX_LOAD) * (p.battery/100.0)
            cands[p.node_id] = s
        return max(cands, key=cands.get)

    def accept(self, task: Task):
        with self._lock:
            self.tasks[task.id] = task
            task.state       = TaskState.RUNNING
            task.assigned_to = self.node_id
            self.my_tasks.append(task.id)

    def execute(self, task: Task) -> dict:
        self.log.info(f"Ejecutando {task.task_type} [{task.id}]")
        try:
            result = run_model(task.task_type, task.payload)
            with self._lock:
                task.state  = TaskState.DONE
                task.result = result
                if task.id in self.my_tasks: self.my_tasks.remove(task.id)
                self._done += 1; self._update_rep()
            self.log.info(f"OK {task.id}: {str(result)[:80]}")
            return result
        except Exception as e:
            with self._lock:
                task.state = TaskState.FAILED
                if task.id in self.my_tasks: self.my_tasks.remove(task.id)
                self._failed += 1; self._update_rep()
            self.log.error(f"FALLO {task.id}: {e}")
            return {'error': str(e)}

    def _update_rep(self):
        t = self._done + self._failed
        if t:
            raw = self._done / t
            self.reputation = max(0.1, min(2.0,
                0.8*self.reputation + 0.2*(raw*2.0)))

    def to_dict(self, t: Task) -> dict:
        return {'id':t.id,'task_type':t.task_type,'origin_id':t.origin_id,
                'priority':t.priority,'payload':t.payload,
                'created_at':t.created_at,'deadline':t.deadline,
                'state':t.state,'assigned_to':t.assigned_to,'result':t.result}

    def from_dict(self, d: dict) -> Task:
        return Task(id=d['id'],task_type=d['task_type'],
                    origin_id=d['origin_id'],priority=d['priority'],
                    payload=d['payload'],created_at=d['created_at'],
                    deadline=d['deadline'],state=d.get('state',TaskState.PENDING),
                    assigned_to=d.get('assigned_to',-1),
                    result=d.get('result',{}))