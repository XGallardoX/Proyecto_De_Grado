# Versión de escritorio del simulador: interfaz web local, paralela a la de terminal

Estoy trabajando en un simulador de redes mesh ad-hoc que corre el
protocolo B.A.T.M.A.N. real, no una reimplementación simplificada. Está
escrito en Python y es el componente técnico de nuestro proyecto de
grado, que hacemos entre dos personas (ver
`contexto/ESTADO_PROYECTO.md`). La versión por terminal ya está
cerrada y funciona bien: ventana pygame, `--headless`, `--inspect` y
`--batch`.

Ahora quiero una **versión de escritorio paralela**: una interfaz
gráfica moderna, muy interactiva y visualmente cuidada. Se sirve desde
un servidor local, se usa en el navegador y corre **exactamente el mismo
núcleo** que la versión de terminal. No es una reescritura ni un
reemplazo: las dos versiones conviven y dan los mismos resultados.

**Antes de escribir código**, lee este documento completo y contrástalo
con el repositorio, porque algunas afirmaciones pueden haber quedado
desactualizadas. Repórtame las discrepancias que encuentres. Después
ejecuta por fases (sección 5).

---

## 1. Encuadre del problema (indicación del director: guía todo el trabajo)

Nuestro director nos dijo: *"la idea es que el problema esté enfocado en la
necesidad de un simulador hecho a la medida para redes
descentralizadas"*.

Eso define para qué existe esta interfaz. No es un adorno. Es el
instrumento que hace **visible y experimentable** lo que un simulador de
propósito general no muestra bien, y por tanto lo que justifica
construir uno a la medida. El Capítulo 2 de la tesis
(`Plantilla/MainMatter/Cap2/M03-Chapter2.tex`, sección `sec:brecha`)
identifica tres vacíos:

1. ns-3, OMNeT++ y similares evalúan un *modelo* del protocolo, no su
   implementación.
2. Los emuladores sí corren código real, pero con un costo alto por
   nodo y sin un modelo de propagación tridimensional que contemple la
   atenuación entre pisos de un edificio.
3. Las herramientas P2P y blockchain operan en la capa de aplicación: no
   modelan el medio radio ni la movilidad física.

El simulador ocupa el punto intermedio. Corre las clases reales de
`mesh/` (`BatmanRouter`, `FaultManager`) en un solo proceso y sólo
sustituye el transporte por un modelo del medio radio que tiene en
cuenta la geometría del edificio. El caso de aplicación es la **Red de
Expansión de Cobertura**: Gateways (`G`) y Nodos de usuario (`N`), y se
evalúan la resiliencia y la conectividad de la malla ante fallos. Ese
framing ya está decidido; no lo reabras.

Esto tiene consecuencias concretas para la interfaz:

- **Tiene que mostrar que la red es descentralizada.** No hay
  coordinador ni vista global: cada nodo tiene su propia tabla de rutas,
  su propia detección de fallos y su propia visión de la red. La
  interfaz debe poder contrastar *lo que cada nodo cree* (el estado
  interno del `BatmanRouter` real) con *la verdad física* (los enlaces
  de radio del `RadioMedium`).
- **Tiene que dejar claro qué es código real y qué es modelo** (ver la
  sección 7).
- **Cada funcionalidad debe poder justificarse** como una capacidad "a
  la medida". La sección 9 pide documentar esa relación.
- **Vocabulario:** Gateway, Nodo de usuario, cobertura, conectividad y
  resiliencia. Nada de "rescatista" ni "superviviente", salvo el nombre
  heredado del escenario `rescatista_perdido`, que se conserva.

---

## 2. Lo que hay hoy (verifícalo)

- **`main.py`** es el único punto de entrada.
  - `construir_simulacion(config_path, n_nodes, n_gateways, static, movilidad)`
    devuelve `(sim, info)`.
  - Otras funciones: `fijar_semilla()`, `correr()`, `modo_headless()`,
    `modo_inspect()` y `ejecutar_lote()`.
  - Constantes: las del edificio, `DT = 0.5`, `DEFAULTS` y los colores
    `C_*`.
  - Flags: `-n/-g`, `--escenario`, `--config`, `--static`,
    `--movilidad`, `--headless`, `--duracion`, `--seed`, `--inspect`,
    `--batch` y `--msg`.
- **`sim/engine.py` (`Simulation`)**
  - Paso y estado: `step()` (no avanza si `paused` es verdadero), `t`,
    `nodes`, `medium`, `recorder` y `log_lines` (se recorta a 300 con
    `pop(0)`).
  - Operaciones interactivas: `fail_node`, `recover_node`, `add_node`
    (sólo crea un `N`, en posición aleatoria), `remove_node` (no deja
    borrar el único Gateway), `send_unicast` (BFS sobre los enlaces con
    fiabilidad > 0; devuelve el camino) y `set_param`.
  - Reinicio: `_build_world()`.
  - Consultas: `gateway_components`, `nodes_in_mesh`, `_union_find` y
    `summary`.
- **`sim/sim_node.py` (`SimNode`)**: `x`, `y`, `piso`, `alive`,
  `battery`, `role`, `label`, `color()`, `history` (≤ 80 puntos),
  `last_msg`, `t_beacon`, y un `router` (`BatmanRouter` real) y un
  `fault` (`FaultManager` real) por nodo.
- **`sim/radio.py` (`RadioMedium`)**: `reliability(a, b)`,
  `broadcast()`, contadores y `packets_visual`.
  - `_Packet` guarda coordenadas, color, `age` y `life`, que dura 1.4 s
    simulados.
  - El tipo OGM/BCN sólo se distingue por el color (`C_OGM`/`C_BCN`).
- **`analysis/metrics.py`**
  - `Recorder`: las series `t`, `alive_G`, `alive_N`, `comp_G`,
    `node_reach`, `avg_tq`, `avg_hops`, `max_silence`, `deliver_ratio`,
    `alerts_active` y `bandwidth`, más `events` como tuplas
    `(t, tipo, texto)`.
  - También están `resumen_corrida()` y `METRICAS_CORRIDA`.
- **`analysis/inspector.py`**: `snapshot_red(sim)`, el volcado en texto
  del estado interno.
- **`analysis/visualizer.py`**
  - `Visualizer` es la ventana pygame (1400×800). Corre a unos 9 s
    simulados por segundo real: `STEP_DT = 1/18` s real por paso de
    `DT = 0.5` s.
  - `build_analysis_figure()` hace la figura de 6 paneles y los reportes
    CSV/JSON/TXT en `reportes/<escenario>_<fecha_hora>/`.
  - `interpretar_mensaje()` parsea el formato `G1>N2 texto`.
- **Otros módulos de `analysis/`:** `reporter.py` (exportación) y
  `lote.py` (agregado de lotes).
- **`mesh/`** es el protocolo real. El simulador no usa `node.py`,
  `api.py`, `memory.py` ni `scheduler.py`.
  - Las rutas de `BatmanRouter` nunca expiran: si un nodo cae, los demás
    conservan su ruta con un `last_seen` cada vez más viejo.
- **Datos de prueba:** en `escenarios/` están los 5 predefinidos, los de
  ejemplo y la carpeta `casos/`. En `lotes/` están `ejemplo.json`,
  `casos.json` y `movilidad.json`.
- **`tests/`**: 144 pruebas `unittest`. Se corren con
  `venv/bin/python -m unittest discover -s tests`. El entorno es
  `venv/`, con Python 3.14; el `python3` del sistema no tiene numpy.
- **Documentación viva**
  - `README.md`, `docs/arquitectura.md`, `docs/movimiento_nodos.md` y
    `contexto/ESTADO_PROYECTO.md`.
  - `docs/guia_ejecucion.md`: sus números salen de corridas con semilla,
    así que también sirven de referencia de regresión.
- **Entorno**
  - No hay Node.js ni npm, y `sudo` pide contraseña interactiva: no se
    pueden instalar paquetes del sistema.
  - `pip` dentro del venv sí funciona.

---

## 3. Qué significa "paralela": contrato de paridad (no negociable)

1. **Un solo núcleo.**
   - La versión web importa `sim/`, `mesh/` y `analysis/` tal como
     están. Arma la simulación con `main.construir_simulacion()` y fija
     la semilla con `main.fijar_semilla()`.
   - **Nada del modelo se reimplementa en JavaScript.** La fiabilidad de
     los enlaces, la conectividad, los componentes, las rutas, las
     métricas y los caminos de los mensajes se calculan en Python y
     llegan ya calculados.
   - El navegador sólo dibuja, anima e interpola.
2. **Mismos resultados.** Con la misma configuración, la misma semilla y
   sin intervenciones, tras *k* pasos la sesión web tiene exactamente la
   misma serie del `Recorder` y el mismo `resumen_corrida()` que
   `correr()` en terminal. Esto se prueba (sección 8).
3. **Mismos archivos.**
   - "Exportar" en la web llama a `build_analysis_figure()` y deja la
     misma carpeta `reportes/<escenario>_<fecha_hora>/` con los mismos
     archivos que la terminal.
   - Además agrega un `sesion_web.json` con la configuración, la
     semilla, las intervenciones (cada una con su instante simulado) y
     el comando de terminal equivalente.
4. **Mismos escenarios.** La web carga los mismos `.json` y `.txt` con
   `sim/config_loader.py`. Lo que guarde el editor de escenarios (fase
   2) tiene que poder correrse con `python main.py --config ...`.
5. **La terminal no cambia.**
   - `--headless`, `--inspect`, `--batch` y la ventana pygame siguen
     funcionando igual y dando los mismos números.
   - Los resultados de `lotes/ejemplo.json` y `lotes/movilidad.json`
     deben salir idénticos antes y después de tu trabajo. Compara
     `corridas.csv` y los valores de `resumen.json`, ignorando las
     fechas. La línea base se toma en la fase 0.
6. **Las mismas funciones que pygame.** Todo lo que hoy hace la ventana
   pygame tiene equivalente en la web, atajos de teclado incluidos
   (tabla en la fase 1).

**Cambios al núcleo (`sim/`, `analysis/`):**

- Sólo aditivos, con valores por defecto que preservan el comportamiento
  actual.
- Sin consumir `random` en caminos de código que ya existen.
- Verificados con la regresión del punto 5.
- `mesh/` no se toca.

---

## 4. Arquitectura decidida

**Servidor HTTP local + interfaz en el navegador.**
`python main.py --web` arranca un servidor en `127.0.0.1` y abre el
navegador por defecto (con `webbrowser`). La simulación vive en el
proceso de Python. Por qué así:

- El núcleo queda en Python, así que la paridad sale por construcción.
- No hay Node.js en la máquina ni permisos de root. Por eso nada de
  Electron, Tauri ni pasos de compilación.
- Un navegador da canvas acelerado, CSS moderno y buena tipografía sin
  dependencias.
- Tiene que funcionar **sin internet**, porque la sustentación puede no
  tenerlo: nada de CDN en tiempo de ejecución.

Decisiones técnicas:

- **Backend sólo con la biblioteca estándar.**
  - `http.server.ThreadingHTTPServer` + **Server-Sent Events** (SSE)
    para el flujo de estado + `POST` JSON para los comandos.
  - Sin dependencias nuevas. Si encuentras una limitación concreta que
    lo impida, propón la dependencia, justifícala y espera mi aprobación
    antes de agregarla a `requirements.txt`.
- **Frontend sin compilación.**
  - HTML, CSS y JavaScript moderno con módulos ES nativos.
  - Canvas 2D para el mapa, con `devicePixelRatio` para pantallas de
    alta densidad.
  - Gráficas: dibujadas a mano en canvas/SVG, o con una librería pequeña
    copiada al repo (por ejemplo uPlot) con su licencia en
    `web/static/vendor/`.
  - Nada de React o Vue con compilación, y nada de npm.
- **Ventana nativa:** queda fuera del alcance obligatorio (ver fase 3).

Estructura propuesta. Ajústala si encuentras algo mejor, y explica por
qué:

```
web/
  __init__.py
  sesion.py      # Sesion: dueña de la Simulation, hilo de simulación,
                 # ritmo, lock, comandos e intervenciones
  estado.py      # funciones puras: Simulation -> dict serializable
                 # (frame, detalle de nodo, matriz, inspector)
  servidor.py    # HTTP + SSE + estáticos + rutas /api/*
  static/
    index.html
    css/app.css
    js/            # main.js, api.js, mapa.js, graficas.js, teclado.js, paneles/...
    vendor/        # sólo si se copia alguna librería (con su licencia)
```

Flags nuevas en `main.py`:

- `--web`; `--puerto` (8765 por defecto; si está ocupado, error claro o
  el siguiente libre); `--no-abrir`.
- `--web` se combina con `--escenario`, `--config`, `-n/-g`,
  `--static`, `--movilidad` y `--seed`, igual que la ventana pygame.
- Combinarlo con `--headless`, `--inspect`, `--batch` o `--duracion` es
  un error.

### Concurrencia (aquí es fácil equivocarse)

**Acceso al estado**

- `Simulation` no es thread-safe, y todo el azar sale del módulo global
  `random`. Por eso la `Sesion` tiene **un solo lock** que protege todo
  acceso a `sim`.
  - El hilo de simulación lo toma para cada lote de pasos y lo suelta
    entre lotes.
  - Los handlers HTTP lo toman para aplicar un comando o serializar, y
    nunca tocan `sim` fuera de él.
  - Se serializa a `dict` bajo el lock; se codifica a JSON fuera.
- Ningún otro código del proceso debe consumir `random`, porque se rompe
  la reproducibilidad. Para elegir una semilla usa `secrets` u
  `os.urandom`.
- Exportar (matplotlib con backend Agg) también va bajo el lock.

**Ritmo y publicación**

- A velocidad 1× el ritmo es el mismo que en pygame: unos 9 s simulados
  por segundo real.
  - Selector de velocidad de 0.25× a 8×, más "máxima".
  - Pausa, y "un paso" estando en pausa. Ojo: `step()` no avanza si
    `sim.paused` es verdadero.
- El hilo de simulación publica un *frame* unas 15–20 veces por segundo
  como máximo, aunque a velocidad máxima dé muchos pasos entre frame y
  frame.
- Despierta a los clientes SSE con una `Condition`. Los handlers SSE
  esperan con timeout y mandan *keep-alive*, para notar las
  desconexiones y el apagado.

**Fallos y ciclo de vida**

- Si el hilo de simulación lanza una excepción, el servidor no muere: la
  registra, la interfaz la muestra y la sesión se puede reiniciar.
- La sesión vive en el servidor. Recargar la página o abrir otra pestaña
  muestra el mismo estado; la selección de nodo es de cada cliente.
- `Ctrl+C` en la terminal, o "Terminar sesión" en la interfaz, exporta
  el análisis (como pygame al salir) y apaga de forma limpia. Cerrar la
  pestaña no detiene nada.

### API (orientativa)

| Método y ruta | Qué hace |
|---|---|
| `GET /`, `GET /static/...` | La interfaz |
| `GET /api/stream` | SSE: un evento `frame` por publicación |
| `GET /api/estado` | El frame actual (para el primer pintado) |
| `GET /api/nodo/<id>` | Detalle de un nodo: tabla de rutas, vecinos (`peers`: último oído, TQ, saltos, batería, en alerta), `fault.failed` y tiempo sin oír a cada vecino comparado con el `timeout` |
| `GET /api/series` | Series completas del `Recorder` y eventos (para reconstruir las gráficas al conectar) |
| `GET /api/inspector` | El texto de `snapshot_red(sim)` |
| `GET /api/escenarios` | Escenarios predefinidos y archivos de `escenarios/` y `escenarios/casos/` |
| `POST /api/comando` | `{"accion": ...}` → `{"ok": true, ...}` o `{"ok": false, "error": "..."}` |
| `GET /api/reportes/...` | Descargar lo exportado (sólo dentro de `reportes/`, sin `..`) |

Acciones de `/api/comando` en la fase 1:

- **Ejecución:** `pausar`, `reanudar`, `paso`, `velocidad`, `reiniciar`.
- **Carga:** `cargar`, que acepta un escenario predefinido, un archivo de
  `escenarios/` o el modo aleatorio `n`/`g`, con `static`, `movilidad` y
  `semilla`.
- **Nodos:** `caer`, `recuperar`, `agregar_nodo`, `eliminar_nodo`.
- **Mensajes:** `mensaje`, que devuelve el camino para animarlo.
- **Parámetros:** `parametro`, con lista blanca.
- **Sesión:** `exportar`, `terminar`.

Valida todo. Un comando inválido devuelve un error legible y nunca rompe
la sesión.

### Frame (esquema con versión: `"esquema": 1`)

El frame se emite muchas veces por segundo, así que tiene que ser
ligero. Campos:

- **Estado general:** `t`, `pausado`, `velocidad`, `escenario`,
  `semilla`.
- **Geometría:** `edificio` (ancho, alto, piso_h, n_pisos, stair_xy,
  stair_half_w).
- **Configuración:** `cfg` (los parámetros editables) y `colores` (los
  `C_*` de `main.py`, una sola fuente de verdad para las dos versiones).
- **`nodos`:** id, etiqueta, rol, x, y, piso, vivo, batería, color,
  en_alerta, estela (≤ 40 puntos) y burbuja de beacon.
- **`enlaces`:** a, b y fiabilidad; sólo los pares con fiabilidad > 0.
- **`paquetes`:** origen, destino, progreso y tipo OGM/BCN. El tipo se
  deduce del color mientras `_Packet` no lo guarde.
- **Conectividad:** `resumen` (`sim.summary()`), `grupos` (componentes
  por union-find) y `nodos_alcanzables`.
- **Novedades:** la última muestra del `Recorder`, los eventos nuevos y
  la cola reciente del log.
  - Para los eventos sirve un cursor por índice, porque
    `recorder.events` sólo crece.
  - Para el log **no**: `log_lines` se recorta con `pop(0)`, así que su
    índice no sirve como cursor.

Lo pesado (tabla de rutas, matriz e inspector) va por sus propios
endpoints, pedido con menos frecuencia.

**Coordenadas:** el mundo es un corte vertical, con `x` horizontal e `y`
como **altura** (crece hacia arriba). En pantalla hay que invertir `y`.

---

## 5. Fases

Ejecuta F0 → F1 → F2 seguidas, con commits por unidad lógica. Detente y
pregúntame sólo si aparece una decisión que me corresponda. **Antes de
F3, detente siempre.**

### Fase 0: reconocimiento y línea base (sin cambiar código)

1. Lee `contexto/CLAUDE.md`, `contexto/ESTADO_PROYECTO.md`, `README.md`,
   `docs/*.md`, `main.py`, `sim/*.py`, `analysis/*.py`,
   `mesh/router.py` y `mesh/fault_manager.py`.
2. Corre las pruebas y guarda la línea base de
   `--batch lotes/ejemplo.json` y `--batch lotes/movilidad.json`. Los
   resultados van a `reportes/`, que está en `.gitignore`.
3. Contrasta este documento con el código y repórtame las discrepancias.
4. Crea la rama `feat/interfaz-web`.

### Fase 1: núcleo web con paridad (MVP sólido)

**Infraestructura:** `web/` completo según la sección 4, y `--web` en
`main.py`.

**Mapa**

- **Edificio:** pisos P1–P3 y el hueco de escalera.
- **Nodos:** el Gateway es un círculo y el Nodo de usuario un rombo, así
  que se distinguen por forma, no sólo por color. Se muestran la
  batería, las alertas (`!`) y los caídos (`X`).
- **Enlaces:** coloreados por fiabilidad con los mismos umbrales de
  pygame (0.66 y 0.33), y con grosor proporcional a la fiabilidad.
- **Animación:** paquetes OGM y BCN, estelas, burbujas de beacon y el
  anillo de alcance del nodo seleccionado.
- **Fluidez:** se interpola entre frames para dibujar a 60 fps.

**Barra superior:** escenario, semilla, reproducir/pausa/un paso,
velocidad, reiniciar, exportar, el reloj T+ y el estado (G vivos, N
vivos y "RED PARTIDA" cuando aplica).

**Paneles**

- **Nodo seleccionado:** tabla de rutas completa y vecinos. Una ruta se
  marca obsoleta cuando el destino está en alerta o su `last_seen`
  supera el `timeout`.
- **Calidad:** entrega, TQ y partición sombreada.
- **Log:** coloreado por tipo.
- **Inspector:** el texto de `snapshot_red`.

**Interacción:** clic, menú contextual y teclado.

**Parámetros:** `rango_comm` y `falloff`, como en pygame, con
`sim.set_param` (deja un evento `PARAM`).

**Mensajes**

- Un compositor donde se eligen el origen y el destino con clic, o se
  escribe `G1>N2 texto` (reutiliza `interpretar_mensaje`).
- Animación salto a salto, y un error legible si el mensaje falla.

**Exportar**

- La carpeta de siempre, más `sesion_web.json`.
- **Comando equivalente en terminal**, por ejemplo
  `python main.py --headless --escenario base --seed 7 --duracion 120`.
  Sólo vale si no hubo intervenciones; si las hubo, la interfaz lo dice.

**Semilla**

- Siempre visible. Si no se pasa `--seed`, la sesión elige una (sin usar
  `random`) y la fija, así toda sesión web es reproducible.
- "Reiniciar" vuelve a fijar la semilla de la sesión y reproduce la
  misma corrida. En pygame, `R` no lo hace: documenta la diferencia.
- La semilla se puede cambiar desde la interfaz.

**Tabla de paridad con pygame.** Todo debe quedar cubierto:

| Ventana pygame | Interfaz web |
|---|---|
| `ESPACIO` pausa | Botón y `ESPACIO` |
| `TAB`, `←`/`→`, clic para seleccionar | Clic, `TAB`, `←`/`→` |
| `1`–`9`: N-ésimo Gateway | `1`–`9` |
| `F` caer / `G` recuperar | Menú contextual y `F`/`G` |
| `A` añadir / `D` eliminar | Botones o menú y `A`/`D` |
| `M` mensaje | Compositor y `M` |
| `I` inspector (a la terminal) | Panel "Inspector" y `I` |
| `S` siguiente escenario | Selector y `S` |
| `+`/`-` alcance, `[`/`]` falloff | Deslizadores y las mismas teclas |
| `P` exportar | Botón y `P` |
| `R` reiniciar | Botón y `R` |
| `Q`/`Esc` salir (exporta) | "Terminar sesión" (exporta). `Esc` sólo cierra diálogos |
| Tabla de rutas, gráfica de calidad, log, leyenda, título de estado | Paneles equivalentes |

**Criterios de aceptación de F1**

- `python main.py --web --escenario base --seed 1` abre la interfaz y la
  simulación corre.
- Recargar la página no pierde la sesión.
- Toda la tabla de paridad funciona.
- La prueba de paridad pasa.
- Exportar deja los mismos archivos que la terminal.
- Las 144 pruebas existentes siguen en verde.

### Fase 2: muy interactivo, con lente de descentralización

**A. Interacción directa**

- **Arrastrar nodos.** Es una operación nueva y aditiva,
  `Simulation.mover_nodo(nid, x, y)`, con los mismos límites que
  `_try_move`. Se registra como intervención y como evento.
- **Agregar un nodo donde se hace clic**, eligiendo el rol G o N.
  - Hay que extender la firma a `add_node(role='N', x=None, y=None)`.
  - Llamada sin argumentos, debe consumir `random` exactamente igual que
    hoy (con su prueba de regresión).
  - Un G nuevo necesita su índice local y su color.
- **Más parámetros en vivo**, con deslizadores, valor por defecto
  visible y "restaurar".
  - La lista blanca sólo incluye claves que se lean de `sim.cfg` en cada
    paso: `perdida_base`, `floor_atten`, `timeout`, `ttl`, `move_speed`,
    `movilidad`, `beacon_cada`, `batman_cada` y los drenajes de batería.
  - Verifica cada una.
- **Línea de tiempo de eventos** con iconos: `FAIL`, `RECOVER`,
  `ALERT_ON`/`OFF`, `PARTITION`, `HEAL`, `PARAM` y `MSG_OK`/`FAIL`. Un
  clic en un evento resalta los nodos implicados.
- **Panel de métricas en vivo** con los 6 paneles de la figura de
  matplotlib: mismos títulos y mismas series, con tooltip y ventana
  temporal ajustable.

**B. Lente de descentralización (el corazón del encuadre)**

- **"Ver como este nodo".** Al seleccionar un nodo, el mapa muestra sólo
  lo que ese nodo sabe.
  - Sus destinos conocidos, con saltos, TQ y antigüedad.
  - Flechas hacia el siguiente salto.
  - Los nodos que considera caídos.
  - Los nodos físicamente alcanzables que todavía no conoce.
  - El resto queda atenuado. Tiene que verse que no hay una vista
    global.
- **Matriz de conocimiento N×N.** Fila = nodo que sabe, columna =
  destino. Cada celda es una de cuatro:
  1. Ruta vigente (con los saltos).
  2. Ruta obsoleta.
  3. Sin ruta, pero conectados físicamente ("aún no converge").
  4. Sin conexión física.

  Arriba va un indicador en vivo de cuántos pares conectados tienen ya
  ruta. Es una métrica **sólo de visualización**: no la agregues a los
  reportes ni al resumen sin preguntarme.
- **Detección de fallos distribuida.** Cada Gateway que vigila a otro
  muestra un anillo que se va llenando con el tiempo que lleva sin
  oírlo, contra el `timeout`. Sé honesto con el detalle: `FaultManager`
  revisa cada 5 s, así que la alerta puede llegar hasta 5 s después de
  que el anillo se completa.
- **Propagación de OGM por origen.** Se filtran los paquetes de un
  origen y se ve la inundación salto a salto, con el TTL bajando. Esto
  requiere que `_Packet` lleve tipo, origen y TTL: es un cambio aditivo
  en `sim/radio.py`, que no toca el azar y se verifica con la
  regresión.
- **Particiones visibles.** Una envolvente coloreada por componente, y
  un aviso cuando la malla se parte o se reunifica.
- **Panel "Qué es real y qué es modelo".**
  - Real: `BatmanRouter` y `FaultManager` de `mesh/`.
  - Modelo: `RadioMedium` y la movilidad.
  - Con contadores en vivo, por ejemplo los OGM procesados por el
    `receive_ogm()` real.

**C. Editor de escenarios**

- **Edición:** colocar nodos G y N en el edificio, editar las secciones
  `building`, `medium`, `protocol` y `events` (`wander`) y la movilidad.
- **Validación:** con `sim/config_loader.py`. Agrega una función pública
  que valide un `dict` reutilizando `_validate`.
- **Guardar:**
  - En `escenarios/`, sin sobrescribir los 5 predefinidos y sin rutas
    fuera de la carpeta.
  - También como descarga del JSON.
  - Mostrando el comando de terminal para correrlo.
- **Opcional: mapa de cobertura.** Un *heatmap* de la mejor fiabilidad
  hacia algún Gateway en cada punto del edificio.
  - Sólo se permite si sale de una refactorización pura de
    `RadioMedium.reliability()` en una función compartida.
  - Esa refactorización debe dar resultados idénticos (probado) y la
    fórmula no se duplica en JS.

**Criterios de aceptación de F2**

- Todo lo anterior funciona con la sesión corriendo.
- Los cambios al núcleo son aditivos y tienen pruebas.
- La regresión de lotes da idéntico.
- Un escenario guardado desde el editor corre con `--config` y con
  `--headless`.

### Fase 3: requiere mi aprobación explícita antes de empezar

- **Eventos programables de caída y recuperación en el esquema de
  escenario**, con la forma
  `{"type": "fail" | "recover", "node_id": .., "t": ..}`, aplicados por
  el motor.
  - Permitiría "exportar la sesión como escenario": las intervenciones
    se vuelven eventos reproducibles en terminal y en lotes.
  - También permitiría medir la reconvergencia en serio.
  - Toca una decisión abierta del proyecto, así que la tomamos entre
    los dos autores.
- **Laboratorio de experimentos.** Armar un lote desde la interfaz y
  correrlo **en un subproceso** (`python main.py --batch <archivo>`),
  con progreso y una tabla y gráficas del resumen agregado.
  - Nunca en un hilo del servidor: compartiría el `random` global con la
    sesión en vivo.
  - La paridad sale por construcción, porque es literalmente el comando
    de terminal.
- **Ventana nativa opcional** (pywebview), con respaldo en el navegador
  y un lanzador de escritorio (`.desktop`). Requiere dependencias, así
  que hay que consultarme.

---

## 6. Diseño visual y experiencia

- **Estética:** un panel técnico limpio y moderno.
  - Tarjetas con bordes suaves, jerarquía clara y animaciones fluidas
    que no mientan: las posiciones reales vienen del servidor y la
    interpolación sólo suaviza.
  - Tema claro y oscuro: respeta `prefers-color-scheme` y además tiene
    un interruptor.
  - Tipografía del sistema, sin Google Fonts, porque tiene que funcionar
    sin conexión.
  - La paleta sale de los colores de `main.py` que envía el backend.
- **Disposición**
  - Pensada para pantallas de 1366×768 a 1920×1080 y para proyector.
  - El mapa es el protagonista. Al lado va un panel con pestañas (Nodo,
    Red, Métricas, Inspector, Parámetros) y abajo la línea de tiempo.
  - **Modo presentación:** esconde los paneles, agranda el mapa y la
    letra para la sustentación.
- **Primer uso**
  - Una pantalla de inicio para elegir escenario, con la descripción de
    cada uno (tómala de la sección 3 de `docs/guia_ejecucion.md`).
  - Un modal `?` con todos los atajos.
- **Información al pasar el cursor**
  - Sobre un nodo: rol, batería, piso, vecinos y rutas.
  - Sobre un enlace: fiabilidad, distancia y pisos.
  - Las capas (enlaces, paquetes, estelas, burbujas, alcance,
    envolventes) se encienden y apagan desde la leyenda.
- **Accesibilidad:** forma además de color, contraste AA, foco visible y
  todo usable con teclado.
- **Rendimiento**
  - 60 fps con 50 nodos y frames de pocas decenas de KB.
  - Sin fugas de memoria tras 30 minutos corriendo.

---

## 7. Honestidad del modelo (la interfaz no maquilla limitaciones)

- **El TQ vale siempre 1.0.** `BatmanRouter` nunca registra los OGM
  perdidos. Rotúlalo así ("TQ calculado por el `BatmanRouter` real; hoy
  no refleja pérdidas", ver `docs/arquitectura.md`) y muestra la calidad
  del medio con la fiabilidad y la tasa de entrega.
- **El ancho de banda es una heurística**: 100 − 5·d Mbps hacia el
  Gateway más cercano. No sale del medio radio; rotúlalo como
  estimación.
- **La conectividad se calcula sobre los enlaces de radio**
  (union-find con fiabilidad > 0), no sobre las tablas de rutas.
- **Los mensajes viajan por el camino más corto en la malla de radio**
  (BFS), no se reenvían por las tablas BATMAN. La interfaz indica si la
  ruta BATMAN ya había convergido, como hace hoy el log.
- **No "arregles" nada de esto en este encargo.** Son decisiones
  abiertas (`contexto/ESTADO_PROYECTO.md`, punto 4 de "Falta"). La
  interfaz sólo las muestra con honestidad.

---

## 8. Pruebas

Todas con `unittest` puro, sin navegador ni pygame, en archivos
`tests/test_web_*.py`.

- **`estado.py`**
  - Claves y tipos del frame; se puede pasar por `json.dumps`;
    etiquetas G/N.
  - Coincide con el modelo: los enlaces son los pares con
    `reliability > 0` y los grupos coinciden con `_union_find`.
- **Paridad**
  - Con la semilla S, *k* pasos con la `Sesion` (que tenga una API de
    avance síncrona, sin hilo, para las pruebas) contra *k* pasos con
    `correr()`.
  - Las series del `Recorder` y `resumen_corrida()` tienen que salir
    idénticas.
  - Varios escenarios, incluyendo `repartir` y `static`.
- **Comandos**
  - Cada acción, válida e inválida.
  - Eliminar el único Gateway.
  - Un mensaje con la malla partida.
  - Un parámetro fuera de la lista blanca da error.
- **Servidor**
  - Se levanta en el puerto 0, en un hilo, y se prueba con `urllib` o
    `http.client`: `/`, `/api/estado`, un comando, y que el SSE entregue
    al menos un frame.
  - *Path traversal*: `/static/../main.py` y `/api/reportes/../../x` se
    rechazan.
- **CLI**
  - `--web` junto con `--headless` o `--batch` da error.
  - `--web --no-abrir` arranca sin abrir el navegador y sin dejar la
    prueba colgada.
- **Fase 2**
  - Límites de `mover_nodo`.
  - `add_node()` sin argumentos consume `random` igual que antes.
  - Validación y guardado del editor (no sobrescribe los predefinidos).
  - La refactorización de `reliability`, si se hace, da idéntico.
- **Lo existente**
  - Las 144 pruebas siguen en verde.
  - La regresión de `lotes/ejemplo.json` y `lotes/movilidad.json` da
    idéntico a la línea base.
- **Verificación visual**
  - Si tienes un navegador automatizable, recorre la tabla de paridad y
    la fase 2 y toma capturas.
  - Si no, deja una lista de chequeo manual en `docs/interfaz_web.md` y
    dime qué no pudiste verificar.

---

## 9. Documentación

- **`README.md`:** una sección "Versión de escritorio (interfaz web
  local)" con cómo arrancarla, las flags, los controles y atajos, y qué
  exporta.
- **`docs/arquitectura.md`:** la nueva capa `web/` en el diagrama, al
  lado de `visualizer.py`, y el modelo de concurrencia.
- **`docs/interfaz_web.md` (nuevo)**
  - La API, el esquema del frame y las decisiones tomadas.
  - Una sección **"Cómo apoya la interfaz la necesidad de un simulador
    a la medida"**: una tabla funcionalidad → capacidad que demuestra →
    cuál de los tres vacíos de `sec:brecha` atiende.
  - Es insumo para los capítulos 1 y 4 de la tesis, que escribiremos
    aparte.
- **`docs/guia_ejecucion.md`:** uno o dos casos con la interfaz. Por
  ejemplo, el caso 1 hecho en la web, y "Ver como este nodo" durante la
  partición de `rescatista_perdido`.
- **`contexto/ESTADO_PROYECTO.md`:** lo hecho y lo pendiente.
- No documentes nada que no exista.

---

## 10. Reglas de trabajo

- **Idioma:** español en el código, los comentarios, la documentación,
  la interfaz y los commits.
- **Autoría de los commits**
  - A nombre de quien usa la sesión: `git config user.name` y
    `user.email` de este repo.
  - **Nunca** agregues `Co-Authored-By: Claude` ni ninguna atribución a
    Claude o Anthropic (regla de `contexto/CLAUDE.md`).
  - Si no hay identidad configurada, avísame antes de commitear.
- **Forma de los commits**
  - Pequeños, uno por unidad lógica.
  - No mezcles cambios al núcleo con funciones de la interfaz en un
    mismo commit.
  - `git push` sólo cuando te lo pida.
- **Dependencias:** no agregues ninguna sin preguntarme.
- **Decisiones**
  - Si algo de este documento choca con el código o con una decisión ya
    tomada, detente y pregúntame en vez de decidir en silencio.
  - Las decisiones de alcance (la fase 3, las métricas) son de los dos
    autores del proyecto, no tuyas.
- **Pygame:** no borres ni cambies el comportamiento de la ventana
  pygame.

---

## 11. Fuera de alcance

- `Plantilla/` (el documento LaTeX de la tesis).
- `mesh/` (el protocolo real), incluido corregir el TQ.
- Cambiar la movilidad por defecto (`seguir`).
- Cambiar el esquema de escenarios de forma incompatible.
- Cambiar las métricas o las columnas de los reportes existentes.
- Despliegue en hardware real (`mesh/node.py`, `api.py`, `memory.py`,
  `scheduler.py`).
- Exponer el servidor a la red: sólo `127.0.0.1`, sin autenticación ni
  multiusuario.
- Grabar y "rebobinar" sesiones: queda como idea futura.

---

## 12. Definición de terminado (F1 + F2)

- `venv/bin/python -m unittest discover -s tests` en verde, con las
  pruebas nuevas incluidas.
- `python main.py --web --escenario base --seed 1` abre la interfaz y
  todo lo de F1 y F2 funciona.
- Funciona sin internet.
- La prueba de paridad pasa.
- La regresión de lotes da idéntico a la línea base.
- Exportar desde la web deja la carpeta de reportes de siempre más
  `sesion_web.json`.
- El "comando equivalente" de una sesión sin intervenciones reproduce
  las mismas métricas en terminal.
- La tabla de paridad está cubierta al 100 %.
- La documentación está al día y `docs/interfaz_web.md` contiene la
  sección del simulador a la medida.

## 13. Al cerrar cada fase, repórtame

- Qué se hizo, con los commits.
- Resultado de las pruebas y de la regresión.
- Qué no se pudo verificar, y por qué.
- Capturas, si se pudieron tomar.
- Decisiones pendientes para los dos autores.
