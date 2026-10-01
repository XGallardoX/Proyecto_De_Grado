import random


def fiabilidad(d, df, cfg):
    """Probabilidad de entrega entre dos puntos a distancia `d` (m) y con
    `df` pisos de diferencia, según el modelo del medio de `cfg`
    (rango_comm, falloff, perdida_base, floor_atten). 0 fuera de rango."""
    rango = cfg['rango_comm']
    if d > rango:
        return 0.0
    # fiabilidad cae con la distancia normalizada
    rel = 1.0 - cfg['falloff'] * (d / rango)
    rel -= cfg['perdida_base']
    # atenuación adicional si están en pisos distintos
    if df:
        rel *= cfg['floor_atten'] ** df
    return max(0.0, min(1.0, rel))


# ══════════════════════════════════════════════════════════════════════════
#  MEDIO RADIO SIMULADO  
# ══════════════════════════════════════════════════════════════════════════
class RadioMedium:
    """
    Único componente "no real": entrega los mensajes broadcast entre
    nodos según la distancia (euclídea en el corte vertical del edificio:
    x horizontal, y altura) y la diferencia de piso. La pérdida de paquetes hace
    que la calidad de enlace y el TQ de BATMAN se comporten como en la
    realidad.  Lleva la cuenta de paquetes intentados/entregados para
    el análisis posterior.
    """

    def __init__(self, sim, cfg):
        self.sim = sim
        self.cfg = cfg
        self.attempted = 0      # acumulado total
        self.delivered = 0
        self._step_attempt = 0  # contadores del paso actual
        self._step_deliver = 0
        self.packets_visual = []  # animación

    def reset_step_counters(self):
        self._step_attempt = 0
        self._step_deliver = 0

    def reliability(self, a, b):
        """Probabilidad de que un paquete de a llegue a b (0 si fuera de rango)."""
        return fiabilidad(a.dist_to(b), abs(a.piso - b.piso), self.cfg)

    def broadcast(self, sender, msg, visual_color=None):
        """
        Difunde msg a todos los nodos vivos en rango (como un broadcast
        UDP en la red ad-hoc real). Devuelve la lista de receptores que
        sí recibieron el paquete.
        """
        recibidos = []
        for node in self.sim.nodes.values():
            if node is sender or not node.alive:
                continue
            rel = self.reliability(sender, node)
            if rel <= 0.0:
                continue
            self.attempted += 1
            self._step_attempt += 1
            if random.random() <= rel:
                self.delivered += 1
                self._step_deliver += 1
                recibidos.append(node)
                node._inbox.append((dict(msg), sender.ip))
        if recibidos and visual_color:
            tipo = msg.get('type')
            origen = msg.get('origin_id', msg.get('node_id'))
            ttl = msg.get('ttl')
            for r in recibidos:
                self.packets_visual.append(
                    _Packet(sender.x, sender.y, r.x, r.y, visual_color,
                            tipo=tipo, origen=origen, ttl=ttl,
                            emisor=sender.id, receptor=r.id))
        return recibidos


class _Packet:
    """Paquete sólo para la animación (no afecta al protocolo). `tipo`
    ('OGM'/'BCN'), `origen` (quien originó el mensaje, no quien lo
    reenvía), `ttl`, `emisor` y `receptor` son informativos."""
    __slots__ = ('x', 'y', 'tx', 'ty', 'color', 'age', 'life',
                 'tipo', 'origen', 'ttl', 'emisor', 'receptor')

    def __init__(self, x, y, tx, ty, color, tipo=None, origen=None,
                 ttl=None, emisor=None, receptor=None):
        self.x, self.y, self.tx, self.ty = x, y, tx, ty
        self.color = color
        self.age = 0.0
        self.life = 1.4
        self.tipo, self.origen, self.ttl = tipo, origen, ttl
        self.emisor, self.receptor = emisor, receptor

    @property
    def progress(self):
        return min(self.age / self.life, 1.0)

    @property
    def pos(self):
        t = self.progress
        return (self.x + (self.tx - self.x) * t,
                self.y + (self.ty - self.y) * t)