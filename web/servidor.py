"""Servidor HTTP local + Server-Sent Events para la interfaz web.

Sólo biblioteca estándar (http.server). Un hilo de fondo (Sesion) avanza
la simulación; cada conexión HTTP se atiende en su propio hilo
(ThreadingHTTPServer) y toma `sesion.lock` para leer o mutar `sesion.sim`.
"""
import json
import mimetypes
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from web import estado

_AQUI = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(_AQUI, "static")
REPORTES_DIR = os.path.join(os.path.dirname(_AQUI), "reportes")

DESCRIPCIONES_ESCENARIOS = {
    "base": "4 Gateway juntos en el piso 3 y 3 Nodos de usuario en los "
           "pisos 1 y 2: el caso de referencia.",
    "colapso_progresivo": "Como base, con baterías escalonadas que se "
                          "gastan rápido: los Gateway van cayendo uno "
                          "tras otro.",
    "particion": "Alcance de radio reducido y dos parejas de Gateway en "
                "esquinas opuestas: la malla arranca partida en dos.",
    "rescatista_perdido": "Como base, pero un Gateway se aleja y pierde "
                         "el contacto con el resto.",
    "denso": "8 Gateway y 6 Nodos de usuario: una malla más poblada.",
}


def _es_subruta(base, ruta):
    base = os.path.realpath(base)
    objetivo = os.path.realpath(ruta)
    return objetivo == base or objetivo.startswith(base + os.sep)


def listar_escenarios():
    from main import ESCENARIOS_DIR, ESCENARIOS_DISPONIBLES
    predefinidos = [
        {"nombre": n, "descripcion": DESCRIPCIONES_ESCENARIOS.get(n, "")}
        for n in ESCENARIOS_DISPONIBLES
    ]
    archivos = []
    for base, _dirs, nombres in os.walk(ESCENARIOS_DIR):
        for nombre in sorted(nombres):
            if nombre.endswith((".json", ".txt")):
                ruta = os.path.relpath(os.path.join(base, nombre),
                                       ESCENARIOS_DIR)
                if ruta.replace(".json", "").replace(".txt", "") in \
                        ESCENARIOS_DISPONIBLES and os.path.dirname(ruta) == "":
                    continue  # ya está en 'predefinidos'
                archivos.append(ruta)
    return {"predefinidos": predefinidos, "archivos": sorted(archivos)}


class Servidor(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        import sys
        exc = sys.exc_info()[1]
        if isinstance(exc, (BrokenPipeError, ConnectionResetError)):
            return  # un cliente (p. ej. un SSE) se desconectó; no es un error
        super().handle_error(request, client_address)


class ManejadorWeb(BaseHTTPRequestHandler):
    sesion = None  # inyectado por crear_servidor() antes de arrancar
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    # ---------- utilidades de respuesta ----------
    def _json(self, status, datos):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _texto(self, status, texto, content_type="text/plain; charset=utf-8"):
        cuerpo = texto.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _archivo(self, ruta):
        if not os.path.isfile(ruta):
            self._texto(404, "no encontrado")
            return
        ctype, _ = mimetypes.guess_type(ruta)
        with open(ruta, "rb") as f:
            cuerpo = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    # ---------- GET ----------
    def do_GET(self):
        url = urlparse(self.path)
        ruta = url.path
        consulta = parse_qs(url.query)

        def entero(nombre, defecto=0):
            try:
                return int(consulta.get(nombre, [defecto])[0])
            except ValueError:
                return defecto

        if ruta == "/":
            self._archivo(os.path.join(STATIC_DIR, "index.html"))
        elif ruta.startswith("/static/"):
            objetivo = os.path.join(STATIC_DIR, ruta[len("/static/"):])
            if not _es_subruta(STATIC_DIR, objetivo):
                self._texto(403, "prohibido")
                return
            self._archivo(objetivo)
        elif ruta == "/api/estado":
            with self.sesion.lock:
                datos = self.sesion.frame()
            self._json(200, datos)
        elif ruta == "/api/stream":
            self._stream_sse()
        elif ruta.startswith("/api/nodo/"):
            self._nodo(ruta[len("/api/nodo/"):])
        elif ruta == "/api/series":
            with self.sesion.lock:
                datos = estado.series(self.sesion.sim, entero("desde"),
                                      entero("desde_evento"), entero("ultimas"))
                datos["generacion"] = self.sesion.generacion
            self._json(200, datos)
        elif ruta == "/api/paquetes":
            origen = entero("origen", None)
            with self.sesion.lock:
                datos = {"origen": origen,
                         "paquetes": estado.paquetes_de_origen(self.sesion.sim, origen)}
            self._json(200, datos)
        elif ruta == "/api/matriz":
            with self.sesion.lock:
                datos = estado.matriz_conocimiento(self.sesion.sim)
            self._json(200, datos)
        elif ruta == "/api/cobertura":
            with self.sesion.lock:
                datos = estado.cobertura(self.sesion.sim)
            self._json(200, datos)
        elif ruta == "/api/escenario/actual":
            posiciones = consulta.get("posiciones", ["iniciales"])[0]
            with self.sesion.lock:
                datos = estado.escenario_actual(self.sesion.sim, posiciones)
            self._json(200, datos)
        elif ruta == "/api/inspector":
            with self.sesion.lock:
                texto = estado.inspector_texto(self.sesion.sim)
            self._texto(200, texto)
        elif ruta == "/api/escenarios":
            self._json(200, listar_escenarios())
        elif ruta.startswith("/api/reportes/"):
            self._reporte(ruta[len("/api/reportes/"):])
        else:
            self._texto(404, "no encontrado")

    def _nodo(self, sub):
        try:
            nid = int(sub)
        except ValueError:
            self._json(400, {"error": "id inválido"})
            return
        with self.sesion.lock:
            detalle = estado.nodo_detalle(self.sesion.sim, nid)
        if detalle is None:
            self._json(404, {"error": f"no existe el nodo {nid}"})
            return
        self._json(200, detalle)

    def _reporte(self, sub):
        if ".." in sub.split("/"):
            self._texto(403, "prohibido")
            return
        objetivo = os.path.join(REPORTES_DIR, sub)
        if not _es_subruta(REPORTES_DIR, objetivo):
            self._texto(403, "prohibido")
            return
        self._archivo(objetivo)

    def _stream_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        ultima_version = -1
        try:
            while True:
                with self.sesion.cond:
                    self.sesion.cond.wait(timeout=1.0)
                    version = self.sesion.version
                    cuerpo = self.sesion.ultimo_frame_json
                if cuerpo is not None and version != ultima_version:
                    ultima_version = version
                    self.wfile.write(
                        f"event: frame\ndata: {cuerpo}\n\n".encode("utf-8"))
                else:
                    self.wfile.write(b": keep-alive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    # ---------- POST ----------
    def do_POST(self):
        if urlparse(self.path).path != "/api/comando":
            self._texto(404, "no encontrado")
            return
        largo = int(self.headers.get("Content-Length") or 0)
        crudo = self.rfile.read(largo) if largo else b"{}"
        try:
            cuerpo = json.loads(crudo or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"ok": False, "error": "JSON inválido"})
            return
        if not isinstance(cuerpo, dict):
            self._json(400, {"ok": False, "error": "se esperaba un objeto JSON"})
            return
        accion = cuerpo.get("accion")
        if not accion:
            self._json(400, {"ok": False, "error": "falta 'accion'"})
            return
        try:
            resultado = self.sesion.comando(accion, cuerpo)
        except ValueError as e:
            self._json(400, {"ok": False, "error": str(e)})
            return
        respuesta = {"ok": True}
        if isinstance(resultado, dict):
            respuesta.update(resultado)
        self._json(200, respuesta)
        if accion == "terminar":
            threading.Thread(target=self.server.shutdown, daemon=True).start()


def crear_servidor(sesion, puerto=8765):
    ManejadorWeb.sesion = sesion
    try:
        return Servidor(("127.0.0.1", puerto), ManejadorWeb)
    except OSError as e:
        raise ValueError(
            f"no se pudo abrir el puerto {puerto} ({e}); prueba con "
            f"--puerto <otro número>")


def ejecutar_servidor(sesion, puerto=8765, abrir=True):
    httpd = crear_servidor(sesion, puerto)
    url = f"http://127.0.0.1:{puerto}/"
    print(f"Interfaz web en {url}  (Ctrl+C para salir)")
    sesion.iniciar_hilo()
    if abrir:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        print("\nCerrando sesión...")
    finally:
        sesion.detener_hilo()
        try:
            carpeta = sesion.exportar()
            print(f"Análisis y reportes exportados en {carpeta}{os.sep}")
        except ValueError as e:
            print(f"[web] no se exportó: {e}")
        httpd.server_close()
