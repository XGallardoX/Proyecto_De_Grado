# Análisis del repo madre — `jofsanchezci/Simulador_BATMAN`

> Clonado en `~/Escritorio/Simulador_BATMAN_madre` (solo para análisis, no
> es parte de este repo). Nada de esto se ha traído todavía a
> `ProyectoGrado` — es el diagnóstico para decidir qué traer.

## Respuesta corta: ¿solo `main` y `develop`?

**Trae `develop`, no `main`.** `main` no aporta nada que `develop` no
tenga: los dos arrancan del mismo commit único `894dea6 "simulador"`,
que es exactamente el commit en el que está hoy nuestro
`ProyectoGrado` (`git log` de nuestro repo también marca `894dea6` como
`HEAD`). `main` no se movió desde entonces; todo el trabajo real pasó
a `develop`.

De las otras 5 ramas remotas, **ninguna hace falta traer aparte ahora**:

| Rama | Estado | ¿Traerla? |
|---|---|---|
| `main` | = commit inicial, sin avances | No aporta nada sobre lo que ya tenemos |
| `develop` | Base + 3 PRs ya mergeados (gitignore, reorganización, reportes) | **Sí, es la base a traer** |
| `chore/SMB-01-add-gitignore` | Ya mergeada en `develop` | No, ya viene incluida |
| `refactor/SMB-02-reorganize-simulator` | Ya mergeada en `develop` | No, ya viene incluida |
| `feat/SMB-03-add-reports-json-csv-and-text` | Ya mergeada en `develop` | No, ya viene incluida |
| `refactor/SMB-04-Improvements-to-Message-Sending` | Apunta al mismo commit que `develop`, **0 commits propios** — parece creada pero nunca trabajada | No, no tiene contenido que traer |
| `feat/real-device-testing` | 1 commit propio, basada en `develop`, **no mergeada** | No por ahora — es despliegue en hardware real, no simulación (ver abajo) |

---

## Qué trae `develop` que nuestro repo no tiene

Nuestro `ProyectoGrado` está congelado en el commit raíz. `develop` ya
avanzó bastante:

```
main.py                    ← nuevo punto de entrada (antes se corría simulacion_batman_real.py)
mesh/
├── node.py                ← MeshNode (antes en batman_node.py)
├── router.py               ← BatmanRouter, PeerInfo, RouteEntry
├── fault_manager.py         ← FaultManager
├── memory.py                ← DistributedMemory
├── scheduler.py             ← DistributedScheduler
└── api.py                   ← CtrlAPI
sim/
├── engine.py                ← Simulation (antes en simulacion_batman_real.py)
├── radio.py                  ← RadioMedium
└── sim_node.py                ← SimNode
analysis/
├── metrics.py                  ← Recorder
├── inspector.py                 ← snapshot_red
├── visualizer.py                 ← Visualizer (pygame)
└── reporter.py                    ← NUEVO: exporta CSV/JSON/TXT (SMB-03)
batman_node.py              ← se queda en el repo, sin cambios, ya no se usa
simulacion_batman_real.py   ← se queda en el repo, sin cambios, ya no se usa
```

O sea: partieron los dos archivos monolíticos que nosotros tenemos en
paquetes (`mesh/`, `sim/`, `analysis/`), dejaron los dos originales
intactos pero huérfanos (nada los importa ya), y sumaron un módulo de
reportes nuevo.

**Cambio de vocabulario del dominio:** los roles ya no son
`R`/`S` (rescatista/superviviente) sino `G`/`N` (Gateway/Nodo), y el
framing pasó de "red de rescate" a **"Red de Expansión de Cobertura"**
(así lo dice el nuevo `main.py`). Esto es una señal de que el enfoque
del proyecto pudo pivotar del escenario de rescate hacia uno más
genérico de cobertura ad-hoc con gateways — vale la pena confirmarlo
con quien lleva el repo madre antes de decidir sobre qué narrativa
construir el documento de grado.

---

## Lo bueno: ya resolvieron parte de lo que nosotros íbamos a diseñar

`main.py` en `develop` ya acepta:

```bash
python main.py -n 10 -g 2 --escenario base
#   -n/--nodes    cantidad total de nodos (validan n > 1)
#   -g/--gateways cantidad de gateways (validan g < n)
```

Y `Simulation.add_node()` / `remove_node()` existen y están conectados
a teclas en el `Visualizer` (líneas 637/642) para añadir o quitar
nodos **en caliente** durante la simulación. Lo probé directamente
sobre el motor (sin pygame, instanciando `Simulation` a mano con
`n_nodes=7, n_gateways=2`): crea los 7 nodos y corre `step()` sin
errores.

Es decir: el problema de "nodos a voluntad" **ya tiene una primera
solución en el repo madre**, aunque más simple que lo que planteamos
en `PLAN_TRABAJO.md` — sirve como punto de partida, no como algo que
haya que re-inventar desde cero.

## Lo que le falta / lo que rompieron (hallazgos concretos)

1. **La colocación sigue sin ser "a voluntad".** `_build_world()`
   ubica cada gateway/nodo en `(random.uniform(5,35), random.uniform(5,25))`
   — posición aleatoria, no elegida. No hay archivo de configuración
   ni forma de decir "el nodo 3 va en (7, 27), piso 3". Nuestra
   propuesta de config JSON con posiciones explícitas (Parte 1.1 del
   plan) sigue siendo necesaria.

2. **`--escenario` ya no hace nada.** `main.py` todavía ofrece
   `--escenario {base,denso,particion}`, pero en `sim/engine.py` no
   queda ningún `if escenario == ...` — el valor solo se guarda y se
   imprime en el log. Los tres escenarios generan exactamente el mismo
   tipo de mundo (posiciones aleatorias uniformes). Es una regresión
   frente a lo que teníamos, donde cada escenario tenía layout y
   parámetros propios.

3. **Se perdieron `--headless`, `--duracion` e `--inspect`.** El
   `main.py` nuevo solo sabe abrir la ventana pygame en vivo. No hay
   forma de correr una simulación sin interfaz gráfica, ni de generar
   el PNG de análisis por script, ni de volcar el snapshot de texto —
   todo eso existía en `simulacion_batman_real.py` y no se migró al
   nuevo entry point.

4. **Bug de rol heredado.** `sim/engine.py::register_found()` sigue
   comprobando `role == 'S'`, pero los roles ahora son `'G'`/`'N'` —
   ese `if` nunca se cumple, así que registrar un "hallazgo" con el
   vocabulario nuevo está roto (es resto del refactor de R/S a G/N que
   no se completó en todos los sitios).

5. **`analysis/reporter.py` (todo el trabajo de SMB-03) no está
   conectado a nada.** Definí un grep sobre las 19 archivos `.py` de
   `develop` buscando `reporter` fuera del propio archivo: cero
   resultados. La función `export_simulation_reports()` existe, genera
   CSV/JSON/TXT, pero ningún flag de CLI ni tecla del visualizador la
   llama. Es una funcionalidad terminada pero huérfana.

6. **`requirements.txt` sigue roto para Python 3.14** (mismo problema
   que ya resolvimos en este repo): falta `matplotlib`, y
   `pandas==1.5.2` / `requests==2.28.1` están fijados a versiones que
   no compilan en 3.14 y que además no se usan en ningún `.py` del
   proyecto.

7. **`README.md` no se actualizó** con la reorganización: sigue
   describiendo `batman_node.py` y `simulacion_batman_real.py` como si
   fueran los archivos vigentes, no menciona `main.py` ni los paquetes
   `mesh/`, `sim/`, `analysis/`, ni el reporter nuevo.

## Rama aparte: `feat/real-device-testing`

Esta rama (1 commit, "fix/ testing real", basada en la punta actual de
`develop`) **borra** `batman_node.py` y `simulacion_batman_real.py`
(los 2 archivos monolíticos huérfanos) y agrega lo que el `README`
prometía pero no existía en el repo: `mesh_cli.py` (CLI de control por
socket contra el puerto 5559) y `setup_mesh.sh` (configuración de la
interfaz Wi-Fi en modo Ad-Hoc real), más 88 líneas nuevas en
`mesh/node.py`. Es trabajo para desplegar la malla en dispositivos
físicos (Raspberry Pi / laptops con Wi-Fi IBSS) — un frente
completamente aparte de la simulación. **No hace falta para lo que nos
pidieron** (rediseñar el simulador), pero es candidata a traer más
adelante si el proyecto llega a la fase de prueba en hardware real.

---

## Recomendación de cómo traerlo

1. Traer solo `develop` como base — es un superconjunto estricto de
   `main` con la reorganización en paquetes y los reportes ya
   integrados.
2. No traer `feat/real-device-testing` ni `refactor/SMB-04` todavía
   (la primera es un frente distinto; la segunda no tiene contenido).
3. Como nuestro `ProyectoGrado` está parado exactamente en el mismo
   commit raíz que `develop`, se puede traer sin conflictos:

   ```bash
   git remote add madre git@github.com:jofsanchezci/Simulador_BATMAN.git
   git fetch madre
   git merge madre/develop      # fast-forward puro, sin conflictos
   ```

4. Ajustar `PLAN_TRABAJO.md`: ya no partimos de los dos archivos
   monolíticos sino de los paquetes `mesh/`/`sim/`/`analysis/` de
   `develop`. El trabajo de la Parte 1 (config por archivo con
   posiciones explícitas) se monta sobre `sim/engine.py::_build_world()`
   en vez de sobre `simulacion_batman_real.py::_build_world()`, y de
   paso conviene cerrar los 7 huecos listados arriba (headless/inspect/
   duración, escenarios reales, bug de rol, reporter conectado,
   requirements, README).
