# Verificación de fuentes y de la brecha frente a ns-3

Fecha: 2026-11-13. Cubre tres pendientes de la lista de Juan Camilo: los
dos puntos que debilitan la brecha (ns-3), las citas que solo se habían
comparado con resúmenes y la literatura reciente. El estado general del
proyecto sigue en [`OFICIAL.md`](OFICIAL.md).

**Cómo se verificó.** Para ns-3 se leyó su documentación en línea. Para
los artículos se leyó el resumen que publican OpenAlex y Semantic
Scholar, y los datos bibliográficos en Crossref. Los RFC se leyeron
completos, porque son públicos. **No se leyó el texto completo de
ningún artículo de pago**: Springer, ScienceDirect, IEEE Xplore y ACM
rechazaron el acceso. Lo que depende de eso está marcado como
"sin verificar".

---

## 1. Los dos puntos que debilitan la brecha (ns-3)

### El módulo de edificios: confirmado

Lo que dice la tesis (Tabla `tab:faltantes`, fila "Modelo de pérdida
entre pisos": *"ns-3 trae un módulo de edificios; hay que configurarlo"*)
es correcto. La documentación de ns-3 (*Buildings Module, Design
documentation*) dice:

- La clase `Building` tiene número de pisos y de cuartos en x y en y.
- El modelo de interiores `ItuR1238PropagationLossModel` suma una
  pérdida que depende del número de pisos entre emisor y receptor:
  `L = 20 log f + N log d + Lf(n) − 28`, con `Lf(n)` de 4n dB en
  edificios residenciales, 15 + 4(n − 1) en oficinas y 6 + 3(n − 1) en
  comerciales.
- Además trae pérdida por muros externos e internos y una ganancia por
  altura de unos 2 dB por piso.
- Los modelos se diseñaron pensando en LTE, pero la documentación dice
  que sirven con otras tecnologías de ns-3, y nombra wifi.

**Consecuencia:** no se puede decir que ns-3 no modela la pérdida entre
pisos. La observación 2 de `sec:brecha` habla de los emuladores, no de
ns-3, y así está bien. El planteamiento del problema (Capítulo 2) dice
que los emuladores "no incluyen un modelo de la pérdida de señal entre
los pisos":
esa frase no se verificó para EMANE y conviene suavizarla a "listo para
usar", como ya dice el Capítulo 3.

### Direct Code Execution (DCE): confirmado, con matices útiles

Lo que dice la tesis (*"permite ejecutar dentro del simulador programas y
pilas de red de Linux sin modificarlos, a cambio de preparar ese código
para el entorno del simulador"*) es correcto. Según la página del
proyecto, su documentación y el resumen de Tazaki et al. (2013):

- Ejecuta aplicaciones y código del núcleo de Linux "casi sin
  modificar", sin cambios en el código fuente.
- Exige recompilar el programa como ejecutable independiente de la
  posición (PIE), y solo ofrece una parte de la interfaz POSIX.
- Solo corre sobre Linux. La versión 1.12 está probada únicamente en
  Ubuntu 20.04 y la 1.11, en Ubuntu 16.04. La última versión con fecha
  en la página del proyecto es la 1.11, de septiembre de 2021.
- El ejemplo de la pila del núcleo usa la rama `libos-v4.4`.
- La documentación leída no menciona batman-adv, módulos del núcleo ni
  la capa inalámbrica (mac80211).
- El resumen destaca dos ventajas que también reclama este trabajo: la
  reproducibilidad determinista y la ejecución en un solo espacio de
  direcciones.

**Consecuencia:** "un solo programa" y "corridas reproducibles" no son
aportes exclusivos de este simulador. No conviene presentarlos así.

### Cómo defender el aporte si el jurado pregunta "¿por qué no ns-3?"

Propuesta de respuesta, apoyada solo en lo verificado:

1. **No se afirma que ns-3 no pueda.** Tiene módulo de edificios y DCE;
   la tesis lo reconoce en el estado del arte y en la Tabla
   `tab:faltantes`.
2. **Lo que se evalúa aquí son las clases del nodo del proyecto**, en
   Python. En ns-3 habría que reescribirlas como modelo en C++, y
   entonces se evaluaría la copia. DCE está hecho para ejecutables de
   Linux recompilados como PIE; no se encontró documentado su uso con
   batman-adv.
3. **El costo de montaje es distinto.** DCE pide un Linux específico
   (Ubuntu 20.04 para la versión 1.12). Este simulador corre con Python
   y tres bibliotecas, en Windows, Linux y macOS.
4. **Lo que el simulador trae de fábrica y allá habría que construir**
   (observación 4 de `sec:brecha`): las métricas de lo que cada nodo
   cree frente a lo que ocurre, la garantía de que la movilidad decide
   solo con información local y la interfaz que muestra la red como la
   ve cada nodo.
5. **Lo que se pierde está declarado:** sin colisiones, sin retardo,
   medio sin calibrar y sin comparación cuantitativa con ns-3. Esa
   comparación es la deuda principal (punto 9 de la lista).

Lo que no se debe decir: que ns-3 no tiene pérdida entre pisos, que no
puede ejecutar código real o que no es reproducible.

---

## 2. Citas contra las fuentes

"Sostiene" quiere decir que el resumen o el RFC respaldan la frase.

### Las 14 añadidas el 2026-11-13

| Fuente | Frase que respalda | Resultado |
|---|---|---|
| Seidel y Rappaport (1992) | Cada piso resta señal; efecto medido en edificios reales | **Sostiene.** El resumen reporta factores de atenuación por piso medidos, hasta cuatro pisos, a 914 MHz |
| Tazaki et al. (2013) | DCE ejecuta programas y pilas de Linux sin modificarlos | **Sostiene.** El resumen dice "casi sin modificar" |
| Lantz et al. (2010) | Emulación con procesos y espacios de nombres de red | **Sostiene** |
| RFC 2501 | Cada nodo es terminal y encaminador; operación distribuida | **Sostiene.** Nombra la operación distribuida como propiedad esencial y el control descentralizado |
| RFC 768, 792 y 9293 | UDP sin confirmación; eco de ICMP; TCP confirma y retransmite | **Sostiene** (leídos en el RFC) |
| RFC 3561 y 8966, Perkins y Bhagwat (1994) | Citas de identificación de AODV, Babel y DSDV | **Sostiene:** son las especificaciones de esos protocolos |
| IEEE 802.11 | El salto se reintenta "hasta 3 veces, como hace la capa de enlace" | **Corregida.** 802.11 sí retransmite, pero sus límites por defecto son 7 (tramas cortas) y 4 (largas), no 3. Se cambió la frase en el Capítulo 5 y en el README: el 3 es una simplificación del simulador |
| Akyildiz et al. (2005) | Los encaminadores forman una red troncal; despliegue rápido y autorreparación | **Sin verificar.** No hay resumen público; el título y el tema coinciden |
| Wehrle et al. (2010) | La simulación por eventos discretos; la simulación es la herramienta más usada | **Sin verificar.** Es un libro; el tema coincide |
| Jain (1991) | Diferencias pareadas por semilla | **Sin verificar, probable.** Las observaciones pareadas son un tema del libro |
| Jain (1991) | "Aplicar una corrección por hacer varias comparaciones" (Conclusiones) | **Dudosa.** No se pudo confirmar que el libro trate esa corrección. Conviene citar una fuente de comparaciones múltiples o quitar la cita |

### Las que la auditoría del 4 de noviembre dejó en resumen

| Fuente | Frase que respalda | Resultado |
|---|---|---|
| Albert et al. (2000) | Las redes libres de escala toleran fallos al azar y son vulnerables a ataques | **Sostiene** |
| Murray et al. (2010) | Compara OLSR, Babel y B.A.T.M.A.N.; gana Babel | **Sostiene** |
| Seither et al. (2011) | batman-adv en una oficina real, con AODV de referencia | **Sostiene** |
| Fontes et al. (2015) | Mininet-WiFi extiende Mininet a redes inalámbricas | **Sostiene en parte.** El resumen habla de estaciones y puntos de acceso inalámbricos virtuales. "Interconectado mediante pares de interfaces virtuales" describe a Mininet cableado: hay que revisarlo en el artículo |
| Baumgart et al. (2009) | OverSim: simulación y aplicaciones reales con el mismo código | **Sostiene en parte.** El resumen respalda las dos cosas; Chord, Pastry y Kademlia no aparecen en el resumen |
| Howard et al. (2002) | Campos potenciales; cada nodo es repelido por los demás y por los obstáculos; distribuido y escalable | **Sostiene** (título y síntesis de Semantic Scholar) |
| Howard et al. (2002) | "Cada nodo conoce su posición [...] como es habitual en estos métodos" (Capítulo 5) | **Dudosa.** No se pudo leer el artículo. Ese método usa lo que cada nodo percibe a su alrededor, y puede que no exija localización. Hay que leerlo antes de la entrega, o apoyar la frase en Liu et al. (2024) |
| Kiess y Mauve (2007) | La inundación básica se comportó en prototipos distinto a lo simulado | **Sin verificar.** No hay resumen público. Es la cita que más importa leer |
| Riley y Henderson (2010) | ns-3 es un simulador nuevo, escrito en C++ | **Sin verificar.** Sin resumen; coincide con la documentación de ns-3 |
| Zeng et al. (1998) | GloMoSim: simulación paralela de redes inalámbricas grandes, por capas | **Sin verificar.** El título coincide; el detalle de las interfaces por capa no se pudo leer |

### Lo que queda por leer con acceso de la universidad

Por orden de riesgo: Kiess y Mauve (la inundación), Howard et al. (la
posición), Fontes et al. (los pares de interfaces), Jain (la corrección
por comparaciones múltiples), Zeng et al. y Riley y Henderson.

---

## 3. Literatura reciente

Se añadieron tres artículos de revista, con el resumen leído y los datos
comprobados en Crossref. Están integrados en el estado del arte
(`M03-Chapter2.tex`).

| Clave | Artículo | Dónde se cita |
|---|---|---|
| `Wang2026QGSwitch` | Wang et al., *IEEE Trans. Vehicular Technology* 75(3), 2026. En equipos reales, batman-adv tarda 36.48 s de media en cambiar de Gateway cuando uno cae; su propuesta lo baja a 1.24 s | `sec:batman-literatura` |
| `Turlykozhayeva2024Proactive` | Turlykozhayeva et al., *Telecom* 5(4), 2024. OLSR, B.A.T.M.A.N. y Babel en hasta once Raspberry Pi; B.A.T.M.A.N. tiene la mejor tasa de entrega | `sec:batman-literatura` |
| `Alam2022JTCR` | Alam y Moh, *J. Network and Computer Applications* 204, 2022. Fuerzas virtuales para mover un enjambre sin perder conectividad | `sec:redes-desastre` |

El artículo de Wang et al. es el más útil para la discusión: mide en
equipos reales el mismo fenómeno que la prueba del puente (cuánto tarda
la red en reaccionar a la caída de un Gateway), y su orden de magnitud
(decenas de segundos) coincide con el `timeout` de 30 s del simulador.
Vale la pena citarlo también en el Capítulo 6.

Con estos, la bibliografía tiene 61 referencias. De 2021 en adelante hay
6 artículos académicos (antes 3), más tres normas (RFC 8966, RFC 9293 e
IEEE 802.11-2020).

**Encontrados y no añadidos:**

- Farajkhah y Çoban, *Simulation Modelling Practice and Theory* 154
  (DOI 10.1016/j.simpat.2026.103372): simulación basada en agentes de
  mallas de teléfonos tras un desastre. Es muy pertinente, pero no tiene
  resumen público. Añadirlo después de leerlo.
- Turlykozhayeva, *Eurasian Physical Technical Journal* 21(2), 2024:
  AODV, DSDV y OLSR en ns-3 con distintas topologías. Sus datos de autor
  en Crossref están incompletos.
- Ray et al., *Multimedia Tools and Applications* 83, 2023: vídeo sobre
  batman-adv. Poco relacionado.

La búsqueda se hizo en OpenAlex, no en Scopus ni en IEEE Xplore, que
piden cuenta institucional. Falta repetirla allí.
