# Estado del proyecto — Simulador BATMAN

> Para Jefferson: resumen de qué se hizo y qué falta. El trabajo va por
> etapas (esto no es la versión final de nada), se va a seguir
> completando. Detalle completo del plan en `PLAN_TRABAJO.md`, del
> análisis del repo madre en `ANALISIS_REPO_MADRE.md`.

Fecha: 2026-09-18

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
- Pruebas: de 40 a 130 (`SimNode`, reportes, modos sin ventana, lotes).

`ANALISIS_REPO_MADRE.md` y `PLAN_TRABAJO.md` ya están commiteados —
antes existían sólo en la máquina local y por eso este documento los
daba por perdidos.

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
   emergencia" del Estado del arte y los objetivos propuestos en
   `PLAN_TRABAJO.md` (4.2–4.3) siguen hablando de búsqueda y rescate:
   hay que llevarlos a la Red de Expansión de Cobertura.

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
   - **La reconvergencia no se observa.** Con la movilidad actual,
     ninguna partición se reunificó en las 50 corridas de los 5
     escenarios (`particion` arranca partida y sigue así; en
     `rescatista_perdido` el Gateway que se aleja no vuelve). Para
     medirla hacen falta escenarios donde la partición se deshaga, o
     eventos de caída/recuperación programables en el escenario (hoy
     la caída y recuperación manual, teclas `F`/`G`, sólo existen en la
     ventana).
   - En modo `-n`/`-g` desde la línea de comandos, `battery_drain` vale
     0.02 en vez del 0.030 por defecto (viene del repo madre, commit
     `bf98d2f`): confirmar si es a propósito.

---

## Cronograma original (referencia, `PLAN_TRABAJO.md` §5)

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
