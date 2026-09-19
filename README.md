# Simulador de redes Ad-Hoc con BATMAN

Simulador de una red mesh ad-hoc que enruta con el protocolo
**B.A.T.M.A.N.** No reimplementa el protocolo de forma simplificada:
usa las mismas clases (`BatmanRouter`, `FaultManager`, `RouteEntry`,
`PeerInfo`) que correrían en un dispositivo real. Lo único simulado es
el **medio radio** — en vez de sockets UDP reales, un `RadioMedium`
decide qué paquetes llegan según distancia 3D y piso. Detalle completo
de cómo encajan las piezas en [`docs/arquitectura.md`](docs/arquitectura.md).

---

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Dependencias: `numpy`, `matplotlib`, `pygame`/`pygame-ce`.

---

## Cómo ejecutar

Punto de entrada único: `main.py`. Por defecto abre una ventana
`pygame` con la simulación en vivo; con `--headless` o `--inspect` corre
sin ventana (ver [Sin ventana](#sin-ventana---headless-e---inspect)).

```bash
python main.py --escenario base
```

### Opciones de `main.py`

| Flag | Qué hace |
|---|---|
| `-n`, `--nodes N` | Cantidad total de nodos, posiciones **aleatorias** (default `2`, requiere `N > 1`). Se ignora si se usa `--config`/`--escenario`. |
| `-g`, `--gateways N` | Cuántos de esos nodos son Gateway (`G`) en modo aleatorio (default `1`, debe ser `< --nodes`). |
| `--escenario {base,colapso_progresivo,particion,rescatista_perdido,denso}` | Atajo a `--config escenarios/<nombre>.json` — carga nodos y posiciones **explícitas**, tiene prioridad sobre `-n`/`-g`. |
| `--config archivo.json` | Ruta a un escenario JSON propio (ver sección siguiente). Tiene prioridad sobre `--escenario` y sobre `-n`/`-g`. |
| `--msg "texto"` | Mensaje de cabecera que se imprime al iniciar. |
| `--static` | Los nodos no se mueven: quedan fijos en la posición inicial (`move_speed=0`). Sin esto, cada Gateway (`G`) camina hacia el Nodo de usuario (`N`) más cercano (ver [`docs/movimiento_nodos.md`](docs/movimiento_nodos.md)). |
| `--headless` | Corre sin ventana durante `--duracion` segundos simulados y exporta la figura y los reportes a `reportes/<escenario>_<fecha_hora>/`. |
| `--duracion N` | Segundos **simulados** en `--headless`/`--inspect` (default `200`, mínimo `1`). Sin uno de esos dos flags es un error. |
| `--seed N` | Fija la semilla de `random` y `numpy`: misma semilla + misma configuración = misma corrida. Vale en cualquier modo. |
| `--inspect` | Corre `--duracion` segundos sin ventana e imprime el estado interno de la red (vecinos, tabla de rutas BATMAN, componentes, enlaces). No genera archivos. |

Tres formas de arrancar, de menor a mayor control sobre la topología:

```bash
# 1) Aleatorio: 5 nodos, 2 gateways, posiciones al azar
python main.py -n 5 -g 2

# 2) Uno de los 5 escenarios predefinidos (posiciones fijas)
python main.py --escenario colapso_progresivo

# 3) Tu propio archivo de escenario
python main.py --config escenarios/dos_nodos.json
```

### Sin ventana: `--headless` e `--inspect`

Para correr sin pantalla (un servidor, o para generar resultados sin
interactuar), las mismas tres formas de arrancar aceptan `--headless`:

```bash
# 50 s simulados del escenario base, reproducible con la semilla 1
python main.py --headless --escenario base --duracion 50 --seed 1

# Un archivo propio, con los nodos fijos
python main.py --headless --config escenarios/edificio_3_pisos.json --static
```

Al terminar imprime un resumen de la corrida (TQ medio, tasa de
entrega, componentes y nodos alcanzables al final, particiones,
reconvergencia, alertas; ver [Métricas de una
corrida](#métricas-de-una-corrida)) y deja en
`reportes/<escenario>_<fecha_hora>/` los mismos cuatro archivos que la
ventana (ver [Qué genera cada ejecución](#qué-genera-cada-ejecución-reportes)).

`--inspect` sirve para mirar por dentro el estado del protocolo en un
instante dado, sin generar archivos:

```bash
python main.py --inspect --escenario particion --duracion 30
```

imprime, para cada nodo, sus vecinos (TQ, saltos, hace cuánto se lo
oyó), su tabla de rutas BATMAN y a quién da por caído, más los grupos
conexos de la malla y la fiabilidad de cada enlace de radio — lo mismo
que la tecla `I` de la ventana.

---

## Archivo de escenario (`--config`)

En vez de `-n`/`-g`/`--escenario` (posiciones aleatorias), `main.py`
acepta un archivo JSON **o texto plano (`.txt`)** con nodos y
posiciones explícitas (o en modo aleatorio, ver más abajo). El formato
se detecta por la extensión del archivo.

```bash
python main.py --config escenarios/edificio_3_pisos.json
```

Esquema:

```json
{
  "name": "edificio_3_pisos",
  "building": { "ancho": 40, "alto": 30, "piso_h": 10, "n_pisos": 3,
                "stair_xy": [20, 15], "stair_half_w": 1.7 },
  "medium":   { "rango_comm": 16, "falloff": 0.85, "floor_atten": 0.55 },
  "protocol": { "timeout": 30, "beacon_cada": 2, "batman_cada": 4 },
  "nodes": [
    { "id": 1, "role": "G", "x": 5,  "y": 5  },
    { "id": 2, "role": "N", "x": 20, "y": 15 }
  ]
}
```

- Sólo `nodes` es obligatorio; `building`/`medium`/`protocol` faltantes
  usan los valores por defecto del simulador.
- `id`: entero único por nodo. `role`: `"G"` (Gateway) o `"N"` (Nodo de
  usuario) — se requiere al menos un `"G"`. `x`/`y`: posición en metros,
  debe caer dentro de `[0, ancho] x [0, alto]`. `battery` (opcional):
  batería inicial 0–100, por defecto 100.
- El **piso** de cada nodo se deriva de `y` (`y // piso_h`), no se
  declara aparte — para ubicarlo en el piso 2 de un edificio de
  `piso_h: 10`, usar `y` entre 10 y 20.
- `events` (opcional): lista de eventos del escenario. Por ahora sólo
  existe `{"type": "wander", "node_id": <id>, "until": <t>}` — el nodo
  se interna lejos hasta el segundo `until` y deja de dar señal.
- Config inválido (id duplicado, rol desconocido, sin gateway,
  coordenadas fuera del edificio, campo faltante) frena la ejecución
  con un mensaje de error específico, antes de arrancar la simulación.

Claves de `medium` y `protocol` (las dos secciones se mezclan sobre los
mismos valores por defecto, así que da igual en cuál va cada clave):

| Clave | Por defecto | Qué controla |
|---|---|---|
| `rango_comm` | `16` | Alcance máximo de radio (m) |
| `perdida_base` | `0.02` | Probabilidad de perder un paquete incluso a 0 m |
| `falloff` | `0.85` | Cuánto cae la fiabilidad del enlace con la distancia |
| `floor_atten` | `0.55` | Factor de atenuación por cada piso de diferencia |
| `timeout` | `30` | Segundos sin oír a otro Gateway antes de marcarlo caído |
| `beacon_cada` | `2` | Segundos entre beacons de identificación |
| `batman_cada` | `4` | Segundos entre OGMs propios |
| `ttl` | `6` | Saltos máximos de un OGM |
| `battery_drain` | `0.030` | % de batería por segundo que gasta un Gateway |
| `battery_drain_nodo` | `0.012` | % de batería por segundo que gasta un Nodo de usuario (el nombre viejo `battery_drain_surv` se sigue aceptando) |
| `move_speed` | `0.32` | Metros por paso de un Gateway (`0` = nodos fijos, ver `--static`) |

En modo aleatorio desde la línea de comandos (`-n`/`-g`, sin archivo),
`battery_drain` vale `0.02` en vez de `0.030`.

### Formato `.txt` (equivalente al JSON, más fácil de editar a mano)

```bash
python main.py --config escenarios/ejemplo.txt
```

```
name: mi_escenario

[building]
ancho=40
alto=30
piso_h=10
n_pisos=3

[medium]
rango_comm=16
falloff=0.85

[protocol]
timeout=30
static=true      # equivale a move_speed=0 (nodos fijos, ver --static)

[nodes]
# id  role  x   y   [battery opcional]
1     G     7   27
2     N     20  15

[events]
# type    node_id  until
wander    2        60
```

- `#` marca comentarios (línea completa o al final de una línea).
- Secciones `[building]`, `[medium]`, `[protocol]` son opcionales,
  `clave=valor` uno por línea — mismas claves que el JSON (`ancho`,
  `rango_comm`, `timeout`, `move_speed`, etc.). `protocol` acepta
  además `static=true/false` como atajo legible de `move_speed=0`.
- `[nodes]` es obligatoria: una línea por nodo (`id role x y
  [battery]`, separado por espacios), **o** modo aleatorio con
  `mode=random`, `n_nodes=N`, `n_gateways=G` en vez de líneas de nodos
  (no se pueden mezclar los dos estilos en la misma sección).
- `[events]` es opcional, una línea por evento: `wander node_id until`.
- Mismas validaciones y mismos mensajes de error que el JSON (id
  duplicado, rol inválido, sin gateway, fuera del edificio, etc.).

Ver [escenarios/ejemplo.txt](escenarios/ejemplo.txt) para un ejemplo
completo funcionando.

Los 5 escenarios de `--escenario` son atajos a
`escenarios/{base,colapso_progresivo,particion,rescatista_perdido,denso}.json`:

| Escenario | Qué plantea |
|---|---|
| `base` | 4 Gateway juntos en el piso 3 y 3 Nodos de usuario repartidos en los pisos 1 y 2. Caso de referencia. |
| `colapso_progresivo` | Como `base`, pero los Gateway arrancan con baterías escalonadas (100/78/56/38 %) y gastan rápido (`battery_drain` 0.45): van cayendo uno tras otro. |
| `particion` | Rango de radio reducido (11 m) y dos parejas de Gateway en esquinas opuestas del edificio: la malla de Gateways arranca partida. |
| `rescatista_perdido` | Como `base`, pero el Gateway 4 se aleja hacia la esquina (38, 2) hasta t = 80 s (evento `wander`) y pierde contacto con el resto. El nombre viene del framing anterior de rescate; se conserva para no romper `--escenario`. |
| `denso` | 8 Gateway y 6 Nodos de usuario: una malla más poblada. |

`dos_nodos.json` y `edificio_3_pisos.json` son dos ejemplos adicionales,
más simples, para probar el formato.

---

## Controles en la ventana en vivo

| Tecla / acción | Efecto |
|---|---|
| `ESPACIO` | Pausa / reanuda |
| `TAB`, `←`/`→`, o clic sobre un nodo | Seleccionar nodo |
| `1`-`9` | Seleccionar el N-ésimo Gateway |
| `F` | El nodo seleccionado cae (deja de emitir) |
| `G` | El nodo seleccionado se recupera |
| `A` | Añadir un nodo nuevo a la simulación |
| `D` | Eliminar el nodo seleccionado |
| `M` | Enviar un mensaje libre entre dos nodos: abre un cuadro de texto donde se escribe `emisor > destino texto`, p. ej. `G1>G3 prueba de enlace` o `N2>G1 hola` (sin letra se asume Gateway: `1>3` es `G1>G3`). `Enter` envía, `Esc` cancela |
| `I` | Vuelca en la terminal el estado interno real de la red: vecinos (TQ, saltos, última vez oído), tabla de rutas BATMAN, componentes/particiones y enlaces de radio |
| `S` | Pasar al siguiente escenario predefinido (cicla entre los 5; la simulación arranca de cero y respeta `--static`) |
| `+`/`-` | Aumentar/reducir el rango de radio |
| `[`/`]` | Reducir/aumentar el `falloff` (degradación con la distancia) |
| `P` | Exportar ahora mismo el análisis y los reportes (sin cerrar la ventana) — ver sección siguiente |
| `R` | Reiniciar la simulación |
| `Q` / `Esc` | Salir (también exporta análisis y reportes) |

Los mensajes se enrutan salto por salto sobre la malla real: llegan
siempre que exista un camino (aunque sea indirecto, multi-salto) entre
origen y destino, y sólo se pierden si la malla está partida o el
destino está caído.

---

## Qué genera cada ejecución (`reportes/`)

Al salir de la ventana (`Q`/`Esc`/cerrar), cada vez que presionas `P`,
o al terminar una corrida `--headless`, se crea una carpeta nueva:

```
reportes/<escenario>_<fecha_hora>/
├── analisis_red.png   ← figura de 6 paneles (matplotlib)
├── reporte.csv         ← serie temporal, una fila por paso registrado
├── reporte.json        ← metadatos + resumen + serie temporal + eventos
└── reporte.txt         ← resumen legible en texto plano
```

Cada ejecución (o cada exportación manual con `P`) tiene su propia
carpeta con marca de tiempo, así que corridas distintas nunca se pisan.
La carpeta `reportes/` está en `.gitignore` — no se commitea.

**`analisis_red.png`** — 6 paneles:
1. Nodos activos en el tiempo (Gateways vs. Nodos de usuario).
2. Auto-reorganización de la malla: nº de componentes conectados
   (1 = malla unida, >1 = partición BATMAN) y nodos de usuario
   alcanzables.
3. Calidad de enrutamiento: TQ medio de las rutas y saltos medios.
4. Detección de gateway perdido: silencio máximo vs. el umbral de
   `timeout` configurado.
5. Calidad del medio radio: ratio de paquetes entregados/intentados.
6. Ancho de banda total de la red, con eventos marcados.

**`reporte.csv`** — una fila por paso registrado (un paso = 0.5 s
simulados). Columnas: `tiempo_s`, `gateways_activos`, `nodos_activos`,
`componentes_malla`, `nodos_alcanzables`, `calidad_ruta_promedio_tq`,
`saltos_promedio`, `silencio_maximo_s`, `tasa_entrega_paquetes`,
`alertas_activas`, `ancho_banda_total_mbps`, y `tipo_evento` /
`descripcion_evento` (si hubo algún evento en ese instante).

**`reporte.json`** — `metadatos` (escenario, fecha, configuración
usada), `resumen` (estado final: nodos por rol, componentes finales,
paquetes transmitidos/recibidos, tasa de entrega), `serie_temporal_metricas`
(las mismas columnas de métricas que el CSV, con los mismos nombres) y
`eventos` (lista cronológica).

**`reporte.txt`** — el mismo resumen en formato legible para pegar en
un informe: parámetros de configuración, estadísticas finales,
promedios de rendimiento y cronología de eventos.

### Métricas de una corrida

El resumen que imprime `--headless` sale de la serie temporal que ya
registra `analysis/metrics.py` (`resumen_corrida()`), sin
instrumentación aparte:

| Métrica | Cómo se calcula |
|---|---|
| TQ medio de rutas | Promedio en el tiempo del TQ medio de todas las rutas de todos los nodos vivos (el mismo valor que "Calidad de Ruta Promedio" de `reporte.txt`). Ver la advertencia de abajo. |
| Saltos medios por ruta | Ídem, con la cantidad de saltos de cada ruta. |
| Tasa de entrega del radio | Paquetes entregados / intentados por el medio en toda la corrida. |
| Componentes de la malla al final | Grupos conexos de Gateways vivos en el último instante (1 = malla unida). |
| Nodos de usuario alcanzables al final | Nodos `N` vivos que comparten grupo con algún Gateway en el último instante: la cobertura que da la malla. |
| Gateways vivos al final | Gateways con batería y sin fallo en el último instante. |
| Episodios de partición | Veces que la malla de Gateways pasó de un componente a más de uno. |
| Tiempo con la malla partida (s) | Tiempo total con más de un componente. |
| Tiempo de reconvergencia (s) | Duración media de los episodios de partición que terminaron en una reunificación: la malla volvió a un solo componente sin perder Gateways en ese paso (el mismo criterio que el evento `HEAL`). Si la partición desaparece porque el Gateway aislado cayó, no cuenta. "No aplica" si ningún episodio se reunificó. |
| Alertas de gateway perdido | Eventos `ALERT_ON`: un Gateway dejó de oír a otro durante más de `timeout` segundos (cada Gateway que lo detecta cuenta una). |
| Primera alerta (s) | Instante de la primera de esas alertas; "no aplica" si no hubo. |

Dos advertencias para interpretarlas:

- **El TQ vale 1.0 en toda ruta que existe.** `BatmanRouter`
  (`mesh/router.py`) sólo agrega un `1` a su ventana deslizante cuando
  recibe un OGM y nunca registra los que se pierden, así que la calidad
  de enlace no baja de 1.0 aunque el medio pierda paquetes. El "TQ
  medio" termina midiendo durante cuánto tiempo hubo rutas (vale 0
  hasta que llega el primer OGM), no la calidad de los enlaces. Ver
  "Limitaciones conocidas" en [`docs/arquitectura.md`](docs/arquitectura.md).
- **Particiones y reconvergencia miden conectividad de radio, no
  tablas de rutas.** Dos Gateways están en el mismo componente si hay un
  camino de enlaces en rango entre ellos (lo mismo que el panel 2 de la
  figura y los eventos `PARTITION`/`HEAL`). El tiempo que tarda BATMAN
  en volver a tener rutas hacia todos no se mide aparte.

---

## Tests

```bash
python -m unittest discover -s tests -v
```

Cubre `sim/` (carga y validación de escenarios, medio radio, motor y
ciclo de vida de `SimNode`: tick, inbox, batería, detección de caídas,
movilidad), `analysis/` (columnas y campos de los reportes, resumen por
corrida, funciones puras de la ventana) y `main.py` sin ventana
(`--headless`, `--inspect`, `--seed`), incluida la regresión de los 5
escenarios migrados. No abre la ventana `pygame` ni necesita pantalla;
sí necesita el entorno con las dependencias de `requirements.txt`.

---

## Estructura del proyecto

```
main.py                  ← punto de entrada (CLI)
mesh/                     ← protocolo BATMAN real (router, fault manager, ...)
sim/                      ← motor de simulación + medio radio + carga de escenarios
analysis/                 ← métricas, visualizador pygame, reportes
escenarios/*.json         ← escenarios predefinidos
tests/                     ← pruebas unitarias
```

Ver [`docs/arquitectura.md`](docs/arquitectura.md) para el detalle de
cómo se relacionan estas capas y por qué las métricas que se ven
(TQ, rutas, particiones) las produce el código real del protocolo y no
una maqueta.
