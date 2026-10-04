"""Laboratorio de experimentos de la interfaz web (Fase 3, parte 2).

Arma un lote (escenarios × semillas, el mismo formato de lotes/*.json) y
lo corre con `python main.py --batch <archivo>` en un **subproceso**.
Nunca en un hilo del servidor: compartiría el módulo `random` global con
la sesión en vivo y rompería la reproducibilidad de las dos. Como es
literalmente el comando de terminal, los resultados son los mismos que
en terminal, por construcción.

Por la misma razón, la validación que se hace acá antes de lanzar el
subproceso es sólo de lectura: el formato del lote (analysis.lote) y el
de cada archivo de escenario (sim.config_loader). Nunca se construye una
Simulation en el proceso del servidor, porque eso consume `random`.
"""
import copy
import json
import os
import re
import subprocess
import sys
import threading
import time

from analysis import lote as lote_mod
from analysis.metrics import METRICAS_CORRIDA

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOTES_DIR = os.path.join(RAIZ, "lotes")
LAB_DIR = os.path.join(RAIZ, "reportes", "laboratorio")

# Topes para que un lote armado a mano no deje la máquina ocupada horas.
MAX_CORRIDAS = 300
MAX_DURACION_S = 3600.0
LINEAS_LOG = 40

_PROGRESO = re.compile(r"^\s*\[(\d+)/(\d+)\]")
_INICIO = re.compile(r"^Lote '.*': \d+ escenarios, (\d+) corridas -> (.+?)[\\/]?$")


def _ruta_config_segura(config):
    """Una ruta de escenario dentro de escenarios/ (con o sin el prefijo
    'escenarios/'). Devuelve (ruta absoluta, ruta relativa a la raíz)."""
    from main import ESCENARIOS_DIR
    if not isinstance(config, str) or not config:
        raise ValueError("'config' debe ser una ruta dentro de escenarios/")
    relativa = config[len("escenarios/"):] if config.startswith("escenarios/") \
        else config
    absoluta = os.path.realpath(os.path.join(ESCENARIOS_DIR, relativa))
    base = os.path.realpath(ESCENARIOS_DIR)
    if not absoluta.startswith(base + os.sep):
        raise ValueError(f"'config' fuera de escenarios/: {config!r}")
    if not os.path.isfile(absoluta):
        raise ValueError(f"archivo de escenario no encontrado: {config!r}")
    return absoluta, os.path.relpath(absoluta, RAIZ)


def validar_lote(lote):
    """Valida un lote armado en la interfaz con las mismas reglas que
    --batch, más los topes del laboratorio y que cada 'config' esté dentro
    de escenarios/. Devuelve (lote listo para escribir, especificación
    normalizada de analysis.lote). Lanza ValueError."""
    from main import ALTO, ANCHO, DT, DURACION_DEFAULT, ESCENARIOS_DISPONIBLES
    from main import N_PISOS, PISO_H
    from sim.config_loader import load_scenario

    if not isinstance(lote, dict):
        raise ValueError("se esperaba un lote (objeto con 'escenarios')")
    lote = copy.deepcopy(lote)
    if not lote.get("nombre"):
        lote["nombre"] = "laboratorio"
    entradas = lote.get("escenarios")
    if not isinstance(entradas, list) or not entradas:
        raise ValueError("el lote necesita al menos una entrada en 'escenarios'")
    absolutas = {}
    for i, entrada in enumerate(entradas):
        if isinstance(entrada, dict) and "config" in entrada:
            absoluta, relativa = _ruta_config_segura(entrada["config"])
            entrada["config"] = relativa
            absolutas[i] = absoluta
            load_scenario(absoluta, default_building=dict(
                ancho=ANCHO, alto=ALTO, piso_h=PISO_H, n_pisos=N_PISOS))

    # analysis.lote valida desde un archivo; las rutas 'config' se le pasan
    # absolutas para que no dependa del directorio de trabajo del servidor
    para_validar = copy.deepcopy(lote)
    for i, absoluta in absolutas.items():
        para_validar["escenarios"][i]["config"] = absoluta
    os.makedirs(LAB_DIR, exist_ok=True)
    temporal = os.path.join(LAB_DIR, f".validar_{os.getpid()}_{threading.get_ident()}.json")
    try:
        with open(temporal, "w", encoding="utf-8") as f:
            json.dump(para_validar, f)
        spec = lote_mod.cargar_lote(temporal, ESCENARIOS_DISPONIBLES,
                                    DURACION_DEFAULT, 2 * DT)
    finally:
        os.remove(temporal)

    total = sum(len(e["semillas"]) for e in spec["escenarios"])
    if total > MAX_CORRIDAS:
        raise ValueError(f"el lote tiene {total} corridas; el laboratorio "
                         f"admite hasta {MAX_CORRIDAS} (para más, usa "
                         f"--batch en la terminal)")
    for e in spec["escenarios"]:
        if e["duracion"] > MAX_DURACION_S:
            raise ValueError(f"'{e['etiqueta']}': la duración máxima en el "
                             f"laboratorio es {MAX_DURACION_S:g} s")
    return lote, spec


def lotes_existentes():
    """Los lotes de lotes/*.json, para cargarlos en el laboratorio."""
    resultado = []
    if os.path.isdir(LOTES_DIR):
        for nombre in sorted(os.listdir(LOTES_DIR)):
            if not nombre.endswith(".json"):
                continue
            try:
                with open(os.path.join(LOTES_DIR, nombre), encoding="utf-8") as f:
                    contenido = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            resultado.append({"archivo": f"lotes/{nombre}", "lote": contenido})
    return resultado


class Laboratorio:
    """Un lote a la vez, en un subproceso `python main.py --batch`."""

    def __init__(self, python=None, raiz=RAIZ):
        self.python = python or sys.executable
        self.raiz = raiz
        self._lock = threading.Lock()
        self._proceso = None
        self._estado = self._vacio()

    @staticmethod
    def _vacio():
        return {"estado": "inactivo", "nombre": None, "archivo": None,
                "comando": None, "carpeta": None, "hechas": 0, "total": 0,
                "lineas": [], "error": None, "resultado": None,
                "inicio": None, "fin": None}

    def estado(self):
        with self._lock:
            datos = copy.deepcopy(self._estado)
        if datos["inicio"] is not None:
            datos["segundos"] = round((datos["fin"] or time.time())
                                      - datos["inicio"], 1)
        return datos

    def corriendo(self):
        with self._lock:
            return self._estado["estado"] == "corriendo"

    def iniciar(self, lote):
        """Valida el lote, lo guarda en reportes/laboratorio/ y lanza el
        subproceso. Lanza ValueError si es inválido o si ya hay uno."""
        if self.corriendo():
            raise ValueError("ya hay un lote corriendo: espera a que termine "
                             "o cancélalo")
        lote, spec = validar_lote(lote)
        os.makedirs(LAB_DIR, exist_ok=True)
        archivo = os.path.join(
            LAB_DIR, f"lote_{spec['nombre']}_{time.strftime('%Y%m%d_%H%M%S')}.json")
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump(lote, f, indent=2, ensure_ascii=False)
            f.write("\n")
        relativo = os.path.relpath(archivo, self.raiz)
        entorno = dict(os.environ, MPLBACKEND="Agg", PYTHONUNBUFFERED="1")
        try:
            proceso = subprocess.Popen(
                [self.python, "main.py", "--batch", relativo], cwd=self.raiz,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="replace", env=entorno)
        except OSError as e:
            raise ValueError(f"no se pudo lanzar el lote: {e}")
        with self._lock:
            self._proceso = proceso
            self._estado = self._vacio()
            self._estado.update(
                estado="corriendo", nombre=spec["nombre"], archivo=relativo,
                comando=f"python main.py --batch {relativo}",
                total=sum(len(e["semillas"]) for e in spec["escenarios"]),
                inicio=time.time())
        threading.Thread(target=self._seguir, args=(proceso,),
                         daemon=True).start()
        return self.estado()

    def cancelar(self):
        with self._lock:
            proceso = self._proceso
            if proceso is None or self._estado["estado"] != "corriendo":
                raise ValueError("no hay ningún lote corriendo")
            self._estado["estado"] = "cancelando"
        proceso.terminate()
        return self.estado()

    def detener(self):
        """Para el apagado del servidor: termina el subproceso si sigue."""
        with self._lock:
            proceso = self._proceso
        if proceso is not None and proceso.poll() is None:
            proceso.terminate()
            try:
                proceso.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proceso.kill()

    def esperar(self, timeout=None):
        """Espera a que termine el lote en curso (para las pruebas)."""
        limite = None if timeout is None else time.time() + timeout
        while True:
            with self._lock:
                if self._estado["estado"] not in ("corriendo", "cancelando"):
                    return True
            if limite is not None and time.time() > limite:
                return False
            time.sleep(0.05)

    # ── hilo que lee la salida del subproceso ──────────────────────────
    def _seguir(self, proceso):
        for linea in proceso.stdout:
            linea = linea.rstrip("\n")
            with self._lock:
                if self._proceso is not proceso:
                    continue
                e = self._estado
                e["lineas"] = (e["lineas"] + [linea])[-LINEAS_LOG:]
                m = _PROGRESO.match(linea)
                if m:
                    e["hechas"], e["total"] = int(m.group(1)), int(m.group(2))
                m = _INICIO.match(linea)
                if m:
                    e["total"] = int(m.group(1))
                    e["carpeta"] = m.group(2)
        codigo = proceso.wait()
        resultado, error = None, None
        with self._lock:
            carpeta = self._estado["carpeta"]
            cancelado = self._estado["estado"] == "cancelando"
        if cancelado:
            estado_final = "cancelado"
        elif codigo != 0:
            estado_final = "error"
            with self._lock:
                error = "\n".join(self._estado["lineas"][-8:]) or \
                    f"el proceso terminó con código {codigo}"
        else:
            try:
                resultado = self._leer_resultado(carpeta)
                estado_final = "terminado"
            except (OSError, ValueError, TypeError) as e:
                estado_final, error = "error", f"no se pudo leer el resumen: {e}"
        with self._lock:
            if self._proceso is proceso:
                self._estado.update(estado=estado_final, resultado=resultado,
                                    error=error, fin=time.time())

    def _leer_resultado(self, carpeta):
        if not carpeta:
            raise ValueError("el lote no informó su carpeta")
        ruta = os.path.join(self.raiz, carpeta, "resumen.json")
        with open(ruta, encoding="utf-8") as f:
            resumen = json.load(f)
        return {
            "carpeta": carpeta,
            "metadatos": resumen["metadatos"],
            "escenarios": resumen["escenarios"],
            "metricas": [{"clave": c, "etiqueta": et, "decimales": d}
                         for c, et, d in METRICAS_CORRIDA],
            "archivos": sorted(n for n in os.listdir(os.path.join(self.raiz, carpeta))
                               if os.path.isfile(os.path.join(self.raiz, carpeta, n))),
        }
