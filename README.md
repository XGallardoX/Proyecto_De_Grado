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

Punto de entrada único: `main.py`. Abre una ventana `pygame` con la
simulación en vivo.

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
| `--static` | Los nodos no se mueven: quedan fijos en la posición inicial (`move_speed=0`). Sin esto, los Gateway (`G`) se comportan como rescatistas y caminan hacia el Nodo de usuario (`N`) más cercano aún no encontrado. |

Tres formas de arrancar, de menor a mayor control sobre la topología:

```bash
# 1) Aleatorio: 5 nodos, 2 gateways, posiciones al azar
python main.py -n 5 -g 2

# 2) Uno de los 5 escenarios predefinidos (posiciones fijas)
python main.py --escenario colapso_progresivo

# 3) Tu propio archivo de escenario
python main.py --config escenarios/dos_nodos.json
```

No hay modo `--headless`/`--inspect` en `main.py` todavía — siempre
abre la ventana `pygame` (ver "Gaps conocidos" en `docs/arquitectura.md`).

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
`escenarios/{base,colapso_progresivo,particion,rescatista_perdido,denso}.json`.
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
| `M` | Enviar un mensaje libre entre dos nodos (abre un cuadro de texto en la ventana: `1>3 cuidado con los escombros`, `Enter` envía, `Esc` cancela) |
| `I` | Vuelca en la terminal el estado interno real de la red: vecinos (TQ, saltos, última vez oído), tabla de rutas BATMAN, componentes/particiones y enlaces de radio |
| `S` | Cambiar de escenario (cicla entre los predefinidos) |
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

Al salir de la ventana (`Q`/`Esc`/cerrar), o cada vez que presionas
`P`, se crea una carpeta nueva:

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

**`reporte.csv`** — una fila por paso registrado, columnas: tiempo,
gateways/nodos activos, componentes de malla, nodos alcanzables, TQ
promedio, saltos promedio, silencio máximo, tasa de entrega, alertas
activas, ancho de banda, hallazgos acumulados, tipo y descripción de
evento (si hubo alguno en ese instante).

**`reporte.json`** — `metadatos` (escenario, fecha, configuración
usada), `resumen` (estado final: nodos por rol, componentes finales,
paquetes transmitidos/recibidos), `serie_temporal_metricas` (igual que
el CSV pero en JSON) y `eventos` (lista cronológica).

**`reporte.txt`** — el mismo resumen en formato legible para pegar en
un informe: parámetros de configuración, estadísticas finales,
promedios de rendimiento y cronología de eventos.

---

## Tests

```bash
python -m unittest discover -s tests -v
```

Corre sobre `sim/config_loader.py`, `sim/radio.py` y `sim/engine.py`
directamente (sin `Visualizer`/pygame, no necesita pantalla), incluida
la regresión de los 5 escenarios migrados.

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

`batman_node.py` y `simulacion_batman_real.py` (raíz del repo) son el
prototipo **anterior** a la migración a `mesh/`/`sim/`/`analysis/`.
Ya no se usan — quedan en el repo sin mantenimiento, huérfanos.
