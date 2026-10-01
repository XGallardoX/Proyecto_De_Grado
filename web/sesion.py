"""Sesion: dueña de una Simulation en el servidor web.

Un solo lock protege todo acceso a `sim` (no es thread-safe y todo el
azar de la simulación sale del módulo `random` global). El hilo de
simulación (`_bucle`) lo toma para avanzar en lotes de pasos; los
comandos HTTP lo toman para aplicar una acción o para serializar un
frame, y nunca tocan `sim` fuera de él.

Para elegir una semilla automática se usa `secrets`, nunca `random`:
consumir `random` fuera de los caminos que ya existen en `sim`/`mesh`
rompería la reproducibilidad de la corrida.
"""
import json
import os
import secrets
import threading
import time

from analysis.visualizer import (build_analysis_figure, interpretar_mensaje,
                                 siguiente_escenario)
from web import estado

SEMILLA_MAXIMA = 2 ** 31 - 1
VELOCIDADES_VALIDAS = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0)
PASO_DT_BASE = 1.0 / 18.0   # s reales por paso de simulación a velocidad 1x
PUBLICAR_CADA = 1.0 / 18.0  # ritmo de publicación de frames (~18 Hz)
MAX_PASOS_POR_LOTE = 400    # tope por iteración del hilo, por si acumula de más
PRESUPUESTO_MAXIMA_S = 0.04  # s reales por iteración cuando velocidad="maxima"

# Parámetros que 'parametro' puede tocar en vivo: sólo claves que el núcleo
# vuelve a leer de sim.cfg en cada paso (verificado una por una):
#   RadioMedium.reliability -> rango_comm, falloff, perdida_base,
#     floor_atten (medium.cfg es el mismo dict que sim.cfg);
#   SimNode.tick -> timeout, beacon_cada, batman_cada, battery_drain,
#     battery_drain_nodo; SimNode._make_ogm -> ttl;
#   SimNode.move -> move_speed, movilidad.
# (tipo, mínimo, máximo) o (str, opciones).
PARAMETROS = {
    "rango_comm": (float, 4.0, 60.0),
    "falloff": (float, 0.0, 1.5),
    "perdida_base": (float, 0.0, 1.0),
    "floor_atten": (float, 0.0, 1.0),
    "timeout": (float, 1.0, 300.0),
    "ttl": (int, 1, 20),
    "beacon_cada": (float, 0.5, 30.0),
    "batman_cada": (float, 0.5, 30.0),
    "battery_drain": (float, 0.0, 5.0),
    "battery_drain_nodo": (float, 0.0, 5.0),
    "move_speed": (float, 0.0, 2.0),
    "movilidad": (str, ("seguir", "repartir")),
}
PARAMETROS_EDITABLES = tuple(PARAMETROS)


def _valor_parametro(clave, valor):
    spec = PARAMETROS[clave]
    if spec[0] is str:
        if valor not in spec[1]:
            raise ValueError(f"'{clave}' debe ser una de {', '.join(spec[1])}")
        return valor
    tipo, minimo, maximo = spec
    try:
        v = tipo(float(valor))
    except (TypeError, ValueError):
        raise ValueError(f"'{clave}' debe ser numérico")
    if not (minimo <= v <= maximo):
        raise ValueError(f"'{clave}' debe estar entre {minimo:g} y {maximo:g}")
    return v


def generar_semilla():
    """Una semilla al azar sin tocar el módulo `random` global."""
    return secrets.randbelow(SEMILLA_MAXIMA - 1) + 1


class Sesion:
    def __init__(self, sim, info, build_args, semilla, velocidad=1.0):
        self.lock = threading.RLock()
        self.cond = threading.Condition()
        self.sim = sim
        self.info = info
        self.build_args = dict(build_args)
        self.semilla = semilla
        self.velocidad = velocidad   # float, o "maxima"
        self.error = None
        self.intervenciones = []
        self.generacion = 0   # sube con cada reconstrucción (reiniciar/cargar)

        self.version = 0
        self.ultimo_frame_json = None

        self._activo = False
        self._hilo = None

    # ── ciclo de vida del hilo de simulación ──────────────────────────
    def iniciar_hilo(self):
        if self._hilo is not None:
            return
        self._activo = True
        self._hilo = threading.Thread(target=self._bucle, daemon=True)
        self._hilo.start()

    def detener_hilo(self):
        self._activo = False
        if self._hilo is not None:
            self._hilo.join(timeout=2.0)
            self._hilo = None

    def _step_seguro(self):
        try:
            self.sim.step()
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
            self.sim.paused = True

    def _bucle(self):
        acumulado = 0.0
        anterior = time.monotonic()
        while self._activo:
            ahora = time.monotonic()
            dt_real = ahora - anterior
            anterior = ahora
            with self.lock:
                if self.error is None and not self.sim.paused:
                    if self.velocidad == "maxima":
                        limite = time.monotonic() + PRESUPUESTO_MAXIMA_S
                        while self.error is None and time.monotonic() < limite:
                            self._step_seguro()
                    else:
                        acumulado += dt_real * self.velocidad / PASO_DT_BASE
                        pasos = min(int(acumulado), MAX_PASOS_POR_LOTE)
                        acumulado -= pasos
                        for _ in range(pasos):
                            self._step_seguro()
                self._publicar()
            time.sleep(PUBLICAR_CADA)

    def _publicar(self):
        """Serializa un frame y despierta a los clientes SSE. Se llama bajo
        el lock; sólo hace trabajo de Python puro (json.dumps), sin I/O de
        red, así que no lo retiene mucho tiempo."""
        cuerpo = json.dumps(self.frame(), ensure_ascii=False)
        with self.cond:
            self.ultimo_frame_json = cuerpo
            self.version += 1
            self.cond.notify_all()

    # ── serialización (llamar con self.lock tomado, o aceptar la carrera
    #    benigna de una lectura consistente de Python) ──────────────────
    def frame(self):
        return estado.frame(self.sim, velocidad=self.velocidad,
                            semilla=self.semilla, error=self.error,
                            generacion=self.generacion,
                            static=bool(self.build_args.get("static")),
                            intervenciones=len(self.intervenciones))

    # ── avance síncrono, para pruebas (sin hilo) ──────────────────────
    def avanzar_sincrono(self, pasos):
        with self.lock:
            for _ in range(pasos):
                self._step_seguro()

    # ── reconstrucción ────────────────────────────────────────────────
    def _reconstruir(self, build_args, semilla):
        # import diferido: evita el ciclo main -> web.sesion -> main
        from main import construir_simulacion, fijar_semilla
        fijar_semilla(semilla)
        sim, info = construir_simulacion(**build_args)
        self.sim, self.info = sim, info
        self.build_args = dict(build_args)
        self.semilla = semilla
        self.error = None
        self.intervenciones = []
        self.generacion += 1

    def reiniciar(self):
        """Vuelve a fijar la semilla de la sesión y reproduce la misma
        corrida desde cero. (En pygame, R no refija la semilla: aquí sí,
        a propósito, para que la sesión siempre sea reproducible.)"""
        with self.lock:
            self._reconstruir(self.build_args, self.semilla)
        return {"semilla": self.semilla}

    def cargar(self, datos):
        from main import ESCENARIOS_DISPONIBLES, ruta_escenario
        config_path = None
        if "escenario" in datos:
            nombre = datos["escenario"]
            if nombre not in ESCENARIOS_DISPONIBLES:
                raise ValueError(f"escenario desconocido: {nombre!r}")
            config_path = ruta_escenario(nombre)
        elif "archivo" in datos:
            config_path = _ruta_escenario_segura(datos["archivo"])
        try:
            n_nodes = int(datos.get("n_nodes", 2))
            n_gateways = int(datos.get("n_gateways", 1))
            semilla = datos.get("semilla")
            semilla = (int(semilla) if semilla not in (None, "")
                       else generar_semilla())
        except (TypeError, ValueError):
            raise ValueError("n_nodes, n_gateways y semilla deben ser enteros")
        if not (1 <= semilla <= SEMILLA_MAXIMA):
            raise ValueError(f"la semilla debe estar entre 1 y {SEMILLA_MAXIMA}")
        # Sin static/movilidad explícitos se conservan los de la sesión
        # (como la tecla S de pygame, que respeta --static/--movilidad).
        static = bool(datos.get("static", self.build_args.get("static", False)))
        movilidad = datos.get("movilidad", self.build_args.get("movilidad"))
        if movilidad not in (None, "seguir", "repartir"):
            raise ValueError("movilidad debe ser 'seguir' o 'repartir'")
        build_args = dict(config_path=config_path, n_nodes=n_nodes,
                          n_gateways=n_gateways, static=static,
                          movilidad=movilidad)
        with self.lock:
            self._reconstruir(build_args, semilla)
        return {"semilla": semilla, "escenario": self.sim.escenario}

    # ── comandos ───────────────────────────────────────────────────────
    def comando(self, accion, datos):
        manejador = self._MANEJADORES.get(accion)
        if manejador is None:
            raise ValueError(f"acción desconocida: {accion!r}")
        return manejador(self, datos)

    def _registrar(self, accion, datos):
        self.intervenciones.append({"t": self.sim.t, "accion": accion,
                                    "datos": datos})

    def _c_pausar(self, datos):
        with self.lock:
            self.sim.paused = True
        return None

    def _c_reanudar(self, datos):
        with self.lock:
            if self.error:
                raise ValueError("la sesión tiene un error; usa 'reiniciar'")
            self.sim.paused = False
        return None

    def _c_paso(self, datos):
        with self.lock:
            if self.error:
                raise ValueError("la sesión tiene un error; usa 'reiniciar'")
            if not self.sim.paused:
                raise ValueError("'paso' sólo vale en pausa")
            # Simulation.step() no avanza si paused es verdadero: se
            # despausa sólo para este paso y se vuelve a pausar.
            self.sim.paused = False
            self._step_seguro()
            self.sim.paused = True
        return None

    def _c_velocidad(self, datos):
        valor = datos.get("valor")
        if valor == "maxima":
            v = "maxima"
        else:
            try:
                v = float(valor)
            except (TypeError, ValueError):
                raise ValueError("'valor' debe ser un número o 'maxima'")
            if not (0.25 <= v <= 8.0):
                raise ValueError("'valor' debe estar entre 0.25 y 8.0, o "
                                 "'maxima'")
        with self.lock:
            self.velocidad = v
        return {"velocidad": v}

    def _c_reiniciar(self, datos):
        return self.reiniciar()

    def _c_cargar(self, datos):
        return self.cargar(datos)

    def _c_caer(self, datos):
        nid = _id_requerido(datos)
        with self.lock:
            n = self.sim.nodes.get(nid)
            if n is None:
                raise ValueError(f"no existe el nodo {nid}")
            self.sim.fail_node(nid)
            self._registrar("caer", {"id": nid})
        return None

    def _c_recuperar(self, datos):
        nid = _id_requerido(datos)
        with self.lock:
            n = self.sim.nodes.get(nid)
            if n is None:
                raise ValueError(f"no existe el nodo {nid}")
            self.sim.recover_node(nid)
            self._registrar("recuperar", {"id": nid})
        return None

    def _c_agregar_nodo(self, datos):
        rol = datos.get("rol", "N")
        if rol not in ("G", "N"):
            raise ValueError("'rol' debe ser 'G' o 'N'")
        x, y = datos.get("x"), datos.get("y")
        if (x is None) != (y is None):
            raise ValueError("hay que pasar 'x' e 'y' juntos (o ninguno)")
        if x is not None:
            x, y = _numero(x, "x"), _numero(y, "y")
        with self.lock:
            nuevo = self.sim.add_node(rol, x, y)
            registro = {"rol": rol}
            if x is not None:
                n = self.sim.nodes[nuevo]
                registro.update(x=n.x, y=n.y)
            self._registrar("agregar_nodo", registro)
        return {"id": nuevo}

    def _c_mover_nodo(self, datos):
        nid = _id_requerido(datos)
        x, y = _numero(datos.get("x"), "x"), _numero(datos.get("y"), "y")
        with self.lock:
            pos = self.sim.mover_nodo(nid, x, y)
            if pos is None:
                raise ValueError(f"no existe el nodo {nid}")
            self._registrar("mover_nodo", {"id": nid, "x": pos[0], "y": pos[1]})
        return {"x": pos[0], "y": pos[1]}

    def _c_eliminar_nodo(self, datos):
        nid = _id_requerido(datos)
        with self.lock:
            if nid not in self.sim.nodes:
                raise ValueError(f"no existe el nodo {nid}")
            antes = len(self.sim.nodes)
            self.sim.remove_node(nid)
            if len(self.sim.nodes) == antes:
                raise ValueError("no se puede eliminar: es el único Gateway")
            self._registrar("eliminar_nodo", {"id": nid})
        return None

    def _c_mensaje(self, datos):
        texto = datos.get("texto")
        if not texto:
            raise ValueError("falta 'texto' (formato 'G1>N2 hola')")
        partes = interpretar_mensaje(texto)
        if partes is None:
            raise ValueError("formato inválido; usa 'G1>N2 texto'")
        origen, destino, cuerpo = partes
        with self.lock:
            ids = {n.label: n.id for n in self.sim.nodes.values()}
            faltan = [e for e in (origen, destino) if e not in ids]
            if faltan:
                raise ValueError(f"no existe el nodo {' ni '.join(faltan)}")
            if origen == destino:
                raise ValueError("el origen y el destino son el mismo nodo")
            a, b = self.sim.nodes[ids[origen]], self.sim.nodes[ids[destino]]
            convergida = a.router.routes.get(b.id) is not None
            camino = self.sim.send_unicast(a.id, b.id, cuerpo)
            self._registrar("mensaje", {"texto": texto})
            motivo = None
            if camino is None:
                motivo = (f"{a.label} está caído" if not a.alive else
                          f"{b.label} está caído" if not b.alive else
                          "no existe ningún camino en la malla (partición)")
            etiquetas = ([self.sim.label_of(i) for i in camino]
                         if camino else None)
            ids_camino = list(camino) if camino else None
        return {"camino": etiquetas, "ids": ids_camino,
                "entregado": camino is not None, "motivo": motivo,
                "ruta_batman_convergida": convergida}

    def _c_cambiar_semilla(self, datos):
        """Reconstruye la misma configuración con otra semilla."""
        try:
            semilla = int(datos.get("semilla"))
        except (TypeError, ValueError):
            raise ValueError("'semilla' debe ser un entero")
        if not (1 <= semilla <= SEMILLA_MAXIMA):
            raise ValueError(f"la semilla debe estar entre 1 y {SEMILLA_MAXIMA}")
        with self.lock:
            self._reconstruir(self.build_args, semilla)
        return {"semilla": semilla}

    def _c_parametro(self, datos):
        clave = _clave_parametro(datos)
        valor = _valor_parametro(clave, datos.get("valor"))
        with self.lock:
            self.sim.set_param(clave, valor)
            self._registrar("parametro", {"clave": clave, "valor": valor})
        return {"clave": clave, "valor": valor}

    def _c_restaurar_parametro(self, datos):
        """Vuelve un parámetro al valor con que arrancó la sesión (el del
        escenario, o el por defecto del simulador)."""
        clave = _clave_parametro(datos)
        with self.lock:
            valor = self.sim._base_cfg[clave]
            self.sim.set_param(clave, valor)
            self._registrar("parametro", {"clave": clave, "valor": valor})
        return {"clave": clave, "valor": valor}

    def _c_validar_escenario(self, datos):
        from web import editor
        return editor.validar(datos.get("escenario"))

    def _c_guardar_escenario(self, datos):
        from web import editor
        return editor.guardar(datos.get("escenario"), datos.get("nombre"),
                              bool(datos.get("sobrescribir", False)))

    def _c_exportar(self, datos):
        carpeta = self.exportar()
        return {"carpeta": carpeta,
                "archivos": sorted(os.listdir(carpeta)),
                "intervenciones": len(self.intervenciones),
                "comando_equivalente": self.comando_equivalente()}

    def _c_terminar(self, datos):
        return {"mensaje": "cerrando sesión"}

    _MANEJADORES = {
        "pausar": _c_pausar, "reanudar": _c_reanudar, "paso": _c_paso,
        "velocidad": _c_velocidad, "reiniciar": _c_reiniciar,
        "cargar": _c_cargar, "caer": _c_caer, "recuperar": _c_recuperar,
        "agregar_nodo": _c_agregar_nodo, "eliminar_nodo": _c_eliminar_nodo,
        "mover_nodo": _c_mover_nodo, "cambiar_semilla": _c_cambiar_semilla,
        "mensaje": _c_mensaje, "parametro": _c_parametro,
        "restaurar_parametro": _c_restaurar_parametro,
        "validar_escenario": _c_validar_escenario,
        "guardar_escenario": _c_guardar_escenario,
        "exportar": _c_exportar, "terminar": _c_terminar,
    }

    # ── exportar / comando equivalente ────────────────────────────────
    def comando_equivalente(self):
        """El comando de terminal que reproduce esta sesión, o None si
        hubo intervenciones (ver contrato de paridad, sección 3)."""
        if self.intervenciones:
            return None
        from main import ESCENARIOS_DISPONIBLES, ruta_escenario
        a = self.build_args
        partes = ["python", "main.py", "--headless"]
        if a.get("config_path"):
            nombre = None
            for esc in ESCENARIOS_DISPONIBLES:
                if os.path.abspath(a["config_path"]) == \
                        os.path.abspath(ruta_escenario(esc)):
                    nombre = esc
                    break
            if nombre:
                partes += ["--escenario", nombre]
            else:
                ruta = a["config_path"]
                relativa = os.path.relpath(ruta)
                partes += ["--config",
                           ruta if relativa.startswith("..") else relativa]
        else:
            partes += ["-n", str(a.get("n_nodes", 2)),
                      "-g", str(a.get("n_gateways", 1))]
        if a.get("static"):
            partes.append("--static")
        if a.get("movilidad"):
            partes += ["--movilidad", a["movilidad"]]
        partes += ["--seed", str(self.semilla)]
        partes += ["--duracion", str(round(self.sim.t, 1))]
        return " ".join(partes)

    def exportar(self):
        with self.lock:
            png = build_analysis_figure(self.sim, None)
            if png is None:
                raise ValueError(
                    "corrida demasiado corta para exportar (hacen falta "
                    "al menos 1 s simulado)")
            carpeta = os.path.dirname(png)
            datos_sesion = {
                "escenario": self.sim.escenario,
                "semilla": self.semilla,
                "configuracion": self.build_args,
                "intervenciones": list(self.intervenciones),
                "comando_equivalente": self.comando_equivalente(),
            }
            with open(os.path.join(carpeta, "sesion_web.json"), "w",
                     encoding="utf-8") as f:
                json.dump(datos_sesion, f, indent=2, ensure_ascii=False)
        return carpeta


def _numero(valor, nombre):
    try:
        v = float(valor)
    except (TypeError, ValueError):
        raise ValueError(f"'{nombre}' debe ser numérico")
    if v != v or v in (float("inf"), float("-inf")):
        raise ValueError(f"'{nombre}' debe ser un número finito")
    return v


def _clave_parametro(datos):
    clave = datos.get("clave")
    if clave not in PARAMETROS:
        raise ValueError(
            f"parámetro no editable: {clave!r} (válidos: "
            f"{', '.join(PARAMETROS_EDITABLES)})")
    return clave


def _id_requerido(datos):
    nid = datos.get("id")
    if nid is None:
        raise ValueError("falta 'id'")
    try:
        return int(nid)
    except (TypeError, ValueError):
        raise ValueError("'id' debe ser un entero")


def _ruta_escenario_segura(nombre):
    """Resuelve un archivo dentro de escenarios/ (incluida escenarios/casos/)
    sin permitir salir de esa carpeta."""
    from main import ESCENARIOS_DIR
    objetivo = os.path.realpath(os.path.join(ESCENARIOS_DIR, nombre))
    base = os.path.realpath(ESCENARIOS_DIR)
    if objetivo != base and not objetivo.startswith(base + os.sep):
        raise ValueError(f"archivo de escenario fuera de escenarios/: {nombre!r}")
    if not os.path.isfile(objetivo):
        raise ValueError(f"archivo no encontrado: {nombre!r}")
    return objetivo


def construir_sesion(config_path=None, n_nodes=2, n_gateways=1,
                     static=False, movilidad=None, semilla=None,
                     velocidad=1.0):
    """Arma una Sesion lista para correr: fija la semilla (una generada al
    azar con `secrets` si no se pasa ninguna) y construye la Simulation con
    main.construir_simulacion, exactamente como --headless/--inspect.
    Lanza ValueError si el escenario o los parámetros son inválidos."""
    from main import construir_simulacion, fijar_semilla
    if semilla is None:
        semilla = generar_semilla()
    fijar_semilla(semilla)
    build_args = dict(config_path=config_path, n_nodes=n_nodes,
                      n_gateways=n_gateways, static=static,
                      movilidad=movilidad)
    sim, info = construir_simulacion(**build_args)
    return Sesion(sim, info, build_args, semilla, velocidad=velocidad)
