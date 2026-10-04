# Estado del proyecto — Simulador BATMAN

> Para Jefferson: resumen de qué se hizo y qué falta. El trabajo va por
> etapas (esto no es la versión final de nada), se va a seguir
> completando. El plan de trabajo y el análisis del repo madre de agosto
> (`PLAN_TRABAJO.md`, `ANALISIS_REPO_MADRE.md`) ya no están en el repo;
> quedan en el historial de git (commit `7acf40e`).

Fecha: 2026-10-03

> **Fase 3 de la interfaz web: decidida el 2026-10-03 (XGallardoX, con
> el visto bueno de Jefferson); la parte 1 ya está hecha y en `main`.**
> Sigue la parte 2 (laboratorio de lotes) y falta acordar qué escenarios
> de fallo van al Capítulo 5. Eventos de fallo programables, con una
> métrica nueva de reconvergencia de rutas y sin reiniciar la secuencia
> de OGM al recuperar un nodo. Laboratorio de lotes sí, después.
> pywebview no. Los hallazgos, las decisiones y dos ajustes que salieron
> al implementar están en [`DECISIONES_FASE3.md`](DECISIONES_FASE3.md).
> La interfaz web (`feat/interfaz-web`) ya está en `main`.

---

## Hecho

**Merge del repo madre** (`jofsanchezci/Simulador_BATMAN`, rama `develop`)
— trajo `main.py` + los paquetes `mesh/`, `sim/`, `analysis/` (roles
renombrados `R`/`S` → `G`/`N` = Gateway/Nodo).

**Bugs de la migración R/S → G/N corregidos:**
- Drenaje de batería y `register_found()` seguían comparando contra los
  roles viejos (`'R'`/`'S'`), que ya no existen — nunca se cumplían.
- `requirements.txt` desactualizado (`pandas`/`requests` sin usar,
  `pygame` sin versión) → corregido a `numpy`, `matplotlib`, `pygame-ce`.
- `.gitignore` heredado ignoraba `*.json`/`*.txt`/`*.csv` en general
  (pensado para los reportes generados) y de paso iba a ignorar
  silenciosamente los escenarios nuevos → acotado al patrón real de los
  reportes (`reporte_*.csv/json/txt`).

**Parte 1 del plan — config de escenario por JSON:**
- `sim/config_loader.py`: carga y valida un archivo de escenario
  (ids únicos, rol `G`/`N`, mínimo un gateway, coordenadas dentro del
  edificio, batería inicial opcional, evento `wander` opcional).
- `main.py`: flags `--config archivo.json` y `--escenario <nombre>`
  (este último ahora es un atajo real a `escenarios/<nombre>.json` —
  antes era un flag que no hacía nada).
- Los 5 escenarios originales del repo madre migrados a
  `escenarios/{base,colapso_progresivo,particion,rescatista_perdido,denso}.json`,
  con fidelidad completa (baterías escalonadas, rango de radio
  reducido en `particion`, el nodo que se pierde en
  `rescatista_perdido`).

**Parte 2 del plan — pruebas:**
- `tests/` con `unittest` (sin dependencias nuevas): 40 tests —
  validación de config, `RadioMedium.reliability()`, `_build_world()`
  con 2/3/10/20 nodos, el parser `.txt`, regresión de los bugs
  corregidos y de los 5 escenarios migrados. Se corren con:
  ```bash
  python -m unittest discover -s tests -v
  ```

Todo esto ya está en `main` (commits `0348693`, `6a41861`, `3d6fb5c`).

**Parte 3 del plan — documentación técnica:**
- `README.md` reescrito: instalación, todas las flags de `main.py`
  explicadas, controles de la ventana en vivo, y qué contiene cada
  reporte (`analisis_red.png`, `reporte.csv/json/txt`). Se quitó la
  sección de despliegue en hardware real (`mesh_cli.py`,
  `setup_mesh.sh`, systemd, etc.) porque documentaba archivos que ya
  no existen en el repo — quedó como huella en el historial de git,
  no en el README activo.
- `docs/arquitectura.md`: explica las 3 capas (`mesh/` protocolo real,
  `sim/` puente de simulación, `analysis/` métricas/visualización) y
  por qué el TQ que se ve en pantalla lo calcula el `BatmanRouter`
  real y no una maqueta. Documenta también qué partes de `mesh/`
  (memoria distribuida, scheduler, API de control) el simulador no
  usa, y dos gaps conocidos (headless roto en `visualizer.py`,
  `register_found()`/`my_survivors` muerto).
- De paso (pedido aparte, no parte del plan original): los reportes y
  el PNG de análisis ahora se agrupan en
  `reportes/<escenario>_<fecha_hora>/` por ejecución en vez de quedar
  sueltos en la raíz del repo.

**Ajustes posteriores (8 de septiembre):**
- Flag `--static` (`move_speed=0`): los nodos quedan fijos en su
  posición inicial. Sin ella, los Gateway se comportan como rescatistas
  y persiguen al Nodo de usuario más cercano no encontrado, por lo que
  convergen entre sí — explicado en `docs/movimiento_nodos.md`.
- `--config` acepta escenarios en `.txt` además de `.json`, con la
  misma validación y los mismos mensajes de error (ver README).

**Track B — arranque del documento de grado:**
- `Plantilla/` entra al repo (antes estaba entera sin trackear), con un
  `.gitignore` propio para los artefactos de compilación: se versionan
  las fuentes `.tex`/`.bib`/`.cls` y las imágenes, no los `.aux`/`.log`/
  `.toc`/`.synctex.gz` ni el `main.pdf` generado.
- Capítulo 2 pasa de "Capítulo 2" genérico a **Estado del arte**:
  simuladores de propósito general (ns-3, OMNeT++/INET, GloMoSim), los
  de redes descentralizadas en sus tres acepciones (MANET/mesh, P2P y
  consenso distribuido), el eje simulación/emulación con tabla
  comparativa, B.A.T.M.A.N. en la literatura, y la brecha que justifica
  el proyecto.
- `referencias.bib` pasa de 5 a 19 entradas (14 nuevas, verificadas
  contra la fuente primaria). De paso desaparecen las 8 citas rotas que
  traía la plantilla y que habrían salido como `[?]` al compilar.

**Simulador, versión de cierre (18 de septiembre):**
- **Framing decidido: Red de Expansión de Cobertura.** Se retiró el
  mecanismo muerto de "hallar supervivientes" (`register_found`,
  `found_ids`, `my_survivors`, `rango_deteccion`) y el vocabulario R/S
  que quedaba en código, logs, ventana y reportes. Ojo, cambian nombres:
  las columnas de `reporte.csv`/`.json` pasan a `gateways_activos`,
  `nodos_activos`, `nodos_alcanzables` y `componentes_malla` (ya no
  existe `supervivientes_hallados_acumulado`), y la clave
  `battery_drain_surv` pasa a `battery_drain_nodo` (la vieja se sigue
  aceptando en los escenarios).
- Se borró el prototipo monolítico (`batman_node.py`,
  `simulacion_batman_real.py`); queda en el historial de git.
- **Sin ventana:** `--headless`, `--duracion`, `--seed` (misma semilla =
  misma corrida) e `--inspect` en `main.py`.
- **Lotes:** `python main.py --batch lotes/ejemplo.json` corre
  escenarios × semillas y resume cada métrica por escenario (media ±
  desviación estándar). Es lo que conviene usar para los resultados del
  documento (Cap. 5). Formato y salida en el README.
- Ventana: se arreglaron dos caídas (tecla `M` al mandar un mensaje y
  tecla `S`), el diálogo de mensajes usa ahora `G1>N2` (antes `R1>R3`,
  que además apuntaba a nodos N) y `A` ya no repite etiquetas.
- El evento `HEAL` y la métrica de reconvergencia ya no cuentan como
  reunificación que la partición desaparezca porque se cayó el Gateway
  aislado (pasaba en `colapso_progresivo`).
- Pruebas: de 40 a 144 (`SimNode`, reportes, modos sin ventana, lotes,
  movilidad, y que los escenarios y lotes del repo sigan cargando).
- **Movilidad `repartir` (opcional):** con la movilidad de siempre
  (`seguir`), cada Gateway va al Nodo de usuario más cercano, y en
  `denso` los 8 terminan encima del mismo (3.2 de 6 nodos cubiertos).
  Con `--movilidad repartir` (o `"movilidad": "repartir"` en el
  escenario o en el lote) va un Gateway por Nodo de usuario: se cubren
  todos, pero la malla de Gateways se parte y la entrega del radio cae
  casi a la mitad. `seguir` sigue siendo el valor por defecto, y se
  verificó que todos los resultados de antes salen idénticos.
  `lotes/movilidad.json` compara los dos modos en los 5 escenarios
  (caso 11 de la guía).
- **Guía de ejecución** en `docs/guia_ejecucion.md`: cómo correr cada
  escenario y 10 casos (tumbar un Gateway, mensajes, ruta multi-salto,
  escenario propio, lote de referencia, movilidad contra nodos fijos,
  barridos de alcance y de timeout), con el comando y el resultado
  esperado. Los archivos de esos casos están en `escenarios/casos/` y
  `lotes/casos.json`.

**Orden del repo (18 de septiembre):** este documento y `CLAUDE.md`
pasan a la carpeta `contexto/`. `PLAN_TRABAJO.md` y
`ANALISIS_REPO_MADRE.md` salen del repo y quedan en `.gitignore` (eran
documentos de trabajo de agosto; siguen en el historial de git).

**Interfaz web, Fase 1 — núcleo con paridad (30 de septiembre):**
arranca la "versión de escritorio" pedida en
`prompt_version_escritorio.md` (ver ahí el encargo completo, por
fases): una interfaz gráfica en el navegador, servida por un servidor
HTTP local (`http.server` + Server-Sent Events, sólo biblioteca
estándar), que corre **el mismo núcleo** que la terminal —
`main.construir_simulacion()`, `sim/`, `mesh/`, `analysis/`— y da los
mismos resultados. Rama `feat/interfaz-web`.

- Paquete nuevo `web/`: `estado.py` (funciones puras `Simulation ->
  dict` serializable: `frame`, `nodo_detalle`, `series`,
  `inspector_texto`), `sesion.py` (`Sesion`: dueña de la `Simulation`
  en el servidor, un lock protege todo acceso, un hilo de fondo avanza
  al mismo ritmo que pygame —9 s simulados/s real a 1×— y publica
  frames a ~18 Hz) y `servidor.py` (`ThreadingHTTPServer` + rutas
  `/api/*` + estáticos). Frontend sin build: HTML/CSS/JS con módulos ES
  nativos, canvas 2D para el mapa.
- `main.py` gana `--web`, `--puerto` y `--no-abrir`; no se combina con
  `--headless`/`--inspect`/`--batch`/`--duracion`.
- Paridad verificada con pruebas: misma semilla ⇒ misma serie del
  `Recorder` y mismo `resumen_corrida()` que `correr()` (`base`,
  `denso` con `repartir`, `static`, modo aleatorio). La semilla
  automática de una sesión sin `--seed` sale de `secrets`, nunca de
  `random`, para no afectar la reproducibilidad.
- Cubre la tabla de paridad de teclado/controles de pygame (pausa, un
  paso, velocidad 0.25×-8×/máxima, reiniciar —acá sí refija la
  semilla, a diferencia de la tecla `R`—, exportar, terminar sesión,
  selección de nodo, caer/recuperar/añadir/eliminar, mensajes,
  inspector, parámetros `rango_comm`/`falloff`, cambiar de escenario).
- Exportar deja los mismos `reporte.csv/json/txt` de siempre más
  `sesion_web.json` (configuración, semilla, intervenciones y el
  comando de terminal equivalente, válido sólo si la sesión no tuvo
  intervenciones).
- 48 pruebas nuevas (`tests/test_web_*.py`: estado, sesión+paridad,
  servidor HTTP/SSE con *path traversal* rechazado, integración de
  `--web` en la CLI) — 192 en total. Regresión de `lotes/ejemplo.json`
  y `lotes/movilidad.json` contra la línea base de antes de esta fase:
  idéntica.
- Verificado contra el proceso real (sin navegador disponible en este
  entorno: no hay Node.js ni forma de instalar un Chromium
  automatizable): SSE entrega ~16-18 frames/s, el reloj de la
  simulación avanza al ritmo esperado, los comandos mutan el estado, y
  "terminar" exporta y apaga el servidor sin dejarlo colgado. Falta la
  verificación visual en un navegador real — lista de chequeo manual en
  `docs/interfaz_web.md` sección 4.
- Documentación: sección nueva en el README ("Versión de escritorio"),
  la capa `web/` en `docs/arquitectura.md`, `docs/interfaz_web.md`
  nuevo (API, esquema del frame, tabla funcionalidad → capacidad → vacío
  de `sec:brecha` que atiende) y un caso web agregado al caso 1 de
  `docs/guia_ejecucion.md`.

**Interfaz web, Fase 2 — interactiva, con lente de descentralización
(30 de septiembre):** misma rama `feat/interfaz-web`. Detalle completo
en `docs/interfaz_web.md`; cómo se usa, en el README; dos casos en la
guía (el 1 en la web y el 12, "ver como este nodo").

- **Cambios aditivos al núcleo** (commit propio, `afa83bb`):
  `Simulation.mover_nodo()` y `add_node(role, x, y)` (sin argumentos
  consume `random` igual que antes, probado), `sim.radio.fiabilidad()`
  (la fórmula de `reliability()` extraída a una función pura, idéntica,
  probado), `_Packet` con tipo/origen/TTL, contadores de uso del código
  real en `SimNode` y `config_loader.validar_escenario()`. `mesh/` no se
  tocó. Regresión de los dos lotes: idéntica.
- **Interacción:** arrastrar nodos, agregar un Gateway o un Nodo de
  usuario con un clic, menú contextual, tooltips, capas, parámetros en
  vivo (12, cada uno verificado contra el código que lo lee en cada
  paso) con su valor por defecto y "restaurar", los 6 paneles de la
  figura en vivo, línea de tiempo de eventos, compositor de mensajes
  con animación salto a salto, semilla editable, pantalla de inicio,
  modo presentación, tema oscuro.
- **Lente de descentralización:** "ver como este nodo", matriz de
  conocimiento N×N con indicador de convergencia (sólo visualización,
  no va a los reportes), anillos de vigilancia contra el `timeout`,
  OGM de un origen con el TTL bajando, envolventes de partición, panel
  "qué es real y qué es modelo".
- **Editor de escenarios:** guarda en `escenarios/` con el formato de
  `--config` (probado: lo guardado corre con `--config` y `--headless`),
  sin pisar los predefinidos. Mapa de cobertura incluido (lo opcional
  del encargo), sobre la refactorización pura de `reliability()`.
- **Problemas encontrados y corregidos en el camino:** con 50 nodos el
  frame pesaba 1.4 MB por los miles de paquetes en vuelo (ahora 64 KB:
  muestra de 300 y los OGM de un origen por su propio endpoint); el
  navegador acumulaba todas las muestras sin tope en sesiones largas.
  También se completó lo que había faltado de la Fase 1 (interpolación
  a 60 fps, menú contextual, compositor con clic, tooltips, capas,
  pantalla de inicio, modo presentación, semilla editable).
- **Pruebas:** 240 (de 192). Nueva `tests/test_web_frontend.py`, que
  ejecuta el JavaScript del frontend con datos reales en
  JavaScriptCore (viene con macOS) y falla si un `NaN`/`undefined` llega
  al dibujo o al HTML. Sigue sin haber verificación en un navegador real
  (no hay uno automatizable en este entorno): lista de chequeo en
  `docs/interfaz_web.md`, sección 4.
- **Pendiente:**
  - ~~Mirar la interfaz en un navegador.~~ Hecho el 2026-10-03 en
    Chrome sobre Linux. Resultados y detalles menores en
    `docs/interfaz_web.md`, sección 4.
  - ~~Fase 3, a decidir entre los dos autores.~~ Decidida el
    2026-10-03 (ver [`DECISIONES_FASE3.md`](DECISIONES_FASE3.md)).
  - ~~Mergear `feat/interfaz-web` a `main`.~~ Hecho el 2026-10-03.

**Fase 3, parte 1 — fallos programables y reconvergencia de rutas
(3 de octubre):** rama `feat/fase3-eventos`, aprobada por Jefferson y
mergeada a `main` el mismo día. Detalle,
commits y números en [`DECISIONES_FASE3.md`](DECISIONES_FASE3.md),
"Estado de la parte 1".

- **Eventos `fail`/`recover` en el escenario**
  (`{"type": "fail", "node_id": 2, "t": 60}`, o `fail 2 60` en `.txt`).
  El motor los aplica entre dos pasos, igual que la interfaz web aplica
  una intervención: una caída programada da la misma corrida que la
  misma caída a mano. Sirven en `--headless` y `--batch`.
- **Recuperar un nodo conserva su secuencia de OGM.** Antes volvía a 0,
  y los demás ignoraban sus OGM hasta superar la secuencia de antes de
  caer: las rutas hacia él tardaban tanto como había estado vivo.
- **Métrica nueva: "Reconvergencia de rutas BATMAN"**
  (`tiempo_reconvergencia_rutas_s`, una columna más al final de los
  reportes de lote). Mide desde que vuelve un Gateway o se reunifica la
  malla hasta que todos los Gateways conectados tienen rutas frescas
  entre sí. El "tiempo de reconvergencia" de antes queda igual, pero
  ahora se documenta como lo que es: la duración de la partición física.
- **Interfaz web:** la tabla de rutas y la matriz usan el mismo criterio
  de ruta vigente que la métrica. Una sesión cuyas únicas intervenciones
  son caer y recuperar se exporta como `escenario_sesion.json` con un
  comando `--config` que la reproduce. El editor crea y muestra caídas y
  recuperaciones.
- **Caso de ejemplo:** `escenarios/casos/puente.txt` (un Gateway puente
  que cae y vuelve), `lotes/fallos.json` y el caso 13 de la guía.
- Pruebas: 268 (de 240), en `tests/test_fase3.py`. La regresión de
  lotes da idéntico en todas las columnas existentes.

---

## Falta

1. **Track B — resto del documento de grado.** Ya está el Capítulo 2
   (Estado del arte). Siguen en blanco, con el relleno instructivo de
   la plantilla: introducción (Cap0), planteamiento y objetivos (Cap1),
   metodología (Cap3), desarrollo (Cap4), resultados (Cap5) y
   conclusiones (Cap9). La portada sigue con los placeholders de la
   plantilla — `\title`, `\author`, `\advisor` y el `pdfauthor` del
   `hyperref` (que todavía dice `MIA-D.Martinez`) — porque hacen falta
   el título definitivo y el nombre del asesor. Además, con el framing
   ya decidido (punto 3), la sección "Redes ad-hoc en escenarios de
   emergencia" del Estado del arte y los objetivos que se habían
   propuesto en el plan de trabajo (§4.2–4.3 de `PLAN_TRABAJO.md`, ya
   fuera del repo) siguen hablando de búsqueda y rescate: hay que
   llevarlos a la Red de Expansión de Cobertura.

2. ~~Compilar el documento.~~ **Hecho.** Se instaló TeX Live en
   `~/texlive/2026` (sin root) y el documento compila limpio:
   `pdflatex` + `bibtex` + 2 pasadas → `main.pdf`, 42 páginas, sin
   citas ni referencias sin resolver. El estado del arte queda en las
   páginas 27–32 (Capítulo 3) y la tabla comparativa como Tabla 3.1.
   Para compilar:
   ```bash
   export PATH=~/texlive/2026/bin/x86_64-linux:$PATH
   cd Plantilla && pdflatex main && bibtex main && pdflatex main && pdflatex main
   ```
   Los únicos avisos de `Overfull \hbox` grandes (82.5pt) vienen del
   banner de capítulo de la plantilla (`\rule{18.5cm}` contra un
   `textwidth` de 15.6cm) y salen en los 8 capítulos por igual — son
   de la plantilla, no del contenido nuevo.

3. ~~Pregunta abierta — framing del proyecto.~~ **Resuelta:** Red de
   Expansión de Cobertura (evaluar la resiliencia y la conectividad de
   la malla ante fallos de nodos). El código ya está alineado (ver
   "Hecho"); falta el documento (punto 1).

4. **Decisiones abiertas sobre las métricas** (salieron al correr el
   primer lote; detalle en "Limitaciones conocidas" de
   `docs/arquitectura.md`):
   - **El TQ vale siempre 1.0.** `BatmanRouter` (`mesh/router.py`)
     nunca registra en su ventana deslizante los OGMs que se pierden,
     así que el "TQ medio" mide cuánto tiempo hubo rutas, no la calidad
     de los enlaces (el prototipo original hacía lo mismo). Corregirlo
     es tocar el protocolo "real" (también lo usa `mesh/node.py`) y
     cambia todos los resultados. ¿Se corrige, o se reporta así y la
     calidad del medio se mide con la tasa de entrega del radio?
   - ~~**La reconvergencia no se observa.**~~ En camino (Fase 3, parte
     1): ya hay eventos de caída/recuperación programables y una métrica
     de reconvergencia de rutas. Falta decidir entre los dos qué
     escenarios de fallo van al Capítulo 5 (decisión 1d). El caso
     `puente` de la guía es sólo un ejemplo.
   - **Una alerta sobre un Gateway a varios saltos no se apaga nunca**
     (hallazgo 4 de `DECISIONES_FASE3.md`): `FaultManager` sólo la borra
     con un beacon directo. Es código del nodo real, como el TQ.
   - **¿Qué movilidad usar en el documento?** `seguir` mantiene la malla
     unida pero cubre poco; `repartir` cubre todo pero la parte (ver
     caso 11 de la guía). Se pueden reportar las dos como comparación,
     o diseñar un tercer modo que reparta sin partir la malla.
   - En modo `-n`/`-g` desde la línea de comandos, `battery_drain` vale
     0.02 en vez del 0.030 por defecto (viene del repo madre, commit
     `bf98d2f`): confirmar si es a propósito.

---

## Cronograma original (del plan de trabajo de agosto, §5)

| Semana | Track A | Track B |
|---|---|---|
| 1 | Esquema JSON + migración escenarios | Problemática + objetivos |
| 2 | Refactor `_build_world`, geometría a instancia | Marco teórico (Cap. 2) |
| 3 | Pruebas, ajustes de UI | Metodología (Cap. 3) |
| 4 | README + `docs/arquitectura.md` | Desarrollo + resultados (Cap. 4–5) |

Semanas 1, 3 y 4 de Track A ya están cubiertas (esquema/migración,
pruebas y documentación); semana 2 (refactor de `_build_world`) no se
verificó puntualmente en esta revisión. De Track B ya está el marco
teórico / estado del arte (Cap. 2, semana 2); falta problemática y
objetivos (semana 1), metodología (semana 3) y desarrollo/resultados
(semana 4).
