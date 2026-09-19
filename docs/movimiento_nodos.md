# Por qué los nodos se movían y "se unían" entre sí

Este documento explica un comportamiento que se observó al correr el
simulador: los nodos (sobre todo los Gateway) parecían converger todos
hacia el mismo punto en vez de quedarse en su posición inicial. No era
un bug — es el modelo de movimiento que trae el simulador por defecto —
pero no estaba documentado en ningún lado, así que quedaba la duda.

## Qué se observaba

Al correr `python main.py -n 3 -g 2` (o cualquier escenario), con el
tiempo los nodos Gateway (`G`) se acercaban y terminaban agrupados
cerca de un mismo nodo de usuario (`N`), en vez de quedarse donde
habían arrancado.

## Por qué pasaba

El modelo de movimiento vive en [`sim/sim_node.py`](../sim/sim_node.py),
método `SimNode.move()`. Ahí cada nodo se mueve según su `role`:

- **`role == "N"`** (Nodo de usuario): casi estático. Solo hace un
  micro-movimiento aleatorio (`random.gauss(0, 0.05)`) — se queda
  prácticamente en el mismo sitio.
- **`role == "G"`** (Gateway): en cada paso busca el nodo `N` más
  cercano y camina hacia él con `_move_avoiding()`, acercándole
  cobertura.

Es decir, el movimiento de los `G` nunca fue aleatorio ni un bug de
física — es una regla de seguimiento: cada Gateway se desplaza hacia
el Nodo de usuario que tiene más cerca.

La regla viene del prototipo anterior, pensado como búsqueda y rescate
(los Gateway eran "rescatistas" que iban a "hallar supervivientes" y,
al hallar uno, pasaban al siguiente). Con el enfoque actual de Red de
Expansión de Cobertura ese mecanismo de hallazgo se retiró del código;
la regla de seguimiento quedó tal cual.

## Cómo decide cada Gateway a cuál nodo ir

La selección del objetivo está en este fragmento de `move()`:

```python
objetivos = [s for s in self.sim.nodes.values()
             if s.role == 'N']
if objetivos:
    tgt = min(objetivos, key=lambda s: self.dist_xy(s.x, s.y))
    tx, ty = tgt.x, tgt.y
```

Regla simple: de todos los nodos `N` (vivos o caídos), cada Gateway
elige el **más cercano a sí mismo** en distancia euclidiana
(`dist_xy`). No hay coordinación entre Gateways ni reparto de
objetivos — cada uno corre este cálculo de forma independiente.

Esto explica por qué "se unían": si dos o más Gateways tienen el mismo
nodo `N` como el más cercano (típico cuando hay pocos `N` respecto a
`G`, como con `-n 3 -g 2`, donde solo hay un `N`), **todos** caminan
hacia ese mismo punto y terminan agrupados ahí — y ahí se quedan,
porque el objetivo no cambia mientras ese `N` siga siendo el más
cercano. Solo si no existe ningún `N` los Gateways patrullan con pasos
aleatorios pequeños.

La única excepción es el evento `wander` de un escenario (lo usa
`rescatista_perdido`): el Gateway indicado camina hacia la esquina
(38, 2) del edificio hasta el segundo `until`, y a partir de ahí vuelve
a la regla de seguimiento — o sea, va hacia el `N` que le quede más
cerca *desde donde terminó*, que no tiene por qué ser el del grupo del
que se alejó.

## Cómo se solucionó: la flag `--static`

La solución no fue "arreglar" el movimiento (es el modelo de movilidad
por defecto), sino agregar una forma explícita de **desactivarlo**
cuando lo que se quiere es una topología fija — por ejemplo, para
probar solo el enrutamiento BATMAN sin que la posición cambie con el
tiempo.

Se agregó un corte temprano en `move()`:

```python
def move(self, now):
    if not self.alive:
        return

    if self.sim.cfg.get('move_speed', 0) <= 0:
        # move_speed=0: nodos estáticos, sin persecución ni jitter.
        self._record_history()
        return

    if self.role == 'N':
        ...
```

Si `move_speed` es `0`, el nodo no persigue nada ni aplica el jitter
aleatorio — se queda exactamente en su posición inicial. Antes de este
cambio, poner `move_speed` bajo (o en `0`) solo hacía que el Gateway
caminara más lento hacia el objetivo, pero el "jitter" aleatorio de
`_move_avoiding()` seguía aplicándose y el nodo terminaba haciendo una
pequeña caminata aleatoria (un paseo browniano), no quedándose quieto
de verdad.

Esto se expone de cuatro formas, todas equivalentes por debajo (todas
terminan poniendo `move_speed=0`):

1. **Flag de `main.py`**: `--static` en la línea de comandos.
   ```bash
   python main.py --escenario base --static
   python main.py -n 3 -g 2 --static
   ```
2. **Escenario JSON**: `"protocol": {"move_speed": 0}`.
3. **Escenario `.txt`**: `static=true` dentro de la sección
   `[protocol]` (ver el [README](../README.md#formato-txt-equivalente-al-json-más-fácil-de-editar-a-mano)
   para el formato `.txt` completo).
4. **Lote (`--batch`)**: `"static": true` en una entrada del archivo
   de lote (ver el [README](../README.md#archivo-de-lote---batch)).

La flag `--static` de la línea de comandos tiene prioridad sobre lo
que diga el archivo de escenario, porque se aplica *después* de cargar
la configuración (ver `main.py`) — puede forzar el modo estático
aunque el archivo diga `static=false`, pero no puede forzar movimiento
si el archivo ya puso `static=true`.

## Otra opción: repartir los Gateway (`movilidad=repartir`)

`--static` evita que los Gateway se junten quitándoles el movimiento. La
movilidad `repartir` los deja moverse pero cambia la regla: **un Gateway
por Nodo de usuario**. En cada paso se emparejan los Gateway y los Nodos
de usuario vivos de forma voraz: primero el par más cercano de todos,
después el más cercano entre los que quedan libres, y así sucesivamente.
Cada Nodo de usuario queda con a lo sumo un Gateway yendo hacia él (lo
hace `Simulation.objetivo_repartido()`, en
[`sim/engine.py`](../sim/engine.py)).

- Si hay más Gateway que Nodos de usuario, los que sobran se quedan
  quietos donde están, de relevo.
- Los Nodos de usuario caídos no se asignan: no hace falta cubrirlos.
- El Gateway que está haciendo su `wander` no participa mientras dure,
  así su nodo queda libre para otro.
- El emparejamiento se recalcula en cada paso con las posiciones del
  momento, así que se adapta si un nodo cae o si se agrega uno (tecla
  `A`).

`seguir` sigue siendo el valor por defecto, así que los resultados de
siempre no cambian. Se elige de las mismas formas que el modo estático,
y el flag tiene prioridad sobre el archivo:

1. **Flag de `main.py`**: `python main.py --escenario denso --movilidad repartir`
2. **Escenario JSON**: `"protocol": {"movilidad": "repartir"}`.
3. **Escenario `.txt`**: `movilidad=repartir` en `[protocol]`.
4. **Lote (`--batch`)**: `"movilidad": "repartir"` en una entrada.

**Qué cambia.** El caso que lo motivó es `denso`: con `seguir`, los 8
Gateway tienen a N5 como el nodo más cercano, a los 40 s están los 8
encima de él y la mitad derecha del edificio queda sin cobertura (3.2 de
los 6 Nodos de usuario alcanzables, de media). Con `repartir` se
reparten y quedan cubiertos los 6 en todas las semillas. A cambio, la
malla de Gateways se estira más allá del alcance de radio: en 7 de 10
semillas termina partida en dos grupos, y la tasa de entrega del radio
baja de 0.756 a 0.352, porque los enlaces son más largos. Es el
compromiso entre cobertura y conectividad. Ninguno de los dos modelos es
"el correcto": cuál usar depende de qué se quiera evaluar. Un tercer
camino, todavía por diseñar, sería repartir sin que la malla se parta,
por ejemplo usando a los Gateway que sobran como relevos entre grupos.
La comparación en los 5 escenarios está en el caso 11 de la
[guía de ejecución](guia_ejecucion.md).
