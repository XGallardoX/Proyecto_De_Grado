"""Plano de datos sobre BATMAN.

Un paquete de datos avanza salto a salto: en cada nodo, el siguiente salto
lo decide BatmanRouter.next_hop() con la tabla de rutas de ESE nodo (código
real de mesh/router.py). Nadie conoce el camino completo. Si el nodo no
tiene ruta, el paquete se pierde; si el salto no llega (el vecino se fue
de alcance, cayó, o la radio pierde la trama y sus reintentos), también.
Así, lo que mide el plano de datos es cuán bien enruta BATMAN, no la
conectividad física (que sigue estando en los grupos de radio). Para no
culpar al protocolo de lo que es física, un paquete cuyo destino no tiene
ningún camino por radio al enviarse se cuenta aparte (sin_camino) y no se
reenvía.

Cada salto se resuelve dentro del paso en que se envía el paquete: en una
red real un salto tarda milisegundos, mucho menos que el paso de 0.5 s, así
que la simulación no puede medir latencia; mide entrega, saltos, el
estiramiento contra el camino más corto y por qué se pierde cada paquete.

Sólo consume `random` cuando hay tráfico (flujos del escenario o mensajes
a mano): una corrida sin tráfico da exactamente lo mismo que antes.
"""
import random
from collections import deque

from sim.radio import _Packet

TTL_DATOS = 50        # como batman-adv: un bucle se corta a los 50 saltos
REINTENTOS_MAC = 3    # 802.11: retransmisiones de una trama unicast sin ACK
VENTANA_ENTREGA = 20.0  # s de la serie de entrega en el tiempo
CADA_DEFECTO = 2.0      # s entre paquetes de un flujo

# Por qué se pierde un paquete. Las dos primeras son físicas (ningún
# protocolo podría entregarlo); las otras cuatro, de enrutamiento.
CAUSAS = ("destino_caido", "sin_camino", "sin_ruta", "ruta_vieja", "enlace",
          "bucle")
NOMBRE_CAUSA = {
    "destino_caido": "el destino está caído",
    "sin_camino": "no hay ningún camino por radio",
    "sin_ruta": "sin ruta en la tabla",
    "ruta_vieja": "el siguiente salto de la tabla ya no está al alcance",
    "enlace": "la radio perdió el salto (con sus reintentos)",
    "bucle": "bucle de enrutamiento (TTL agotado)",
    "origen_caido": "el origen está caído",
}


class PlanoDatos:
    """Flujos de tráfico y reenvío de paquetes de datos de una Simulation.

    `trafico` (de sim.cfg["traffic"], ya validado por sim.config_loader):
        {"flujos": [{"src": id, "dst": id, "cada": s, "desde": s,
                     "hasta": s | None}, ...],
         "aleatorios": K, "cada": s}
    Los K flujos aleatorios unen pares de Nodos de usuario distintos (de
    todos los nodos si hay menos de dos), elegidos al construir la
    simulación con `random`.
    """

    def __init__(self, sim, trafico=None):
        self.sim = sim
        self.flujos = []
        self.enviados = 0
        self.entregados = 0
        self.perdidas = dict.fromkeys(CAUSAS, 0)
        self.saltos = []          # de los entregados
        self.estiramientos = []   # saltos reales / saltos del camino más corto
        self.intentos_mac = 0
        self.exitos_mac = 0
        self._recientes = deque()  # (t, entregado) de la última ventana
        self._configurar(trafico or {})

    # ── flujos ──
    def _configurar(self, trafico):
        cada = float(trafico.get("cada", CADA_DEFECTO))
        for f in trafico.get("flujos", []):
            self._agregar_flujo(f["src"], f["dst"], f.get("cada", cada),
                                f.get("desde", 0.0), f.get("hasta"))
        k = int(trafico.get("aleatorios", 0))
        if k > 0:
            ids = sorted(n.id for n in self.sim.nodes.values() if n.role == 'N')
            if len(ids) < 2:
                ids = sorted(self.sim.nodes)
            if len(ids) >= 2:
                for _ in range(k):
                    src, dst = random.sample(ids, 2)
                    self._agregar_flujo(src, dst, cada, 0.0, None)

    def _agregar_flujo(self, src, dst, cada, desde, hasta):
        self.flujos.append({"src": src, "dst": dst, "cada": float(cada),
                            "desde": float(desde),
                            "hasta": None if hasta is None else float(hasta),
                            "prox": float(desde)})

    def descripcion_flujos(self):
        return [{"src": f["src"], "dst": f["dst"], "cada": f["cada"],
                 "desde": f["desde"], "hasta": f["hasta"]} for f in self.flujos]

    def tick(self, t):
        """Envía los paquetes de los flujos cuyo instante ya llegó."""
        for f in self.flujos:
            while f["prox"] <= t + 1e-9 and (f["hasta"] is None
                                              or f["prox"] <= f["hasta"] + 1e-9):
                f["prox"] += f["cada"]
                if f["src"] in self.sim.nodes:
                    self.enviar(f["src"], f["dst"])

    # ── reenvío ──
    def enviar(self, src_id, dst_id):
        """Origina un paquete de `src_id` a `dst_id` y lo reenvía salto a
        salto. Devuelve {"entregado", "camino" (ids recorridos), "causa"
        (None si llegó), "optimo" (ids del camino más corto por radio al
        enviar, o None)}. Un origen caído no envía nada (no cuenta)."""
        sim = self.sim
        a = sim.nodes.get(src_id)
        if a is None or not a.alive:
            return {"entregado": False, "camino": [src_id],
                    "causa": "origen_caido", "optimo": None}
        self.enviados += 1
        optimo = sim._shortest_path(src_id, dst_id)
        camino = [src_id]
        b = sim.nodes.get(dst_id)
        causa = None
        if b is None or not b.alive:
            causa = "destino_caido"
        elif optimo is None:
            causa = "sin_camino"
        else:
            actual, ttl = a, TTL_DATOS
            while actual.id != dst_id:
                if ttl == 0:
                    causa = "bucle"
                    break
                salto = actual.router.next_hop(dst_id)
                if salto is None:
                    causa = "sin_ruta"
                    break
                sig = sim.nodes.get(salto[0])
                rel = (sim.medium.reliability(actual, sig)
                       if sig is not None and sig.alive else 0.0)
                if rel <= 0.0:
                    causa = "ruta_vieja"
                    break
                if not self._transmitir(actual, sig, rel, src_id, ttl):
                    causa = "enlace"
                    break
                ttl -= 1
                camino.append(sig.id)
                actual = sig
        entregado = causa is None
        if entregado:
            self.entregados += 1
            saltos = len(camino) - 1
            self.saltos.append(saltos)
            if optimo and len(optimo) > 1:
                self.estiramientos.append(saltos / (len(optimo) - 1))
        else:
            self.perdidas[causa] += 1
        self._recientes.append((sim.t, entregado))
        return {"entregado": entregado, "camino": camino, "causa": causa,
                "optimo": optimo}

    def _transmitir(self, emisor, receptor, rel, origen, ttl):
        """Unicast de un salto al alcance (`rel` > 0, la fiabilidad del
        RadioMedium) con los reintentos de la capa de enlace."""
        for _ in range(1 + REINTENTOS_MAC):
            self.intentos_mac += 1
            if random.random() <= rel:
                self.exitos_mac += 1
                self.sim.medium.packets_visual.append(
                    _Packet(emisor.x, emisor.y, receptor.x, receptor.y,
                            getattr(self.sim, "C_MSG", "#9B59B6"),
                            tipo="DATA", origen=origen, ttl=ttl,
                            emisor=emisor.id, receptor=receptor.id))
                return True
        return False

    # ── lectura para el Recorder y el resumen ──
    def entrega_reciente(self, t):
        """Fracción entregada de los paquetes enviados en los últimos
        VENTANA_ENTREGA s; 1.0 si no se envió ninguno (como deliver_ratio)."""
        while self._recientes and self._recientes[0][0] < t - VENTANA_ENTREGA:
            self._recientes.popleft()
        if not self._recientes:
            return 1.0
        return sum(1 for _, ok in self._recientes if ok) / len(self._recientes)
