# Por qué los nodos se movían y "se unían" entre sí

Este documento explica un comportamiento que se observó al correr el
simulador: los nodos (sobre todo los Gateway) parecían converger todos
hacia el mismo punto en vez de quedarse en su posición inicial. No era
un bug — es el modelo de movimiento tipo "rescate" que trae el
simulador por defecto — pero no estaba documentado en ningún lado, así
que quedaba la duda.

## Qué se observaba

Al correr `python main.py -n 3 -g 2` (o cualquier escenario), con el
tiempo los nodos Gateway (`G`) se acercaban y terminaban agrupados
cerca de un mismo nodo de usuario (`N`), en vez de quedarse donde
habían arrancado.

## Por qué pasaba

El modelo de movimiento vive en [`sim/sim_node.py`](../sim/sim_node.py),
método `SimNode.move()`. Ahí cada nodo se mueve según su `role`:

- **`role == "N"`** (Nodo de usuario): representa a alguien atrapado.
  Solo hace un micro-movimiento aleatorio (`random.gauss(0, 0.05)`) —
  se queda prácticamente en el mismo sitio.
- **`role == "G"`** (Gateway): el simulador lo trata como un
  **rescatista**. En cada paso busca el nodo `N` más cercano que
  todavía no haya sido "encontrado" y camina hacia él con
  `_move_avoiding()`.

Es decir, el movimiento de los `G` nunca fue aleatorio ni un bug de
física — es lógica de búsqueda-y-rescate: los rescatistas van a buscar
supervivientes.

## Cómo decidía cada Gateway a cuál nodo ir

La selección del objetivo está en este fragmento de `move()`:

```python
objetivos = [s for s in self.sim.nodes.values()
             if s.role == 'N'
             and s.id not in self.sim.found_ids]
if objetivos:
    tgt = min(objetivos, key=lambda s: self.dist_xy(s.x, s.y))
    tx, ty = tgt.x, tgt.y
```

Regla simple: de todos los nodos `N` que **aún no han sido
encontrados** (`found_ids`), cada Gateway elige el **más cercano a sí
mismo** en distancia euclidiana (`dist_xy`). No hay coordinación entre
Gateways ni reparto de objetivos — cada uno corre este cálculo de
forma independiente.

Esto explica por qué "se unían": si dos o más Gateways tienen el mismo
nodo `N` como el más cercano (típico cuando hay pocos `N` respecto a
`G`, como con `-n 3 -g 2`, donde solo hay un `N`), **todos** caminan
hacia ese mismo punto y terminan agrupados ahí. Una vez que ese `N` se
marca como encontrado (`register_found`), los Gateways libres pasan a
perseguir el siguiente `N` más cercano no encontrado; si ya no queda
ninguno, patrullan con pasos aleatorios pequeños.

## Cómo se solucionó: la flag `--static`

La solución no fue "arreglar" el movimiento (es el comportamiento
querido para simular rescate), sino agregar una forma explícita de
**desactivarlo** cuando lo que se quiere es una topología fija — por
ejemplo, para probar solo el enrutamiento BATMAN sin que la posición
cambie con el tiempo.

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

Esto se expone de tres formas, todas equivalentes por debajo (todas
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

La flag `--static` de la línea de comandos tiene prioridad sobre lo
que diga el archivo de escenario, porque se aplica *después* de cargar
la configuración (ver `main.py`) — puede forzar el modo estático
aunque el archivo diga `static=false`, pero no puede forzar movimiento
si el archivo ya puso `static=true`.
