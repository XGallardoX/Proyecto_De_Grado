# Estado del proyecto — Simulador BATMAN

> Para Jefferson: resumen de qué se hizo y qué falta. El trabajo va por
> etapas (esto no es la versión final de nada), se va a seguir
> completando. Detalle completo del plan en `PLAN_TRABAJO.md`, del
> análisis del repo madre en `ANALISIS_REPO_MADRE.md`.

Fecha: 2026-09-08

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
   el título definitivo y el nombre del asesor.

2. **Compilar el documento.** El estado del arte se escribió y se
   revisó de forma estática (entornos y llaves balanceados, tabla
   consistente, las 17 citas resuelven contra `referencias.bib`), pero
   **no se compiló**: esta máquina no tiene toolchain de LaTeX
   instalado. Falta una pasada por Overleaf, o instalar `texlive`, para
   confirmar que sale limpio.

3. **Pregunta abierta — framing del proyecto (necesita que la
   resuelvan entre los dos):** `register_found()`/`my_survivors`
   ("hallar" un nodo) es código muerto — nada llena `my_survivors`, la
   mecánica de detección por proximidad (`rango_deteccion`) nunca se
   portó al motor nuevo. Y el `main.py` nuevo ya no habla de "rescate"
   sino de "Red de Expansión de Cobertura". Antes de escribir la
   Parte 4 del documento de grado (problemática, objetivos) hay que
   decidir: ¿se implementa la detección y se mantiene el framing de
   rescate, o se reemplaza por una métrica de cobertura/conectividad?
   Esto cambia el objetivo general y los objetivos específicos del
   documento (ver sección 4.2–4.3 de `PLAN_TRABAJO.md`).

4. **Gaps menores conocidos:** no hay modo `--headless`/`--duracion`
   en `main.py` — existía en el `simulacion_batman_real.py` viejo y
   hay un intento de portarlo al final de `analysis/visualizer.py`,
   pero está roto (revienta con `TypeError` al primer uso, ver
   "Gaps conocidos" en `docs/arquitectura.md`). El modo gráfico
   (`pygame`) sí se probó manualmente y corre sin errores.

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
