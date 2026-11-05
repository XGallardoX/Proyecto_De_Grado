# Documento oficial del proyecto

Fecha: 2026-11-04. **Este es el archivo oficial**: si otro documento de
`contexto/` o `docs/` dice algo distinto sobre el estado del proyecto,
manda este. Los demás quedan como historia y detalle (ver el final).

---

## Datos de la tesis

| Campo | Valor | Estado |
|---|---|---|
| Título | *Un simulador a la medida para redes descentralizadas: cobertura y resiliencia de una malla B.A.T.M.A.N.* | Confirmado |
| Tutor y profesor | Joaquín Fernando Sánchez Cifuentes | Confirmado |
| Autores | Juan Camilo Gallardo Sánchez (XGallardoX) y Jefferson Gutiérrez Tovar | Confirmado |
| Programa | Pregrado en Ingeniería de Ciencias de la Computación e Inteligencia Artificial, Universidad Sergio Arboleda | Confirmado. La clase `MIA-USA.cls` viene de la maestría; se ajustó la portada |
| Encuadre | Problema: la necesidad de un simulador hecho a la medida para redes descentralizadas. Caso de aplicación: Red de Expansión de Cobertura | Decidido |

## Estado actual

**El simulador y el borrador completo del documento están hechos.** El PDF
compila sin errores ni referencias rotas: 74 páginas. Copia para leer sin
instalar LaTeX: `Plantilla/documento_actual.pdf`.

| Parte del documento | Archivo en `Plantilla/` | Estado |
|---|---|---|
| Portada | `main.tex` | Completa |
| Agradecimientos | `FrontMatter/F03-Acknowledgements.tex` | Borrador breve; los autores lo revisan |
| Dedicatoria | `FrontMatter/F02-Dedication.tex` | Activa con texto provisional; **la escriben los autores** |
| Resumen y abstract | `FrontMatter/F04-Abstract.tex` | Escrito |
| Símbolos y glosario | `FrontMatter/F05`, `F06` | Escritos |
| Cap. 1 Introducción | `MainMatter/Cap0/` | Escrito |
| Cap. 2 Planteamiento y objetivos | `MainMatter/Cap1/` | Escrito |
| Cap. 3 Estado del arte | `MainMatter/Cap2/` | Revisado y actualizado al encuadre |
| Cap. 4 Metodología | `MainMatter/Cap3/` | Escrito |
| Cap. 5 Desarrollo | `MainMatter/Cap4/` | Escrito |
| Cap. 6 Resultados y discusión | `MainMatter/Cap5/` | Escrito |
| Cap. 7 Conclusiones | `MainMatter/Cap9/` | Escrito |
| Anexo A Reproducción | `BackMatter/B01-Anexos.tex` | Escrito |

Ojo con los números: los nombres de carpeta no coinciden con el capítulo
impreso. Lo que el código y los documentos viejos llaman "Capítulo 5" es el
**Capítulo 6** del PDF. Dentro del texto se usan siempre `\ref`.

## Lo que falta

**De los autores (no se puede resolver desde el repo):**

1. Escribir la dedicatoria: hoy dice `[Dedicatoria por escribir]`.
2. Revisar los agradecimientos.
3. Leer el borrador completo. Lo escribió Claude a partir del repo: los
   objetivos, la metodología y las conclusiones son una propuesta que el tutor
   debe validar.
4. Confirmar en qué plantilla y con qué norma se entrega en pregrado: esta nació
   para la maestría, y las referencias salen en estilo `apalike` (con "and" e
   "in" en inglés).
5. Leer de primera mano las fuentes que más pesan (ver "Fuentes").

**Límites del trabajo, ya declarados en la tesis:**

- No se validó contra hardware ni contra batman-adv. Lo que corre es la
  implementación en Python de `mesh/`, con diferencias conocidas respecto de
  B.A.T.M.A.N. (Sección 5.11 del PDF).
- El medio de radio es simple: simétrico y sin colisiones.
- No se mide latencia.
- La escala llega a unas decenas de nodos: con 100 nodos densos ya corre por
  debajo del tiempo real.

**Menores, opcionales:**

- Renombrar el escenario `rescatista_perdido` (la tesis explica el nombre).
- El docstring de `Simulation.gateway_components` dice "sólo gateways", pero
  la conectividad usa los enlaces de todos los nodos vivos. La tesis describe
  el comportamiento real; falta corregir el comentario.

## Resultados oficiales

Todas las cifras del Capítulo 6 salen de estos lotes (10 semillas cada uno,
420 corridas en total), corridos el 2026-11-04:

| Lote (`lotes/`) | Qué compara | Tablas |
|---|---|---|
| `capitulo5_fallos.json` | Caídas con Gateway fijos | `fallos`, `calidad` |
| `capitulo5_fallos_movil.json` | Las mismas caídas con movilidad descentralizada | `fallos_movil`, `calidad_movil` |
| `movilidad.json` | Tres modos de movilidad, sin tráfico | `movilidad` |
| `movilidad_datos.json` (nuevo) | Tres modos con 6 flujos de datos | `movilidad_datos` |
| `robustez.json` | Fallos al azar contra dirigidos | `robustez` |
| `generalidad.json` (nuevo) | B.A.T.M.A.N. contra inundación en dos mapas | `generalidad` |

La tabla `diferencias` trae las diferencias pareadas con su intervalo del 95 %.

Resultados principales:

- **La cobertura no revela la partición.** Si cae el puente, la malla queda
  partida 90 s con cobertura media de 1.000.
- **Fallos dirigidos:** entrega de datos de 0.284 contra 0.502 al azar
  (diferencia de 0.218, IC 95 % de 0.149 a 0.287), sin diferencia concluyente
  en cobertura.
- **Gateway móviles:** la partición por el puente baja de 90 s a 6.2 s, pero la
  cobertura en ese fallo baja a 0.922.
- **El plano de control se degrada:** en `base`, la exactitud del conocimiento
  cae de 0.95 (`seguir`) a 0.55 (descentralizada).
- **Inundación contra B.A.T.M.A.N.:** depende del mapa. En campo abierto gana la
  inundación con cerca del doble de transmisiones; en el edificio gana
  B.A.T.M.A.N. (0.786 contra 0.430).

**Correcciones respecto de lo que decía `PLAN_SIGUIENTE.md`:**

- Allí la movilidad descentralizada figuraba como la de mejor entrega en
  `colapso_progresivo`. Con diferencias pareadas, frente a `seguir` no es
  concluyente (IC de -0.016 a +0.052). Vale lo de la tesis.
- Allí la inundación solo se había medido en campo abierto, con 3 semillas, y
  ganaba. En el edificio, con 10 semillas, pierde por mucho.

**Reproducibilidad:** las cinco tablas de los lotes del 27 de octubre salieron
idénticas byte a byte al correrlas de nuevo en esta máquina el 4 de noviembre.
Después solo cambió su formato (anchos de columna).

## Fuentes

Auditoría del 2026-11-04 sobre la bibliografía impresa (40 referencias, ninguna
cita rota).

| Tipo | Cantidad | Qué se comprobó |
|---|---|---|
| Artículos, capítulos y RFC con DOI | 34 | Existe en Crossref; título, año y autores coinciden. El RFC 3626 no trae autores en Crossref: se comprobó en el RFC |
| Borrador de la IETF | 1 | Existe en el IETF, con esos autores; está vencido y no es un estándar |
| Documentación de proyectos | 4 | ns-3, INET, EMANE, batman-adv: páginas en línea. Son primarias, no revisadas por pares |
| Repositorio base | 1 | `jofsanchezci/Simulador_BATMAN`, en línea |

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

**Reciente:** solo 3 de las referencias académicas son de 2021 en adelante. Hay que
ampliar la búsqueda en Scopus o IEEE Xplore si el tutor pide literatura más actual.

**Sin cita, como conocimiento general:** los nombres comerciales QualNet, Riverbed
Modeler y NetSim.

## Cómo trabajar

```bash
# Pruebas (371; en Linux se omite 1, que necesita macOS)
venv/bin/python -m unittest discover -s tests

# Rehacer los resultados y regenerar tablas y figuras
venv/bin/python main.py --batch lotes/<lote>.json   # los seis de arriba
venv/bin/python -m analysis.capitulo5

# Compilar (TeX Live en ~/texlive/2026, en la máquina de XGallardoX)
export PATH=~/texlive/2026/bin/x86_64-linux:$PATH
cd Plantilla && pdflatex main && bibtex main && pdflatex main && pdflatex main
```

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
| `docs/guia_ejecucion.md` | Casos de uso con su salida esperada |
| `docs/arquitectura.md`, `docs/movimiento_nodos.md`, `docs/interfaz_web.md` | Referencia técnica |
