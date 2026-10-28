# Cómo cambió el objetivo del proyecto

Fecha: 2026-10-27

Este archivo explica, en orden, cómo el proyecto pasó de ser un
simulador de rescatistas a ser un simulador de redes descentralizadas, y
por qué hoy los Gateway se mueven aunque en algún momento se decidió que
los resultados principales irían con nodos fijos. Es contexto: las
decisiones puntuales y el plan están en
[`PLAN_SIGUIENTE.md`](PLAN_SIGUIENTE.md), y lo hecho en
[`ESTADO_PROYECTO.md`](ESTADO_PROYECTO.md).

En una frase: **no es un simulador de rescatistas; es un simulador a la
medida para evaluar cobertura y resiliencia de redes descentralizadas.
Los nodos no están obligados a quedarse fijos: los resultados principales
se miden con nodos fijos, y se repiten con Gateway móviles que deciden
solos.**

---

## 1. El punto de partida (agosto 2026): rescatistas

El repo madre (`jofsanchezci/Simulador_BATMAN`, rama `develop`) simulaba
una operación de **búsqueda y rescate** con una red ad-hoc:

- Los radios eran **rescatistas** (`R`) y las personas por encontrar,
  **supervivientes** (`S`).
- Cada rescatista caminaba hacia el superviviente más cercano que no
  había sido encontrado.
- La red corría el protocolo BATMAN real (`mesh/`) sobre un medio de
  radio simulado.

## 2. Primer cambio (2026-09-18): Red de Expansión de Cobertura

Se resolvió la pregunta abierta del encuadre del proyecto: pasa a ser una
**Red de Expansión de Cobertura**. El objetivo es *evaluar la resiliencia
y la conectividad de la malla ante fallos de nodos*.

Qué se hizo en el código:

- Roles renombrados `R`/`S` → **`G`** (Gateway) y **`N`** (Nodo de
  usuario), también en logs, ventana, reportes y columnas del CSV.
- Se retiró el mecanismo de "hallar supervivientes" (`register_found`,
  `found_ids`, `my_survivors`, `rango_deteccion`).
- Aparecieron los eventos de fallo programables (`fail`/`recover`), la
  reconvergencia de rutas y los escenarios de fallo del Capítulo 5.

Por qué: una red de cobertura es **infraestructura desplegada**. Los
radios se instalan en un lugar; no persiguen gente. Lo interesante es qué
pasa cuando uno falla.

### La decisión D3 (2026-10-03): resultados principales con nodos fijos

Con ese encuadre se decidió que los resultados principales del Capítulo 5
irían **con nodos fijos**, por dos motivos:

1. Un despliegue de cobertura es fijo.
2. Los dos modelos de movilidad que existían entonces tenían defectos
   conocidos:
   - `seguir`: cada Gateway va al Nodo de usuario más cercano, y todos
     terminan apilados sobre el mismo nodo.
   - `repartir`: un Gateway por Nodo de usuario, lo que cubre a todos pero
     parte la malla y hace parpadear los enlaces.

`seguir` contra `repartir` quedaba solo como comparación secundaria
(caso 11 de la guía). De ahí viene la idea de que "los nodos ya no se
deben mover y el movimiento quedó para comparar".

## 3. Segundo cambio (2026-10-26): redes *descentralizadas*

El director dio el encuadre de fondo: *"la idea es que el problema esté
enfocado en la necesidad de un simulador hecho a la medida para redes
descentralizadas"*.

Al revisar el simulador con ese objetivo aparecieron tres lugares donde
decidía con información global, como un coordinador central, lo cual
contradice la tesis:

1. La movilidad `seguir` mira las posiciones de *todos* los nodos, y
   `repartir` es un emparejamiento global que hace el motor.
2. La entrega de mensajes por BFS sobre el grafo real *garantizaba* la
   llegada si existía camino: las tablas de BATMAN no decidían nada.
3. Solo circulaban OGM y beacons; no había tráfico de datos.

Se decidió el alcance completo (D7), ejecutado en los pasos 8 a 11:

| Paso | Qué se hizo |
|---|---|
| 8 | **Plano de datos sobre BATMAN.** Cada paquete avanza salto a salto por la tabla de rutas del nodo que lo tiene, con pérdidas del medio, TTL y detección de bucles |
| 9 | **Movilidad descentralizada de los Gateway.** Cada uno decide solo con lo que oye (atracción a los usuarios a su cargo, repulsión entre Gateway, expansión de los ociosos y una regla que le impide romper un enlace sin rodeo). Es la movilidad **por defecto** |
| 10 | **Métricas de descentralización:** qué tanto coincide lo que cada nodo cree con la realidad, nodos críticos (puntos de articulación) y fallos al azar contra fallos dirigidos |
| 11 | **Generalidad:** mapa de campo abierto, usuarios que caminan (random waypoint y grupos) y un protocolo de comparación (inundación) |

### Y D3 se reabre (D8)

Con la movilidad descentralizada, el movimiento **deja de ser un
artefacto**: ya no apila ni parte la malla por una regla global. Por eso
la decisión **D8 reabre D3**: los resultados del Capítulo 5 se vuelven a
correr con la movilidad descentralizada *además* de con nodos fijos. Eso
se hizo en el paso 12 (2026-10-27).

## 4. Dónde estamos hoy

| Pregunta | Respuesta |
|---|---|
| ¿Es un simulador de rescatistas? | No. Es de cobertura y resiliencia en redes descentralizadas |
| ¿Los nodos deben estar fijos? | No es una regla. Los resultados principales van con nodos fijos, y se repiten con Gateway móviles descentralizados |
| ¿Qué papel tienen `seguir` y `repartir`? | Son la **línea base centralizada**, para mostrar qué se gana decidiendo sin coordinador |
| ¿Qué es lo "por defecto"? | La movilidad `descentralizada` |

Qué aporta el movimiento descentralizado, con las cifras del paso 12
(10 semillas):

- **Más cobertura.** En `denso`, la cobertura media pasa de 0.51
  (`seguir`) a 0.994, y se alcanzan los 6 Nodos de usuario.
- **La red se repara sola.** Con Gateway móviles, la partición por la
  caída del puente baja de **90 s a 6.2 s**, y la cascada deja 4 de 6
  Nodos cubiertos (3 con nodos fijos).
- **Más datos entregados de punta a punta** que con `seguir` y `repartir`
  (por ejemplo `denso`: 0.281 contra 0.140 y 0.182).
- **El costo:** la malla queda estirada, con enlaces más largos, TQ más
  bajo (0.38 en `denso`) y más alertas (30 de media, contra 0 con
  `seguir`).
- **Los fallos dirigidos duelen más que los fallos al azar:** la entrega
  de datos cae a 0.28 contra 0.50, y la malla queda partida 180 s contra
  42 s.

## 5. Restos del encuadre viejo

Quedan nombres y textos heredados. No rompen nada, pero conviene
limpiarlos en la tesis:

- El escenario **`rescatista_perdido`** conserva el nombre del framing de
  rescate (un Gateway se aleja y pierde contacto con el resto).
- El evento **`wander`** (un Gateway camina hacia la esquina (38, 2) hasta
  un instante dado) viene del mismo origen.
- La sección **"Redes ad-hoc en escenarios de emergencia"** del
  Capítulo 2 de la tesis sigue hablando de búsqueda y rescate. El paso 6
  del plan ya la marca para pasarla a la Red de Expansión de Cobertura.
- Los objetivos del plan de trabajo de agosto (§4.2–4.3 de
  `PLAN_TRABAJO.md`, ya fuera del repo; queda en el historial, commit
  `7acf40e`) también hablaban de búsqueda y rescate.

**Decisión pendiente:** renombrar `rescatista_perdido`. Tocaría
escenarios, lotes, guía, pruebas y tablas de `Plantilla/`. Nadie la ha
pedido todavía.

## 6. Dónde mirar cada cosa

| Tema | Archivo |
|---|---|
| Decisiones D1 a D11 y el plan por pasos | [`PLAN_SIGUIENTE.md`](PLAN_SIGUIENTE.md) |
| Lo hecho, por etapas | [`ESTADO_PROYECTO.md`](ESTADO_PROYECTO.md) |
| Historia de la Fase 3 (fallos programables) | [`DECISIONES_FASE3.md`](DECISIONES_FASE3.md) |
| Los tres modos de movilidad y sus umbrales | `docs/movimiento_nodos.md` |
| Comparación de los tres modos con cifras | `docs/guia_ejecucion.md`, caso 11 |
| Escenarios de fallo del Capítulo 5, fijos y móviles | `docs/guia_ejecucion.md`, caso 14 |
| Cómo apoya la interfaz la tesis del simulador a la medida | `docs/interfaz_web.md`, sección 3 |
