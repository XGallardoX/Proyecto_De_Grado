# Decisiones pendientes: Fase 3 de la interfaz web

Fecha: 2026-09-30 · Rama: `feat/interfaz-web`

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

## Cómo responder

Basta una línea por punto en este archivo o en un mensaje, por ejemplo:

- 1 (eventos programables): sí / no / sí, pero ...
- 2 (laboratorio): sí / no / más adelante
- 3 (ventana nativa): sí / no

También queda por decidir cuándo se mergea `feat/interfaz-web` a `main`
(está subida como rama aparte, sin merge).
