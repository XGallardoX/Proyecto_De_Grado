# Interfaz web (versión de escritorio)

API, esquema del frame, decisiones de diseño y verificación de la
interfaz web local (`python main.py --web`), paralela a la ventana
pygame. Cómo encaja `web/` en las capas del simulador:
[`arquitectura.md`](arquitectura.md#web--interfaz-web-local-paralela-a-pygame).
Cómo arrancarla y qué hace cada control: el README ("Versión de
escritorio").

---

## 1. Arquitectura y concurrencia

Un solo proceso Python: el servidor HTTP (`web/servidor.py`) y el hilo
de simulación de la `Sesion` (`web/sesion.py`) viven en el proceso que
arrancó `main.py --web`. El frontend (`web/static/`) se sirve tal cual:
HTML, CSS y módulos ES nativos, sin compilación, sin dependencias ni
CDN (funciona sin internet).

**Un lock.** `Simulation` no es thread-safe y todo el azar sale del
módulo `random` global, así que `Sesion.lock` protege **todo** acceso a
`sim`:

- El hilo de simulación (`Sesion._bucle`) lo toma para avanzar un lote
  de pasos y serializar el frame siguiente, y lo suelta entre
  iteraciones (duerme ~1/18 s fuera del lock).
- Cada handler HTTP lo toma para aplicar un comando o leer `sim`, y
  nunca lo toca fuera de él. Se serializa a `dict` bajo el lock; el JSON
  del frame que va por SSE se arma una sola vez por publicación.
- Para elegir una semilla automática se usa `secrets`, nunca `random`:
  consumir `random` en un camino nuevo rompería la reproducibilidad
  (ver la prueba de paridad, sección 4).
- Exportar (matplotlib con backend Agg) también va bajo el lock.

**Ritmo.** A 1× el hilo avanza 9 s simulados por segundo real, igual
que pygame (`STEP_DT = 1/18 s` real por paso de `DT = 0.5 s`). El
selector va de 0.25× a 8×; "máxima" corre en ráfagas de 40 ms reales por
iteración para no monopolizar el lock (con los 7 nodos de
`colapso_progresivo` se midieron unos 2000 s simulados por segundo
real). Se publica un frame por iteración (~18 Hz) y se
despierta a los clientes SSE con una `Condition`; los handlers SSE
esperan con timeout y mandan *keep-alive* para notar desconexiones.

**Fallos.** Si `sim.step()` lanza una excepción, la `Sesion` la guarda
en `error`, pausa y sigue sirviendo HTTP; la interfaz la muestra y
"Reiniciar" reconstruye la simulación.

**Ciclo de vida.** La sesión vive en el servidor: recargar la página o
abrir otra pestaña reconecta al mismo estado. La selección de nodo, la
lente, el filtro de OGM, las capas y el tema son de cada pestaña.
`Ctrl+C` en la terminal o "Terminar" en la interfaz (que dispara
`httpd.shutdown()` desde un hilo aparte) exporta el análisis y apaga
limpio. Cerrar la pestaña no detiene nada.

---

## 2. API HTTP

Sólo en `127.0.0.1:<puerto>` (por defecto 8765), sin autenticación.

| Método y ruta | Qué devuelve |
|---|---|
| `GET /`, `GET /static/...` | La interfaz (rechaza `..` con 403) |
| `GET /api/stream` | Server-Sent Events: un evento `frame` por publicación |
| `GET /api/estado` | El frame actual |
| `GET /api/nodo/<id>` | Rutas BATMAN (con `obsoleta`), vecinos, `cree_caidos`, `alcanzables_sin_ruta` y `vigilancia`; 404 si no existe |
| `GET /api/series?desde=N&desde_evento=M&ultimas=K` | Series del `Recorder` desde la muestra `N` (o las últimas `K`) y eventos desde `M`, con `total`, `eventos_total` y `generacion` |
| `GET /api/matriz` | Matriz de conocimiento N×N (sección 3 del frame) |
| `GET /api/cobertura` | Mejor fiabilidad hacia algún Gateway vivo en cada celda de 1 m |
| `GET /api/paquetes?origen=ID` | Todos los OGM en vuelo que originó `ID` |
| `GET /api/escenario/actual?posiciones=iniciales\|actuales` | El escenario de la sesión con el esquema de `escenarios/*.json` |
| `GET /api/inspector` | El texto de `snapshot_red(sim)` |
| `GET /api/escenarios` | Predefinidos (con descripción) y archivos de `escenarios/` |
| `GET /api/reportes/<ruta>` | Lo exportado (sólo dentro de `reportes/`, sin `..`) |
| `POST /api/comando` | `{"accion": ..., ...}` → `{"ok": true, ...}` o `{"ok": false, "error": "..."}` |

### Acciones de `/api/comando`

| Acción | Datos | Qué hace |
|---|---|---|
| `pausar` / `reanudar` | — | `reanudar` falla si hay un error activo |
| `paso` | — | Un paso, sólo en pausa (`Simulation.step()` no avanza en pausa: se despausa para ese paso) |
| `velocidad` | `valor`: 0.25-8 o `"maxima"` | Ritmo del hilo |
| `reiniciar` | — | Misma configuración y misma semilla, desde cero |
| `cambiar_semilla` | `semilla` | Misma configuración, otra semilla |
| `cargar` | `escenario` \| `archivo` \| `n_nodes`+`n_gateways`; `static`, `movilidad`, `semilla` opcionales | Otra red. Sin `static`/`movilidad` conserva los de la sesión (como la tecla `S` de pygame) |
| `caer` / `recuperar` | `id` | `fail_node` / `recover_node` |
| `agregar_nodo` | `rol` (`G`/`N`), `x`, `y` opcionales | Sin datos, igual que la tecla `A` de pygame |
| `mover_nodo` | `id`, `x`, `y` | Recortado a los límites de `_try_move`; evento `MOVE` |
| `eliminar_nodo` | `id` | Error si es el único Gateway |
| `mensaje` | `texto` (`G1>N2 hola`) | Devuelve `camino`, `ids`, `entregado`, `motivo` y `ruta_batman_convergida` |
| `parametro` | `clave`, `valor` | Lista blanca con tipo y rango (abajo) |
| `restaurar_parametro` | `clave` | Vuelve al valor con que arrancó la sesión |
| `validar_escenario` | `escenario` | Mismas reglas que `--config` |
| `guardar_escenario` | `escenario`, `nombre`, `sobrescribir` | Escribe `escenarios/<nombre>.json` (nunca un predefinido) |
| `exportar` | — | Carpeta, archivos y comando equivalente |
| `terminar` | — | El servidor exporta y se apaga |

**Lista blanca de parámetros en vivo:** sólo claves que el núcleo vuelve
a leer de `sim.cfg` en cada paso, verificadas una por una (y probadas:
cambiar cualquiera altera la corrida a partir de ese paso):
`rango_comm`, `falloff`, `perdida_base`, `floor_atten` (las lee
`RadioMedium.reliability`), `timeout`, `beacon_cada`, `batman_cada`,
`battery_drain`, `battery_drain_nodo` (`SimNode.tick`), `ttl`
(`SimNode._make_ogm`), `move_speed` y `movilidad` (`SimNode.move`).

**Intervenciones.** Toda acción que cambia la corrida (caer, recuperar,
agregar, mover, eliminar, mensaje, parámetro) se registra con su
instante simulado. El **comando equivalente** de terminal sólo existe si
no hubo intervenciones; si las hubo, la interfaz lo dice y quedan en
`sesion_web.json`.

### Esquema del frame (`"esquema": 1`)

`web/estado.py:frame()`. Campos:

- **Estado:** `t`, `pausado`, `velocidad`, `escenario`, `semilla`,
  `static`, `intervenciones` (cuántas), `error`, `generacion` (sube con
  cada reinicio o carga: el cliente sabe que empezó otra corrida).
- **Geometría y configuración:** `edificio`, `cfg` (parámetros en vivo),
  `cfg_base` (los de arranque), `colores` (los `C_*` de `main.py`).
- **`nodos`:** id, etiqueta, rol, x, y, piso, vivo, batería, color,
  en_alerta, estela (10 puntos), beacon, n_rutas, n_vecinos.
- **`enlaces`:** `[a, b, fiabilidad, distancia]`, sólo pares con
  `reliability > 0`.
- **`paquetes`:** `[x0, y0, x1, y1, progreso, tipo, origen, ttl]`, una
  muestra determinista de a lo sumo 300 (a paso fijo, sin `random`), y
  `paquetes_total`. Con 50 nodos hay miles en vuelo; la interfaz avisa
  cuando dibuja una muestra.
- **Conectividad:** `resumen` (`sim.summary()`), `grupos`
  (`_union_find` sobre todos los nodos vivos), `nodos_alcanzables`.
- **Lente:** `vigilancia` (cada Gateway observador, a quién vigila,
  silencio contra `timeout`, si lo cree caído y cuándo es su próximo
  chequeo) y `contadores` (uso del código real contra el modelo).
- **Novedades:** `eventos_nuevos` (últimos 20, con índice absoluto y los
  `nodos` que menciona cada uno), `eventos_total`, `log` (últimas 20
  líneas: `log_lines` se recorta con `pop(0)` y su índice no sirve de
  cursor, así que el cliente deduplica) y `ultima_muestra`.

Tamaño medido: 9 KB con 7 nodos, 28 KB con 20 y 64 KB con 50 nodos y 844
enlaces (antes de compactarlo, con 50 nodos pesaba 1.4 MB por los
paquetes). Hay una prueba que lo exige por debajo de 80 KB.

**Matriz de conocimiento** (`/api/matriz`): fila = el nodo que sabe,
columna = el destino. Estados: `vigente` (con `hops`), `obsoleta` (el
destino está en alerta o hace más que el `timeout` que no se lo oye),
`sin_converger` (la radio los conecta pero no hay ruta) y
`sin_conexion`. Una ruta vigente u obsoleta lleva además `fisico`: en
falso, el nodo todavía tiene la ruta pero la radio ya no los conecta
(la interfaz la marca con borde punteado). El indicador de arriba
cuenta cuántos pares conectados por radio ya tienen ruta vigente. Es
una métrica **sólo de visualización**: no está en los reportes ni en el
resumen.

**Coordenadas:** corte vertical, `x` horizontal e `y` altura (crece
hacia arriba): en pantalla se invierte `y`.

---

## 3. Cómo apoya la interfaz la necesidad de un simulador a la medida

Indicación del director: *"la idea es que el problema esté enfocado en
la necesidad de un simulador hecho a la medida para redes
descentralizadas"*. El Capítulo 2 de la tesis
(`Plantilla/MainMatter/Cap2/M03-Chapter2.tex`, `sec:brecha`) identifica
tres vacíos:

1. ns-3, OMNeT++ y similares evalúan un *modelo* del protocolo, no su
   implementación.
2. Los emuladores corren código real, pero con un costo alto por nodo y
   sin un modelo de propagación que contemple la atenuación entre pisos.
3. Las herramientas P2P y blockchain operan en la capa de aplicación: no
   modelan el medio radio ni la movilidad física.

| Funcionalidad de la interfaz | Capacidad que demuestra | Vacío que atiende |
|---|---|---|
| Panel "Nodo": tabla de rutas, vecinos y detección de fallos del `BatmanRouter` y el `FaultManager` reales, en vivo | Se inspecciona el estado interno exacto de la implementación, no de un modelo, sin instrumentar hardware | 1 |
| Panel "Real / modelo" con contadores de llamadas a `receive_ogm()` y `FaultManager.check()` | Deja explícito qué parte es código del protocolo y qué parte es simulación | 1 y 2 |
| "Ver como este nodo" | Cada nodo tiene su propia visión de la red: no hay vista global ni coordinador | 1 y 3 (ni los simuladores de modelos ni las herramientas de aplicación la exponen de forma interactiva) |
| Matriz de conocimiento N×N y su indicador de convergencia | Cuánto tarda la información en propagarse y qué rutas sobreviven a una partición (la ruta "vigente" que la radio ya no sostiene) | 1 |
| Anillos de vigilancia contra el `timeout` | La detección de fallos es distribuida: cada Gateway decide por su cuenta, con la latencia real del chequeo cada 5 s | 1 |
| OGM de un origen, con el TTL bajando | La inundación del protocolo real salto a salto | 1 y 3 |
| Enlaces coloreados por fiabilidad y mapa de cobertura (distancia + pisos) | Un medio con atenuación entre pisos de un edificio, no un grafo lógico | 2 y 3 |
| Arrastrar nodos, agregar Gateways, cambiar parámetros en vivo | Experimentar el efecto de la topología y del medio sobre el protocolo real sin desplegar hardware | 2 |
| Envolventes de partición y aviso de partición/reunificación | La auto-reorganización de la malla, visible | 3 |
| Exportar con `sesion_web.json` y el comando equivalente | La exploración interactiva no reemplaza el dato reproducible: una sesión sin intervenciones es, literalmente, una corrida de terminal | 1 y 2 |
| Editor de escenarios que guarda en el formato de `--config` | Diseñar el caso a la medida y llevarlo a lotes con semillas | 2 y 3 |

Insumo para los capítulos 1 y 4 de la tesis.

---

## 4. Verificación

### Hecha

- **Paridad con la terminal** (`tests/test_web_sesion.py`): con la
  misma semilla, k pasos por la `Sesion` dan exactamente la misma serie
  del `Recorder` y el mismo `resumen_corrida()` que `correr()`, en
  `base`, `denso` con `repartir`, `static` y modo aleatorio.
- **Regresión de lotes:** `lotes/ejemplo.json` y `lotes/movilidad.json`
  dan `corridas.csv` y `resumen.csv` idénticos a la línea base tomada
  antes de la Fase 1, también después de los cambios al núcleo de la
  Fase 2.
- **Núcleo** (`tests/test_nucleo_aditivo.py`): `add_node()` sin
  argumentos consume `random` igual que antes; `fiabilidad()` da
  idéntico a la fórmula original en 900 pares al azar; límites de
  `mover_nodo`; `_Packet` con tipo, origen y TTL; contadores;
  `validar_escenario` igual a `load_scenario`.
- **Backend** (`tests/test_web_*.py`): forma y tamaño del frame,
  enlaces y grupos iguales al modelo, cada comando válido e inválido,
  que cada parámetro de la lista blanca se lea en vivo, la matriz contra
  las tablas de rutas, la cobertura contra la fórmula del medio, las
  series incrementales, el editor (no pisa predefinidos, no sale de la
  carpeta, lo guardado corre con `--config` y `--headless`), el servidor
  en un puerto efímero (rutas, SSE, *path traversal*) y `--web` en la
  CLI (conflictos de flags y un arranque real que se cierra con
  `terminar`).
- **Frontend sin navegador** (`tests/test_web_frontend.py`): ejecuta los
  módulos de `web/static/js` en JavaScriptCore con datos reales y un DOM
  simulado: `main.js` completo recibiendo frames por el SSE simulado, el
  mapa con todas las capas, la lente, el filtro de OGM, selección,
  arrastre, herramienta de agregar y menú contextual con el puntero, los
  6 paneles de gráficas con tooltip, la línea de tiempo, la matriz, los
  paneles y el editor. Falla si un `NaN`, `undefined` o `null` llega al
  canvas o al HTML (comprobado rompiendo un dato a propósito).
- **Proceso real:** `python main.py --web` sirve la página y los
  estáticos con su tipo MIME, el SSE entrega ~16-18 frames por segundo,
  los comandos mutan el estado y `terminar` exporta y apaga sin dejar el
  proceso colgado.

### Pendiente: mirar la interfaz en un navegador

En el entorno donde se hizo este trabajo no hay un navegador
automatizable (sin Node.js ni Chromium, y `safaridriver` requiere
habilitarlo con permisos de administrador), así que no hay capturas ni
se midieron los 60 fps ni la memoria tras 30 minutos. Lista de chequeo:

- [ ] `python main.py --web --escenario base`: el edificio, 4 Gateway
  (círculos) y 3 Nodos de usuario (rombos); se mueven suave, sin
  saltos ni parpadeos; la consola del navegador sin errores.
- [ ] Tabla de paridad con pygame, con el teclado y con los botones:
  Espacio, Tab/←/→ y clic, 1-9, F/G, A/D, M, I, S, +/-, [/], P, R, Q.
- [ ] Caso 1 de la guía (tumbar G4) en la web.
- [ ] Caso 12 de la guía: "ver como este nodo" durante la partición de
  `rescatista_perdido`.
- [ ] Arrastrar un nodo, agregar un Gateway con clic, menú contextual.
- [ ] Matriz de conocimiento al arrancar (pocos pares con ruta) y a los
  30 s.
- [ ] OGM de un origen en `cadena.txt`: el TTL bajando salto a salto.
- [ ] Editor: guardar, cargar en la sesión, correr el comando que
  muestra en la terminal.
- [ ] Tema oscuro (sistema e interruptor), modo presentación en un
  proyector, ventana angosta (el panel lateral pasa abajo).
- [ ] Rendimiento: `-n 50 -g 10` fluido; 30 minutos a velocidad máxima
  sin que crezca la memoria de la pestaña (el cliente conserva como
  mucho 50 000 muestras y 300 líneas de log).

---

## 5. Limitaciones conocidas (la interfaz no las maquilla)

- **El TQ vale siempre 1.0** en toda ruta que existe: `BatmanRouter` no
  registra los OGM perdidos. Se rotula así en las gráficas, el panel
  "Real / modelo" y la lente; la calidad del medio es la tasa de entrega.
- **El ancho de banda es una heurística** (100 − 5·d Mbps hacia el
  Gateway más cercano), rotulada como estimación.
- **Grupos y nodos alcanzables se calculan sobre los enlaces de radio**
  (`_union_find`), no sobre las tablas de rutas.
- **Los mensajes viajan por el camino más corto en la malla de radio**
  (BFS), no por las tablas BATMAN; se indica si la ruta BATMAN ya había
  convergido.
- **Los paquetes del mapa son una muestra** cuando hay más de 300 en
  vuelo (salvo con el filtro de un origen, que los muestra todos).
- **Las rutas de `BatmanRouter` no expiran**: por eso la interfaz las
  marca obsoletas (destino en alerta o sin oírse más que el `timeout`)
  en vez de borrarlas.

Ninguna se "arregla" en este trabajo: son decisiones abiertas del
proyecto (`contexto/ESTADO_PROYECTO.md`, punto 4 de "Falta").
