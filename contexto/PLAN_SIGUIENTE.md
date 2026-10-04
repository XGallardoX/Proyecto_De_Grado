# Dónde quedamos y cómo seguir

Fecha: 2026-10-03 · `main` en `c336764`

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
- **Pruebas:** 288 en verde (`venv/bin/python -m unittest discover -s
  tests`). En macOS además corre `tests/test_web_frontend.py`, que en
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

## Plan de ejecución (en orden)

Cada paso: pruebas en verde, commits chicos (uno por unidad lógica) a
nombre de quien usa la sesión y **sin** `Co-Authored-By` (ver
`contexto/CLAUDE.md`), y `git push` a `main` al terminar el paso.

- [ ] **Paso 1 — D4 y D6.** Quitar el 0.02 del modo aleatorio. Agregar
  `cobertura_media` a `analysis/metrics.py` (`METRICAS_CORRIDA`,
  `resumen_corrida`) con pruebas. Regresión: con D6, las columnas
  existentes de `lotes/ejemplo.json` y `lotes/movilidad.json` dan
  idéntico; D4 sólo cambia corridas `-n`/`-g`.
- [ ] **Paso 2 — D2.** Recuperar la alerta con un OGM nuevo, en
  `sim/sim_node.py` y `mesh/node.py`, con una prueba en el caso
  `escenarios/casos/puente.txt`: G1 y G3 dejan de creerse caídos después
  de que G2 vuelve.
- [ ] **Paso 3 — D1.** Corregir la ventana del TQ en `mesh/router.py`,
  con pruebas: OGM salteados bajan el TQ, los duplicados no lo tocan y
  un enlace sin pérdidas sigue en 1.0. Revisar la elección de rutas (que
  la de mejor TQ gane) y los textos que dicen "TQ = 1.0": README,
  `docs/arquitectura.md`, `docs/interfaz_web.md` y los rótulos de la
  interfaz.
- [ ] **Paso 4 — Nueva línea base.** Volver a correr
  `lotes/ejemplo.json`, `casos.json`, `movilidad.json`, `fallos.json` y
  `capitulo5_fallos.json`, y los comandos de los casos de
  `docs/guia_ejecucion.md`. Actualizar todos los números citados en la
  guía, el README, `docs/arquitectura.md`, `DECISIONES_FASE3.md` (sólo
  si cita cifras vigentes) y este archivo. Las cifras nuevas son la
  referencia de regresión de ahí en adelante.
- [ ] **Paso 5 — Resultados del Capítulo 5.** Correr
  `lotes/capitulo5_fallos.json` con `"figuras": true` (y la comparación
  de movilidad, `lotes/movilidad.json`, como resultado secundario).
  Dejar tablas y figuras listas para el documento.
- [ ] **Paso 6 — Documento de tesis** (`Plantilla/`, lo último). Escribir
  los capítulos 0, 1, 3, 4, 5 y 9 con el encuadre del director
  (*"la necesidad de un simulador hecho a la medida para redes
  descentralizadas"*), pasar la sección de emergencias del Capítulo 2 a
  la Red de Expansión de Cobertura y completar la portada (título,
  autores, asesor y `pdfauthor`). Insumos: `docs/interfaz_web.md` §3
  (funcionalidad → vacío que atiende), la guía y los resultados del
  paso 5. Para compilar hace falta TeX Live (en la máquina de
  XGallardoX está en `~/texlive/2026`; ver `ESTADO_PROYECTO.md`).

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
