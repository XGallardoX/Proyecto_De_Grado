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

## 2. Los cuatro modos de un vistazo

| Quiero… | Comando | Qué deja |
|---|---|---|
| Ver la red en vivo e interactuar | `python main.py --escenario base` | Una ventana; al cerrarla, figura y reportes en `reportes/` |
| Una corrida sin ventana | `python main.py --headless --escenario base --seed 1` | Un resumen en pantalla y `reportes/base_<fecha_hora>/` |
| Ver el estado interno del protocolo | `python main.py --inspect --escenario particion --duracion 30` | Texto por pantalla, sin archivos |
| Resultados con varias semillas | `python main.py --batch lotes/ejemplo.json` | Un resumen agregado y `reportes/lote_<nombre>_<fecha_hora>/` |

Para elegir la red hay tres opciones: `--escenario <nombre>` (uno de los
5 predefinidos), `--config <archivo>` (un `.json` o `.txt` propio) o
`-n N -g G` (N nodos al azar, G de ellos Gateways). Encima de cualquiera
se puede agregar `--static` (los nodos no se mueven) y `--seed N` (la
corrida se repite igual). `--duracion` fija los segundos simulados sin
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
Gateway (`G`) se mueven hacia el Nodo de usuario (`N`) más cercano,
salvo que se use `--static`
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
semillas, 200 s, con movilidad; detalle en el [caso 7](#caso-7--los-5-escenarios-con-10-semillas)):

- **`base`**: la malla de Gateways queda unida. Los cuatro caminan
  hacia N2 (el de la esquina (5, 5)) y lo cubren; N1 y N3 quedan fuera
  de alcance (1.2 nodos alcanzables de media). En 1 de las 10 semillas
  un Gateway sigue a otro nodo y se separa del grupo.
- **`colapso_progresivo`**: los Gateway caen uno tras otro y al final
  queda sólo G1. Cada caída la detectan los que siguen vivos unos 30 s
  después, que es el `timeout` (5.3 alertas de media).
- **`particion`**: 2 componentes los 200 s y ninguna alerta. Los dos
  grupos nunca llegaron a oírse, y `FaultManager` sólo vigila a los
  Gateway que alguna vez oyó.
- **`rescatista_perdido`**: hacia t ≈ 41 s G4 sale del alcance del
  resto y la malla queda partida el resto de la corrida (159 s). La
  primera alerta llega hacia los 67 s y G4 no vuelve. Un detalle
  interesante: al final se alcanzan los 3 nodos de usuario (más que en
  `base`), porque G4 queda cubriendo a N1 y N3 aunque esté separado de
  la malla. Es un ejemplo de cobertura contra conectividad.
- **`denso`**: la malla nunca se parte; alcanza 3.2 de los 6 nodos de
  usuario de media.

---

## 4. Casos

Cada caso tiene un objetivo, el comando y lo que deberías ver. Los
casos 1 y 2 son con la ventana; el resto, sin ella. Los archivos que
usan los casos 4, 9 y 10 están en [`escenarios/casos/`](../escenarios/casos/)
(cada uno explica en su cabecera de qué caso es), y
[`lotes/casos.json`](../lotes/casos.json) corre los casos 9 y 10 de una
vez.

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

### Caso 2 — Mandar mensajes por la malla

**Objetivo:** ver que un mensaje llega por cualquier camino que exista
y que sólo falla si la malla está partida.

```bash
python main.py --escenario particion
```

- Pulsa `M`, escribe `G1>G2 hola` y `Enter`: llega en 1 salto, porque
  G1 y G2 están en el mismo grupo.
- Pulsa `M` y escribe `G1>G3 hola`: el log dice
  `Mensaje G1→G3 no entregado: no existe ningún camino en la malla
  (partición de red).`
- `G1>N1 hola` también llega: N1 está cerca de ese grupo.

Para ver un mensaje de varios saltos:

```bash
python main.py --config escenarios/casos/cadena.txt
```

Ahí `G1>N3 hola` llega en 3 saltos, vía G1 → N1 → N2 → N3, y se ve
viajar salto a salto. El formato es `emisor>destino texto`; sin letra
se asume Gateway (`1>2` es `G1>G2`).

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
  TQ medio de rutas                     : 0.990
  Saltos medios por ruta                : 1.25
  Tasa de entrega del radio             : 0.667
  Componentes de la malla al final      : 1
  Nodos de usuario alcanzables al final : 1
  Gateways vivos al final               : 4
  Episodios de partición                : 0
  Tiempo con la malla partida (s)       : 0.0
  Tiempo de reconvergencia (s)          : no aplica
  Alertas de gateway perdido            : 0
  Primera alerta (s)                    : no aplica
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
    N1       N1              1     1.00  15   0.5s
    N2       N1              2     1.00  13   8.5s
    N3       N1              3     1.00  14   5.5s
```

Para llegar a N3, G1 manda por N1 (su siguiente salto) y la ruta tiene
3 saltos. Fíjate en que el TQ dice 1.00 aunque cada enlace entrega
menos de la mitad de los paquetes (tasa de entrega 0.45). Es la
limitación conocida del TQ, explicada en la [sección 5](#5-dónde-quedan-los-resultados-y-cómo-leerlos).
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
entrega 0.348 y los 6 Nodos de usuario alcanzables al final. Para
guardar una red aleatoria como escenario se usa un `.txt` con
`mode=random`, `n_nodes=8` y `n_gateways=2` en `[nodes]`.

> En este modo (`-n`/`-g` sin archivo), `battery_drain` vale 0.02 en
> vez del 0.030 por defecto (viene del repo madre). Un `.txt` con
> `mode=random` usa el 0.030.

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
| `base` | 0.864 ± 0.033 | 1.10 ± 0.32 | 1.20 ± 0.63 | 4.00 | 16.5 ± 52.2 | 0.60 ± 1.90 | 55.0 (1 de 10) |
| `colapso_progresivo` | 0.799 ± 0.020 | 1.00 | 1.00 | 1.00 | 4.9 ± 15.5 | 5.30 ± 0.95 | 109.0 ± 19.0 |
| `particion` | 0.960 ± 0.005 | 2.00 | 2.00 | 4.00 | 200.0 | 0.00 | no aplica |
| `rescatista_perdido` | 0.742 ± 0.062 | 2.00 | 3.00 | 4.00 | 159.2 ± 0.3 | 6.20 ± 0.63 | 67.5 ± 2.6 |
| `denso` | 0.756 ± 0.032 | 1.00 | 3.20 ± 1.55 | 8.00 | 0.0 | 0.00 | no aplica |
| `base` fijo (`base_static`) | 0.716 ± 0.006 | 1.00 | 0.00 | 4.00 | 0.0 | 0.00 | no aplica |

(Donde no hay "±", la desviación es 0.) El TQ medio sale entre 0.99 y
1.0 en todos, y el tiempo de reconvergencia, "no aplica" en todos. Las dos
cosas son esperables con el código actual: ver la
[sección 5](#5-dónde-quedan-los-resultados-y-cómo-leerlos).

Para tu propio lote, copia `lotes/ejemplo.json` y cambia la lista. El
formato completo está en el README ("Archivo de lote").

### Caso 8 — Movilidad contra nodos fijos

**Objetivo:** medir qué aporta que los Gateway se muevan.

Sale del mismo lote del caso 7, que corre `base` dos veces: con
movilidad y con `"static": true`.

| | Entrega del radio | N alcanzables al final |
|---|---|---|
| `base` (se mueven) | 0.864 ± 0.033 | 1.20 ± 0.63 |
| `base_static` (fijos) | 0.716 ± 0.006 | 0.00 |

Fijos en el piso 3, los Gateway no llegan a ningún Nodo de usuario.
Moviéndose, se acercan a N2 y lo cubren, y de paso los enlaces quedan
más cortos, lo que sube la entrega. Para comparar así cualquier
escenario, agrega al lote una entrada con `"static": true`.

### Caso 9 — Alcance de radio contra cobertura

**Objetivo:** barrer un parámetro (`rango_comm`) y ver su efecto.

```bash
python main.py --batch lotes/casos.json
```

Este lote corre los casos 9 y 10 juntos (100 simulaciones, unos 5 s).
Para el alcance compara `base` con nodos fijos a 16 m (el valor por defecto),
20 m y 24 m (`escenarios/casos/base_rango20.txt` y `base_rango24.txt`):

| Alcance | N alcanzables al final | Entrega del radio | Saltos medios |
|---|---|---|---|
| 16 m (`alcance_16m`) | 0 | 0.716 ± 0.006 | 1.18 ± 0.02 |
| 20 m (`alcance_20m`) | 1 | 0.688 ± 0.003 | 1.35 ± 0.06 |
| 24 m (`alcance_24m`) | 3 | 0.515 ± 0.004 | 1.72 ± 0.09 |

Más alcance da más cobertura (de 0 a 3 nodos de usuario), pero a costa
de enlaces más largos y débiles: la entrega baja y las rutas tienen más
saltos. Con los nodos fijos, la cobertura depende sólo de la geometría,
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
`colapso_timeout60.txt`).

| Timeout | Primera alerta, 9 de 10 semillas | Media de las 10 | Alertas |
|---|---|---|---|
| 15 s | 100 s | 94.0 ± 19.0 | 6.30 ± 0.95 |
| 30 s | 115 s | 109.0 ± 19.0 | 5.30 ± 0.95 |
| 60 s | 145 s | 140.0 ± 15.8 | 3.10 ± 0.32 |

La latencia de detección es el `timeout` más lo que falte para el
siguiente chequeo (hasta 5 s). La semilla 4 se sale del patrón (40, 55
y 95 s): ahí G4 se había separado del grupo antes de morir, y lo que se
detecta es esa separación.

Con un timeout largo también hay menos alertas, porque algunas caídas
ya no llega a detectarlas nadie. Con 60 s, G3 muere (124.5 s) antes de
que le venza el timeout para G4, y la caída de G2 (173.5 s) se
detectaría después de los 200 s que dura la corrida.

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

1. **El TQ vale 1.0 en toda ruta que existe.** El router no registra
   los OGMs perdidos, así que el "TQ medio" mide cuánto tiempo hubo
   rutas, no su calidad. Para la calidad de los enlaces, usa la **tasa
   de entrega del radio**.
2. **"Tiempo de reconvergencia: no aplica"** es lo normal con la
   movilidad actual: ninguna partición se reunifica en los escenarios
   predefinidos (el Gateway que se separa no vuelve).
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
| El TQ sale ≈ 1.0 siempre | Es la limitación conocida del router, no un error de tu corrida (ver la sección 5). |
