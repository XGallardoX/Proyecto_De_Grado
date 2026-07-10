import random

# ══════════════════════════════════════════════════════════════════════════
#  MEDIO RADIO SIMULADO  
# ══════════════════════════════════════════════════════════════════════════
class RadioMedium:
    """
    Único componente "no real": entrega los mensajes broadcast entre
    nodos según la distancia 3D y el piso. La pérdida de paquetes hace
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
        d = a.dist_to(b)
        rango = self.cfg['rango_comm']
        if d > rango:
            return 0.0
        # fiabilidad cae con la distancia normalizada
        rel = 1.0 - self.cfg['falloff'] * (d / rango)
        rel -= self.cfg['perdida_base']
        # atenuación adicional si están en pisos distintos
        df = abs(a.piso - b.piso)
        if df:
            rel *= self.cfg['floor_atten'] ** df
        return max(0.0, min(1.0, rel))

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
            for r in recibidos:
                self.packets_visual.append(
                    _Packet(sender.x, sender.y, r.x, r.y, visual_color))
        return recibidos


class _Packet:
    """Paquete sólo para la animación (no afecta al protocolo)."""
    __slots__ = ('x', 'y', 'tx', 'ty', 'color', 'age', 'life')

    def __init__(self, x, y, tx, ty, color):
        self.x, self.y, self.tx, self.ty = x, y, tx, ty
        self.color = color
        self.age = 0.0
        self.life = 1.4

    @property
    def progress(self):
        return min(self.age / self.life, 1.0)

    @property
    def pos(self):
        t = self.progress
        return (self.x + (self.tx - self.x) * t,
                self.y + (self.ty - self.y) * t)