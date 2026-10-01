# Interfaz web (versión de escritorio)

API, esquema del frame, decisiones de diseño y verificación de la
interfaz web local (`--web`), paralela a la ventana pygame. Ver
[`docs/arquitectura.md`](arquitectura.md#web--interfaz-web-local-paralela-a-pygame)
para cómo encaja `web/` en las capas del simulador, y el README para
cómo arrancarla.

---

## 1. Arquitectura y concurrencia

Un solo proceso Python: el servidor HTTP (`web/servidor.py`) y el hilo
de simulación de la `Sesion` (`web/sesion.py`) viven en el mismo
proceso que construyó `main.py --web`. No hay build ni paso de
compilación en el frontend (`web/static/`): HTML/CSS/JS servidos tal
cual, con módulos ES nativos y canvas 2D.

**El lock.** `Simulation` no es thread-safe y todo el azar sale del
módulo `random` global, así que `Sesion.lock` (un `threading.RLock`)
protege **todo** acceso a `sim`:

- El hilo de simulación (`Sesion._bucle`) lo toma para avanzar un lote
  de pasos y serializar el frame siguiente; lo suelta entre
  iteraciones (duerme `~1/18 s` fuera del lock).
- Cada handler HTTP lo toma para aplicar un comando o para leer `sim`
  (`/api/estado`, `/api/nodo/<id>`, `/api/series`, `/api/inspector`) y
  nunca lo toca fuera de él.
- Elegir una semilla automática usa `secrets.randbelow()`, nunca
  `random`: consumir `random` en un camino que no existía antes de
  `web/` rompería la reproducibilidad de la corrida (ver la prueba de
  paridad, sección 4).

**Ritmo.** A velocidad 1× el hilo avanza 9 s simulados por segundo
real — el mismo ritmo que la ventana pygame (`STEP_DT = 1/18 s` real
por paso de `DT = 0.5 s`). El selector de velocidad (0.25× a 8×, más
"máxima") escala ese acumulador; "máxima" corre en ráfagas acotadas a
40 ms reales por iteración para no monopolizar el lock. El hilo
publica un frame serializado (JSON) y despierta a los clientes SSE con
una `Condition` en cada iteración (~18 Hz), por debajo del límite de
"15-20 Hz" del encargo.

**Fallos.** Si `sim.step()` lanza una excepción, `Sesion` la guarda en
`self.error`, pausa la sesión y sigue sirviendo HTTP — no se cae el
servidor. La interfaz muestra el error en la barra superior; "Reiniciar"
lo limpia reconstruyendo la simulación desde cero.

**Ciclo de vida.** La sesión vive en el servidor, no en el navegador:
recargar la página o abrir otra pestaña reconecta al mismo estado (la
selección de nodo es sólo del cliente, vía `localStorage`/estado JS,
no se manda al servidor). `Ctrl+C` en la terminal, o "Terminar sesión"
en la interfaz (que manda `{"accion": "terminar"}` y dispara
`httpd.shutdown()` desde un hilo aparte para no autobloquearse), exporta
el análisis y apaga de forma limpia — verificado con el proceso real
(sección 4).

---

## 2. API HTTP

Todas las rutas son relativas a `http://127.0.0.1:<puerto>/` (por
defecto `8765`), sólo accesible desde la propia máquina.

| Método y ruta | Qué hace |
|---|---|
| `GET /`, `GET /static/...` | La interfaz (HTML/CSS/JS) |
| `GET /api/stream` | Server-Sent Events: un evento `frame` por publicación (~18 Hz) |
| `GET /api/estado` | El frame actual (para el primer pintado o un refresco manual) |
| `GET /api/nodo/<id>` | Detalle de un nodo: rutas BATMAN, vecinos, a quién cree caído. 404 si no existe |
| `GET /api/series` | Series completas del `Recorder` + eventos con índice, para reconstruir las gráficas al conectar |
| `GET /api/inspector` | El texto de `snapshot_red(sim)` (texto plano) |
| `GET /api/escenarios` | Escenarios predefinidos (con descripción) y archivos de `escenarios/` |
| `POST /api/comando` | `{"accion": ..., ...}` → `{"ok": true, ...}` o `{"ok": false, "error": "..."}` |
| `GET /api/reportes/<ruta>` | Descarga de lo exportado (sólo dentro de `reportes/`, sin `..`) |

### Acciones de `/api/comando` (F1)

| Acción | Datos | Qué hace |
|---|---|---|
| `pausar` / `reanudar` | — | Pausa o reanuda (`reanudar` falla si hay un error activo: usar `reiniciar`) |
| `paso` | — | Un paso, sólo en pausa (despausa internamente para el único `sim.step()`, porque `Simulation.step()` no avanza si `paused` es verdadero, y vuelve a pausar) |
| `velocidad` | `{"valor": 0.25-8.0 \| "maxima"}` | Cambia el ritmo del hilo |
| `reiniciar` | — | Refija la semilla de la sesión y reconstruye desde cero (a diferencia de la tecla `R` de pygame, que no refija semilla) |
| `cargar` | `{"escenario"\|"archivo", "n_nodes", "n_gateways", "static", "movilidad", "semilla"}` | Carga otro escenario o archivo (sólo dentro de `escenarios/`); limpia las intervenciones |
| `caer` / `recuperar` | `{"id": int}` | `Simulation.fail_node` / `recover_node` |
| `agregar_nodo` | — | `Simulation.add_node()` (F1: sólo `N`, posición aleatoria; F2 lo extiende) |
| `eliminar_nodo` | `{"id": int}` | `Simulation.remove_node()`; error si es el único Gateway |
| `mensaje` | `{"texto": "G1>N2 hola"}` | Reutiliza `interpretar_mensaje()`; devuelve el camino (BFS) para animarlo |
| `parametro` | `{"clave": "rango_comm"\|"falloff", "valor": num}` | Lista blanca F1 (como en pygame); F2 la extiende |
| `exportar` | — | `build_analysis_figure()` + `sesion_web.json`; devuelve la carpeta y el comando equivalente |
| `terminar` | — | Marca el cierre; el servidor exporta y se apaga al volver de `serve_forever()` |

Cada acción que muta la simulación (todas menos `pausar`/`reanudar`/
`paso`/`velocidad`) se registra como una **intervención** (`{t, accion,
datos}`). El **comando equivalente** (sección 3 del encargo, "mismos
resultados") sólo se calcula si la lista de intervenciones está vacía:
con intervenciones no hay forma de reproducir la sesión con un sólo
comando de terminal, y se lo dice así a quien exporta.

### Esquema del frame (`"esquema": 1`)

Construido en `web/estado.py:frame()`. Campos: `t`, `pausado`,
`velocidad`, `escenario`, `semilla`, `error`, `edificio` (ancho, alto,
piso_h, n_pisos, stair_xy, stair_half_w), `cfg` (sólo los parámetros de
`medium`/`protocol`, no la definición estática de `nodes`/`events`),
`colores` (los `C_*` de `main.py`, una sola fuente de verdad para las
dos versiones), `nodos` (id, etiqueta, rol, x, y, piso, vivo, batería,
color, en_alerta, estela ≤40 puntos, beacon), `enlaces` (sólo pares con
`reliability > 0`, igual que `_union_find`), `paquetes` (posición de
origen/destino interpolada por `progreso`, tipo OGM/BCN/MSG deducido
por color — ver "limitaciones" más abajo), `resumen`
(`sim.summary()`), `grupos` (componentes por `_union_find`, sobre todos
los nodos vivos, no sólo Gateways), `nodos_alcanzables`
(`sim.nodes_in_mesh()`), `eventos_nuevos` (últimos ≤20, con índice
absoluto), `eventos_total`, `log` (últimas ≤20 líneas) y
`ultima_muestra` (el último punto del `Recorder`, para graficar sin
pedir `/api/series` en cada frame).

El frame es deliberadamente liviano: lo pesado (tabla de rutas por
nodo, series completas, el texto del inspector) va por sus propios
endpoints, pedidos con menos frecuencia (al seleccionar un nodo, al
conectar, al abrir la pestaña Inspector).

---

## 3. Cómo apoya la interfaz la necesidad de un simulador a la medida

Indicación del director (ver `prompt_version_escritorio.md`, sección 1):
*"la idea es que el problema esté enfocado en la necesidad de un
simulador hecho a la medida para redes descentralizadas"*. El Capítulo 2
de la tesis (`Plantilla/MainMatter/Cap2/M03-Chapter2.tex`, `sec:brecha`)
identifica tres vacíos que ns-3/OMNeT++ (simulan un *modelo*, no la
implementación), los emuladores (código real pero caro por nodo, sin
modelo 3D de atenuación entre pisos) y las herramientas P2P/blockchain
(capa de aplicación, sin medio radio ni movilidad física) dejan sin
cubrir.

| Funcionalidad de la interfaz | Capacidad que demuestra | Vacío de `sec:brecha` que atiende |
|---|---|---|
| Panel "Nodo": tabla de rutas y vecinos de un `BatmanRouter` real, en vivo | Se puede inspeccionar el estado interno exacto del protocolo real sin instrumentar hardware | (1) modelo vs. implementación: acá es la implementación |
| Enlaces coloreados por `RadioMedium.reliability()` (distancia + piso) | Visualiza un medio con atenuación 3D entre pisos, no un grafo lógico plano | (2) emuladores sin modelo de propagación por edificio |
| Exportar deja los mismos `reporte.csv/json/txt` que la terminal, más `sesion_web.json` con el comando equivalente | La exploración interactiva no reemplaza el dato reproducible: toda sesión sin intervenciones es, literalmente, una corrida de terminal | (1) y (2): resultados comparables entre modelo real y exploración |
| Mensajes salto a salto sobre la malla real (BFS + estado de convergencia BATMAN) | Hace visible la diferencia entre "hay camino físico" y "BATMAN ya convergió" | (3) herramientas de aplicación que no modelan el medio |
| Panel "Qué es real y qué es modelo" (F2) | Honestidad explícita sobre qué corre `mesh/` real y qué es `RadioMedium`/movilidad | Los tres: a la medida no significa "todo simulado", significa elegir qué simular |
| "Ver como este nodo" / matriz de conocimiento N×N (F2) | Hace visible que no hay vista global: cada nodo tiene su propia tabla de rutas | Ninguno de los tres (ns-3, emuladores ni P2P) expone esto de forma interactiva por diseño |

(Las filas marcadas F2 son de la fase 2 del encargo, implementada
después de este documento; se listan acá porque motivan el diseño de
la fase 1.)

---

## 4. Verificación hecha en esta fase (F1)

El entorno de esta sesión no tiene Node.js ni un navegador
automatizable (`chromium-cli` no está instalado y no hay forma de
instalarlo: sin npm y `sudo` pide contraseña interactiva), así que no
se pudo tomar una captura de pantalla real. Lo que sí se verificó,
contra el **proceso real** (`python main.py --web`, no sólo los tests):

- `GET /` sirve el HTML; `GET /static/js/main.js` y `/static/css/app.css`
  sirven con el `Content-Type` correcto (`text/javascript`, `text/css`).
- `GET /api/stream` entregó 48 eventos `frame` en 3 s reales (~16 Hz).
- El reloj de la simulación avanzó de verdad entre llamadas (de
  `t=0.5` a `t=194.0` en el tiempo que tomó hacer las llamadas
  siguientes), al ritmo esperado (~9 s simulados por segundo real).
- `POST /api/comando` con `pausar` cambió `pausado` a `true` en el
  siguiente `GET /api/estado`.
- `GET /api/nodo/<id>` devuelve la tabla de rutas de un `BatmanRouter`
  real.
- `POST /api/comando` con `terminar` exportó
  `reportes/<escenario>_<fecha_hora>/` (los 4 archivos de siempre) y el
  proceso terminó limpio (sin quedar colgado).
- Las 192 pruebas (`144` de antes + `48` nuevas en
  `tests/test_web_*.py`) pasan: `estado.py` (forma del frame,
  serializable, enlaces/grupos coinciden con el modelo), paridad exacta
  con `correr()` (misma semilla ⇒ misma serie del `Recorder` y mismo
  `resumen_corrida()`, en `base`, `denso` con `repartir`, `static` y
  modo aleatorio), comandos (válidos e inválidos, eliminar el único
  Gateway, mensaje con la malla partida, parámetro fuera de lista
  blanca), el servidor HTTP/SSE levantado en un puerto efímero (rutas,
  un comando, un evento SSE real, *path traversal* rechazado en
  `/static/` y `/api/reportes/`), y la integración de `--web` en
  `main.py` (conflictos con `--headless`/`--inspect`/`--batch`/
  `--duracion`, y un arranque real en un puerto fijo con `--no-abrir`
  que se cierra con `terminar`).
- La regresión de `lotes/ejemplo.json` y `lotes/movilidad.json` contra
  la línea base de la Fase 0 dio **idéntica** (mismo `resumen.csv` y
  `corridas.csv`, salvo fecha): la ventana pygame y los modos sin
  ventana no cambiaron.

### Lista de chequeo manual (pendiente, requiere un navegador)

- [ ] Abrir `python main.py --web --escenario base` y confirmar que el
  mapa dibuja el edificio, los 4 Gateway (círculos) y los 3 Nodos de
  usuario (rombos) en las posiciones esperadas.
- [ ] Confirmar que los nodos se mueven en vivo y las estelas/enlaces
  se actualizan sin parpadeos ni errores en la consola del navegador.
- [ ] Probar la tabla de paridad completa con teclado (1-9, F/G, A/D,
  M, I, S, +/-, [/], P, R, Q) y con los botones equivalentes.
- [ ] Caso 1 de `docs/guia_ejecucion.md` (tumbar G4 y ver la alerta) en
  la interfaz web.
- [ ] "Ver como este nodo" (F2) durante la partición de
  `rescatista_perdido`.
- [ ] Tema oscuro (`prefers-color-scheme` y el interruptor manual).
- [ ] Responsive en una ventana angosta (el panel lateral pasa a la
  parte de abajo, según el CSS en `web/static/css/app.css`).

---

## 5. Limitaciones conocidas (honestidad del modelo)

Igual que en pygame (ver "Limitaciones conocidas" en
[`arquitectura.md`](arquitectura.md)); la interfaz web no las oculta:

- **El TQ vale siempre 1.0** en toda ruta que existe — `BatmanRouter`
  no registra los OGM perdidos. El panel de métricas rotula el TQ como
  "calculado por el `BatmanRouter` real" y muestra la **tasa de
  entrega del radio** para la calidad real del medio.
- **El tipo de paquete (OGM/BCN/MSG) se deduce por color**, porque
  `sim.radio._Packet` no guarda el tipo — el mismo gap que señala
  `prompt_version_escritorio.md` sección 2. Corregirlo (para la
  "propagación de OGM por origen" de la fase 2) es un cambio aditivo en
  `sim/radio.py`, pendiente.
- **Los mensajes viajan por el camino más corto en la malla de radio**
  (BFS), no por las tablas BATMAN — el panel de mensaje indica si la
  ruta BATMAN ya había convergido para ese destino.
- **La conectividad (`grupos`, `nodos_alcanzables`) se calcula sobre
  los enlaces de radio**, no sobre las tablas de rutas.

Ninguna de estas se "arregla" en el alcance de la interfaz: son
decisiones abiertas del proyecto (`contexto/ESTADO_PROYECTO.md`, punto
4 de "Falta").
