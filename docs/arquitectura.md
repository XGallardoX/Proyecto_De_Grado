# Arquitectura del simulador

Este documento explica cómo encajan `mesh/`, `sim/` y `analysis/`, y por
qué las métricas que se ven en el simulador (TQ, tabla de rutas,
particiones de la malla) las produce el protocolo BATMAN real y no una
maqueta simplificada.

## Las 3 capas

```
┌─────────────────────────────────────────────────────────────┐
│  analysis/   métricas, visualización, reportes               │
│    metrics.py, inspector.py, visualizer.py, reporter.py      │
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
entrega, etc.). `analysis/inspector.py` vuelca ese estado interno como
texto (tecla `I`). `analysis/visualizer.py` dibuja la ventana `pygame`
en vivo y construye la figura de 6 paneles con `matplotlib` al salir
(o con `P`). `analysis/reporter.py` exporta esa misma información a
CSV/JSON/TXT. Desde la reorganización de `reportes/`, ambos (figura y
reportes) comparten una sola carpeta con marca de tiempo por ejecución
— ver el README para el detalle de qué contiene cada archivo.

## `main.py`

Es la única pieza que no vive en un paquete: parsea los argumentos
(`-n`/`-g`, `--escenario`, `--config`, `--msg`), arma la configuración
del edificio y de la simulación, instancia `Simulation` y arranca
`Visualizer`. No conoce nada del protocolo BATMAN — sólo cablea las
tres capas de arriba.

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
repo (los antiguos `batman_node.py`/`simulacion_batman_real.py` en la
raíz eran el intento anterior a la migración a `mesh/`/`sim/`, ya
huérfanos).

## Gaps conocidos

- **No hay modo headless.** `main.py` siempre abre la ventana
  `pygame`. Existe un bloque `if __name__ == "__main__"` al final de
  `analysis/visualizer.py` con flags `--headless`/`--inspect`/`--seed`
  que sugiere que hubo un intento de portarlo, pero está roto: llama a
  `Simulation(escenario=..., cfg=cfg)` sin los parámetros
  (`DEFAULTS`, `DT`, dimensiones del edificio, colores) que
  `Simulation.__init__` requiere, así que revienta con `TypeError` al
  primer uso. Si se retoma el headless, ese bloque es más un punto de
  partida a corregir que código funcional a reutilizar tal cual.
- **`register_found()`/`my_survivors` es código muerto.** Nada llena
  `my_survivors` en el motor nuevo — la detección por proximidad
  (`rango_deteccion`) del prototipo viejo nunca se portó. Antes de
  documentar esto como una capacidad, hay que decidir si se implementa
  o se retira (ver `ESTADO_PROYECTO.md`).
