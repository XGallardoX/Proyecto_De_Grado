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
| `GET /api/laboratorio` | Estado del laboratorio: `estado` (`inactivo`, `corriendo`, `cancelando`, `terminado`, `cancelado`, `error`), `hechas`/`total`, últimas líneas de `--batch`, el comando de terminal y, al terminar, el `resultado` (escenarios y métricas de `resumen.json`) |
| `GET /api/lotes` | Los lotes de `lotes/*.json`, para cargarlos en el laboratorio |
| `POST /api/laboratorio` | `{"accion": "iniciar", "lote": {...}}` o `{"accion": "cancelar"}` |

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
instante simulado. El **comando equivalente** de terminal existe si no
hubo intervenciones, o si las únicas fueron caer y recuperar y la sesión
salió de un archivo con nodos explícitos. En ese segundo caso,
"Exportar" escribe además `escenario_sesion.json`: el escenario cargado
con esas intervenciones como eventos `fail`/`recover` en su instante, y
el comando lo usa con `--config`. El motor aplica esos eventos en el
mismo punto del ciclo en que la sesión aplica una intervención (entre
dos pasos), así que la corrida es la misma: misma serie del `Recorder` y
mismo `resumen_corrida()` (probado en `tests/test_fase3.py`). Lo único
que cambia en `reporte.csv` es el texto del evento ("caído (manual)"
contra "caído (programado)"). Con cualquier otra intervención no hay
comando equivalente: la interfaz lo dice y quedan en `sesion_web.json`.

**Editor y eventos.** El editor de escenarios edita los tres tipos de
evento: `wander`, caída (`fail`) y recuperación (`recover`).

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
columna = el destino. Estados: `vigente` (con `hops`), `obsoleta`
(ningún OGM refrescó la ruta en el último `timeout`: el criterio de
`analysis.metrics.ruta_vigente`, el mismo de la métrica
`tiempo_reconvergencia_rutas_s`),
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
| Exportar con `sesion_web.json` y el comando equivalente | La exploración interactiva no reemplaza el dato reproducible: una sesión sin intervenciones, o con sólo caídas y recuperaciones (exportadas como eventos del escenario), es literalmente una corrida de terminal | 1 y 2 |
| Editor de escenarios que guarda en el formato de `--config` | Diseñar el caso a la medida y llevarlo a lotes con semillas | 2 y 3 |
| Laboratorio de experimentos (lotes `--batch` en un subproceso, con tabla y gráfica) | Pasar de la exploración a resultados con varias semillas sin salir de la interfaz, con los mismos números que la terminal | 1 y 2 |

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

### En un navegador (revisión del 3 de octubre)

Se recorrió la lista en Chrome sobre Linux (ventana de 1568×770 de
contenido), con la extensión Claude in Chrome. No se tomaron capturas
para el repo.

- [x] `base`: el edificio, los Gateway como círculos y los Nodos de
  usuario como rombos; sin errores en la consola.
- [x] Tabla de paridad: Espacio, clic, 1-9, F/G, A/D, M, I, S, +/-,
  [/], P y R funcionan. **No se probaron** Tab, ←/→ ni Q (Q está
  cubierta por `tests/test_web_cli.py`).
- [x] Caso 1 (tumbar G4): `FAIL` en t = 341 s y las tres alertas en
  t = 375 s.
- [x] Caso 12: la partición a los 41 s, la detección a los 70 s y la
  lente de G4, como dice la guía.
- [x] Arrastrar un nodo, agregar un Gateway con el menú contextual y el
  menú contextual de un nodo.
- [x] Matriz de conocimiento: un Gateway recién agregado aparece como
  "conectado por radio, sin ruta aún" y la cobertura baja al 44 %.
- [x] OGM de un origen en `cadena.txt`: los paquetes llevan su TTL. Ojo:
  toda la inundación ocurre dentro de un mismo paso de 0.5 s (los nodos
  procesan su bandeja en orden dentro de `step()`), así que se ven a la
  vez los saltos con TTL 6, 5 y 4, no como una onda en el tiempo.
- [x] Editor: guardar en `escenarios/` y correr el comando con
  `--headless --config`. No se probó "Cargarlo en esta sesión".
- [x] Comando equivalente: una sesión sin intervenciones
  (`colapso_progresivo`, semilla 1836583462, 36.5 s) da el mismo
  `reporte.csv`, byte a byte, que la terminal.
- [x] Interruptor de tema, modo presentación (`Z`) y ventana angosta
  (900 px: el panel pasa abajo, sin scroll horizontal). No se probó
  el tema según la preferencia del sistema ni un proyector real.
- [~] Rendimiento con 50 nodos y 10 Gateway: 58-59 fps, frames de 63 KB
  y heap de 14-33 MB que el recolector libera. Se probó 1-2 minutos,
  **no 30**. El núcleo no sostiene el ritmo de 1× con 50 nodos: aun en
  "máxima" da unos 7.5 s simulados por segundo real (1× pide 9).

**Detalles encontrados (ninguno bloquea):**
- El aviso dice "intervenciónes", con tilde (`main.js`, línea 336).
- Con una ventana de unos 1568 px, al aparecer el aviso de
  intervenciones la barra superior pasa a dos líneas y todo baja unos
  27 px.
- ~~La tabla de rutas y la matriz deciden si una ruta está obsoleta
  por el `last_seen` del vecino (también lo refrescan los beacons), no
  por el de la ruta.~~ Corregido en la Fase 3: usan
  `analysis.metrics.ruta_vigente`, el mismo criterio de la métrica de
  reconvergencia de rutas.
- ~~Tras un mensaje que falla, el texto queda en el compositor y el
  siguiente se escribe pegado a él.~~ Corregido: queda seleccionado y lo
  que se escribe lo reemplaza.
- Con nodos apilados (la movilidad `seguir`), las etiquetas se
  superponen y no se leen. Sigue así.
- ~~Varios textos usan voseo.~~ Corregido: tuteo en la interfaz, los
  mensajes de error y la guía.
- ~~El aviso dice "intervenciónes" y la barra superior salta de línea.~~
  Corregidos.

---

### Laboratorio y ventana propia (Fase 3)

- **Laboratorio** (`web/laboratorio.py`): un lote a la vez, con
  `python main.py --batch` en un subproceso (`cwd` = la raíz del repo,
  `MPLBACKEND=Agg`). Antes de lanzarlo valida sólo leyendo: el formato
  del lote con `analysis.lote` y cada escenario con `config_loader`.
  Nunca construye una `Simulation` en el servidor, porque eso consume
  `random` (probado). Las rutas `config` tienen que estar dentro de
  `escenarios/`. El progreso sale de las líneas `[k/N]` de `--batch` y
  el resultado, del `resumen.json` de la carpeta. Probado: el resumen
  del laboratorio es igual al de `ejecutar_lote()` con el mismo archivo.
  Verificado en Chrome con `lotes/fallos.json` (mismos números que en la
  terminal) y cancelando `lotes/ejemplo.json` a la mitad.
- **Ventana propia** (`--ventana`, `web/ventana.py`): el modo `--app` de
  un navegador basado en Chromium, buscado en el `PATH` y, en macOS y
  Windows, en sus rutas habituales; si no hay ninguno, el navegador por
  defecto. En la máquina de la revisión detecta Brave. Reemplaza a
  pywebview, que no se pudo instalar sin root (decisión 3).

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
  marca obsoletas (ningún OGM las refrescó en el último `timeout`) en
  vez de borrarlas.
- **Recuperar un nodo no es un arranque en frío**: conserva su secuencia
  de OGM. `BatmanRouter` no contempla que una secuencia vuelva a 0 (ver
  "Limitaciones conocidas" en `docs/arquitectura.md`).

Hasta el 2026-10-05 había una más: una alerta sobre un Gateway a varios
saltos no se apagaba, porque `FaultManager` sólo la borraba con un
beacon directo (`contexto/DECISIONES_FASE3.md`, hallazgo 4). Ahora la
apaga también un OGM nuevo de ese origen (decisión D2 de
`contexto/PLAN_SIGUIENTE.md`).
