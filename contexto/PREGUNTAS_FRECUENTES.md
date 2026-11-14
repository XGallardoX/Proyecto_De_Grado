# Preguntas frecuentes: cómo funciona el simulador

Respuestas cortas y explícitas a las dudas que van saliendo sobre qué
hace el programa y cómo funciona. Cada pregunta se verificó contra el
código; entre paréntesis queda dónde mirar. Las preguntas nuevas se
agregan al final.

**Índice**

1. [¿Qué hace el programa?](#1-qué-hace-el-programa)
2. [¿Cómo se corre?](#2-cómo-se-corre)
3. [¿Qué escenarios hay y por qué?](#3-qué-escenarios-hay-y-por-qué)
4. [¿Cuál es la arquitectura?](#4-cuál-es-la-arquitectura)
5. [¿Qué opciones tiene la interfaz web?](#5-qué-opciones-tiene-la-interfaz-web)
6. [¿Es un simulador de rescatistas?](#6-es-un-simulador-de-rescatistas)
7. [¿Un nodo cae solo si se le acaba la batería?](#7-un-nodo-cae-solo-si-se-le-acaba-la-batería)
8. [¿Qué son OGM, beacon y TTL?](#8-qué-son-ogm-beacon-y-ttl)
9. [¿Hasta dónde llega un OGM y un beacon?](#9-hasta-dónde-llega-un-ogm-y-un-beacon)
10. [¿Qué tipos de paquete de datos hay?](#10-qué-tipos-de-paquete-de-datos-hay)

---

## 1. ¿Qué hace el programa?

Simula una **red de radios que se organizan solos**, sin una central que
mande, para medir qué cobertura da y cómo se adapta cuando algunos
fallan o se mueven.

- Los **Gateways** (`G`) son los radios que forman la malla y se hablan
  entre sí.
- Los **Nodos de usuario** (`N`) son quienes necesitan cobertura y se
  conectan a los Gateways.
- Los radios corren **BATMAN**, un protocolo de redes malladas. El
  simulador no lo imita: corre el **código real** (`mesh/router.py`).
  Lo que se simula es el mundo físico: posiciones, alcance de la señal y
  paquetes perdidos.

La pregunta que contesta es: *¿qué pasa con la cobertura y la conexión
si un radio falla?*

## 2. ¿Cómo se corre?

Desde la raíz del repo, con el entorno virtual (en Windows,
`venv\Scripts\python`).

| Quiero… | Comando |
|---|---|
| Verlo en una ventana | `python main.py --escenario base` |
| Verlo en el navegador | `python main.py --web --escenario base` |
| Correr sin ventana y obtener un resumen | `python main.py --headless --escenario base --seed 1` |
| Mirar el estado interno del protocolo | `python main.py --inspect --escenario particion --duracion 30` |
| Repetir con muchas semillas y promediar | `python main.py --batch lotes/ejemplo.json` |

Opciones que se agregan encima: `--seed N` (la corrida sale siempre
igual), `--static` (nadie se mueve), `--movilidad seguir|repartir|descentralizada`,
`--duracion S`, `--trafico K` (K flujos de datos entre usuarios) y
`--param tipo_paquete=udp|icmp|tcp` (el tipo de paquete de esos flujos;
ver la [pregunta 10](#10-qué-tipos-de-paquete-de-datos-hay)).
Los resultados quedan en `reportes/`. Guía completa con casos:
`docs/guia_ejecucion.md`.

## 3. ¿Qué escenarios hay y por qué?

Los cinco predefinidos usan el mismo edificio (40 × 30 m, 3 pisos):

| Escenario | Qué plantea |
|---|---|
| `base` | 4 Gateways juntos arriba y 3 usuarios abajo: el caso de referencia |
| `colapso_progresivo` | Las baterías se acaban una a una: cómo se degrada la red |
| `particion` | Alcance corto y dos parejas en esquinas opuestas: la malla arranca partida |
| `rescatista_perdido` | Un Gateway se aleja y pierde contacto: cobertura contra conectividad |
| `denso` | 8 Gateways y 6 usuarios: qué pasa cuando hay muchos radios |

Además: `campo_abierto` (un terreno de 120 × 80 m con usuarios que
caminan), `escenarios/casos/` (ejemplos de la guía) y `escenarios/fallos/`
(las pruebas del Capítulo 6 de la tesis: un mismo despliegue de 7
Gateways con distintos fallos). Se pueden crear escenarios propios en `.json` o `.txt`
(`--config`) o con el editor de la interfaz web.

## 4. ¿Cuál es la arquitectura?

```
main.py            puerta de entrada: lee las opciones y arma la simulación
├── mesh/          el protocolo BATMAN real (rutas, TQ, detección de fallos)
├── sim/           el mundo simulado: nodos, radio con pérdidas, movilidad,
│                  eventos programados y plano de datos
├── analysis/      métricas, figuras, reportes, lotes y tablas del Capítulo 6
└── web/           servidor local + interfaz en el navegador
```

(El módulo que genera esas tablas se sigue llamando
`analysis/capitulo5.py` y las deja en `Plantilla/MainMatter/Cap5/`: son
nombres de antes de renumerar. En el PDF, los resultados son el
Capítulo 6.)

Una corrida avanza en pasos de 0.5 s: `sim/` mueve los nodos y entrega
los mensajes con pérdidas, `mesh/` decide las rutas dentro de cada nodo
y `analysis/` mide todo mientras pasa. Detalle: `docs/arquitectura.md`.

## 5. ¿Qué opciones tiene la interfaz web?

Se abre con `python main.py --web`. Zonas:

- **Barra lateral:** Simular, Editor de escenarios, ⚗ Laboratorio,
  Exportar; abajo, modo presentación, tema claro/oscuro, atajos y
  terminar sesión.
- **Barra superior:** escenario, semilla, reiniciar, pausa, un paso,
  velocidad (0.25× a 8× y "máxima"), reloj y avisos (red partida,
  intervenciones, error).
- **Mapa:** Gateways como círculos y usuarios como rombos. Clic
  selecciona, arrastrar mueve, clic derecho abre el menú. Capas:
  enlaces, paquetes, estelas, beacons, alcance, grupos, vigilancia,
  cobertura, fuerzas y críticos.
- **Herramientas del mapa:** "ver como este nodo" (`L`: solo lo que ese
  nodo sabe), anillos de vigilancia, "OGM de" (`O`) y compositor de
  mensajes (`M`).
- **Panel lateral:** Nodo (rutas y vecinos), Red (matriz de
  conocimiento N×N), Tráfico (enviar paquetes UDP, ICMP o TCP y ver qué
  pasó con cada uno; [pregunta 10](#10-qué-tipos-de-paquete-de-datos-hay)),
  Métricas (gráficas en vivo), Real / modelo, Inspector y Parámetros
  (ajustes en vivo con "restaurar").
- **Editor de escenarios:** coloca nodos con clic, edita medio,
  protocolo, movilidad y eventos; valida y guarda en `escenarios/`.
- **Laboratorio:** corre un lote con varias semillas, con progreso,
  tabla y gráfica. Da los mismos números que la terminal.
- **Exportar:** `reportes/<escenario>_<fecha>/` más `sesion_web.json`
  con la semilla, las intervenciones y el comando equivalente.

Detalle: README ("Versión de escritorio") y `docs/interfaz_web.md`.

## 6. ¿Es un simulador de rescatistas?

No. Nació así (agosto), pero hoy es un simulador de **cobertura y
adaptabilidad en redes descentralizadas** (el título de la tesis dice
"adaptabilidad", no "resiliencia", por indicación del tutor). Los
resultados principales del Capítulo 6 se miden con nodos fijos, y se repiten con Gateways móviles
que deciden solos con lo que oyen. Historia completa y decisiones:
[`HISTORIA_ENCUADRE.md`](HISTORIA_ENCUADRE.md).

## 7. ¿Un nodo cae solo si se le acaba la batería?

No: hay cuatro vías.

| Vía | Cómo ocurre | Dónde |
|---|---|---|
| Batería | Cada paso resta `battery_drain × 0.5 s`; al llegar a 0 cae ("sin batería") | `sim/sim_node.py:116-123` |
| Evento programado | El escenario trae `fail <nodo> <t>` y el motor lo aplica en ese instante | `sim/engine.py:356` |
| Caída elegida al llegar el momento | `fail_azar` tumba un nodo vivo al azar; `fail_critico` el que más separa la malla | `sim/engine.py:363-383` |
| Manual | Tecla `F`, menú del nodo o comando web | `sim/engine.py:386` |

Las tres últimas terminan en `fail_node`, que lo marca caído y le pone
la batería en 0. Solo cambia el texto del log ("caído (programado)",
"(al azar)", "(dirigido)" o "(manual)").

- **Gasto por defecto:** 0.030 %/s un Gateway y 0.012 %/s un usuario. En
  una corrida de 200 s casi nunca se agota; solo en escenarios hechos
  para eso, como `colapso_progresivo`.
- **No son una caída:** un nodo que sale de alcance o cuyos paquetes se
  pierden *parece* caído a sus vecinos (alerta) pero sigue vivo.
  Eliminar un nodo (`D`) lo saca de la simulación, no lo deja caído.
- Un nodo caído vuelve con `recover`; conserva su secuencia de OGM (no es
  un arranque en frío).

## 8. ¿Qué son OGM, beacon y TTL?

Son los tres conceptos con que los radios se enteran unos de otros.

### OGM (Originator Message)

El mensaje de **"aquí estoy"** de BATMAN. Cada nodo emite uno propio cada
`batman_cada` segundos (4 s por defecto) y los demás lo **reenvían**, así
que se propaga por toda la malla como una inundación.

- Lleva: quién lo originó (`origin_id`), un número de secuencia
  creciente (`seq`), el TTL, el camino recorrido (`path`), el TQ
  acumulado (`tq`) y las alertas de fallo que conoce.
- Sirve para tres cosas: **saber que el origen existe y está vivo**,
  **construir la tabla de rutas** (por qué vecino se llega a cada
  destino) y **medir la calidad del enlace** (el TQ).
- **Calidad (TQ):** cada nodo cuenta cuántos OGM de cada vecino le
  llegaron entre los últimos esperados. Si se pierden, el TQ baja. El TQ
  de una ruta es el producto de los TQ de sus saltos, y se elige la ruta
  de mayor TQ.
- Cuando un OGM nuevo llega, el nodo lo reenvía **una sola vez**, con
  el TTL bajado en 1, el nodo agregado al camino y el TQ multiplicado por
  la calidad del enlace por donde llegó. Las copias repetidas o viejas
  se descartan.
- Un OGM nuevo de un origen también prueba que está vivo, así que
  **apaga su alerta** de caída (`sim/sim_node.py:190-206`).

### Beacon (BCN)

El mensaje de **"hola, soy yo"** de un solo salto: se anuncia ante los
vecinos directos. Cada nodo emite uno cada `beacon_cada` segundos (2 s
por defecto).

- Lleva: su id, rol, batería, carga, reputación, un texto y, desde el
  paso 9, su **posición** (se supone un GPS o UWB de interiores).
- **No se reenvía:** solo lo oye quien está al alcance de la radio.
- Sirve para **descubrir vecinos directos**, mantener fresca su "última
  vez visto" y **dar la posición** que usa la movilidad
  `descentralizada` para decidir hacia dónde moverse.
- En el mapa se ve como un pulso alrededor del nodo (capa "Beacons").

### TTL (Time To Live)

El **número de saltos que le quedan a un mensaje** antes de descartarse.
Evita que un mensaje circule para siempre.

- Un OGM sale con `ttl = 6` (parámetro `ttl`, entre 1 y 20) y cada nodo
  que lo reenvía le resta 1. Con `ttl <= 1` ya no se reenvía.
- Por eso un OGM **no llega más lejos de 6 saltos**: un nodo a más de 6
  saltos del origen nunca se entera de él. En el simulador, con redes de
  pocos nodos, casi nunca limita.
- Los paquetes de datos (el plano de datos) tienen su propio TTL, de 50
  saltos, como batman-adv.

### Cómo se relacionan

| | OGM | Beacon |
|---|---|---|
| Alcance | Toda la malla (hasta el TTL) | Solo vecinos directos |
| Frecuencia | Cada 4 s (`batman_cada`) | Cada 2 s (`beacon_cada`) |
| Se reenvía | Sí, una vez por nodo | No |
| Para qué | Rutas y TQ | Vecinos, batería y posición |
| TTL | Sí | No aplica |

El detector de fallos de un Gateway se apoya en ambos: cada 5 s revisa a
qué Gateways lleva más de `timeout` segundos (30 por defecto) sin oír, y
lo que refresca esa "última vez visto" son los OGM y los beacons.

## 9. ¿Hasta dónde llega un OGM y un beacon?

Los dos se emiten con el mismo mecanismo (`RadioMedium.broadcast`,
`sim/radio.py:50`). La diferencia está en lo que hace quien los recibe.

**Una emisión, tanto de OGM como de beacon, llega a todos los nodos
vivos que estén dentro del alcance de la radio del emisor**, no solo al
más cercano. A cada uno le llega con una probabilidad (la fiabilidad del
enlace) que baja con la distancia y con los pisos de por medio:

```
fiabilidad = 1 − falloff·(distancia / rango_comm) − perdida_base
             (× floor_atten por cada piso de diferencia)
             = 0 si la distancia supera rango_comm
```

Con los valores por defecto (alcance 16 m), un vecino a 2 m casi siempre
recibe el mensaje y uno a 15 m lo recibe pocas veces. Por eso hay
paquetes perdidos aunque el nodo esté "en rango".

### OGM: "toda la malla" es por saltos, con un límite

- El origen lo emite y lo reciben **sus vecinos dentro de su rango**.
- Cada vecino que lo recibe por primera vez **lo vuelve a emitir** desde
  su posición, así que llega a los vecinos *de ese vecino*, y así
  sucesivamente.
- **Sí tiene límite de saltos: el TTL.** Sale con 6 (`ttl`), cada
  reenvío resta 1 y con `ttl <= 1` ya no se reenvía.

Ejemplo, en una fila de nodos `A - B - C - D - E - F - G - H`, cada uno a
alcance solo del siguiente: el OGM de A llega a B (1 salto), C (2), D (3),
E (4), F (5) y G (6). **H nunca se entera de A**, porque está a 7 saltos.

Por eso "toda la malla" quiere decir *todos los nodos alcanzables
encadenando saltos, hasta el TTL*. Un nodo fuera del alcance de todos, o
a más de 6 saltos del origen, no recibe ese OGM.

### Beacon: un solo salto, pero a todos los vecinos en rango

El beacon **no se reenvía**, pero eso no significa que solo llegue al
nodo más cercano. Llega a **todos los vecinos directos**, es decir, a
todos los que estén dentro del alcance de la radio del emisor (cada uno
con su probabilidad). Es como decir "hola" en voz alta: lo oye quien está
lo bastante cerca.

Se puede pensar como una **tarjeta de presentación** que cada nodo reparte
a sus vecinos directos: lleva su id, rol, batería, posición y un texto.
Con ella el vecino sabe que existe, que sigue vivo y dónde está.

| | OGM | Beacon |
|---|---|---|
| Quién lo recibe | Vecinos en rango; los que lo reciben nuevo lo reenvían | Todos los vecinos en rango |
| Se reenvía | Sí, una vez por nodo | No |
| Alcance total | Hasta `ttl` saltos (6) | 1 salto |
| Para qué | Que todos conozcan rutas y calidad | Vecinos directos, batería, posición |

## 10. ¿Qué tipos de paquete de datos hay?

Tres: **UDP, ICMP y TCP** (`sim/datos.py`, desde el 2026-11-13). Los OGM
y los beacons son mensajes del protocolo; estos son los datos que los
usuarios mandan por la malla. Los tres avanzan igual, salto a salto, con
la tabla de rutas del nodo que tiene el paquete. Cambia lo que pasa de
extremo a extremo:

| Tipo | Qué hace | Cuándo cuenta como entregado |
|---|---|---|
| `udp` (por defecto) | Un datagrama de ida, sin confirmación | Si llega al destino |
| `icmp` | Un eco (ping): el destino responde por su propia tabla de rutas | Si la respuesta vuelve al origen |
| `tcp` | El destino confirma y el origen retransmite hasta 3 veces | Si el segmento llega al destino |

- **Son modelos simplificados:** no hay establecimiento de conexión,
  ventanas ni control de congestión. Las retransmisiones de TCP ocurren
  dentro del mismo paso de 0.5 s, así que solo recuperan pérdidas de la
  radio, no una ruta que falta.
- **Cómo se elige el tipo:** en la terminal y en los lotes, con
  `--param tipo_paquete=icmp` (o `"parametros"` en el lote); en un
  escenario, con `tipo=...` en `[traffic]` o en cada flujo; en la
  interfaz web, en la pestaña **Tráfico**.
- **Pestaña Tráfico:** se eligen origen, destino, tipo, cantidad e
  intervalo (con 0 s salen todos de una vez). Muestra las cuentas por
  tipo, los flujos y el recorrido de ida y vuelta de los últimos
  paquetes, con el motivo de cada pérdida.
- **Resultado medido** (`lotes/tipos_paquete.json`, 10 semillas, 6
  flujos en el edificio): TCP entrega 0.924, UDP 0.772 e ICMP 0.646. TCP
  lo consigue con 2.6 veces las transmisiones de UDP (19.39 contra 7.46
  por paquete). ICMP entrega menos porque necesita que lleguen la ida y
  la vuelta.

Caso con su salida esperada: `docs/guia_ejecucion.md`, caso 15.

---

*Agregar nuevas preguntas debajo, con el mismo formato: título numerado,
respuesta corta y dónde mirar en el código o la documentación.*
