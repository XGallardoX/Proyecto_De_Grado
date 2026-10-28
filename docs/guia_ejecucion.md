# Guía de ejecución: escenarios y casos

Guía práctica para correr el simulador: cómo preparar el entorno, qué
plantea cada escenario y una serie de casos con el comando exacto y lo
que deberías ver. La referencia completa de flags y formatos está en el
[README](../README.md); esto es el camino corto.

Todos los comandos se corren **desde la raíz del repositorio** y con el
entorno virtual activado. Los resultados que se citan salen de correr
esos mismos comandos. Como cada corrida queda fijada por su semilla, con
el mismo código deberías obtener exactamente los mismos números. Si
algún día cambian, es que cambió el código, no el azar.

> **Movilidad por defecto.** Desde el paso 9 del plan, los Gateway se
> mueven por defecto con la movilidad `descentralizada` (cada uno decide
> sólo con lo que oye). Todas las cifras de esta guía se rehicieron con
> ella en el paso 12 (2026-10-27), salvo donde el caso lo dice: el caso
> 10B y el 12 se quedan con `seguir`, porque ahí la movilidad tapa lo
> que el caso quiere mostrar. Los casos con nodos fijos (`--static`) no
> cambiaron.

**Contenido**

1. [Preparar el entorno](#1-preparar-el-entorno)
2. [Los cuatro modos de un vistazo](#2-los-cuatro-modos-de-un-vistazo)
3. [Los escenarios predefinidos](#3-los-escenarios-predefinidos)
4. [Casos](#4-casos)
   1. [Tumbar un Gateway y ver cómo lo detecta la malla](#caso-1--tumbar-un-gateway-y-ver-cómo-lo-detecta-la-malla)
   2. [Mandar mensajes por la malla](#caso-2--mandar-mensajes-por-la-malla)
   3. [Una corrida reproducible sin ventana](#caso-3--una-corrida-reproducible-sin-ventana)
   4. [Mirar por dentro una ruta multi-salto](#caso-4--mirar-por-dentro-una-ruta-multi-salto)
   5. [Armar tu propio escenario](#caso-5--armar-tu-propio-escenario)
   6. [Una red aleatoria reproducible](#caso-6--una-red-aleatoria-reproducible)
   7. [Los 5 escenarios con 10 semillas](#caso-7--los-5-escenarios-con-10-semillas)
   8. [Movilidad contra nodos fijos](#caso-8--movilidad-contra-nodos-fijos)
   9. [Alcance de radio contra cobertura](#caso-9--alcance-de-radio-contra-cobertura)
   10. [Timeout: falsas alarmas contra rapidez de detección](#caso-10--timeout-falsas-alarmas-contra-rapidez-de-detección)
   11. [Seguir contra repartir: cobertura contra conectividad](#caso-11--seguir-contra-repartir-cobertura-contra-conectividad)
   12. [Ver la red como la ve cada nodo (interfaz web)](#caso-12--ver-la-red-como-la-ve-cada-nodo-interfaz-web)
   13. [Un Gateway puente que cae y vuelve: las dos reconvergencias](#caso-13--un-gateway-puente-que-cae-y-vuelve-las-dos-reconvergencias)
   14. [Escenarios de fallo de un despliegue de cobertura (laboratorio)](#caso-14--escenarios-de-fallo-de-un-despliegue-de-cobertura-laboratorio)
5. [Dónde quedan los resultados y cómo leerlos](#5-dónde-quedan-los-resultados-y-cómo-leerlos)
6. [Problemas frecuentes](#6-problemas-frecuentes)

---

## 1. Preparar el entorno

```bash
python3 -m venv venv                # una sola vez
source venv/bin/activate            # en cada terminal nueva (Windows: venv\Scripts\activate)
pip install -r requirements.txt     # numpy, matplotlib, pygame-ce
python -m unittest discover -s tests
```

La última línea tiene que decir `OK` (son más de 130 pruebas y tardan
un par de segundos). Si ya existe un entorno (`venv/` o `.venv/`), basta con
activarlo. Probado con Python 3.14.

> Sin el entorno activado, `python` es el del sistema y todo falla con
> `ModuleNotFoundError: No module named 'numpy'`.

---

## 2. Los cinco modos de un vistazo

| Quiero… | Comando | Qué deja |
|---|---|---|
| Ver la red en vivo e interactuar | `python main.py --escenario base` | Una ventana; al cerrarla, figura y reportes en `reportes/` |
| Lo mismo, en el navegador | `python main.py --web --escenario base` | Una pestaña en `http://127.0.0.1:8765/`; al terminar la sesión, los mismos reportes más `sesion_web.json` |
| En una ventana propia | `python main.py --web --ventana --escenario base` | La misma interfaz, en una ventana sin pestañas (modo app de Chrome, Chromium, Brave o Edge) |
| Una corrida sin ventana | `python main.py --headless --escenario base --seed 1` | Un resumen en pantalla y `reportes/base_<fecha_hora>/` |
| Ver el estado interno del protocolo | `python main.py --inspect --escenario particion --duracion 30` | Texto por pantalla, sin archivos |
| Resultados con varias semillas | `python main.py --batch lotes/ejemplo.json` | Un resumen agregado y `reportes/lote_<nombre>_<fecha_hora>/` |

Para elegir la red hay tres opciones: `--escenario <nombre>` (uno de los
5 predefinidos), `--config <archivo>` (un `.json` o `.txt` propio) o
`-n N -g G` (N nodos al azar, G de ellos Gateways). Encima de cualquiera
se puede agregar `--static` (los nodos no se mueven),
`--movilidad seguir` o `repartir` (las dos de línea base, centralizadas,
en vez de la `descentralizada` por defecto; ver el
[caso 11](#caso-11--seguir-contra-repartir-cobertura-contra-conectividad))
y `--seed N` (la corrida se repite igual). `--duracion` fija los segundos simulados sin
ventana (200 por defecto). En `--batch` todo eso va dentro del archivo
de lote.

En la ventana, las teclas más útiles son `1`–`9` para seleccionar un
Gateway, `F`/`G` para tumbar/recuperar el nodo seleccionado, `M` para
mandar un mensaje, `I` para volcar el estado a la terminal, `P` para
exportar sin cerrar y `Q` para salir (también exporta). La lista
completa está en el README. La ventana avanza unos 9 s simulados por
cada segundo real.

---

## 3. Los escenarios predefinidos

Todos usan el mismo edificio: 40 × 30 m en 3 pisos de 10 m, visto como
un corte vertical (`x` es la posición horizontal, `y` la altura). Los
Gateway (`G`) se mueven por la movilidad `descentralizada` (cada uno
decide sólo con lo que oye de los demás), salvo que se use `--static`
(ver [`movimiento_nodos.md`](movimiento_nodos.md)).

| Escenario | Qué plantea |
|---|---|
| `base` | 4 Gateway juntos en el piso 3 y 3 Nodos de usuario en los pisos 1 y 2: el caso de referencia. |
| `colapso_progresivo` | Como `base`, con baterías escalonadas (100/78/56/38 %) que se gastan rápido: G4 cae a los 84.5 s, G3 a los 124.5 s y G2 a los 173.5 s. |
| `particion` | Alcance de radio reducido (11 m) y dos parejas de Gateway en esquinas opuestas: la malla arranca partida en dos. |
| `rescatista_perdido` | Como `base`, pero G4 camina hacia la esquina (38, 2) hasta t = 80 s y pierde el contacto con el resto (nombre heredado del framing anterior). |
| `denso` | 8 Gateway y 6 Nodos de usuario. |

Cada uno se ve en vivo con `python main.py --escenario <nombre>` y se
corre sin ventana con `python main.py --headless --escenario <nombre>
--seed 1`. Lo que deberías ver, según el lote de referencia (10
semillas, 200 s, con la movilidad `descentralizada`; detalle en el
[caso 7](#caso-7--los-5-escenarios-con-10-semillas)):

- **`base`**: la malla de Gateways casi siempre queda unida (partida 5.2
  s de media: sólo en 3 de las 10 semillas se parte) y se alcanzan 2.8 de
  los 3 Nodos de usuario al final. Con `seguir`, en cambio, los cuatro
  Gateway se apilaban sobre N2 y sólo se alcanzaban 1.2.
- **`colapso_progresivo`**: los Gateway caen uno tras otro y al final
  queda sólo G1 (0.3 nodos alcanzables al final). La primera alerta
  llega hacia los 51.5 s, antes de la primera caída (84.5 s): no es una
  caída, es un enlace que se separa o parpadea mientras los Gateway se
  reubican. Por eso hay más alertas (7.3) que con `seguir` (5.3).
- **`particion`**: casi los 200 s con la malla partida (195.1 s de
  media; en 2 de las 10 semillas los grupos llegan a oírse un rato) y
  ninguna alerta: `FaultManager` sólo vigila a los Gateway que alguna
  vez oyó.
- **`rescatista_perdido`**: G4 se separa del resto (a los 35.5 s con la
  semilla 1) y la malla queda partida 59.0 s de media: a diferencia de `seguir`, donde
  la partición duraba hasta el final (159 s), los Gateway se acercan y
  la malla se reúne (1.1 componentes al final). La primera alerta llega
  hacia los 38 s y hay 10 en total.
- **`denso`**: la malla nunca se parte y se alcanzan los 6 nodos de
  usuario (cobertura media 0.994, contra 0.51 con `seguir`, donde los 8
  Gateway se apilaban sobre N5). El costo son enlaces más largos: TQ
  medio 0.38 y 30.3 alertas de media por enlaces que parpadean. El
  [caso 11](#caso-11--seguir-contra-repartir-cobertura-contra-conectividad)
  compara los tres modos de movilidad.

---

## 4. Casos

Cada caso tiene un objetivo, el comando y lo que deberías ver. Los
casos 1 y 2 son con la ventana; el resto, sin ella. Los archivos que
usan los casos 4, 9 y 10 están en [`escenarios/casos/`](../escenarios/casos/)
(cada uno explica en su cabecera de qué caso es).
[`lotes/casos.json`](../lotes/casos.json) corre los casos 9 y 10 de una
vez, y [`lotes/movilidad.json`](../lotes/movilidad.json), el caso 11.

### Caso 1 — Tumbar un Gateway y ver cómo lo detecta la malla

**Objetivo:** ver la detección de un Gateway caído y su recuperación.

```bash
python main.py --escenario base --static
```

1. Pulsa `4` para seleccionar a G4 (o haz clic sobre él).
2. Pulsa `F`: G4 cae (queda gris, con una `X`).
3. Espera unos 30–35 s simulados, que son 3–4 s reales. G1, G2 y G3
   levantan la alerta: se pintan de rojo con un `!` en la etiqueta, y
   en el panel de log aparece
   `⚠ G1: sin señal de G4 > 30s — se marca caído` (y lo mismo para G2 y
   G3).
4. Con G4 todavía seleccionado, pulsa `G`: vuelve, y alrededor de un
   segundo simulado después los tres registran
   `G1: señal de G4 recuperada` (y lo mismo G2 y G3).
5. Pulsa `Q`. La cronología de eventos queda en el `reporte.txt` de la
   carpeta nueva en `reportes/`.

**Qué deberías ver** (lo mismo, reproducido sin ventana con la
semilla 1): la caída en t = 20 s, las tres alertas en t = 50 s, la
recuperación en t = 100 s y las tres alertas apagadas en t = 101 s. La
demora es el `timeout` (30 s) más el tiempo hasta el siguiente chequeo,
porque `FaultManager` revisa cada 5 s.

**Detalle normal:** al volver, G4 todavía tiene las tablas de antes de
caer, así que durante 1–4 s puede "no oír" a sus vecinos
(`G4 no oye a G1`). Se apaga solo en cuanto recibe sus beacons.

**El mismo caso en la interfaz web:**

```bash
python main.py --web --escenario base --static
```

Selecciona G4 (clic sobre el nodo, o tecla `4`) y pulsa `F` (o
"Caer" en la pestaña **Nodo**, o clic derecho sobre el nodo): se pone
gris con una `X`. Selecciona G1: con la capa "Vigilancia" prendida, el
anillo sobre G4 se va llenando con el silencio. Entre 25 y 30 s
simulados después de la caída, la pestaña **Nodo** de G1 muestra la
ruta a G4 obsoleta (en rojo: ningún OGM la refrescó en el último
`timeout`); a los 30-35 s aparecen "Cree caídos: G4" y, en el log y en
la línea de tiempo, las mismas tres alertas `⚠ G1: sin señal de G4 > 30s`. Selecciona G4 de
nuevo y pulsa `G` (recuperar): un segundo simulado después, las alertas
se apagan. "Terminar" (o `Q`) deja la misma cronología en el
`reporte.txt` de `reportes/`.

### Caso 2 — Mandar mensajes por la malla

**Objetivo:** ver que un mensaje viaja por las tablas de BATMAN, salto
a salto, y por qué puede no llegar.

```bash
python main.py --escenario particion
```

- Pulsa `M`, escribe `G1>G2 hola` y `Enter`: llega en 1 salto, porque
  G1 y G2 se oyen.
- Pulsa `M` y escribe `G1>G3 hola`: el log dice
  `Mensaje G1→G3 no entregado: no hay ningún camino por radio en G1`.
  La malla está partida: ningún protocolo podría entregarlo.
- `G1>N1 hola` también llega, directo o por G2: lo decide la tabla de
  G1 según qué OGM de N1 le llegó mejor.

Para ver un mensaje de varios saltos:

```bash
python main.py --config escenarios/casos/cadena.txt
```

Ahí `G1>N3 hola` va por G1 → N1 → N2 → N3 y se ve viajar salto a salto.
Los enlaces de la cadena pierden paquetes, así que no siempre llega: con
el mensaje mandado a los 30 s simulados llega con `--seed 2`; con
`--seed 1` la radio pierde el salto en N1 (aun con sus 3 reintentos), y
con `--seed 3` G1 todavía no tiene ruta a N3. El log dice en qué nodo y por qué se perdió. El formato es
`emisor>destino texto`; sin letra se asume Gateway (`1>2` es `G1>G2`).

Para tráfico continuo en vez de mensajes sueltos, `--trafico K` agrega K
flujos entre Nodos de usuario al azar (un paquete cada 2 s); el resumen
de `--headless` y `--batch` suma la entrega de datos y por qué se perdió
cada paquete (ver el README, "Plano de datos").

### Caso 3 — Una corrida reproducible sin ventana

**Objetivo:** obtener resultados sin pantalla y poder repetirlos.

```bash
python main.py --headless --escenario base --duracion 50 --seed 1
```

**Qué deberías ver**, después del banner de configuración y de tres
líneas `[reporter] Reporte exportado a …`:

```
============================================================
 Corrida headless · escenario 'base' · 50 s simulados
============================================================
  TQ medio de rutas                     : 0.716
  Saltos medios por ruta                : 1.17
  Tasa de entrega del radio             : 0.370
  Componentes de la malla al final      : 1
  Nodos de usuario alcanzables al final : 0
  Gateways vivos al final               : 4
  Episodios de partición                : 0
  Tiempo con la malla partida (s)       : 0.0
  Tiempo de reconvergencia (s)          : no aplica
  Alertas de gateway perdido            : 0
  Primera alerta (s)                    : no aplica
  Reconvergencia de rutas BATMAN (s)    : no aplica
  Cobertura media de Nodos de usuario   : 0.120
  Entrega de datos                      : no aplica
  (… las demás métricas de datos: «no aplica», porque no hay tráfico)
  Exactitud del conocimiento de rutas   : 0.906
  Pares con ruta fantasma               : 0.000
  Pares con ruta faltante               : 0.094
  Nodos críticos (articulación), media  : 0.59
  Eventos registrados                   : 0
------------------------------------------------------------
 Figura y reportes en reportes/base_<fecha_hora>/
============================================================
```

La carpeta tiene `analisis_red.png` (la figura de 6 paneles),
`reporte.csv`, `reporte.json` y `reporte.txt`. Si lo corres otra vez
con `--seed 1`, el `reporte.csv` sale idéntico; con otra semilla,
distinto. Sin `--seed`, cada corrida es distinta.

### Caso 4 — Mirar por dentro una ruta multi-salto

**Objetivo:** comprobar en las tablas del protocolo que BATMAN arma
rutas de varios saltos.

[`escenarios/casos/cadena.txt`](../escenarios/casos/cadena.txt) pone un
Gateway y tres Nodos de usuario en fila, a 10 m entre sí. Con 16 m de
alcance, cada uno oye sólo a sus vecinos inmediatos.

```bash
python main.py --inspect --config escenarios/casos/cadena.txt --duracion 60 --seed 1
```

**Qué deberías ver** en el bloque de G1:

```
  Tabla de rutas BATMAN (a quien / por quien / con que calidad):
    destino  via(sig.salto)  hops  TQ    seq  edad
    -------  --------------  ----  ----  ---  ----
    N1       N1              1     0.38  15   0.5s
    N2       N1              2     0.42  13   8.5s
    N3       N1              3     0.04  14   5.5s
```

Para llegar a N3, G1 manda por N1 (su siguiente salto) y la ruta tiene
3 saltos. El TQ refleja que cada enlace entrega menos de la mitad de los
paquetes (tasa de entrega 0.46): la ruta a N3, que cruza tres enlaces
con pérdidas, queda casi en 0.
Con menos duración, alguna ruta puede no haber aparecido todavía: con
pérdidas altas, los OGMs tardan en atravesar la cadena.

### Caso 5 — Armar tu propio escenario

**Objetivo:** probar una topología propia.

El formato `.txt` es el más cómodo. Por ejemplo, `mi_escenario.txt`:

```
name: mi_escenario

[protocol]
static=true           # nodos fijos; bórralo para que los Gateway se muevan

[nodes]
# id  rol  x   y   [batería]
1     G    5   5
2     G    35  25
10    N    15  5
11    N    25  15    80
```

- `x` va de 0 a 40 e `y` de 0 a 30. El piso sale de `y`: 0–10 es el
  piso 1, 10–20 el 2 y 20–30 el 3.
- Hace falta al menos un `G`. Los `id` no se pueden repetir.
- Se pueden cambiar el edificio (`[building]`) y cualquier parámetro
  del medio o del protocolo (`[medium]`/`[protocol]`, tabla de claves
  en el README), y agregar un evento `wander` en `[events]`.

Para validarlo rápido, sin abrir la ventana:

```bash
python main.py --inspect --config mi_escenario.txt --duracion 5
```

Con estas posiciones, los dos Gateway quedan unidos a través de los dos
nodos de usuario (cada salto mide 10–14 m, dentro de los 16 m de
alcance). El `--inspect` debería mostrar un solo grupo con
`G1, G2, N1, N2` y `Nodos alcanzables : 2/2`. Si separas más los nodos,
vas a ver el grupo partirse. Si algo del archivo está mal, se frena
antes de simular y dice qué (ver la [sección 6](#6-problemas-frecuentes)).
Después se corre igual que cualquier escenario: con ventana, con
`--headless` o dentro de un lote.

### Caso 6 — Una red aleatoria reproducible

**Objetivo:** probar una red sin diseñarla a mano, pero poder repetirla.

```bash
python main.py --headless -n 8 -g 2 --seed 7 --duracion 100
```

Son 8 nodos en posiciones al azar, 2 de ellos Gateway. Con `--seed 7`
salen siempre las mismas posiciones y el mismo resultado: tasa de
entrega 0.313 y los 6 Nodos de usuario alcanzables al final. Para
guardar una red aleatoria como escenario se usa un `.txt` con
`mode=random`, `n_nodes=8` y `n_gateways=2` en `[nodes]`. El modo
aleatorio de la línea de comandos y el `.txt` con `mode=random` usan los
mismos valores por defecto (por ejemplo `battery_drain` 0.030).

### Caso 7 — Los 5 escenarios con 10 semillas

**Objetivo:** el resultado que va al documento, del tipo "se corrieron
10 semillas por escenario".

```bash
python main.py --batch lotes/ejemplo.json
```

Corre 63 simulaciones (los 5 escenarios con 10 semillas, `base` con
nodos fijos y un archivo propio con 3) en unos 6 s, e imprime el
resumen. Lo principal (media ± desviación estándar muestral; entre
paréntesis, en cuántas corridas aplicó la métrica cuando no fue en
todas):

| Escenario | Entrega del radio | Componentes al final | N alcanzables al final | G vivos al final | Malla partida (s) | Alertas | Primera alerta (s) |
|---|---|---|---|---|---|---|---|
| `base` | 0.271 ± 0.012 | 1.00 | 2.80 ± 0.42 | 4.00 | 5.2 ± 15.2 | 6.60 ± 2.27 | 51.5 ± 23.5 |
| `colapso_progresivo` | 0.272 ± 0.020 | 1.00 | 0.30 ± 0.95 | 1.00 | 0.0 | 7.30 ± 1.06 | 51.5 ± 23.5 |
| `particion` | 0.465 ± 0.041 | 1.80 ± 0.42 | 2.30 ± 0.48 | 4.00 | 195.1 ± 11.7 | 0.00 | no aplica |
| `rescatista_perdido` | 0.293 ± 0.015 | 1.10 ± 0.32 | 2.80 ± 0.42 | 4.00 | 59.0 ± 17.5 | 10.00 ± 1.70 | 38.0 ± 3.5 |
| `denso` | 0.301 ± 0.004 | 1.00 | 6.00 | 8.00 | 0.0 | 30.30 ± 7.47 | 46.0 ± 3.9 |
| `base` fijo (`base_static`) | 0.716 ± 0.006 | 1.00 | 0.00 | 4.00 | 0.0 | 0.00 | no aplica |

(Donde no hay "±", la desviación es 0.) Las dos reconvergencias, que
sólo aplican si una partición se reunifica o un Gateway vuelve, dan
valores en pocas corridas: "Tiempo de reconvergencia" 9.2 ± 13.1 s en 3
de las 10 de `base`, 134.5 ± 74.2 s en 2 de `particion` y 50.9 ± 22.3 s
en las 10 de `rescatista_perdido` (donde la partición se cierra al
acercarse los Gateway); en `colapso_progresivo` y `denso` no aplican
(ver la [sección 5](#5-dónde-quedan-los-resultados-y-cómo-leerlos)). La
"Reconvergencia de rutas BATMAN" sólo aplica en `rescatista_perdido`
(50.8 ± 26.1 s, en 9 de las 10) y en 1 de las 10 de `particion` (2.5 s).

El TQ medio y la cobertura media, que no entran en la tabla de arriba:

| Escenario | TQ medio | Cobertura media |
|---|---|---|
| `base` | 0.468 ± 0.041 | 0.837 ± 0.108 |
| `colapso_progresivo` | 0.514 ± 0.047 | 0.416 ± 0.061 |
| `particion` | 0.547 ± 0.049 | 0.766 ± 0.131 |
| `rescatista_perdido` | 0.563 ± 0.028 | 0.746 ± 0.082 |
| `denso` | 0.383 ± 0.009 | 0.994 ± 0.006 |
| `base_static` | 0.762 ± 0.012 | 0.000 |

El TQ baja donde las rutas cruzan enlaces con más pérdidas o más
saltos. Con la movilidad `descentralizada` los Gateway se reparten para
cubrir más Nodos de usuario, y la malla queda estirada: enlaces más
largos y rutas con más saltos (en `denso`, 2.39 saltos medios), así que
el TQ y la entrega del radio son bastante menores que con nodos fijos
o con `seguir` (caso 11), a cambio de cobertura.

Para tu propio lote, copia `lotes/ejemplo.json` y cambia la lista. El
formato completo está en el README ("Archivo de lote").

### Caso 8 — Movilidad contra nodos fijos

**Objetivo:** medir qué aporta que los Gateway se muevan.

Sale del mismo lote del caso 7, que corre `base` dos veces: con
movilidad y con `"static": true`.

| | Entrega del radio | N alcanzables al final |
|---|---|---|
| `base` (se mueven) | 0.271 ± 0.012 | 2.80 ± 0.42 |
| `base_static` (fijos) | 0.716 ± 0.006 | 0.00 |

Fijos en el piso 3, los Gateway no llegan a ningún Nodo de usuario.
Moviéndose, se reparten hacia los Nodos de usuario y cubren 2.8 de los
3. El costo es la entrega del radio: baja de 0.716 a 0.271, porque los
Gateway se alejan entre sí y los enlaces quedan más largos y débiles
(con `seguir` se apilaban sobre N2 y la entrega subía a 0.864, pero a
costa de cubrir sólo 1.2 Nodos de usuario; ver el caso 11). Para
comparar así cualquier escenario, agrega al lote una entrada con
`"static": true`.

### Caso 9 — Alcance de radio contra cobertura

**Objetivo:** barrer un parámetro (`rango_comm`) y ver su efecto.

```bash
python main.py --batch lotes/casos.json
```

Este lote corre los casos 9 y 10 juntos (100 simulaciones, unos 5 s).
Para el alcance compara `base` con nodos fijos a 16 m (el valor por defecto),
20 m y 24 m (`escenarios/casos/base_rango20.txt` y `base_rango24.txt`):

| Alcance | N alcanzables al final | Entrega del radio | Saltos medios | TQ medio |
|---|---|---|---|---|
| 16 m (`alcance_16m`) | 0 | 0.716 ± 0.006 | 1.17 ± 0.08 | 0.762 ± 0.012 |
| 20 m (`alcance_20m`) | 1 | 0.688 ± 0.003 | 1.37 ± 0.06 | 0.723 ± 0.026 |
| 24 m (`alcance_24m`) | 3 | 0.515 ± 0.004 | 1.71 ± 0.10 | 0.614 ± 0.040 |

Más alcance da más cobertura (de 0 a 3 nodos de usuario), pero a costa
de enlaces más largos y débiles: la entrega y el TQ bajan, y las rutas
tienen más saltos. Con los nodos fijos, la cobertura depende sólo de la geometría,
por eso no varía entre semillas.

**Para barrer otro parámetro:** copia el escenario, cambia el valor en
`[medium]` o `[protocol]`, y agrega una entrada con su propia etiqueta
en el lote. Por ejemplo:
`{ "config": "escenarios/casos/mi_variante.txt", "etiqueta": "mi_variante" }`.

### Caso 10 — Timeout: falsas alarmas contra rapidez de detección

**Objetivo:** ver el compromiso del `timeout` de detección de caídas.
Sale del mismo `lotes/casos.json`.

**A. Timeout corto → falsas alarmas.** Es `base` con nodos fijos, donde
no cae ningún Gateway, así que toda alerta es falsa: la provocan las
pérdidas del medio (`escenarios/casos/base_timeout4.txt`,
`base_timeout8.txt`).

| Timeout | Alertas (todas falsas) |
|---|---|
| 4 s | 0.50 ± 0.71 (en 4 de las 10 semillas) |
| 8 s | 0 |
| 30 s (por defecto) | 0 |

**B. Timeout largo → detección tardía.** Es `colapso_progresivo`, donde
G4 muere a los 84.5 s (`escenarios/casos/colapso_timeout15.txt` y
`colapso_timeout60.txt`). Estas tres entradas del lote llevan
`"movilidad": "seguir"`: con la movilidad por defecto, los Gateway que
se reubican separan enlaces antes de la primera caída y esas alertas
tapan la latencia de detección que el caso quiere medir (ver la nota de
abajo).

| Timeout | Primera alerta, 9 de 10 semillas | Media de las 10 | Alertas |
|---|---|---|---|
| 15 s | 100 s | 94.0 ± 19.0 | 6.30 ± 0.95 |
| 30 s | 115 s | 109.0 ± 19.0 | 5.30 ± 0.95 |
| 60 s | 145 s | 140.0 ± 15.8 | 3.10 ± 0.32 |

La latencia de detección es el `timeout` más lo que falte para el
siguiente chequeo (hasta 5 s). La semilla 4 se sale del patrón (40, 55
y 95 s): ahí G4 se había separado del grupo antes de morir, y lo que se
detecta es esa separación.

Con la movilidad `descentralizada` (por defecto) el patrón de las
alertas es otro: la primera llega a 26.0 ± 4.6 s con timeout 15, a
51.5 ± 23.5 s con 30 y a 124.0 ± 28.1 s con 60, con 14.4, 7.3 y 3.1
alertas. Con 15 y 30 s, en promedio *antes* de la primera caída (84.5
s); con 60 s, antes de los 144.5 s que daría esa caída más el timeout.
Es la separación de los Gateway que se mueven, no el fallo, lo que
dispara el detector (por ejemplo, con la semilla 1, G4 deja de oír a G1
a los 60 s y lo recupera a los 64 s, sin que nadie haya caído): el
compromiso del timeout se ve igual, pero mezclado con ese ruido.

Con un timeout largo también hay menos alertas, porque algunas caídas
ya no llega a detectarlas nadie. Con 60 s, G3 muere (124.5 s) antes de
que le venza el timeout para G4, y la caída de G2 (173.5 s) se
detectaría después de los 200 s que dura la corrida.

### Caso 11 — Seguir contra repartir: cobertura contra conectividad

**Objetivo:** comparar los tres modelos de movilidad de los Gateway.

Con `seguir` (la de antes del paso 9), cada Gateway camina hacia el
Nodo de usuario que tiene más cerca, sin coordinarse con los demás. En
`denso`, N5 es el más cercano de los 8 Gateway, así que a los 40 s están
los 8 encima de él y la mitad derecha del edificio queda sin cobertura.
`repartir` asigna un Gateway por Nodo de usuario (detalle en
[`movimiento_nodos.md`](movimiento_nodos.md)). Las dos deciden con
información global, como un coordinador central, y son la línea base.
`descentralizada` (la de por defecto) hace que cada Gateway decida sólo
con lo que oye: atracción a los usuarios a su cargo, repulsión entre
Gateway, expansión de los ociosos y una regla que le impide romper un
enlace sin rodeo. Para verlo en vivo:

```bash
python main.py --escenario denso --movilidad seguir   # los 8 van a N5
python main.py --escenario denso --movilidad repartir # se reparten
python main.py --escenario denso                      # descentralizada
```

Para medirlo con 10 semillas en los 5 escenarios (100 simulaciones,
unos 10 s):

```bash
python main.py --batch lotes/movilidad.json
```

En cada celda, `seguir` → `repartir` → `descentralizada`:

| Escenario | N alcanzables al final | Componentes al final | Malla partida (s) | Entrega del radio |
|---|---|---|---|---|
| `base` | 1.20 ± 0.63 → **3** → 2.80 ± 0.42 (de 3) | 1.10 ± 0.32 → 3.00 → 1.00 | 16.5 → 178.2 → 5.2 | 0.864 → 0.489 → 0.271 |
| `colapso_progresivo` | 1.00 → 2.00 → 0.30 ± 0.95 (de 3) | 1.00 → 1.00 → 1.00 | 4.9 → 102.2 → 0.0 | 0.799 → 0.467 → 0.272 |
| `particion` | 2.00 → **3** → 2.30 ± 0.48 (de 3) | 2.00 → 3.00 → 1.80 ± 0.42 | 200 → 200 → 195.1 | 0.960 → 0.795 → 0.465 |
| `rescatista_perdido` | 3.00 → 3.00 → 2.80 ± 0.42 (de 3) | 2.00 → 2.00 → 1.10 ± 0.32 | 159.2 → 158.7 → 59.0 | 0.742 → 0.480 → 0.293 |
| `denso` | 3.20 ± 1.55 → **6** → **6** (de 6) | 1.00 → 1.70 ± 0.48 → 1.00 | 0.0 → 85.2 ± 52.7 → 0.0 | 0.756 → 0.352 → 0.301 |

Cobertura media y TQ medio (`seguir` → `repartir` → `descentralizada`):

| Escenario | Cobertura media | TQ medio |
|---|---|---|
| `base` | 0.40 → 0.95 → 0.84 | 0.89 → 0.77 → 0.47 |
| `colapso_progresivo` | 0.36 → 0.82 → 0.42 | 0.86 → 0.75 → 0.51 |
| `particion` | 0.67 → 0.99 → 0.77 | 0.98 → 0.88 → 0.55 |
| `rescatista_perdido` | 0.91 → 0.93 → 0.75 | 0.79 → 0.70 → 0.56 |
| `denso` | 0.51 → 0.99 → 0.99 | 0.82 → 0.50 → 0.38 |

**Qué muestra `descentralizada`:** sin coordinador, consigue la
cobertura de `repartir` donde la geometría lo permite (`denso`: los 6
Nodos de usuario, y la malla nunca se parte, contra 85 s partida de
`repartir`; `base`: 2.8 de 3 con la malla unida salvo 5.2 s, contra 178 s
partida de `repartir`). No lo logra en `colapso_progresivo` (0.3 Nodos
alcanzables al final: sólo queda G1 y los demás se fueron cayendo) ni en
`particion`, donde los dos grupos arrancan sin oírse. El costo es la
calidad del medio: la entrega del radio (0.27–0.47) y el TQ (0.38–0.56)
quedan por debajo de los dos modos centralizados, porque la malla se
estira y los enlaces son largos. Y hay más alertas (30.3 en `denso`,
contra 0 con `seguir`) por enlaces que parpadean.

Con tráfico de datos de aplicación (`trafico: 6` en el lote, 10 semillas,
200 s) `descentralizada` es la que más datos entrega de punta a punta:

| Escenario | Entrega de datos (`seguir` → `repartir` → `descentralizada`) |
|---|---|
| `base` | 0.211 → 0.205 → **0.277** |
| `colapso_progresivo` | 0.216 → 0.196 → **0.234** |
| `denso` | 0.140 → 0.182 → **0.281** |

Es porque cubre a más Nodos de usuario: entre los pares que sí tienen
un camino por radio, `seguir` entrega más (0.40 contra 0.30 en `base`).
Los umbrales de la movilidad `descentralizada` y su elección están en
[`movimiento_nodos.md`](movimiento_nodos.md).

**Qué muestran `seguir` y `repartir`:** `repartir` cubre todos, o casi todos, los Nodos de
usuario. Para lograrlo, los Gateway se alejan entre sí más allá del
alcance de radio y la malla de Gateways se parte: en `base` queda en 3
grupos casi toda la corrida, y en `denso` termina en dos grupos en 7 de
las 10 semillas (en las otras 3, los dos Gateway que sobran la mantienen
unida). Los enlaces son más largos y la entrega cae casi a la mitad. Las
alertas de gateway perdido se disparan (en `denso`, de 0 a 55 de media),
porque cada separación se detecta como un Gateway que dejó de oírse, y
cada reconexión la apaga, así que un enlace que parpadea vuelve a
alertar. El TQ medio también cae (en `denso`, de 0.82 a 0.50): las
rutas son más largas y cruzan enlaces débiles. En
`rescatista_perdido` casi no cambia nada: el Gateway que se aleja ya
cubría la otra punta del edificio.

**Reconvergencia.** `denso` con `repartir` es el único caso en el que la
malla se parte y se vuelve a unir: 11.7 ± 9.2 episodios de partición por
corrida, con una reconvergencia de 7.9 ± 10.0 s (en 9 de las 10
corridas). La reconvergencia de las rutas BATMAN, que mide otra cosa
(caso 13), da 24.2 ± 17.5 s en 7 de las 10. Muchos de esos episodios
son parpadeos, no reconexiones
reales: un Gateway que ya llegó a su nodo sigue dando pasos de 0.32 m a
su alrededor, y si otro Gateway queda justo en el borde de los 16 m de
alcance, el enlace se prende y se apaga. Por ejemplo, la semilla 1 tiene
22 episodios de 2.7 s de media.

Ninguno de los dos modelos es "el correcto": es el compromiso entre
cobertura y conectividad de una red de expansión de cobertura. Para
compararlos en tus propios escenarios, agrega al lote la misma entrada
dos veces, una con `"movilidad": "seguir"` y otra con
`"movilidad": "repartir"`.

### Caso 12 — Ver la red como la ve cada nodo (interfaz web)

**Objetivo:** ver que no hay una vista global: cada nodo tiene su propia
tabla de rutas y su propia idea de quién está caído, y tarda en enterarse
de una partición.

```bash
python main.py --web --escenario rescatista_perdido --seed 1 --movilidad seguir
```

(Con `--movilidad seguir` porque el recorrido de abajo, con sus tiempos,
es el de esa movilidad. Con la `descentralizada` por defecto, la
partición ocurre antes —a los 35.5 s con la semilla 1— y se cierra a
los 97.5 s cuando G4 se reúne con el resto; la idea, que cada nodo se
entera tarde y por su cuenta, es la misma.)

G4 se aleja hacia la esquina (38, 2). Con la semilla 1, la malla se
parte a los **41 s** (aviso "RED PARTIDA" y un toast), pero la detección
recién llega a los **70 s**: el `timeout` de 30 s más lo que falta para
el siguiente chequeo de `FaultManager`.

1. Pausa cerca de t = 60 s (Espacio; `⏭ Paso` avanza de a 0.5 s) y
   selecciona G4 (tecla `4`). Pulsa `L` ("ver como este nodo"): G4
   todavía tiene rutas a G1, G2 y G3 (de 4, 1 y 1 saltos) aunque la
   radio ya no lo conecte con ellos. En la pestaña **Red**, la matriz
   muestra esas celdas como "vigente" con borde punteado: lo que el nodo
   cree contra lo que hay.
2. Con G4 seleccionado y la capa "Vigilancia" prendida, los anillos
   sobre G1, G2 y G3 se van llenando a medida que crece el silencio.
3. Reanuda hasta pasar los 70 s: las rutas de G4 hacia el otro grupo
   pasan a obsoletas (en rojo), G4 cree caídos a G1, G2 y G3, y G1 (con
   `1` y `L`) cree caído a G4. Cada lado decidió por su cuenta.

La convergencia también se ve al arrancar cualquier escenario: la
matriz empieza con pocas celdas verdes y se va llenando a medida que los
OGM se propagan (en este mismo escenario, a los 30 s, 24 de los 42
pares conectados por radio ya tienen ruta).
### Caso 13 — Un Gateway puente que cae y vuelve: las dos reconvergencias

**Objetivo:** programar una caída y una recuperación en el escenario y
ver la diferencia entre las dos medidas de reconvergencia.

En [`escenarios/casos/puente.txt`](../escenarios/casos/puente.txt) hay
tres Gateway en fila, a 9 m entre sí, con los nodos fijos. G1 y G3
quedan a 18 m, fuera del alcance de 16 m, así que sólo se comunican a
través de G2. La sección `[events]` programa la caída y la vuelta de G2:

```
[events]
fail     2  60
recover  2  100
```

(En JSON: `{"type": "fail", "node_id": 2, "t": 60}`; ver el README.)

```bash
python main.py --headless --config escenarios/casos/puente.txt --duracion 160 --seed 1
```

**Qué deberías ver** en el resumen (semilla 1):

```
  Episodios de partición                : 1
  Tiempo con la malla partida (s)       : 40.0
  Tiempo de reconvergencia (s)          : 40.0
  Alertas de gateway perdido            : 6
  Primera alerta (s)                    : 75.0
  Reconvergencia de rutas BATMAN (s)    : 5.0
  Cobertura media de Nodos de usuario   : 1.000
```

y en la cronología de `reporte.txt`: G2 cae a los 60 s, la malla se
parte a los 60.5 s, las alertas llegan entre los 75 y los 90 s, G2
vuelve a los 100 s y la malla se reunifica a los 100.5 s.

**Cómo leerlo:**

- **"Tiempo de reconvergencia" (40.0 s) no mide al protocolo.** Mide
  cuánto duró la partición de la malla de radio, y como los nodos
  caídos no se mueven, da exactamente el tiempo que G2 estuvo caído (de
  60 a 100 s). Es el dato de entrada, no un resultado.
- **"Reconvergencia de rutas BATMAN" (5.0 s) sí.** Cuenta desde que G2
  vuelve hasta que G1, G2 y G3 tienen, todos con todos, una ruta que un
  OGM refrescó en el último `timeout`. Depende del intervalo de OGM
  (4 s) y de cuántos se pierden por el camino.
- **La primera alerta llega a los 75 s, antes de los 90 s** que
  darían la caída más el `timeout`: G3 ya venía oyendo a G1 de forma
  intermitente (a dos saltos, por enlaces que pierden casi la mitad de
  los paquetes), y lo último que sabía de él era más viejo que la
  caída.
- **G1 y G3 dejan de creerse caídos pocos segundos después de que G2
  vuelve** (`ALERT_OFF` a los 103.5 s y a los 105 s). No se oyen
  directo: la alerta se apaga con el primer OGM nuevo del otro que G2
  les reenvía, con el mismo criterio con que se encendió (los OGM son
  los que refrescan el `last_seen` del vecino). Igual en el simulador y
  en el nodo real (`MeshNode._handle_bcast`).

**Con 10 semillas** ([`lotes/fallos.json`](../lotes/fallos.json), que
también corre la variante
[`puente_corto.txt`](../escenarios/casos/puente_corto.txt), con G2 de
vuelta a los 70 s):

```bash
python main.py --batch lotes/fallos.json
```

| G2 caído | Malla partida (s) | Tiempo de reconvergencia (s) | Reconvergencia de rutas BATMAN (s) | Alertas |
|---|---|---|---|---|
| 40 s (`puente_40s`) | 40.0 | 40.0 | 14.8 ± 5.7 | 5.90 ± 0.57 |
| 10 s (`puente_10s`) | 10.0 | 10.0 | 1.6 ± 2.6 | 1.10 ± 0.88 |

Con la caída corta, más corta que el `timeout` de 30 s, las rutas hacia
G2 nunca llegan a quedar viejas: en 8 de las 10 semillas el episodio se
cierra en la primera muestra (0.5 s). Las alertas que aparecen igual
son falsas alarmas entre G1 y G3, por los enlaces con pérdidas.

**En la interfaz web**, `casos/puente.txt` se abre desde el botón de
carpeta junto al escenario y
corre con sus eventos programados (salen en el log como "caído
(programado)"). También se puede hacer a mano, con cualquier escenario:
tumbar un Gateway con `F`, recuperarlo con `G` y exportar. Como las únicas intervenciones fueron caídas y
recuperaciones, la exportación deja `escenario_sesion.json` con esas
intervenciones como eventos `fail`/`recover` y un comando de terminal
`--config` que reproduce la misma corrida.

### Caso 14 — Escenarios de fallo de un despliegue de cobertura (laboratorio)

**Objetivo:** comparar tipos de fallo sobre un mismo despliegue, con 10
semillas, desde la terminal o desde el laboratorio de la interfaz. Son los
escenarios del Capítulo 5 (decisión D5 de `contexto/PLAN_SIGUIENTE.md`).

[`escenarios/fallos/`](../escenarios/fallos/) tiene un despliegue de 7
Gateway fijos en los 3 pisos que cubren 6 Nodos de usuario
(`cobertura_edificio.txt`, el control sin fallos) y cuatro variantes con
eventos programados:

| Archivo | Qué cae | Por qué ese Gateway |
|---|---|---|
| `fallo_redundante.txt` | G2, de 60 a 150 s | Parte de la malla redundante de los pisos 1 y 2: no parte nada |
| `fallo_puente.txt` | G6, de 60 a 150 s | Único puente al piso 3: la malla se parte en dos |
| `fallo_borde.txt` | G7, de 60 a 150 s | Único Gateway al alcance de N6: N6 queda sin cobertura |
| `fallo_cascada.txt` | G6 a los 60 s, G7 a los 100 s, G3 a los 140 s, sin vuelta | Degradación progresiva |

El despliegue usa radios de 12 m de alcance con enlaces más fiables que
los del medio por defecto (`falloff` 0.5, atenuación por piso 0.8; ver
la cabecera de los archivos). Con el medio por defecto, un despliegue
con puente y borde en este edificio necesita enlaces tan largos que la
entrega cae a 0.32 y las falsas alarmas tapan los fallos.

```bash
python main.py --batch lotes/capitulo5_fallos.json
```

(o, en la interfaz, "⚗ Laboratorio" → Cargar `lotes/capitulo5_fallos.json`
→ Correr: mismos números, con la tabla y una gráfica por métrica.)

| Experimento | Malla partida (s) | Tiempo de reconvergencia (s) | Reconvergencia de rutas BATMAN (s) | Alertas | N alcanzables al final | Cobertura media |
|---|---|---|---|---|---|---|
| `cobertura_edificio` (control) | 0.0 | no aplica | no aplica | 3.10 ± 2.60 | 6 | 1.000 |
| `fallo_redundante` | 0.0 | no aplica | 7.7 ± 3.7 | 16.80 ± 2.44 | 6 | 1.000 |
| `fallo_puente` | 90.0 | 90.0 | 19.4 ± 6.7 | 22.00 ± 1.76 | 6 | 1.000 |
| `fallo_borde` | 0.0 | no aplica | 17.1 ± 9.0 | 11.80 ± 1.69 | 6 | 0.938 |
| `fallo_cascada` | 40.0 | no aplica | no aplica | 20.10 ± 0.32 | 3 | 0.736 |

(240 s simulados, semillas 1-10; la entrega del radio es 0.60 y el TQ
medio, entre 0.32 y 0.36, en todos.)

**Cómo leerlo:**

- **La reconvergencia de rutas sí distingue los fallos:** volver a
  tener rutas frescas tras recuperar un Gateway redundante tarda unos
  8 s; tras recuperar el puente o el borde, de 17 a 20 s, porque sus
  OGM tienen que atravesar más saltos con pérdidas.
- **"Tiempo de reconvergencia" repite el dato de entrada** (90 s en
  `fallo_puente`, el tiempo que G6 estuvo caído), como en el caso 13.
- **En la cascada** la partición dura 40 s y no se "reunifica": termina
  cuando cae G7, el último Gateway del lado aislado. Al final quedan 3
  de 6 Nodos de usuario cubiertos (N2, N5 y N6 dependían de G3, G6 y G7).
- **La cobertura media sí ve la caída del borde.** En `fallo_borde`, N6
  se queda sin cobertura de los 60 a los 150 s; "N alcanzables al
  final" es 6 porque G7 ya volvió, pero la cobertura media es 0.938: un
  Nodo de 6 sin cubrir durante 90 de los 240 s (1 − 90/240/6). En la
  cascada, 0.736. La caída del puente no le quita cobertura a nadie,
  porque los Nodos del piso 3 siguen con su Gateway aunque la malla se
  parta.
- **Las alertas incluyen falsas alarmas** (unas 3 en el control, por
  los enlaces con pérdidas). Cada alerta se apaga cuando vuelve a llegar
  un OGM del Gateway, así que un enlace que parpadea puede alertar
  varias veces.
- **El TQ es bajo (≈ 0.33)** porque las rutas cruzan casi 3 saltos con
  entrega 0.60: el TQ se multiplica salto a salto.

**Con los Gateway móviles (D8).** Los resultados principales son con
nodos fijos (una red de expansión de cobertura es infraestructura
desplegada), pero se repiten con la movilidad `descentralizada`
([`lotes/capitulo5_fallos_movil.json`](../lotes/capitulo5_fallos_movil.json):
los mismos cinco escenarios con `"parametros": {"move_speed": 0.32,
"movilidad": "descentralizada"}`; los archivos fijan `static=true`, y el
parámetro lo pisa):

```bash
python main.py --batch lotes/capitulo5_fallos_movil.json
```

| Experimento | Malla partida (s) | Reconvergencia de rutas BATMAN (s) | Alertas | N alcanzables al final | Cobertura media |
|---|---|---|---|---|---|
| `cobertura_edificio` (control) | 0.0 | no aplica | 6.60 ± 5.56 | 6 | 1.000 |
| `fallo_redundante` | 0.0 | 15.5 ± 9.5 | 14.50 ± 2.92 | 6 | 1.000 |
| `fallo_puente` | 6.2 ± 6.4 | 9.7 ± 7.0 | 14.30 ± 2.71 | 6 | 0.922 ± 0.043 |
| `fallo_borde` | 17.0 ± 53.8 | 30.1 ± 25.5 | 18.30 ± 7.72 | 6 | 0.959 ± 0.024 |
| `fallo_cascada` | 6.2 ± 6.4 | 4.3 ± 4.0 (5 de 10) | 17.20 ± 2.82 | 4 ± 1 | 0.826 ± 0.054 |

La entrega del radio es 0.60 y el TQ medio 0.34–0.36, igual que con
nodos fijos. Lo que cambia es la respuesta al fallo: los Gateway
sobrevivientes se reubican, así que la malla partida por la caída del
puente pasa de 90 s a 6.2 s, y la cascada deja 4 de 6 Nodos cubiertos
(3 con nodos fijos) y una cobertura media de 0.826 (0.736). El costo son
más alertas (14–18, contra 12–22 con fijos, pero 6.6 en el control
contra 3.1) por los enlaces que parpadean al moverse.

**Tablas y figuras para el documento.** Con la salida de este lote y la
de `lotes/movilidad.json` (caso 11) en `reportes/`:

```bash
python -m analysis.capitulo5
```

Toma el último lote de cada uno, o los que se le pasen con `--fallos`,
`--movilidad` y `--fallos-movil` (este último, la variante con Gateway
móviles de arriba, si existe), y escribe en `Plantilla/` lo que el
Capítulo 5 incluye con `\input{}` y `\includegraphics{}`:
- las tablas `MainMatter/Cap5/tablas/fallos.tex`, `calidad.tex`,
  `fallos_movil.tex`, `calidad_movil.tex` y `movilidad.tex` (esta última
  compara los tres modos de movilidad: etiquetas `tab:cap5-fallos`,
  `tab:cap5-calidad`, `tab:cap5-fallos-movil`, `tab:cap5-calidad-movil` y
  `tab:cap5-movilidad`);
- las figuras `Images/Cap5/cobertura_tiempo.pdf` (cobertura en el
  tiempo, con las caídas sombreadas), `comparacion_fallos.pdf` y
  `movilidad.pdf`.

No corre simulaciones: las cifras son las del `resumen.json` del lote.
Con `"figuras": true` en el lote, además, cada corrida guarda su figura
de 6 paneles (`analisis_red.png`) en `reportes/`. Con esa opción las
cifras salen idénticas: se verificó.

---

## 5. Dónde quedan los resultados y cómo leerlos

`reportes/` se crea **en el directorio desde el que corres**
`main.py`; por eso conviene correr siempre desde la raíz del repo. Está
en `.gitignore`.

```
reportes/
├── base_<fecha_hora>/                  ← una corrida (ventana o --headless)
│   ├── analisis_red.png                ← figura de 6 paneles
│   ├── reporte.csv                     ← serie temporal, una fila cada 0.5 s
│   ├── reporte.json                    ← configuración + resumen + serie + eventos
│   └── reporte.txt                     ← resumen legible y cronología de eventos
└── lote_<nombre>_<fecha_hora>/         ← un lote (--batch)
    ├── resumen.txt                     ← media ± desviación por escenario
    ├── resumen.csv                     ← lo mismo, una fila por escenario
    ├── resumen.json
    ├── corridas.csv                    ← una fila por corrida
    └── <etiqueta>/semilla_<n>/         ← los reportes de cada corrida
```

- **Para tablas del documento:** `resumen.csv`, con
  `<métrica>_media`, `<métrica>_desv` y `<métrica>_n`.
- **Para gráficos de dispersión o boxplots:** `corridas.csv`, con un
  valor por semilla.
- **Para seguir una corrida en el tiempo:** su `reporte.csv`, o la
  figura (con `"figuras": true` en el lote, cada corrida guarda la
  suya).
- **Para ver una corrida del lote en la ventana:** su etiqueta y su
  semilla alcanzan. Por ejemplo, la semilla 4 de `base`:
  `python main.py --escenario base --seed 4` (más `--static` si la
  entrada del lote lo tenía). Sin ventana y con la misma duración que
  el lote, `--headless --duracion 200` da exactamente las métricas de
  esa fila de `corridas.csv`.

**Tres cosas a tener en cuenta al interpretar** (detalle en
"Limitaciones conocidas" de [`arquitectura.md`](arquitectura.md)):

1. **El TQ es la calidad de las rutas según BATMAN**: la fracción de
   OGM recibidos de las últimas 16 secuencias, multiplicada salto a
   salto. El "TQ medio" vale 0 mientras no hay rutas, así que también
   pesa cuánto tiempo las hubo. La **tasa de entrega del radio** mide el
   medio directamente, sin pasar por el protocolo.
2. **"Tiempo de reconvergencia: no aplica"** es lo normal con la
   movilidad actual: ninguna partición se reunifica en los escenarios
   predefinidos (el Gateway que se separa no vuelve). Ojo: esa métrica
   mide cuánto duró la partición *física*, no cuánto tardó BATMAN en
   volver a tener rutas; para eso está "Reconvergencia de rutas BATMAN"
   (caso 13).
3. **Particiones, componentes y nodos alcanzables** se miden sobre los
   enlaces de radio (hay camino si los nodos están en alcance), no
   sobre las tablas de rutas de BATMAN.

---

## 6. Problemas frecuentes

| Lo que ves | Qué pasa |
|---|---|
| `ModuleNotFoundError: No module named 'numpy'` | El entorno virtual no está activado: `source venv/bin/activate`. |
| `main.py: error: --duracion sólo aplica con --headless o --inspect` | En la ventana la simulación dura hasta que la cierras; agrega `--headless` o `--inspect`. |
| `main.py: error: --batch no se combina con --seed: …` | En un lote, semillas, duración, escenarios y `static` van dentro del archivo. |
| `Error en archivo de lote: …: clave desconocida 'semilla' (válidas: …)` | Una clave mal escrita; aquí era `semillas`. |
| `Error en archivo de lote: escenario 'no_existe': escenarios/no_existe.txt: archivo no encontrado` | Las rutas de `config` son relativas al directorio desde el que corres: corre desde la raíz del repo. |
| `Error en archivo de lote: …: etiqueta repetida 'base' — usa "etiqueta" …` | Dos entradas del mismo escenario necesitan etiquetas distintas. |
| `Error en archivo de escenario: …: nodo 2 en (45.0, 5.0) queda fuera del edificio [0,40.0]x[0,30.0]` | Coordenadas fuera del edificio. |
| `Error en archivo de escenario: …: se requiere al menos un nodo con role 'G' (Gateway)` | Falta un Gateway. |
| `Error en archivo de escenario: …: id de nodo duplicado: 1` | Dos nodos con el mismo `id`. |
| `Error: La cantidad de Gateways debe ser menor que el total de nodos.` | Con `-n`/`-g`, `-g` tiene que ser menor que `-n`. |
| La ventana no abre (sin pantalla, por SSH) | Usa `--headless` o `--inspect`: no necesitan pantalla. |
| No encuentro los reportes | Están en `reportes/`, dentro del directorio desde el que corriste el comando. |
