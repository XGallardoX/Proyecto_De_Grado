# Decisiones pendientes: Fase 3 de la interfaz web

Fecha: 2026-09-30 · Rama: `feat/interfaz-web`

> **Actualización 2026-10-03:** se revisó la rama en Linux y aparecieron
> dos hallazgos que cambian el alcance de la parte 1 (sección
> "Revisión del 3 de octubre", al final). Las decisiones de XGallardoX
> están en "Decisiones", también al final. **Jefferson dio el visto
> bueno el 2026-10-03**, también a la parte 1 ya implementada y a sus
> dos ajustes ("Estado de la parte 1").

Las fases 1 y 2 de `prompt_version_escritorio.md` (la interfaz web
local, `python main.py --web`) están hechas y probadas. El detalle está
en `contexto/ESTADO_PROYECTO.md` y en `docs/interfaz_web.md`. El
encargo pide que la **Fase 3 no arranque sin el acuerdo de los dos
autores**, así que quedan acá las tres partes, cada una por separado,
para decidir cuáles se hacen.

Antes de decidir conviene abrir la interfaz y probarla. No se pudo
mirar en un navegador real desde el entorno donde se programó: la lista
de chequeo está en `docs/interfaz_web.md`, sección 4. La prueba más
corta es:

```bash
python main.py --web --escenario rescatista_perdido --seed 1
```

---

## 1. Eventos de caída y recuperación programables en el escenario

**Qué es.** Un tipo de evento nuevo en el esquema de escenario, al lado
del `wander` que ya existe:

```json
"events": [
  {"type": "fail",    "node_id": 4, "t": 60},
  {"type": "recover", "node_id": 4, "t": 120}
]
```

El motor (`sim/engine.py`) lo aplicaría en ese instante, igual que hoy
lo hacen las teclas `F`/`G` o la interfaz web.

**Qué permite.**
- Medir la **reconvergencia en serio**. Hoy sale "no aplica" en casi
  todas las corridas, porque ninguna partición se deshace sola (punto
  4 de "Falta" en `ESTADO_PROYECTO.md`). Con caídas y vueltas
  programadas, un lote con 10 semillas daría tiempos de reconvergencia
  comparables, que es lo que más le falta al Capítulo 5.
- Exportar una sesión web **con** intervenciones como escenario
  reproducible: hoy, si alguien tumba un nodo a mano, la sesión ya no
  tiene comando equivalente de terminal.
- Experimentos de fallo controlados en `--batch`.

**Qué toca.** `sim/config_loader.py` (validar el evento nuevo),
`sim/engine.py` (aplicarlo), el formato `.txt` de escenarios, el editor
web, el README y la guía. Es aditivo: los escenarios actuales no tienen
estos eventos, así que sus resultados no cambian (se verificaría con la
regresión de lotes, como en las fases anteriores).

**Por qué hay que decidirlo entre los dos.** Cambia el esquema de
escenarios y, sobre todo, define **cómo se va a medir la
reconvergencia en el documento**, que era una decisión abierta. Si se
hace, conviene acordar también qué escenarios de fallo van al
Capítulo 5.

**Costo estimado.** Bajo a medio.

---

## 2. Laboratorio de experimentos en la interfaz

**Qué es.** Armar un lote (escenarios × semillas, como
`lotes/ejemplo.json`) desde la interfaz, correrlo y ver el progreso, la
tabla y las gráficas del resumen agregado.

**Cómo.** Corriendo literalmente `python main.py --batch <archivo>` en
un **subproceso**, nunca en un hilo del servidor: compartiría el
`random` global con la sesión en vivo y rompería la reproducibilidad.
Como es el mismo comando de la terminal, los resultados son idénticos
por construcción.

**Qué permite.** Generar los resultados del documento sin salir de la
interfaz, y mostrarlo en la sustentación.

**Qué toca.** Sólo `web/` (servidor y frontend). No cambia el modelo
ni las métricas.

**Para decidir.** Es útil, pero no agrega nada que la terminal no haga
ya (`--batch`). Vale la pena si se quiere mostrar la generación de
resultados en vivo durante la sustentación.

**Costo estimado.** Medio.

---

## 3. Ventana nativa opcional

**Qué es.** Abrir la interfaz en una ventana de escritorio propia
(con `pywebview`) en vez de una pestaña del navegador, con un lanzador
de escritorio. Si `pywebview` no está, se abre en el navegador como
ahora.

**Qué toca.** Agrega una **dependencia nueva** a `requirements.txt`
(`pywebview`, que en cada sistema operativo usa otro motor web), y el
encargo pide consultarlo antes.

**Para decidir.** Es sólo de presentación: la interfaz ya funciona
igual en el navegador. Los riesgos son que la instalación se complique
en la máquina de la sustentación y que se agregue una dependencia que
hay que mantener.

**Costo estimado.** Bajo, más el riesgo de instalación.

---

## Revisión del 3 de octubre (Linux)

**Verificación de la rama.**
- `venv/bin/python -m unittest discover -s tests`: 240 pruebas en
  verde. Se salta 1, `test_web_frontend.py`, porque busca el `jsc` de
  macOS y en Linux no está.
- Regresión de lotes: `lotes/ejemplo.json` y `lotes/movilidad.json`
  dan idéntico en `main` y en la rama (`corridas.csv` byte a byte,
  `resumen.json` sin las fechas).
- Lista de chequeo en el navegador: recorrida el mismo día en Chrome
  sobre Linux, sin nada que bloquee. Los resultados y los detalles
  encontrados están en `docs/interfaz_web.md`, sección 4.

**Hallazgo 1: `tiempo_reconvergencia_s` mide la partición física, no
la reconvergencia de BATMAN.** `resumen_corrida()`
(`analysis/metrics.py`) promedia la duración de los episodios en que la
malla de Gateways estuvo partida, calculada con `_union_find` sobre los
enlaces de radio. No mira las tablas de rutas. Con eventos programados
la métrica devolvería el dato de entrada: si un Gateway puente cae en
t₁ y vuelve en t₂, como los nodos caídos no se mueven, el episodio dura
t₂ − t₁. Así que la parte 1, tal como estaba planteada, **no** daría
una medida de reconvergencia.

**Hallazgo 2: después de recuperar un nodo, las rutas hacia él tardan
lo mismo que el nodo estuvo vivo antes de caer.**
`Simulation.recover_node()` (`sim/engine.py`) pone `_ogm_seq = 0`, y
`BatmanRouter.receive_ogm()` (`mesh/router.py`) descarta todo OGM con
una secuencia menor o igual a la última que vio de ese origen. Los
demás nodos ignoran los OGM del nodo recuperado hasta que su secuencia
supera la de antes de caer, y además no los reenvían.

Medido con `base`, `--static` y semilla 1:
- G2 cae en t = 60 s con la secuencia en 15 (un OGM cada 4 s) y vuelve
  en t = 90 s.
- Las rutas de G1, G3 y G4 hacia G2 siguen sin refrescarse hasta
  t ≈ 150 s (antigüedad de 70 s en t = 130). Es decir, unos 60 s, que
  es justo lo que G2 estuvo vivo antes de caer.
- Los `ALERT_OFF` llegan en 1 a 4 s, porque los beacons (`BCN`) llegan
  directo y no pasan por esa comprobación. Por eso el efecto no se ve
  en los eventos ni en los reportes, pero sí en la matriz de
  conocimiento de la interfaz (rutas obsoletas).

Los lotes actuales no recuperan nodos, así que sus resultados no se ven
afectados. Lo afectado es la tecla `G` de pygame y "recuperar" en la
web.

**Hallazgo 3: pywebview no se puede instalar en esta máquina.** El
venv es Python 3.14. El motor GTK de pywebview necesita compilar
PyGObject contra los *headers* de `gobject-introspection`, que no están
instalados, y no hay `sudo`. El motor Qt exigiría PyQt + QtWebEngine
(cientos de MB). Brave (Chromium) sí está instalado.

---

## Decisiones

Tomadas por XGallardoX el 2026-10-03, con el visto bueno de Jefferson
el mismo día. La parte 1 ya está implementada (ver "Estado de la parte
1", al final).

**1. Eventos `fail`/`recover` programables: sí, con estas condiciones.**

- *1a. Qué se llama reconvergencia.* Hay dos medidas distintas y se
  reportan las dos:
  - `tiempo_reconvergencia_s` se queda como está (mismos números, misma
    columna), pero en la documentación y en la tesis se describe como
    **duración de la partición física**.
  - Se agrega una métrica nueva, `tiempo_reconvergencia_rutas_s`.
    Arranca en el `RECOVER` o el `HEAL` y termina cuando todo par de
    Gateways vivos del mismo componente de radio tiene, en los dos
    sentidos, una ruta vigente: el `last_seen` **de la ruta**
    (`RouteEntry`, que sólo refrescan los OGM) dentro del `timeout`.
    (Al implementarla se quitó la condición "y el destino sin alerta":
    ver "Estado de la parte 1", ajuste 1.)
  - Ojo: la matriz de conocimiento y la tabla de rutas de la interfaz
    **no** usan hoy ese criterio. Miran el `last_seen` del vecino
    (`PeerInfo`), que también refrescan los beacons. Por eso, en la
    revisión del 3 de octubre, una ruta de G1 a G4 con 151 s sin
    refrescarse se mostraba como vigente (hallazgo 2). Al implementar
    la métrica, la interfaz debe pasar a usar el mismo criterio, para
    que lo que se ve y lo que se reporta coincidan.
  - La métrica nueva es aditiva: una columna más al final. Las columnas
    existentes deben salir idénticas en la regresión de lotes.
- *1b. Secuencia de OGM al recuperar.* `recover_node()` deja de
  reiniciar `_ogm_seq`: la recuperación modela un nodo que vuelve a la
  red, no un arranque en frío. Así la métrica de 1a mide el protocolo y
  no el artefacto del hallazgo 2.
  - `mesh/` no se toca.
  - El arranque en frío (secuencia desde 0 contra un router que no lo
    contempla) queda documentado como limitación conocida de
    `mesh/router.py` en `docs/arquitectura.md` y en
    `docs/interfaz_web.md` §5.
  - Esto cambia lo que pasa al recuperar un nodo con la tecla `G` de
    pygame y con "recuperar" en la web. Los lotes no cambian (se
    verifica con la regresión).
- *1c. Alcance.*
  - Sólo los tipos `fail` y `recover`, con la forma
    `{"type": ..., "node_id": ..., "t": ...}`, al lado de `wander`, en
    `.json` y en `.txt`.
  - Se aplican en el mismo punto del ciclo en que la web aplica las
    intervenciones (entre pasos), para que una sesión exportada como
    escenario reproduzca exactamente la corrida. Esto lleva una prueba
    de paridad.
  - "Exportar la sesión como escenario" sólo vale si las intervenciones
    fueron caer/recuperar. Si hubo mover, agregar, eliminar o cambiar
    parámetros, se sigue mostrando que no hay comando equivalente.
- *1d. Escenarios de fallo para el Capítulo 5:* se definen entre los
  dos al implementar la parte 1.

**2. Laboratorio de experimentos: sí, después de la parte 1.** Corre
`python main.py --batch` en un subproceso, como estaba planteado. Vale
más con la parte 1 hecha, porque permite lotes con fallos programados.

**3. Ventana nativa con pywebview: no** (hallazgo 3). Alternativa
opcional, sin dependencias, sólo si sobra tiempo: abrir la interfaz en
el modo aplicación de un navegador Chromium (`--app=URL`), que da una
ventana sin barra de navegador. Si no hay uno, se abre en el navegador
normal, como ahora.

**4. Merge de `feat/interfaz-web` a `main`: antes de la Fase 3**,
después de recorrer la lista de chequeo en un navegador.

**Orden:** lista de chequeo en el navegador → merge a `main` → parte 1
(1b, 1a, 1c) → parte 2 → parte 3 alternativa, si sobra tiempo.

---

## Estado de la parte 1 (2026-10-03)

La lista de chequeo se recorrió y `feat/interfaz-web` se mergeó a `main`
(fast-forward, subido). La parte 1 está implementada en la rama
`feat/fase3-eventos`, un commit por decisión:

- **1b** (`8be99ed`): `recover_node()` conserva la secuencia de OGM.
- **1a** (`c18f70f`): métrica `tiempo_reconvergencia_rutas_s`, y
  `f643acf`: la tabla de rutas y la matriz de la interfaz usan el mismo
  criterio (`analysis.metrics.ruta_vigente`).
- **1c** (`ad949db`): eventos `fail`/`recover` en el escenario (`.json`
  y `.txt`), aplicados por el motor; `cac7b12`: la web exporta una
  sesión con caídas y recuperaciones como `escenario_sesion.json` con su
  comando `--config`, y el editor maneja los eventos nuevos.
- Caso de ejemplo `escenarios/casos/puente.txt` (y `puente_corto.txt`),
  `lotes/fallos.json` y el caso 13 de la guía. **No** es la selección de
  escenarios del Capítulo 5 (1d sigue pendiente entre los dos).

Regresión: las columnas existentes de `lotes/ejemplo.json` y
`lotes/movilidad.json` dan idéntico; la única diferencia es la columna
nueva al final. Pruebas: 268 en verde (1 omitida, la de `jsc`).

**Dos ajustes respecto a lo decidido**, que salieron al implementar:

1. **La ruta vigente no mira las alertas.** Con "y el destino sin
   alerta", ningún episodio de `denso` con `repartir` se cerraba en
   200 s: `PeerInfo.in_alert` se contagia (cada OGM lleva la lista de
   caídos de quien lo emite y marca en alerta a esos nodos en todos los
   que lo reciben, aunque los oigan bien), y `FaultManager.failed` sólo
   se limpia con un beacon directo (hallazgo 4). Quedó sólo la
   antigüedad de la ruta, que es lo que mide la capa de enrutamiento;
   las alertas ya tienen sus propias métricas.
2. **Un disparador con un episodio abierto se suma a ese episodio.**
   Cuando vuelve un Gateway puente, el `RECOVER` y el `HEAL` que provoca
   medio paso después abrían dos episodios para un mismo hecho, y el
   promedio de la corrida salía con medio paso de menos.

**Números del caso de ejemplo** (`lotes/fallos.json`, 10 semillas):
con G2 caído 40 s, "tiempo de reconvergencia" da 40.0 ± 0.0 s (el dato
de entrada, como anticipaba el hallazgo 1) y la reconvergencia de rutas
14.8 ± 5.7 s. Con G2 caído 10 s, menos que el `timeout`, 10.0 ± 0.0 s
contra 1.6 ± 2.6 s. En `denso` con `repartir`, la reconvergencia de
rutas da 24.2 ± 17.5 s (7 de 10 corridas).

**Hallazgo 4: en el simulador, una alerta sobre un Gateway a varios
saltos no se apaga nunca.** `SimNode._drain_inbox` (réplica de
`MeshNode._handle_bcast`) sólo llama a `FaultManager.recover()` al
recibir un beacon directo. Un Gateway que sólo se oye a través de otros
(por OGM) queda en `fault.failed` hasta el final aunque sus rutas se
refresquen. En el caso `puente`, G1 y G3 se siguen creyendo caídos
después de que G2 vuelve. Afecta a "Alertas de gateway perdido" y a la
capa de detección, no a la reconvergencia de rutas. Es código del nodo
real: queda como decisión aparte, igual que el TQ.

**Aprobada y mergeada:** Jefferson dio el visto bueno a la parte 1 y a
los dos ajustes el 2026-10-03, y `feat/fase3-eventos` se mergeó a `main`
ese día.

**Pendiente:** 1d (qué escenarios de fallo van al Capítulo 5) y la
parte 2 (laboratorio de lotes). Ver la sección siguiente.

---

## Estado de las partes 2 y 3, y propuesta para 1d (2026-10-03)

Rama `feat/fase3-resto`.

- **Parte 2, laboratorio de experimentos: hecha.** Botón "⚗ Laboratorio"
  en la interfaz: arma un lote o carga uno de `lotes/`, lo corre con
  `python main.py --batch` en un subproceso y muestra el progreso, la
  tabla del resumen y una gráfica. Validación sólo de lectura (no
  consume `random`), topes de 300 corridas y 3600 s, cancelable.
  Probado que da lo mismo que la terminal. Detalle en
  `docs/interfaz_web.md`.
- **Parte 3, ventana propia: hecha con la alternativa decidida.**
  `--web --ventana` abre la interfaz en el modo `--app` de Chrome,
  Chromium, Brave, Edge o Vivaldi; si no hay ninguno, el navegador por
  defecto. Sin dependencias nuevas. No se hizo un lanzador `.desktop`:
  necesitaría rutas absolutas de cada máquina, y el comando ya alcanza.
- **Detalles de la revisión en el navegador: corregidos** la tilde de
  "intervenciónes", la barra superior que saltaba de línea, el texto
  que quedaba pegado en el compositor y el voseo. Queda uno: con nodos
  apilados las etiquetas se superponen.
- **1d, escenarios de fallo para el Capítulo 5: decidido** (D5 de
  `PLAN_SIGUIENTE.md`). `escenarios/fallos/`: un
  despliegue de cobertura (7 Gateway fijos en 3 pisos, 6 Nodos de
  usuario) con un Gateway redundante, un puente y un borde, y cuatro
  experimentos (caída de cada uno, con vuelta, y una cascada sin
  vuelta). `lotes/capitulo5_fallos.json` los corre con 10 semillas, y el
  caso 14 de la guía trae los números. Los tres puntos que quedaban
  abiertos se decidieron el 2026-10-03 (D3, D5 y D6 de
  `PLAN_SIGUIENTE.md`):
  1. **El medio del despliegue no es el por defecto** (alcance 12 m,
     `falloff` 0.5, atenuación por piso 0.8). Con el por defecto, la
     entrega cae a 0.32, hay 13.6 falsas alarmas en el control y la
     reconvergencia de rutas se cierra en 1 a 4 de 10 corridas. Hay que
     justificarlo en el documento (radios de menor potencia) o cambiarlo.
  2. **Nodos fijos.** Los fallos se estudian sin movilidad para aislar
     su efecto; la movilidad sigue siendo una decisión aparte.
  3. **La cobertura durante una caída no tiene métrica de resumen**:
     sólo "N alcanzables al final". Una cobertura media en el tiempo
     (promedio de `nodos_alcanzables`) mostraría cuánto se pierde
     mientras un Gateway está caído. Sería una métrica nueva: no se
     agregó sin acordarlo.
