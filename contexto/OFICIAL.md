# Documento oficial del proyecto

Fecha: 2026-11-22. **Este es el archivo oficial**: si otro documento de
`contexto/` o `docs/` dice algo distinto sobre el estado del proyecto,
manda este. Los demás quedan como historia y detalle (ver el final).

---

## Datos de la tesis

| Campo | Valor | Estado |
|---|---|---|
| Título | *Un simulador para redes descentralizadas: cobertura y adaptabilidad de una malla B.A.T.M.A.N.* | Cambiado el 2026-11-13 por indicación del tutor (sin "a la medida"; "adaptabilidad" en vez de "resiliencia") |
| Tutor y profesor | Joaquín Fernando Sánchez Cifuentes | Confirmado |
| Autores | Juan Camilo Gallardo Sánchez (XGallardoX) y Jefferson Gutiérrez Tovar | Confirmado |
| Programa | Pregrado en Ingeniería de Ciencias de la Computación e Inteligencia Artificial, Universidad Sergio Arboleda | Confirmado. La plantilla `MIA-USA.cls` es la misma de pregrado y posgrado: solo cambian los datos de portada |
| Encuadre | Problema: una sola pregunta (cómo implementar un simulador para redes descentralizadas…). Objetivo general: *implementar* el simulador. Objetivos específicos: requerimientos, diseño, implementación y pruebas. Caso de aplicación: Red de Expansión de Cobertura | Decidido (tutor, 2026-11-13) |

## Estado actual

**El simulador y el borrador completo del documento están hechos, con las
correcciones del tutor del 2026-11-13 aplicadas** (ver la sección siguiente) y
los ajustes de redacción del 2026-11-17 y 2026-11-20. El PDF compila sin errores
ni referencias rotas: 92 páginas (comprobado el 2026-11-22 en Linux). Copia para
leer sin instalar LaTeX: `Plantilla/documento_actual.pdf`.

| Parte del documento | Archivo en `Plantilla/` | Estado |
|---|---|---|
| Portada | `main.tex` | Completa |
| Agradecimientos | `FrontMatter/F03-Acknowledgements.tex` | Borrador breve; los autores lo revisan |
| Dedicatoria | `FrontMatter/F02-Dedication.tex` | Espacio para cada autor; **falta escribirla** |
| Resumen y abstract | `FrontMatter/F04-Abstract.tex` | Escrito |
| Símbolos y glosario | `FrontMatter/F05`, `F06` | Escritos |
| Cap. 1 Introducción | `MainMatter/Cap0/` | Escrito |
| Cap. 2 Planteamiento y objetivos | `MainMatter/Cap1/` | Escrito |
| Cap. 3 Estado del arte | `MainMatter/Cap2/` | Reescrito en lenguaje sencillo (2026-11-17, primera versión): mismas 51 fuentes y 68 citas |
| Cap. 4 Metodología | `MainMatter/Cap3/` | Escrito. Explica por qué 10 o 30 semillas y no una sola. Ya no trae los requerimientos ni la tabla de experimentos (pasaron al Cap. 5) |
| Cap. 5 Desarrollo | `MainMatter/Cap4/` | Reorganizado: 5.1 Requerimientos, 5.2 Diseño, 5.3 Implementación, 5.4 Pruebas (sin la antigua 5.4.2: las comprobaciones automáticas están solo en el Anexo B) |
| Cap. 6 Resultados y discusión | `MainMatter/Cap5/` | Organizado por prueba (P1 a P11): esperado contra obtenido |
| Cap. 7 Conclusiones | `MainMatter/Cap9/` | Escrito |
| Anexos | `BackMatter/B01-Anexos.tex` | A: reproducción (sin la sección para compilar el documento). B: comprobaciones automáticas (las 397 pruebas `unittest`) |

Ojo con los números: los nombres de carpeta no coinciden con el capítulo
impreso. Lo que el código y los documentos viejos llaman "Capítulo 5" es el
**Capítulo 6** del PDF. Dentro del texto se usan siempre `\ref`.

## Correcciones del tutor (2026-11-13)

Aplicadas en el documento:

- Sin "a la medida"; "cobertura y adaptabilidad", sin "resiliencia"; "medio de
  radiofrecuencia" en vez de "medio radio" (también en el código y los docs).
- Problema formulado como una sola pregunta; objetivo general "Implementar…";
  objetivos específicos: requerimientos, diseño, implementación y pruebas.
- Secciones numeradas con el capítulo (2.1, 2.2…): cambio en `MIA-USA.cls`.
  **Esto reemplaza la regla anterior de "manda la plantilla" para los títulos.**
- Cap. 5 en el orden de los objetivos. Las "pruebas" son simulaciones (P1 a P11),
  cada una con nombre, propósito y resultado esperado (tabla `tab:experimentos`);
  las pruebas `unittest` pasaron al Anexo B como "comprobaciones automáticas".
- Redacción menos técnica; cada ecuación con sus símbolos definidos; leyendas de
  figuras que describen lo que se ve; citas en las afirmaciones que las admiten.
- Evidencia visual: 11 capturas de la interfaz en `Images/Cap4/`, tomadas del
  simulador (escenario `fallo_puente`, semilla 1), más una tabla con las métricas
  de una corrida (`tab:corrida-puente`).
- 14 referencias nuevas, comprobadas en Crossref (RFC 768 y 792, en el RFC).

En el simulador: tipos de paquete **UDP, ICMP y TCP** (`sim/datos.py`), con
`tipo`/`cantidad` por flujo, el parámetro `tipo_paquete`, la pestaña **Tráfico**
de la interfaz y el lote `lotes/tipos_paquete.json` (tabla `tipos_paquete`).
Los lotes con tráfico se volvieron a correr y sus tablas salieron idénticas.

Pendiente de esas correcciones: que los autores lean el texto nuevo; el tutor
también pidió revisar la redacción y comparar el simulador con otros modelos
(la Tabla `tab:faltantes` del Cap. 6 es un primer paso).

## Avance del 2026-11-13 (después de las correcciones)

Hecho por Jefferson sobre la lista de pendientes de Juan Camilo:

- **Documentos al día con la pestaña Tráfico y los tipos de paquete:**
  `contexto/PREGUNTAS_FRECUENTES.md` (pregunta 10 nueva; "adaptabilidad" y
  "Capítulo 6"), `docs/interfaz_web.md` (sin "a la medida"; comandos
  `enviar_paquetes` y `quitar_flujo`; campo `trafico` del frame; apartado de la
  pestaña) y `docs/guia_ejecucion.md` (caso 15, con la salida de la semilla 1 y
  del lote).
- **Guía visual rehecha:** `docs/guia_visual_simulador.pdf` (26 páginas) tiene
  todas las capturas tomadas de nuevo con la interfaz actual, una página para
  la pestaña Tráfico y la redacción al día. Su fuente y los guiones para
  regenerarla quedaron en `docs/guia_visual/` (ver su `LEEME.md`).
- **Brecha frente a ns-3, confirmada en su documentación:** el módulo de
  edificios sí modela la pérdida entre pisos y *Direct Code Execution* sí
  ejecuta código de Linux. Lo que dice la tesis es correcto. La respuesta
  propuesta para la sustentación está en `contexto/VERIFICACION_FUENTES.md`.
- **Citas contra las fuentes:** una corregida (802.11 no reintenta 3 veces por
  defecto; el 3 es una simplificación del simulador) y dos dudosas sin resolver
  (ver "Fuentes").
- **Literatura reciente:** tres artículos de 2022 a 2026 integrados al estado
  del arte (61 referencias en total).

**Compilado el 2026-11-13** en la máquina de Jefferson (Windows, MiKTeX 25.12):
92 páginas, sin errores, sin citas ni referencias rotas y con las 61 entradas en
la bibliografía. `Plantilla/documento_actual.pdf` ya es esa versión.

## Avance del 2026-11-14 (decisiones y reparto)

Juan Camilo tomó las decisiones que Jefferson dejó abiertas, y el resto de
la lista se repartió entre Claude y Jefferson. **El detalle, el reparto y el
orden de las tareas de Jefferson están en
[`PENDIENTES.md`](PENDIENTES.md).** En resumen:

- **Punto 10 (acercar el protocolo a B.A.T.M.A.N.):** no se hace; queda como
  recomendación. **Escenarios:** no se renombran. **Defensa frente a ns-3:**
  aprobada.
- **Punto 11 (TCP con tiempo real):** en vez de rediseñar, la pestaña Tráfico
  estima el retardo (2 ms por intento de radio y 1 s de espera antes de cada
  retransmisión de TCP, RFC 6298) y dibuja la línea de tiempo de cada paquete.
  No cambia ningún resultado.
- **Capturas con semilla fija:** `fuerzas_cobertura.png` y `trafico.png`, con
  `docs/guia_visual/capturar_tesis.py`.
- **Punto 12:** N1 sin ruta a N6 a los 40 s es efecto del TTL de 6 de los OGM
  (con TTL 7 la ruta llega a los 13 s). Documentado en la tesis y en la guía.
- **Punto 13:** 30 semillas en las pruebas P7 a P9 y corrección de Holm en la
  tabla `diferencias` (ver "Resultados oficiales"). P7 pasa a cumplirse **en
  parte**: ocho pruebas dieron lo esperado y tres en parte (P6, P7 y P9).
- **Texto:** Wang et al. en el Cap. 6; la frase de la posición ya no se apoya
  en Howard; Holm reemplaza a Jain en la corrección por comparaciones
  múltiples; "listo para usar" en la frase de los emuladores. Dos referencias
  nuevas: Holm (1979) y RFC 6298 (63 en total).
- **Pendiente de Claude:** la comparación cuantitativa con otro modelo (punto
  9), con el alcance por fijar con Juan Camilo.

## Avance del 2026-11-17 y 2026-11-20 (Jefferson)

- **P10 con 30 semillas (2026-11-17):** `movilidad_datos`, `robustez` y
  `generalidad` repetidos en Windows (Python 3.14): las diez tablas salieron
  idénticas a las del repo. Las figuras cambian de bytes solo por la versión
  de matplotlib; no se subieron. **P10 se cumple también para estos lotes.**
- **Cap. 3 en lenguaje sencillo (2026-11-17), primera versión:** frases más
  cortas y cada término técnico explicado. Comprobado el 2026-11-22: la lista
  de `\cite` (68 citas, 51 fuentes), las etiquetas y las referencias cruzadas
  son idénticas a las de antes. Falta ajustarlo si la lectura de fuentes
  (punto 6) o la búsqueda de literatura (punto 7) cambian alguna frase.
- **Ajustes de redacción y estructura (2026-11-20):**
  - Cap. 4: por qué se usan varias semillas (10 en P3 a P6, 30 en P7 a P9)
    y amenazas a la validez al día con las 30 semillas y Holm.
  - Objetivos específicos sin subtítulos en negrita; fuera las frases del
    tipo "este capítulo sigue el orden de los objetivos" (Cap. 2, Cap. 5 y
    conclusiones). Introducción y Cap. 5: el Cap. 4 es cómo se trabajó y cómo
    se mide; el 5, lo que se construyó.
  - 5.4.2 (comprobaciones automáticas) eliminada: ya está en el Anexo B.
  - Resumen de las pruebas: columna "¿Se cumple?" y porcentaje en las que se
    cumplen en parte (P6 40 %, P7 67 %, P9 50 %), también en las conclusiones.
  - Anexo A sin la sección para compilar.
  - Guía visual: "medio de radiofrecuencia" en las dos frases que faltaban.
- **Corrección del 2026-11-22 (Claude):** el texto nuevo del Cap. 4 decía
  "10 semillas en P4 a P6"; P3 (`tipos_paquete`) también usa 10. Quedó "P3 a P6".

## Lo que falta

**De los autores (no se puede resolver desde el repo):**

1. Escribir cada uno su dedicatoria, debajo de su nombre en
   `Plantilla/FrontMatter/F02-Dedication.tex`.
2. Revisión a cargo de XGallardoX: agradecimientos, borrador completo, cómo se
   presenta el repositorio del tutor y lectura de las fuentes clave (ver "Fuentes").

Decisión de los autores (2026-11-04): el documento no lleva nota sobre el uso de IA.

**Límites del trabajo, ya declarados en la tesis:**

- No se validó contra hardware ni contra batman-adv. Lo que corre es la
  implementación en Python de `mesh/`, con diferencias conocidas respecto de
  B.A.T.M.A.N. (Sección 5.11 del PDF).
- El medio de radiofrecuencia es simple: simétrico y sin colisiones.
- No se mide latencia. La pestaña Tráfico muestra una **estimación** del
  retardo, que no se usa en ningún resultado.
- La escala llega a unas decenas de nodos: con 100 nodos densos ya corre por
  debajo del tiempo real.

**Menores, opcionales:**

- Renombrar el escenario `rescatista_perdido` (la tesis explica el nombre).
- El docstring de `Simulation.gateway_components` dice "sólo gateways", pero
  la conectividad usa los enlaces de todos los nodos vivos. La tesis describe
  el comportamiento real; falta corregir el comentario.

## Resultados oficiales

Todas las cifras del Capítulo 6 salen de estos lotes. Desde el 2026-11-14,
`movilidad_datos`, `robustez` y `generalidad` usan **30 semillas**; los demás, 10
(790 corridas en total). Fechas: 2026-11-04 (fallos y movilidad), 2026-11-13
(`tipos_paquete`) y 2026-11-14 (los tres de 30 semillas):

| Lote (`lotes/`) | Qué compara | Tablas |
|---|---|---|
| `capitulo5_fallos.json` | Caídas con Gateway fijos | `fallos`, `calidad` |
| `capitulo5_fallos_movil.json` | Las mismas caídas con movilidad descentralizada | `fallos_movil`, `calidad_movil` |
| `movilidad.json` | Tres modos de movilidad, sin tráfico | `movilidad` |
| `movilidad_datos.json` (30 semillas) | Tres modos con 6 flujos de datos | `movilidad_datos` |
| `robustez.json` (30 semillas) | Fallos al azar contra dirigidos | `robustez` |
| `generalidad.json` (30 semillas) | B.A.T.M.A.N. contra inundación en dos mapas | `generalidad` |
| `tipos_paquete.json` (2026-11-13) | UDP, ICMP y TCP en el edificio, 6 flujos | `tipos_paquete` |

La tabla `diferencias` trae las 14 diferencias pareadas con su intervalo del
95 % y el valor p de la prueba t pareada corregido por Holm
(`analysis/capitulo5.py`: `p_pareada`, `holm`). Una diferencia es concluyente si
ese valor es menor que 0.05.

Resultados principales:

- **La cobertura no revela la partición.** Si cae el puente, la malla queda
  partida 90 s con cobertura media de 1.000.
- **Fallos dirigidos:** entrega de datos de 0.338 contra 0.542 al azar
  (diferencia de 0.204, IC 95 % de 0.159 a 0.249, concluyente con Holm), sin
  diferencia concluyente en cobertura.
- **Gateway móviles:** la partición por el puente baja de 90 s a 6.2 s, pero la
  cobertura en ese fallo baja a 0.922.
- **El plano de control se degrada:** en `base`, la exactitud del conocimiento
  cae de 0.95 (`seguir`) a 0.55 (descentralizada).
- **Tipos de paquete:** TCP entrega 0.924, UDP 0.772 e ICMP 0.646; TCP usa 2.6
  veces las transmisiones de UDP.
- **Inundación contra B.A.T.M.A.N.:** depende del mapa. En campo abierto gana la
  inundación con cerca del doble de transmisiones; en el edificio gana
  B.A.T.M.A.N. (0.811 contra 0.465).
- **Movilidad con datos:** la descentralizada entrega más que `seguir` y
  `repartir` en `base` y `denso`; en `colapso_progresivo` no es concluyente
  con Holm (frente a `repartir`, p corregido 0.078; con 10 semillas y sin
  corrección parecía concluyente).

**Correcciones respecto de lo que decía `PLAN_SIGUIENTE.md`:**

- Allí la movilidad descentralizada figuraba como la de mejor entrega en
  `colapso_progresivo`. Con 30 semillas y la corrección de Holm no es
  concluyente ni frente a `seguir` ni frente a `repartir`. Vale lo de la tesis.
- Allí la inundación solo se había medido en campo abierto, con 3 semillas, y
  ganaba. En el edificio, con 10 semillas, pierde por mucho.

**Reproducibilidad:** las cinco tablas de los lotes del 27 de octubre salieron
idénticas byte a byte al correrlas de nuevo en esta máquina el 4 de noviembre.
Después solo cambió su formato (anchos de columna). El 2026-11-14, el lote
`tipos_paquete` salió idéntico tras añadir el retardo estimado. El 2026-11-17,
Jefferson repitió en Windows los tres lotes de 30 semillas y las diez tablas
salieron idénticas: la prueba P10 ("idénticas en dos computadores") vale para
todos los lotes.

## Fuentes

Auditoría del 2026-11-04 sobre la bibliografía impresa (44 referencias, ninguna
cita rota). El 2026-11-13 se añadieron 14 más (58 en total): 12 comprobadas en
Crossref; los RFC 768 y 792 y el libro de Jain (1991), por su referencia canónica.

| Tipo | Cantidad | Qué se comprobó |
|---|---|---|
| Artículos, capítulos y RFC con DOI | 36 | Existe en Crossref; título, año y autores coinciden. El RFC 3626 no trae autores en Crossref: se comprobó en el RFC |
| Borrador de la IETF | 1 | Existe en el IETF, con esos autores; está vencido y no es un estándar |
| Documentación y software | 6 | ns-3, INET, EMANE, batman-adv, Python y pygame-ce: páginas en línea. Son primarias, no revisadas por pares |
| Repositorio base del tutor | 1 | `jofsanchezci/Simulador_BATMAN`, en línea; el perfil de GitHub coincide con su nombre |

**Nivel de lectura:** se comparó lo que afirma el texto con los **resúmenes**, no
con los artículos completos (salvo una parte de Seither et al.). Sin resumen
disponible en las bases: Riley et al. (ns-3); de Kiess, Howard y Albert se leyó el
resumen en otras páginas. Los detalles de GloMoSim, OverSim y Mininet-WiFi salen de
lo que se sabe de esas herramientas: conviene revisarlos en el artículo.

**Corregido en la auditoría:** cita de 2010 que no podía sustentar los modelos
actuales de ns-3; Zou y Chakrabarty presentados como método local; el borrador de
2008 usado para respaldar el TQ; EMANE atribuido a quien no lo mantiene; Kurkowski
con una afirmación de repetibilidad que no se pudo comprobar; Albert et al. aplicado
a una malla que no es libre de escala; herramientas nombradas sin cita; el sitio de
ns-2, caído; y afirmaciones sin respaldo sobre ns-3 y batman-adv.

**Verificación del 2026-11-13** (`contexto/VERIFICACION_FUENTES.md`): se
contrastaron las 14 referencias nuevas y las que habían quedado en resumen. No se
pudo leer el texto completo de ningún artículo de pago. Quedan por leer con acceso
de la universidad, por orden de riesgo: Kiess y Mauve (la frase sobre la
inundación), Howard et al. (la frase "cada nodo conoce su posición", **dudosa**),
Fontes et al., Jain (la cita de la corrección por comparaciones múltiples,
**dudosa**), Zeng et al. y Riley y Henderson.

**Reciente:** 6 de las referencias académicas son de 2021 en adelante (eran 3; el
2026-11-13 se añadieron Wang et al., Turlykozhayeva et al. y Alam y Moh, con lo que
la bibliografía llega a 61). La búsqueda se hizo en OpenAlex: falta repetirla en
Scopus o IEEE Xplore.

**2026-11-14:** Holm (1979), para la corrección por comparaciones múltiples, y
RFC 6298, para la espera de 1 s antes de retransmitir: 63 referencias. Jain ya no
se cita para la corrección (sigue para las diferencias pareadas), y Howard ya no
respalda la frase "cada nodo conoce su posición", que quedó como supuesto del
trabajo.

**Sin cita, como conocimiento general:** los nombres comerciales QualNet, Riverbed
Modeler y NetSim.

## Cómo trabajar

```bash
# Pruebas (397; en Linux se omite 1, que necesita macOS)
venv/bin/python -m unittest discover -s tests

# Rehacer los resultados y regenerar tablas y figuras
venv/bin/python main.py --batch lotes/<lote>.json   # los siete de arriba
venv/bin/python -m analysis.capitulo5

# Compilar (TeX Live en ~/texlive/2026, en la máquina de XGallardoX)
export PATH=~/texlive/2026/bin/x86_64-linux:$PATH
cd Plantilla && pdflatex main && bibtex main && pdflatex main && pdflatex main
```

En Windows (máquina de Jefferson) se compila con MiKTeX, instalado con
`winget install MiKTeX.MiKTeX`. Los mismos cuatro comandos, desde `Plantilla\`;
a veces hace falta una pasada más de `pdflatex` si avisa "Rerun". MiKTeX descarga
solo los paquetes que falten.

- **Formato:** manda la plantilla, salvo la numeración de secciones, que por
  indicación del tutor lleva el capítulo (2.1, 2.2…). Márgenes, "Cuadro" en los
  títulos de tablas, bibliografía numerada y anexos antes de ella quedan como los trae.
- Las tablas de `MainMatter/Cap5/tablas/` y las figuras de `Images/Cap5/` son
  generadas: no se editan a mano. Si cambia un resultado, hay que revisar
  también las cifras citadas en la prosa del Capítulo 6, el resumen y las
  conclusiones, que están escritas a mano.
- `Plantilla/documento_actual.pdf` se actualiza a mano, solo cuando hay una
  versión para compartir.
- Commits a nombre de quien usa la sesión y sin atribución a Claude (ver
  `CLAUDE.md`).

## Los otros documentos

| Archivo | Para qué sirve ahora |
|---|---|
| `contexto/PLAN_SIGUIENTE.md` | Decisiones D1 a D11 y detalle de los pasos 1 a 12 (historia) |
| `contexto/ESTADO_PROYECTO.md` | Crónica hasta el 3 de octubre (historia) |
| `contexto/DECISIONES_FASE3.md` | Historia de la Fase 3 |
| `contexto/HISTORIA_ENCUADRE.md` | Por qué cambió el objetivo del proyecto |
| `contexto/PENDIENTES.md` | Decisiones del 2026-11-14 y reparto del resto entre Claude y Jefferson |
| `contexto/VERIFICACION_FUENTES.md` | ns-3 frente a la brecha, citas contra las fuentes y literatura reciente (2026-11-13) |
| `contexto/PREGUNTAS_FRECUENTES.md` | Respuestas cortas sobre cómo funciona el simulador |
| `docs/guia_ejecucion.md` | Casos de uso con su salida esperada |
| `docs/arquitectura.md`, `docs/movimiento_nodos.md`, `docs/interfaz_web.md` | Referencia técnica |
