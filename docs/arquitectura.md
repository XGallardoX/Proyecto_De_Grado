# Arquitectura del simulador

Este documento explica cómo encajan `mesh/`, `sim/` y `analysis/`, y por
qué las métricas que se ven en el simulador (TQ, tabla de rutas,
particiones de la malla) las produce el protocolo BATMAN real y no una
maqueta simplificada.

## Las 3 capas

```
┌─────────────────────────────────────────────────────────────┐
│  analysis/   métricas, visualización, reportes, lotes        │
│    metrics.py, inspector.py, visualizer.py, reporter.py,     │
│    lote.py                                                   │
└───────────────────────────▲───────────────────────────────────┘
                             │ lee el estado de
┌───────────────────────────┴───────────────────────────────────┐
│  sim/        puente de simulación                             │
│    engine.py (Simulation) · sim_node.py (SimNode) · radio.py  │
│    (RadioMedium) · config_loader.py                            │
└───────────────────────────▲───────────────────────────────────┘
                             │ usa directamente
┌───────────────────────────┴───────────────────────────────────┐
│  mesh/       protocolo BATMAN real                             │
│    router.py (BatmanRouter) · fault_manager.py (FaultManager) │
└─────────────────────────────────────────────────────────────┘
```

### `mesh/` — el protocolo real

`mesh/router.py` tiene `BatmanRouter`: recibe OGMs (`receive_ogm`),
calcula el **TQ** acumulado a partir de una ventana deslizante de
paquetes recibidos exitosamente (`link_quality`) y mantiene la tabla de
rutas (`RouteEntry`) eligiendo siempre la de mayor TQ. `FaultManager`
(`mesh/fault_manager.py`) detecta caídas comparando `last_seen` contra
un timeout. Estas son exactamente las clases que usaría un nodo real
corriendo sobre sockets UDP/TCP (`mesh/node.py`, con `mesh/api.py`
como API de control, `mesh/memory.py` como almacén distribuido y
`mesh/scheduler.py` para repartir tareas de cómputo) — pero el
simulador **no usa `mesh/node.py`**, sólo la parte de enrutamiento y
detección de fallos.

### `sim/` — el puente de simulación

`sim/sim_node.py` (`SimNode`) instancia un `BatmanRouter` y un
`FaultManager` reales por cada nodo (`sim_node.py:33-34`). En cada
`tick()`, en vez de escribir en un socket UDP, llama a
`sim.medium.broadcast(...)`. Los mensajes que sí llegan se acumulan en
`self._inbox`, y `_drain_inbox()` los procesa llamando a
`self.router.receive_ogm(msg, from_ip, now)` — **la misma función**
que procesaría un OGM llegado por red real. El TQ, la tabla de rutas y
la reconvergencia que ves en pantalla son, por tanto, un efecto directo
del algoritmo BATMAN real, no de un cálculo simulado aparte.

Lo único que sim/radio.py aporta —y lo único no real del sistema— es
decidir **qué OGMs/beacons llegan**: `RadioMedium.reliability(a, b)`
calcula una probabilidad de entrega a partir de la distancia 3D, el
rango de radio (`rango_comm`), una degradación con la distancia
(`falloff`), pérdida base y una atenuación extra si los nodos están en
pisos distintos (`floor_atten`). `broadcast()` tira un dado por cada
receptor en rango y sólo entrega el paquete si "gana"; lleva la cuenta
de paquetes intentados/entregados para las métricas de calidad del
medio.

`sim/engine.py` (`Simulation`) construye el mundo (a partir de
`sim/config_loader.py`, que valida un JSON de escenario, o de
`-n`/`-g` con posiciones aleatorias), avanza todos los `SimNode` un
paso `DT` a la vez, y expone las operaciones que el visualizador
dispara (añadir/quitar/matar/revivir nodo, enviar mensaje, cambiar
parámetros de radio en caliente).

### `analysis/` — métricas, visualización y reportes

`analysis/metrics.py` (`Recorder`) muestrea la serie temporal en cada
paso (nodos vivos, componentes de la malla, TQ medio, ratio de
entrega, etc.), y `resumen_corrida()` la condensa en las métricas
escalares de una corrida completa (las que imprime `--headless`).
`analysis/inspector.py` vuelca ese estado interno como
texto (tecla `I`). `analysis/visualizer.py` dibuja la ventana `pygame`
en vivo y construye la figura de 6 paneles con `matplotlib` al salir
(o con `P`). `analysis/reporter.py` exporta esa misma información a
CSV/JSON/TXT. Desde la reorganización de `reportes/`, ambos (figura y
reportes) comparten una sola carpeta con marca de tiempo por ejecución
— ver el README para el detalle de qué contiene cada archivo.
`analysis/lote.py` es la parte pura del runner de lote: valida el
archivo de lote, agrega las métricas de varias corridas (media ±
desviación estándar muestral por escenario, ignorando las corridas donde
una métrica no aplica) y escribe el resumen; correr cada corrida lo
hace `main.py`.

## `main.py`

Es la única pieza que no vive en un paquete. No conoce nada del
protocolo BATMAN — sólo cablea las tres capas de arriba:

- `construir_simulacion()` arma una `Simulation` lista para correr a
  partir de un archivo de escenario (`--config`/`--escenario`, vía
  `sim/config_loader.py`) o de `-n`/`-g`, con la geometría del edificio,
  los valores por defecto del medio (`DEFAULTS`) y los colores. Todos
  los modos pasan por aquí, así que una misma configuración produce la
  misma simulación en la ventana y sin ella.
- Después elige el modo: la ventana (`Visualizer`, por defecto),
  `--headless` (`correr()` + `build_analysis_figure()`, que exporta la
  figura y los reportes, más el resumen de `resumen_corrida()`),
  `--inspect` (`correr()` + `snapshot_red()`) o `--batch`
  (`ejecutar_lote()`: para cada escenario × semilla del archivo de lote
  fija la semilla, construye, corre y exporta, igual que `--headless`;
  después agrega con `analysis/lote.py`).
- `--seed` llama a `fijar_semilla()` antes de construir la simulación.
  Todo el azar del simulador (posiciones aleatorias, desfase inicial de
  los temporizadores, pérdidas del medio, movilidad) sale del módulo
  `random`, así que misma semilla + misma configuración = misma corrida.

## Qué NO usa el simulador (y por qué existe igual)

`mesh/node.py`, `mesh/api.py`, `mesh/memory.py` y `mesh/scheduler.py`
implementan el nodo real completo para desplegar en hardware
(Raspberry Pi u otro Linux con Wi-Fi Ad-Hoc): sockets UDP/TCP reales,
una API de control para un CLI externo, una memoria clave-valor
distribuida con vector clocks, y un scheduler que reparte tareas de ML
(regresión, MLP, fusión de sensores, planificación de rutas) entre
nodos. El simulador actual sólo ejercita la porción de enrutamiento +
detección de fallos de ese stack (vía `SimNode`); memoria distribuida,
scheduler y API de control no están conectados a `main.py` — quedan
disponibles para un modo de despliegue real que hoy no existe en el
repo. (El prototipo monolítico anterior a la migración a
`mesh/`/`sim/`/`analysis/`, `batman_node.py` + `simulacion_batman_real.py`,
se retiró del repo; queda en el historial de git.)

## Limitaciones conocidas

- **El TQ de `BatmanRouter` no refleja pérdidas.** `receive_ogm()`
  (`mesh/router.py`) agrega un `1` a la ventana deslizante de cada
  (origen, vecino) por cada OGM que recibe, pero nunca un `0` por los
  que se pierden; `link_quality()` promedia esa ventana. Resultado:
  toda ruta existente tiene TQ = 1.0, aunque el medio pierda entre un 5
  y un 25 % de los paquetes según el escenario (verificado en los 5
  escenarios predefinidos). El prototipo original (`batman_node.py`)
  hacía lo mismo. Mientras no se corrija, el "TQ medio" de la figura y
  de los reportes mide cuánto tiempo hubo rutas, no su calidad. Es
  código de la capa del protocolo real (lo usa también `mesh/node.py`),
  así que corregirlo cambia el protocolo y todos los resultados: queda
  como decisión aparte.
- **Con la movilidad por defecto, las particiones no se reunifican.**
  En `lotes/ejemplo.json` (5 escenarios × 10 semillas, 200 s) ningún
  episodio de partición terminó en reunificación: `particion` arranca
  partida y sigue así; en `rescatista_perdido` el Gateway 4, pasado
  `until`, sigue al Nodo de usuario más cercano (en la otra punta del
  edificio) y no vuelve; en `base`, a veces un Gateway sigue a otro
  nodo y se separa. El tiempo de reconvergencia sale "no aplica". Para
  medirlo hacen falta escenarios donde la partición se deshaga (ver
  [`movimiento_nodos.md`](movimiento_nodos.md) para la regla de
  movilidad).
- **No hay fallos programables en el escenario.** Sin ventana, los
  únicos fallos posibles son la batería agotada (`battery`,
  `battery_drain`) y el alejamiento (`wander`); la caída y la
  recuperación manual de un nodo (teclas `F`/`G`) sólo existen en la
  ventana. Un tipo de evento que haga caer o volver un nodo en un
  instante dado permitiría experimentos de fallo controlados en lote.
- **La conectividad se mide sobre los enlaces de radio.** Componentes,
  particiones, reunificaciones (eventos `PARTITION`/`HEAL`) y nodos
  alcanzables se calculan con union-find sobre los enlaces con
  fiabilidad > 0, no sobre las tablas de rutas. No hay una métrica de
  cuánto tarda BATMAN en volver a tener rutas hacia todos tras un
  cambio de topología.
- **Resto del framing de rescate en `mesh/`.** Los OGM del nodo real
  (`mesh/node.py`) y `PeerInfo` (`mesh/router.py`) conservan un campo
  `survivors`, que el nodo real emite siempre vacío. El simulador ya no
  lo emite ni lo lee (el mecanismo de "hallar supervivientes" se
  retiró); se deja porque es parte del formato de mensaje del nodo
  real, que queda fuera del alcance de esta fase.
