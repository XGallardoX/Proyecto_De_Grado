# Plan de trabajo — Simulador de malla BATMAN + documento de grado

> Documento de trabajo para los dos. Resume cómo abordar el encargo:
> rediseñar el simulador para que acepte cualquier número de nodos desde
> un archivo de configuración, y armar la documentación del proyecto de
> grado sobre la plantilla ya presente en el repositorio. **No se ha
> tocado ni ejecutado ningún código todavía** — esto es la hoja de ruta
> para acordarla antes de empezar.

- **Track A** — Rediseño del simulador
- **Track B** — Documento de grado

---

## 0. Diagnóstico del código actual

`batman_node.py` es el protocolo real (`BatmanRouter`, `PeerInfo`,
`RouteEntry`, `FaultManager`, `DistributedScheduler`,
`DistributedMemory`) — puro stdlib, no hay que tocarlo.
`simulacion_batman_real.py` lo envuelve en `SimNode` y sustituye los
sockets por un `RadioMedium` que modela pérdida de paquetes por
distancia y piso. Ahí está lo que hay que resolver:

**Hallazgo 1 — nodos fijos en código.**
`Simulation._build_world()` (líneas 523–546) define los 5 escenarios
(`base`, `colapso_progresivo`, `particion`, `rescatista_perdido`,
`denso`) como listas de tuplas `(id, x, y, piso)` escritas a mano en el
código. Añadir o mover un nodo hoy exige editar el script.

**Hallazgo 2 — geometría y parámetros globales.**
El edificio (`ANCHO`, `ALTO`, `PISO_H`, `N_PISOS`, `STAIR_XY`) y los
valores por defecto del medio (`DEFAULTS`) son constantes de módulo,
no de instancia. El CLI y las teclas en caliente ya permiten ajustar
cosas como `rango_comm` o `timeout`, pero no la lista de nodos ni la
geometría.

**Hallazgo 3 — límite menor en la UI.**
Las teclas `1`–`9` para seleccionar rescatista sólo cubren 9 nodos
(línea ~1713); con `TAB`, flechas o clic ya funciona cualquier
cantidad. Hay que ampliarlo o documentarlo como límite conocido.

**Hallazgo 4 — dependencias.**
`requirements.txt` no incluye `matplotlib` (se usa para el PNG de
análisis) y sí fija `pandas==1.5.2` y `requests==2.28.1`, que no se
usan en ningún `.py` del repo y además no compilan en Python 3.14. Ya
lo resolvimos en el entorno local (versiones actuales +
`pygame-ce`); falta reflejarlo en el archivo del repo.

---

## 1. Rediseño del simulador *(Track A)*

> **Estado (2026-08-26):** 1.1/1.2/1.3 implementados sobre `sim/engine.py`
> (base traída de `develop` del repo madre, roles `G`/`N`) —
> `sim/config_loader.py` valida y carga el JSON, `--config`/`--escenario`
> en `main.py` (`--escenario` ahora es un atajo real a
> `escenarios/<nombre>.json`, ya no está inerte — bug #2 cerrado),
> `_build_world()` usa los nodos explícitos si vienen del config. Los 5
> escenarios del repo madre (`base`, `colapso_progresivo`, `particion`,
> `rescatista_perdido`, `denso`) están migrados a `escenarios/*.json`
> con mapeo directo R→G/S→N, incluida la fidelidad de baterías
> escalonadas (`battery` por nodo) y el evento `wander` del rescatista
> perdido (nueva sección `events` del esquema). Parte 2 (pruebas) cubierta
> con `tests/` (`unittest`, sin pygame/display) — ver ahí para detalle.
> Sigue abierta la pregunta de framing: el `ANALISIS_REPO_MADRE.md`
> marcó que `register_found`/`my_survivors` ("hallar" un nodo) no está
> conectado a ninguna mecánica de proximidad en el código nuevo —
> decidir si se implementa o se reemplaza por una métrica de cobertura
> antes de construir la Parte 4 del documento de grado sobre esa base.

**Meta:** número y ubicación de nodos arbitrarios, y el escenario
completo (nodos, edificio, medio, protocolo) definido en un archivo
externo — sin editar `simulacion_batman_real.py` para crear un caso
nuevo.

### 1.1 Formato del archivo de escenario

JSON (ya se usa `json` en `batman_node.py`, no suma una dependencia
nueva). Esquema propuesto:

```json
{
  "name": "dos_nodos",
  "building": { "ancho": 40, "alto": 30, "piso_h": 10, "n_pisos": 3,
                "stair_xy": [20, 15], "debris_count": 10 },
  "medium":   { "rango_comm": 16, "falloff": 0.85, "floor_atten": 0.55 },
  "protocol": { "timeout": 30, "beacon_cada": 2, "batman_cada": 4 },
  "nodes": [
    { "id": 1,   "role": "R", "x": 7,  "y": 27, "piso": 3 },
    { "id": 2,   "role": "R", "x": 11, "y": 27, "piso": 3 },
    { "id": 101, "role": "S", "x": 34, "y": 3,  "piso": 1 }
  ],
  "events": []
}
```

Validación al cargar: ids únicos, `role` en `{"R","S"}`, coordenadas
dentro del edificio, mínimo un rescatista. Errores con mensaje claro,
no `assert` silencioso.

### 1.2 Cambios en el código

- Nuevo flag `--config archivo.json` en el `argparse`, alternativo a
  `--escenario`.
- `_build_world()` deja el bloque `if esc == 'base': R = [...]` e
  itera `config["nodes"]` para instanciar cada `SimNode`.
- `ANCHO`, `ALTO`, `PISO_H`, `N_PISOS`, `STAIR_XY` pasan de constantes
  de módulo a atributos de `Simulation`, leídos desde
  `config["building"]` (con los valores actuales como default si el
  campo falta).
- `_init_obstacles` toma `debris_count` y una semilla del config en
  vez del diccionario fijo por nombre de escenario.
- Los eventos especiales de hoy (el `wanderer` de
  `rescatista_perdido`, las baterías escalonadas de
  `colapso_progresivo`) se generalizan a la lista `events` del
  config, interpretada por tipo.
- UI: ampliar o documentar el límite de las teclas 1–9 (hallazgo 3);
  confirmar que los paneles laterales no rompen su layout con muchos
  nodos.

### 1.3 Compatibilidad hacia atrás

Migrar los 5 escenarios actuales a `escenarios/*.json` generados desde
el código de hoy, para que `--escenario base` siga funcionando como
atajo a `--config escenarios/base.json`.

---

## 2. Pruebas *(Track A)*

> **Estado (2026-08-26):** implementado en `tests/` con `unittest`
> (stdlib, sin dependencias nuevas) — `python -m unittest discover -s
> tests -v`, 32 tests, todos verdes. Cubre carga/validación de config,
> `RadioMedium.reliability()`, `_build_world()` con 2/3/10/20 nodos, y
> regresión de los 5 escenarios migrados (1.3) construyendo la
> `Simulation` directamente (sin `Visualizer`/pygame, así no depende de
> tener pantalla). **No implementado:** el humo vía `--headless
> --duracion 10` de la lista original no aplica tal cual — ese flag no
> existe en el `main.py` nuevo (viene de la Parte 3, doc técnica
> pendiente); la prueba manual del modo gráfico tampoco se pudo correr
> en este entorno por falta de display.

- Carga/validación de config: casos válidos e inválidos (ids
  duplicados, rol inválido, coordenadas fuera del edificio).
- `RadioMedium.reliability()` con distancias y diferencias de piso
  conocidas.
- `_build_world()` con configs de 2, 3, 10 y 20 nodos: verificar que
  se crean exactamente los nodos, roles y posiciones esperados.
- Humo: `--headless --duracion 10` sobre un config nuevo, sin
  excepciones, con PNG generado.
- Regresión: correr los 5 escenarios migrados en headless y comparar
  métricas clave contra el comportamiento actual (rescatistas vivos
  al final, hallados) para confirmar que el refactor no cambió el
  protocolo.
- Manual: abrir el modo gráfico con 2 nodos y con 15+, confirmar que
  selección (TAB/clic/números) y HUD siguen siendo usables.

---

## 3. Documentación de funcionamiento *(Track A)*

- `README.md`: sección "Formato de archivo de escenario" con el
  esquema campo por campo y un ejemplo mínimo de 2 nodos.
- `docs/arquitectura.md`: las tres capas del sistema — protocolo real
  (`batman_node.py`) / puente de simulación (`SimNode`,
  `RadioMedium`) / visualización y análisis — y por qué el TQ que se
  ve es real y no una maqueta.
- Guía corta de cómo se procesa un archivo de escenario, desde que se
  lee hasta que existen los `SimNode`.

---

## 4. Documento de grado *(Track B)*

Sobre la plantilla ya presente en `Plantilla/` (clase `MIA-USA.cls`,
orquestada desde `main.tex`). Hoy los capítulos están en blanco,
numerados genéricos ("Capítulo 1"…"Capítulo 5"); hay que renombrarlos
y llenarlos.

### 4.1 Problemática desde la literatura

Líneas a rastrear en `Bibliography/referencias.bib`: redes ad-hoc en
escenarios de rescate/desastre, el protocolo B.A.T.M.A.N. y sus
variantes, y la brecha entre simuladores de MANET habituales (ns-3,
OMNeT++, que *reimplementan* el protocolo como maqueta) frente a
ejecutar el código real de producción en la simulación — que es
exactamente lo que hace `simulacion_batman_real.py` hoy. Esa brecha es
la justificación natural del proyecto.

### 4.2 Objetivo general *(propuesta a validar)*

> Diseñar e implementar un simulador reconfigurable de redes ad-hoc
> con el protocolo B.A.T.M.A.N. real, que permita evaluar la
> resiliencia de la malla ante fallos de nodos en escenarios de
> búsqueda y rescate.

### 4.3 Objetivos específicos *(propuesta, 4)*

1. **Caracterizar el problema desde la literatura.** Identificar, a
   partir de trabajos previos, los requisitos de comunicación y
   tolerancia a fallos de redes ad-hoc en operaciones de rescate.
2. **Rediseñar el simulador para nodos configurables.** Extender
   `simulacion_batman_real.py` para aceptar número y ubicación
   arbitrarios de nodos mediante archivos de configuración externos.
3. **Implementar y validar el comportamiento del protocolo.**
   Verificar mediante pruebas que el enrutamiento BATMAN real (TQ,
   reconvergencia, detección de fallos) se mantiene correcto bajo el
   nuevo esquema configurable.
4. **Evaluar el desempeño de la malla.** Medir TQ, tiempos de
   reconvergencia y de detección de fallos en escenarios generados a
   partir de configuraciones variables, y documentar los resultados.

Estos cuatro objetivos calzan 1 a 1 con las partes 1–3 de este plan
más el trabajo de literatura — conviene revisarlos juntos antes de
escribirlos en el documento final.

### 4.4 Mapa de la plantilla a llenar

| Sección | Archivo | Contenido |
|---|---|---|
| Introducción | `MainMatter/Cap0/M01-Introduction.tex` | Contexto, problemática y alcance del simulador |
| Capítulo 1 → Planteamiento y objetivos | `MainMatter/Cap1/M02-Chapter1.tex` | Problema (4.1), objetivo general y los 4 específicos (4.2–4.3) |
| Capítulo 2 → Marco teórico | `MainMatter/Cap2/M03-Chapter2.tex` | BATMAN, MANET, simuladores existentes, citas de `referencias.bib` |
| Capítulo 3 → Metodología | `MainMatter/Cap3/M04-Chapter3.tex` | Diseño del esquema de configuración y plan de pruebas (Partes 1–2) |
| Capítulo 4 → Desarrollo | `MainMatter/Cap4/M05-Chapter4.tex` | Implementación del rediseño, con capturas de los escenarios nuevos |
| Capítulo 5 → Resultados | `MainMatter/Cap5/M06-Chapter5.tex` | Métricas de TQ/reconvergencia de la evaluación (objetivo 4) |
| Conclusiones | `MainMatter/Cap9/M10-Conclusiones.tex` | Ya trae las secciones "Conclusiones" y "Recomendaciones" listas |
| Front matter | `FrontMatter/F01…F06` | Aprobación, dedicatoria, agradecimientos, resumen, símbolos, glosario |

---

## 5. Cronograma sugerido *(ambos tracks)*

**Semana 1 — Problemática + esquema de config.**
Track B: redactar 4.1 y dejar cerrados el objetivo general y los 4
específicos. Track A: cerrar el esquema JSON (1.1) y el plan de
migración de escenarios.

**Semana 2 — Implementación del rediseño.**
Track A: refactor de `_build_world`, geometría a instancia, migración
de los 5 escenarios a JSON (1.2–1.3). Track B: avanzar marco teórico
(Capítulo 2).

**Semana 3 — Pruebas y ajustes de UI.**
Track A: pruebas de carga/validación, regresión de los 5 escenarios,
prueba manual con nodos extremos (Parte 2). Track B: metodología
(Capítulo 3).

**Semana 4 — Documentación técnica + resultados.**
Track A: `README` y `docs/arquitectura.md` (Parte 3). Track B:
desarrollo y resultados (Capítulos 4–5) con las métricas obtenidas en
la Semana 3.

---

*Nada ejecutado — pendiente de validar con el equipo.*
