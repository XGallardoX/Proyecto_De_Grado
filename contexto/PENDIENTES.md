# Qué se hizo y qué falta

Fecha: 2026-11-13. Sigue la lista de 14 puntos que Juan Camilo le pasó a
Jefferson. El estado general del proyecto está en [`OFICIAL.md`](OFICIAL.md),
que manda sobre este archivo.

Ojo: la lista llegó con líneas cortadas. Los puntos 2, 5, 6, 8, 9, 12, 13 y
14, y las dos decisiones del final, se leyeron incompletos. Conviene que
Juan Camilo la vuelva a pasar como archivo.

## Resumen

| Punto | Tema | Estado |
|---|---|---|
| 1 | Dedicatorias | Falta |
| 2 | Lectura completa del PDF | Falta |
| 3 | `PREGUNTAS_FRECUENTES.md` y guía visual | Hecho |
| 4 | `interfaz_web.md` y caso de UDP/ICMP/TCP | Hecho |
| 5 | Los dos puntos de ns-3 que debilitan la brecha | Hecho; falta acordar la defensa |
| 6 | Citas contra las fuentes | A medias |
| 7 | Literatura reciente | A medias |
| 8 | Reescribir el estado del arte | Falta |
| 9 | Comparación cuantitativa con otro modelo | Falta |
| 10 | Acercar el protocolo a B.A.T.M.A.N. | Falta: decisión |
| 11 | TCP con tiempo real | Falta: decisión |
| 12 | N1 sin ruta hacia N6 a los 40 s | Reproducido, sin investigar |
| 13 | Estadística (más semillas, comparaciones múltiples) | Falta |
| 14 | Preparar la sustentación | Empezado |

## Lo que se hizo

- **Punto 3.** `contexto/PREGUNTAS_FRECUENTES.md` dice "adaptabilidad" y
  "Capítulo 6", nombra la pestaña Tráfico y tiene una pregunta 10 sobre UDP,
  ICMP y TCP. `docs/guia_visual_simulador.pdf` se rehízo (26 páginas): todas
  las capturas son de la interfaz actual y hay una página para la pestaña
  Tráfico. Su fuente quedó en `docs/guia_visual/`.
- **Punto 4.** `docs/interfaz_web.md` ya no dice "a la medida" y documenta la
  pestaña Tráfico y los comandos `enviar_paquetes` y `quitar_flujo`.
  `docs/guia_ejecucion.md` tiene el caso 15, con la salida de la semilla 1 y
  del lote `tipos_paquete`.
- **Punto 5.** Se confirmó en la documentación de ns-3 que su módulo de
  edificios modela la pérdida entre pisos y que *Direct Code Execution*
  ejecuta código de Linux. Lo que dice la tesis es correcto. Hay una
  respuesta propuesta para el jurado en `contexto/VERIFICACION_FUENTES.md`.
- **Punto 6 (parte).** Se contrastaron las 14 citas nuevas y las que estaban
  en resumen. Se corrigió una: 802.11 no reintenta 3 veces por defecto; el 3
  es una simplificación del simulador (Capítulo 5 y README).
- **Punto 7 (parte).** Tres artículos de 2022 a 2026 integrados al estado del
  arte: Wang et al., Turlykozhayeva et al. y Alam y Moh. La bibliografía
  queda en 61 referencias.
- **Compilación.** Se instaló MiKTeX en la máquina de Jefferson. La tesis
  compila: 92 páginas, sin citas ni referencias rotas.
  `Plantilla/documento_actual.pdf` es esa versión.
- **Pruebas.** Las 390 pasan (1 omitida).

## Lo que falta y por qué

### Falta porque es una decisión de los dos autores

- **Punto 10, acercar el protocolo a B.A.T.M.A.N.** Reenviar solo el OGM del
  mejor vecino y borrar rutas por tiempo cambia todos los resultados: hay que
  repetir las 450 corridas, regenerar las tablas y reescribir las cifras del
  Capítulo 6, el resumen y las conclusiones. Hay que decidir si se hace o si
  queda como recomendación. **Es la decisión que bloquea a las demás.**
- **Punto 11, TCP con tiempo real.** Implica rediseñar `sim/datos.py` y sus
  pruebas, y también cambia resultados. Si se hace, conviene hacerlo junto
  con el punto 10 para repetir las corridas una sola vez.
- **Renombrar los escenarios** `rescatista_perdido` y `colapso_progresivo`.
  Cambia lotes, tablas y texto.
- **Rehacer con semilla fija la captura de las capas del mapa.** Hoy es la
  única con semilla al azar.
- **Punto 5, la defensa frente a ns-3.** La propuesta está escrita; falta que
  los dos la acuerden.

### Falta porque depende de una de esas decisiones

- **Punto 2, lectura completa del PDF.** Es trabajo de los autores, no se
  puede delegar. Si se aprueba el punto 10, las cifras cambian, así que
  conviene leer después.
- **Punto 9, comparación con ns-3 o batman-adv.** Es la tarea más grande y la
  deuda principal de la tesis. No se empezó por tres razones: los números
  propios pueden cambiar con el punto 10; ns-3 y batman-adv necesitan Linux
  (en la máquina de Jefferson habría que usar WSL); y falta definir el
  alcance (qué escenarios, cuántas semillas, qué métricas).
- **Punto 12, N1 sin ruta hacia N6 a los 40 s.** Se reprodujo (caso 15 de la
  guía: a los 40 s no hay ruta, a los 120 s sí). No se midió con qué TTL se
  arregla, porque el reenvío de OGM es justo lo que cambia el punto 10.
- **Punto 13, estadística.** Subir las semillas obliga a repetir corridas;
  conviene juntarlo con los puntos 10 y 11. La corrección por comparaciones
  múltiples además necesita una fuente que la respalde (ver abajo).

### Falta porque no se pudo hacer desde esta máquina

- **Punto 6, leer los artículos completos.** Springer, ScienceDirect, IEEE
  Xplore y ACM rechazaron el acceso; solo se leyeron resúmenes y RFC. Hay
  que leerlos con la cuenta de la universidad, en este orden:
  1. Kiess y Mauve: la frase sobre la inundación en prototipos.
  2. Howard et al.: "cada nodo conoce su posición" (Capítulo 5). **Dudosa.**
  3. Fontes et al.: "pares de interfaces virtuales" en Mininet-WiFi.
  4. Jain: la cita de la corrección por comparaciones múltiples
     (Conclusiones). **Dudosa.**
  5. Zeng et al. y Riley y Henderson.
- **Punto 7, Scopus e IEEE Xplore.** La búsqueda se hizo en OpenAlex, que es
  abierta. Las otras dos piden cuenta institucional. Queda un artículo
  pertinente sin añadir porque no tiene resumen público: Farajkhah y Çoban
  (DOI 10.1016/j.simpat.2026.103372).

### Falta porque es personal

- **Punto 1, dedicatorias.** Cada autor escribe la suya en
  `Plantilla/FrontMatter/F02-Dedication.tex`. Faltan las dos.

### Falta porque no se llegó

- **Punto 8, reescribir el estado del arte.** No estaba en esta tanda. Va
  después de los puntos 6 y 7, para no reescribir frases que luego cambian.
  Regla de control: la lista de `\cite` debe ser la misma antes y después.
- **Punto 14, preparar la sustentación.** Solo está la respuesta a "¿por qué
  no usar ns-3?". Faltan las demás: por qué no se validó con equipos, qué
  significa "código real" y por qué P6 y P9 se cumplen solo en parte.

## Orden sugerido

1. Decidir el punto 10 (y con él 11 y 13).
2. Mientras tanto, lo que no depende de eso: dedicatorias (1), lectura de
   fuentes con acceso de la universidad (6), Scopus e IEEE Xplore (7).
3. Si se aprueba el 10: implementarlo, repetir las corridas una sola vez con
   11 y 13 incluidos, y revisar el 12 sobre el protocolo nuevo.
4. Comparación con otro modelo (9).
5. Reescribir el estado del arte (8), lectura completa (2) y sustentación (14).
