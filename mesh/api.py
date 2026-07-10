import logging
import socket
import threading
import time
import json, struct
from typing import Optional


BUFFER        = 65535

def encode(msg: dict) -> bytes:
    raw = json.dumps(msg, separators=(',', ':')).encode()
    return struct.pack('>I', len(raw)) + raw

def decode_tcp(sock) -> Optional[dict]:
    try:
        h = b''
        while len(h) < 4:
            c = sock.recv(4 - len(h))
            if not c: return None
            h += c
        length = struct.unpack('>I', h)[0]
        if length > 10_000_000: return None
        d = b''
        while len(d) < length:
            c = sock.recv(min(length - len(d), BUFFER))
            if not c: return None
            d += c
        return json.loads(d.decode())
    except Exception: return None

class CtrlAPI:
    def __init__(self, node: "MeshNode",CTRL_PORT):
        self.node = node
        self.log  = logging.getLogger(f"Ctrl[N{node.node_id}]")
        self.CTRL_PORT = CTRL_PORT
    def start(self):
        threading.Thread(target=self._serve, daemon=True, name="ctrl-api").start()

    def _serve(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(('127.0.0.1', self.CTRL_PORT))
        srv.listen(5); srv.settimeout(2.0)
        self.log.info(f"CtrlAPI en 127.0.0.1:{self.CTRL_PORT}")
        while self.node._running:
            try:
                conn,_ = srv.accept()
                threading.Thread(target=self._handle,
                                 args=(conn,), daemon=True).start()
            except socket.timeout: continue
            except Exception as e: self.log.error(f"Accept: {e}")
        srv.close()

    def _handle(self, conn):
        try:
            msg = decode_tcp(conn)
            if not msg: return
            resp = self._dispatch(msg.get('cmd',''), msg)
            conn.sendall(encode(resp))
        except Exception as e:
            try: conn.sendall(encode({'error':str(e)}))
            except: pass
        finally: conn.close()

    def _dispatch(self, cmd: str, msg: dict) -> dict:
        node = self.node; now = time.time()
        if cmd == 'status':
            return node.status()
        elif cmd == 'peers':
            with node.router._lock:
                return {'peers':[{
                    'node_id':p.node_id,'ip':p.ip,'battery':p.battery,
                    'load':p.load,'reputation':round(p.reputation,3),
                    'hops':p.hops,'tq':round(p.tq,3),'in_alert':p.in_alert,
                    'lost':p.is_lost(now,node.TIMEOUT_ALERT),'last_seen':round(now-p.last_seen,1)
                } for p in node.router.peers.values()]}
        elif cmd == 'routes':
            with node.router._lock:
                return {'routes':[{
                    'dest':r.dest,'via_ip':r.via_ip,'via_id':r.via_id,
                    'hops':r.hops,'tq':round(r.tq,3),
                    'last_seen':r.last_seen,'seq':r.seq
                } for r in node.router.routes.values()]}
        elif cmd == 'mem_read':
            key = msg.get('key')
            if key: return {'value': node.memory.read(key)}
            return {'entries': node.memory.all_entries()}
        elif cmd == 'mem_write':
            key = msg.get('key'); val = msg.get('value')
            if not key: return {'ok': False}
            node.memory.write(key, val); return {'ok': True}
        elif cmd == 'submit_task':
            t = node.submit_task(msg.get('task_type','LinReg'),
                                 msg.get('payload',{}),
                                 msg.get('priority',2))
            return {'task_id':t.id,'assigned_to':t.assigned_to,'state':t.state}
        elif cmd == 'tasks':
            with node.scheduler._lock:
                return {'tasks':[node.scheduler.to_dict(t)
                                 for t in node.scheduler.tasks.values()]}
        elif cmd == 'fault_log':
            return {'log':node.fault_mgr.recent_log(20),
                    'failed':list(node.fault_mgr.failed)}
        return {'error': f'Cmd desconocido: {cmd}'}