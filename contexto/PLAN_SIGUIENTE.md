# Dónde quedamos y cómo seguir

Fecha: 2026-10-26 (decisiones D7-D11 y pasos 7-12; las D1-D6 son del 2026-10-03)

Este archivo es el punto de partida para retomar el trabajo, en cualquier
máquina y con cualquiera de los dos autores. Las decisiones de abajo **ya
están tomadas**: no hace falta volver a consultarlas, sólo ejecutarlas.
Al terminar cada paso del plan, márcalo como hecho (`[x]`) en este mismo
archivo, en el mismo commit.

---

## Dónde quedamos

- **Simulador por terminal:** cerrado (ventana pygame, `--headless`,
  `--inspect`, `--batch`). Guía en `docs/guia_ejecucion.md`.
- **Interfaz web** (`python main.py --web`, o `--web --ventana`):
  completa, Fases 1 a 3. Incluye la lente de descentralización, el
  editor de escenarios, el laboratorio de experimentos y la exportación
  de sesiones como escenario. Detalle en `docs/interfaz_web.md`.
- **Fase 3 del núcleo:** eventos `fail`/`recover` programables en el
  escenario, métrica "Reconvergencia de rutas BATMAN" y escenarios de
  fallo del Capítulo 5 en `escenarios/fallos/` (historia y hallazgos en
  `DECISIONES_FASE3.md`).
- **Pruebas:** 328 en verde (`venv/bin/python -m unittest discover -s
  tests`; en Windows, `venv\Scripts\python`). En macOS además corre `tests/test_web_frontend.py`, que en
  Linux se omite porque necesita el `jsc` de macOS.
- **Documento de tesis** (`Plantilla/`): sólo el Capítulo 2. Se escribe
  **al final**, cuando estén los resultados (paso 6).

---

## Decisiones tomadas (2026-10-03)

Eran las decisiones abiertas del punto 4 de "Falta" en
`ESTADO_PROYECTO.md` y los tres puntos de la decisión 1d.

**D1. El TQ se corrige en `mesh/router.py`.** Hoy vale siempre 1.0
porque `receive_ogm()` agrega un `1` a la ventana deslizante por cada OGM
recibido y nunca un `0` por los perdidos. En BATMAN el TQ es justamente
la fracción de OGM recibidos de las últimas N secuencias de cada vecino,
así que esto es un defecto respecto del protocolo, no una simplificación.
Con TQ = 1.0 siempre, la métrica central de BATMAN no informa nada y la
elección de rutas por calidad no se ejercita: es lo primero que se
cuestionaría de un simulador que dice correr el código real.
- Cómo: por cada vecino (origen, IP de quien lo entregó), guardar la
  última secuencia vista. Cuando llega una mayor, agregar un `0` por
  cada secuencia salteada (hasta el tamaño de la ventana) y después un
  `1`. Las copias duplicadas o viejas no tocan la ventana. Esto se hace
  antes del descarte de duplicados que ya existe para el reenvío.
- Se arregla también para el nodo real, porque `mesh/node.py` usa el
  mismo router.
- Consecuencia: cambian todas las cifras (TQ medio, y quizá las rutas
  elegidas). Hay que volver a correr los lotes y actualizar los números
  de la guía, el README y los textos que dicen "el TQ vale 1.0",
  incluidos los rótulos de la interfaz web.

**D2. Un OGM nuevo de un origen apaga su alerta.** Hoy el `FaultManager`
detecta la caída con el `last_seen` del vecino, que refrescan los OGM,
pero sólo la apaga con un beacon directo. Un Gateway a varios saltos
queda "caído" para siempre (hallazgo 4). Se agrega `fault.recover(origen)`
cuando llega un OGM **nuevo** de ese origen, en `sim/sim_node.py` y en
`mesh/node.py`, para que la réplica siga siendo fiel. Detección y
recuperación quedan con el mismo criterio. Cambian las cifras de
alertas.

**D3. Movilidad: los resultados principales van con nodos fijos.** Una
Red de Expansión de Cobertura es infraestructura desplegada, y los dos
modelos de movilidad tienen artefactos conocidos: `seguir` apila los
Gateway y `repartir` parte la malla y hace parpadear los enlaces.
`seguir` contra `repartir` queda sólo como comparación secundaria en el
Capítulo 5 (caso 11 de la guía). No se diseña un tercer modo. `seguir`
sigue siendo el valor por defecto de la línea de comandos.

**D4. Se quita la excepción de `battery_drain` en el modo `-n`/`-g`.**
`construir_simulacion()` pone 0.02 en ese modo (viene del repo madre,
commit `bf98d2f`, sin motivo documentado), cuando el valor por defecto de
todo lo demás es 0.030. Pasa a usar `DEFAULTS`, como el resto. Cambian
los números del modo aleatorio (caso 6 de la guía).

**D5. Los escenarios de `escenarios/fallos/` son los del Capítulo 5.**
- El medio propio del despliegue (alcance 12 m, `falloff` 0.5,
  atenuación por piso 0.8) se mantiene y se justifica en la metodología
  como radios de baja potencia para interiores. Con el medio por
  defecto, un despliegue con puente y borde en este edificio pierde la
  mayoría de los paquetes.
- Nodos fijos (D3).

**D6. Métrica nueva: cobertura media.** `cobertura_media` es el promedio
en el tiempo de la fracción de Nodos de usuario vivos que están
alcanzables (la serie `nodos_alcanzables` dividida por los Nodos vivos;
se saltan las muestras sin Nodos vivos). Mide cuánta cobertura se pierde
mientras un Gateway está caído, que hoy no aparece en el resumen porque
sólo se reporta el valor final. Es aditiva: una columna más al final.

---

## Decisiones tomadas (2026-10-26)

Al revisar el simulador con el objetivo de la tesis (*un simulador hecho
a la medida para redes descentralizadas*) aparecieron tres lugares donde
decide con información global, como un coordinador central:

1. La movilidad `seguir` (`SimNode.move`) recorre `sim.nodes` y lleva a
   cada Gateway al Nodo de usuario más cercano mirando las posiciones de
   *todos*: por eso todos terminan apilados sobre el mismo nodo.
   `repartir` es un emparejamiento global que hace el motor.
2. `Simulation.send_unicast` entrega los mensajes por BFS sobre el grafo
   real y *garantiza* la entrega si existe camino: las tablas de BATMAN
   no deciden nada.
3. Sólo circulan OGM y beacons; no hay tráfico de datos.

**D7. Alcance completo: A + B + C + D**, en este orden después del front:
- **A. Plano de datos sobre BATMAN.** Cada paquete avanza salto a salto
  por la tabla de rutas *del nodo que lo tiene* (siguiente salto =
  `via_id` de su ruta), con las pérdidas del `RadioMedium`, TTL y
  detección de bucles; sin ruta o con el salto perdido, se pierde. Flujos
  de tráfico configurables en el escenario (origen, destino, cada cuánto).
  Métricas: tasa de entrega de datos, latencia, saltos reales contra el
  camino óptimo (estiramiento). Los mensajes manuales de la interfaz
  usan el mismo plano de datos.
- **B. Movilidad descentralizada de los Gateway** (modo nuevo, por
  defecto al terminar el paso): cada Gateway decide sólo con lo que oye
  (sus `PeerInfo`, el TQ y los beacons de los Nodos de usuario):
  atracción a los Nodos de usuario que oye débil o que nadie cubre,
  repulsión de los Gateway que oye demasiado fuerte, y no se aleja si
  perdería su último vecino Gateway. `seguir` y `repartir` quedan como
  comparación (línea base centralizada).
- **C. Métricas de descentralización:** divergencia entre lo que cada
  nodo cree y la realidad (lo que hoy muestra la lente, como número),
  nodos críticos (puntos de articulación de la malla) y fallos al azar
  contra fallos dirigidos al nodo más crítico.
- **D. Generalidad:** mapas que no sean sólo el edificio de 3 pisos
  (campo abierto), modelos de movilidad estándar (random waypoint y por
  grupos) y un protocolo de comparación (inundación simple) contra BATMAN.

**D8. D3 se reabre.** Con B, la movilidad deja de ser un artefacto: los
resultados del Capítulo 5 se vuelven a correr al final (paso 12) con la
movilidad descentralizada además de nodos fijos.

**D9. El front va primero** (paso 7): rediseño visual completo, sin
cambiar el contrato con el servidor ni los IDs que usan las pruebas.

**D10.** Las fuentes de la interfaz (Inter y JetBrains Mono, OFL) van
dentro del repo en `web/static/fuentes/`, para que se vea igual sin
conexión.

**D11. El documento de tesis (paso 6) sigue siendo lo último**, después
del paso 12.

---

## Plan de ejecución (en orden)

Cada paso: pruebas en verde, commits chicos (uno por unidad lógica) a
nombre de quien usa la sesión y **sin** `Co-Authored-By` (ver
`contexto/CLAUDE.md`), y `git push` a `main` al terminar el paso.

- [x] **Paso 1 — D4 y D6.** Quitar el 0.02 del modo aleatorio. Agregar
  `cobertura_media` a `analysis/metrics.py` (`METRICAS_CORRIDA`,
  `resumen_corrida`) con pruebas. Regresión: con D6, las columnas
  existentes de `lotes/ejemplo.json` y `lotes/movilidad.json` dan
  idéntico; D4 sólo cambia corridas `-n`/`-g`.
  *Hecho (2026-10-05).* Regresión verificada contra `HEAD` anterior: 0
  celdas distintas en las columnas existentes de los dos lotes (63 y 100
  corridas); la única diferencia es la columna `cobertura_media`. El caso
  6 de la guía (`-n 8 -g 2 --seed 7 --duracion 100`) da las mismas cifras
  porque en 100 s ningún Gateway agota la batería con 0.02 ni con 0.030:
  D4 sólo se nota en corridas largas del modo aleatorio. Pruebas: 292
  (de 288). La etiqueta en los reportes es "Cobertura media de Nodos de
  usuario". Las guías con bloques de salida completos (`guia_ejecucion.md`)
  no muestran aún esa línea: se refrescan en el paso 4.
- [x] **Paso 2 — D2.** Recuperar la alerta con un OGM nuevo, en
  `sim/sim_node.py` y `mesh/node.py`, con una prueba en el caso
  `escenarios/casos/puente.txt`: G1 y G3 dejan de creerse caídos después
  de que G2 vuelve.
  *Hecho (2026-10-05).* En `puente.txt` (semilla 1) G1 y G3 se
  recuperan mutuamente a los 103.5 y 105 s; las cifras del resumen del
  caso 13 no cambian. Prueba también del nodo real
  (`MeshNode._handle_bcast`): un OGM nuevo recupera, una copia repetida
  no. Pruebas: 294.
- [x] **Paso 3 — D1.** Corregir la ventana del TQ en `mesh/router.py`,
  con pruebas: OGM salteados bajan el TQ, los duplicados no lo tocan y
  un enlace sin pérdidas sigue en 1.0. Revisar la elección de rutas (que
  la de mejor TQ gane) y los textos que dicen "TQ = 1.0": README,
  `docs/arquitectura.md`, `docs/interfaz_web.md` y los rótulos de la
  interfaz.
  *Hecho (2026-10-05).* La elección de rutas también se corrigió: antes
  ganaba la primera copia de cada secuencia sin mirar el TQ, y las copias
  por otros vecinos se descartaban antes de compararlas. Ahora el vecino
  actual refresca la ruta; otro la reemplaza sólo con TQ mayor que el del
  actual, descontadas las secuencias que el actual se perdió; y cualquier
  copia no vieja mantiene vigente el `last_seen` (sin esto, una ruta por
  un vecino mejor cuya copia se perdió quedaba vieja aunque llegaran OGM
  por otro, y la reconvergencia de rutas no se cerraba). Pruebas en
  `tests/test_router_tq.py`; 305 en total. Ejemplos con `--seed 1
  --static`: TQ medio 0.740 en `base`, 0.514 en `denso`, 0.711 en
  `particion` (antes ≈ 1.0). La tabla del caso 4 de la guía ya está
  actualizada; el resto de las cifras, en el paso 4.
- [x] **Paso 4 — Nueva línea base.** Volver a correr
  `lotes/ejemplo.json`, `casos.json`, `movilidad.json`, `fallos.json` y
  `capitulo5_fallos.json`, y los comandos de los casos de
  `docs/guia_ejecucion.md`. Actualizar todos los números citados en la
  guía, el README, `docs/arquitectura.md`, `DECISIONES_FASE3.md` (sólo
  si cita cifras vigentes) y este archivo. Las cifras nuevas son la
  referencia de regresión de ahí en adelante.
  *Hecho (2026-10-05).* Se compararon los 5 lotes contra `f925c79`
  (antes de D2 y D1). Cambian el TQ medio y los saltos medios en todos
  los escenarios. Las alertas cambian solo donde un Gateway vuelve o un
  enlace parpadea, porque ahora cada alerta se apaga y puede volver a
  encenderse (D2): `denso` con `repartir` pasa de 38.9 a 54.7; los
  escenarios del Cap. 5 suben entre 0.4 y 1.1; `puente_40s` pasa de 5.7
  a 5.9. La reconvergencia de rutas apenas se mueve
  (`fallo_redundante` 7.75 → 7.65 y `fallo_puente` 19.85 → 19.45). El
  resto de las métricas da idéntico: entrega, componentes, alcanzables,
  particiones, reconvergencia física y cobertura media. Referencia
  nueva, con semillas 1-10:
  - TQ medio: `base` 0.889, `colapso_progresivo` 0.861, `particion`
    0.978, `rescatista_perdido` 0.790, `denso` 0.816, `base_static`
    0.762.
  - Escenarios del Cap. 5: TQ entre 0.32 y 0.36.
  - Cobertura media: `fallo_borde` 0.938 y `fallo_cascada` 0.736 (1.0
    en los demás).

  Se actualizaron en la guía los casos 3, 7, 9, 11, 12 (los saltos de
  G4 a los 60 s), 13 y 14. Los casos 1 y 6 salen igual. README y
  `docs/arquitectura.md` no citaban cifras que cambiaran.
- [x] **Paso 5 — Resultados del Capítulo 5.** Correr
  `lotes/capitulo5_fallos.json` con `"figuras": true` (y la comparación
  de movilidad, `lotes/movilidad.json`, como resultado secundario).
  Dejar tablas y figuras listas para el documento.
  *Hecho (2026-10-05).* Se corrió con `"figuras": true` desde una copia
  del lote, para no dejar la opción activada en el repo. El resumen sale
  idéntico al de la corrida sin figuras. Nuevo `analysis/capitulo5.py`
  (`python -m analysis.capitulo5`, con pruebas en
  `tests/test_capitulo5.py`; 309 pruebas en total). Escribe:
  - Tablas, para `\input{MainMatter/Cap5/tablas/...}`:
    `Plantilla/MainMatter/Cap5/tablas/fallos.tex` (respuesta a cada
    fallo), `calidad.tex` (TQ, saltos, entrega) y `movilidad.tex`
    (*seguir* / *repartir*, secundario).
  - Figuras vectoriales: `Plantilla/Images/Cap5/cobertura_tiempo.pdf`,
    `comparacion_fallos.pdf` y `movilidad.pdf`.

  Etiquetas para citarlas: `tab:cap5-fallos`, `tab:cap5-calidad` y
  `tab:cap5-movilidad`. No se compiló el PDF en esta máquina (no tiene
  TeX Live). Las tablas usan solo `array`, que la plantilla ya carga.
- [ ] **Paso 6 — Documento de tesis** (`Plantilla/`, lo último). Escribir
  los capítulos 0, 1, 3, 4, 5 y 9 con el encuadre del director
  (*"la necesidad de un simulador hecho a la medida para redes
  descentralizadas"*), pasar la sección de emergencias del Capítulo 2 a
  la Red de Expansión de Cobertura y completar la portada (título,
  autores, asesor y `pdfauthor`). Insumos: `docs/interfaz_web.md` §3
  (funcionalidad → vacío que atiende), la guía y los resultados del
  paso 5. Para compilar hace falta TeX Live (en la máquina de
  XGallardoX está en `~/texlive/2026`; ver `ESTADO_PROYECTO.md`).

- [x] **Paso 7 — Rediseño del front (D9, D10).** Barra lateral de
  secciones, controles de reproducción al centro, íconos SVG propios,
  tipografía Inter/JetBrains Mono, tokens de color para tema oscuro y
  claro, mapa con pisos como tarjetas, halos y pulsos de beacon,
  etiquetas con batería que no se enciman, gráficas en tarjetas y
  diálogos rediseñados.
  *Hecho (2026-10-26).* Se corrigieron de paso dos defectos: el tema
  guardado se aplicaba después de que el mapa leía los colores (mapa
  oscuro con paneles claros), y los avisos con `hidden` se veían por un
  `display` del CSS. `tests/frontend/stub.js` ahora simula los
  degradados del canvas. 309 pruebas en verde; el frontend se verificó
  en Chrome (sin errores de consola) en los dos temas.
- [x] **Paso 8 — A: plano de datos sobre BATMAN** (D7).
  *Hecho (2026-10-26).* `sim/datos.py` (`PlanoDatos`) y
  `BatmanRouter.next_hop()` en `mesh/router.py`. Cada paquete avanza
  salto a salto con la tabla del nodo que lo tiene; cada salto es un
  unicast con 3 reintentos (como 802.11) sobre la fiabilidad del medio;
  TTL 50 (como batman-adv). Tráfico: sección `traffic` del escenario
  (flujos explícitos y/o `aleatorios`), `--trafico K`, clave `trafico`
  del lote, campo en el diálogo de inicio y en el laboratorio. Los
  mensajes manuales (ventana y web) usan el mismo plano de datos.
  Decisiones al implementar:
  - **Sin latencia**: cada salto se resuelve dentro del paso (en una red
    real tarda ms, mucho menos que el paso de 0.5 s); se mide entrega,
    saltos, estiramiento y causas de pérdida. Por eso no hay latencia en
    las métricas, aunque D7 la mencionaba.
  - **Causas** separadas en físicas (`destino_caido`, `sin_camino`: no
    hay camino por radio al enviar, el paquete no se reenvía) y de
    enrutamiento (`sin_ruta`, `ruta_vieja`: el siguiente salto de la tabla
    está caído o fuera de alcance, `enlace`, `bucle`). Métrica clave para
    comparar protocolos: `entrega_datos_con_camino`.
  - Sin tráfico no se consume azar. Regresión: `capitulo5_fallos.json`
    y `ejemplo.json` (113 corridas) dan 0 celdas distintas; las columnas
    nuevas quedan vacías.
  - La figura PNG y la interfaz suman un 7.º panel sólo si hubo tráfico.
  - Los flujos arrancan en t = 0: las primeras pérdidas `sin_ruta` son
    la convergencia inicial (≈3-8 % en 200 s), se dejan a propósito.
  Hallazgos (con `--trafico 6`, nodos fijos, semillas 1-2):
  - **Bucles reales en las tablas** (1-2 % de los paquetes, entre t≈14 y
    50 s en `fallo_redundante`: ping-pong G3↔G2). Este `BatmanRouter`
    reenvía la primera copia de cada OGM venga por donde venga; BATMAN
    real sólo reenvía la que llegó por el mejor vecino. Se deja como
    está (cambiaría el plano de control); es un resultado para el Cap. 5.
  - **Reparación lenta de rutas**: tras caer un Gateway, la ruta por él
    sigue en la tabla ≈50 s (`ruta_vieja` de t=62 a 110 en
    `fallo_redundante`): sólo se reemplaza cuando su TQ descontado cae
    por debajo del de otro vecino; BATMAN real purga el originador por
    timeout.
  - Con `seguir` (`base`, `denso`) entre el 32 y el 78 % de los paquetes
    no tiene ningún camino por radio: los Gateway apilados dejan Nodos
    de usuario sin cobertura. Es lo que tiene que arreglar el paso 9.
  Pruebas: `tests/test_datos.py` (19); 328 en total.
- [ ] **Paso 9 — B: movilidad descentralizada de los Gateway** (D7, D8).
- [ ] **Paso 10 — C: métricas de descentralización** (D7).
- [ ] **Paso 11 — D: mapas, movilidad estándar y protocolo de
  comparación** (D7).
- [ ] **Paso 12 — Resultados de nuevo.** Volver a correr los lotes y el
  Capítulo 5 con todo lo anterior; actualizar cifras de la guía, el
  README y las tablas/figuras de `Plantilla/`. Después, el paso 6.

---

## Cómo retomarlo

1. Traer lo último y preparar el entorno (la primera vez en esa
   máquina):
   ```bash
   git pull
   python3 -m venv venv
   venv/bin/pip install -r requirements.txt
   venv/bin/python -m unittest discover -s tests
   ```
2. Abrir Claude Code en la raíz del repo y decirle:

   > Lee `contexto/PLAN_SIGUIENTE.md` y ejecuta el siguiente paso
   > pendiente del plan. Las decisiones ya están tomadas. Al terminar,
   > marca el paso como hecho en ese archivo, corre las pruebas y haz
   > commit y push a main.

   Para hacer varios pasos seguidos: "ejecuta los pasos 1 a 3 del plan".
3. Si se hace a mano, lo mismo: el siguiente paso sin marcar.
