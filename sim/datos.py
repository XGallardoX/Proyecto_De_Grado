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

Protocolo de comparación (protocolo_datos = "inundacion"): sin tablas,
cada nodo que recibe una copia nueva la difunde una vez (broadcast, sin
reintentos: no hay ACK en broadcast). Entrega más a cambio de muchas más
transmisiones; `transmisiones` cuenta las de los dos protocolos (cada
intento unicast de BATMAN, cada difusión de la inundación).

Tipo de paquete (`tipo` de un flujo o de un envío a mano). Los tres usan
el mismo reenvío salto a salto; cambia lo que pasa de extremo a extremo:

  - "udp" (por defecto): un datagrama de ida, sin confirmación. Es el
    comportamiento de siempre.
  - "icmp": un eco (ping). La petición va y el destino responde por SU
    tabla de rutas; cuenta como entregado sólo si la respuesta vuelve.
  - "tcp": el destino confirma cada segmento (ACK) y el origen lo
    retransmite hasta RETRANSMISIONES_TCP veces si no recibe la
    confirmación. Cuenta como entregado si el segmento llegó.

Son modelos simplificados: no hay establecimiento de conexión, ventanas ni
control de congestión, y las retransmisiones de TCP ocurren dentro del
mismo paso, así que sólo recuperan pérdidas de la radio (una ruta que
falta o un bucle no cambian dentro del paso).

Sólo consume `random` cuando hay tráfico (flujos del escenario o mensajes
a mano): una corrida sin tráfico da exactamente lo mismo que antes, y un
flujo "udp" da exactamente lo mismo que antes de existir los tipos.
"""
import random
from collections import deque

from sim.radio import _Packet

TTL_DATOS = 50        # como batman-adv: un bucle se corta a los 50 saltos
REINTENTOS_MAC = 3    # 802.11: retransmisiones de una trama unicast sin ACK
VENTANA_ENTREGA = 20.0  # s de la serie de entrega en el tiempo
CADA_DEFECTO = 2.0      # s entre paquetes de un flujo
TIPOS_PAQUETE = ("udp", "icmp", "tcp")
TIPO_DEFECTO = "udp"
RETRANSMISIONES_TCP = 3   # de extremo a extremo, además de los reintentos MAC
MAX_HISTORIAL = 200       # últimos paquetes que se recuerdan (para verlos)
NOMBRE_TIPO = {
    "udp": "UDP (datagrama sin confirmación)",
    "icmp": "ICMP (eco: petición y respuesta)",
    "tcp": "TCP (con confirmación y retransmisión)",
}

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
        self.transmisiones = 0    # unicast de BATMAN + difusiones de inundación
        self._recientes = deque()  # (t, entregado) de la última ventana
        # por tipo de paquete y los últimos paquetes, para la interfaz
        self.por_tipo = {t: {"enviados": 0, "entregados": 0,
                             "retransmisiones": 0, "sin_respuesta": 0}
                         for t in TIPOS_PAQUETE}
        self.historial = deque(maxlen=MAX_HISTORIAL)
        self._n_paquete = 0
        self._n_flujo = 0
        self._configurar(trafico or {})

    # ── flujos ──
    def _configurar(self, trafico):
        cada = float(trafico.get("cada", CADA_DEFECTO))
        tipo = trafico.get("tipo")   # None: el de sim.cfg["tipo_paquete"]
        for f in trafico.get("flujos", []):
            self._agregar_flujo(f["src"], f["dst"], f.get("cada", cada),
                                f.get("desde", 0.0), f.get("hasta"),
                                f.get("tipo", tipo), f.get("cantidad"))
        k = int(trafico.get("aleatorios", 0))
        if k > 0:
            ids = sorted(n.id for n in self.sim.nodes.values() if n.role == 'N')
            if len(ids) < 2:
                ids = sorted(self.sim.nodes)
            if len(ids) >= 2:
                for _ in range(k):
                    src, dst = random.sample(ids, 2)
                    self._agregar_flujo(src, dst, cada, 0.0, None, tipo)

    def tipo_de(self, flujo):
        """El tipo de paquete de un flujo: el suyo o, si no lo fija, el del
        parámetro `tipo_paquete` (que se puede cambiar en marcha)."""
        return flujo["tipo"] or self.sim.cfg.get("tipo_paquete", TIPO_DEFECTO)

    def _agregar_flujo(self, src, dst, cada, desde, hasta,
                       tipo=None, cantidad=None):
        self._n_flujo += 1
        flujo = {"id": self._n_flujo, "src": src, "dst": dst,
                 "cada": float(cada), "desde": float(desde),
                 "hasta": None if hasta is None else float(hasta),
                 "prox": float(desde), "tipo": tipo,
                 "cantidad": None if cantidad is None else int(cantidad),
                 "enviados": 0, "entregados": 0}
        self.flujos.append(flujo)
        return flujo

    def agregar_flujo(self, src, dst, tipo=TIPO_DEFECTO, cada=CADA_DEFECTO,
                      cantidad=None, desde=None):
        """Agrega un flujo con la simulación en marcha (la interfaz):
        `cantidad` paquetes de `tipo`, uno cada `cada` s, desde `desde`
        (ahora, si no se indica). Sin `cantidad` no termina."""
        if tipo not in TIPOS_PAQUETE:
            raise ValueError(f"tipo de paquete desconocido: {tipo!r} "
                             f"(válidos: {', '.join(TIPOS_PAQUETE)})")
        if src == dst:
            raise ValueError("el origen y el destino son el mismo nodo")
        for nid in (src, dst):
            if nid not in self.sim.nodes:
                raise ValueError(f"no existe el nodo {nid}")
        if cada <= 0:
            raise ValueError("'cada' debe ser mayor que 0")
        if cantidad is not None and cantidad < 1:
            raise ValueError("'cantidad' debe ser al menos 1")
        return self._agregar_flujo(src, dst, cada,
                                   self.sim.t if desde is None else desde,
                                   None, tipo, cantidad)

    def quitar_flujo(self, flujo_id):
        """Quita un flujo por su id. Devuelve si existía."""
        antes = len(self.flujos)
        self.flujos = [f for f in self.flujos if f["id"] != flujo_id]
        return len(self.flujos) != antes

    @staticmethod
    def flujo_activo(f, t):
        """Si el flujo todavía tiene paquetes por enviar en el instante `t`."""
        if f["cantidad"] is not None and f["enviados"] >= f["cantidad"]:
            return False
        return f["hasta"] is None or f["prox"] <= f["hasta"] + 1e-9

    def descripcion_flujos(self):
        """Los flujos como se escriben en un escenario: `tipo` y `cantidad`
        sólo aparecen si no son los de por defecto."""
        out = []
        for f in self.flujos:
            d = {"src": f["src"], "dst": f["dst"], "cada": f["cada"],
                 "desde": f["desde"], "hasta": f["hasta"]}
            if f["tipo"] is not None:
                d["tipo"] = f["tipo"]
            if f["cantidad"] is not None:
                d["cantidad"] = f["cantidad"]
            out.append(d)
        return out

    def tick(self, t):
        """Envía los paquetes de los flujos cuyo instante ya llegó."""
        for f in self.flujos:
            while f["prox"] <= t + 1e-9 and self.flujo_activo(f, t):
                f["prox"] += f["cada"]
                if f["src"] in self.sim.nodes:
                    r = self.enviar(f["src"], f["dst"], self.tipo_de(f))
                    if r["causa"] != "origen_caido":
                        f["enviados"] += 1
                        f["entregados"] += r["entregado"]

    # ── reenvío ──
    def enviar(self, src_id, dst_id, tipo=None):
        """Origina un paquete de `src_id` a `dst_id` y lo reenvía salto a
        salto. Devuelve {"entregado", "camino" (ids recorridos a la ida),
        "causa" (None si llegó), "optimo" (ids del camino más corto por
        radio al enviar, o None), "tipo", "vuelta" (ids que recorrió la
        respuesta de ICMP o la confirmación de TCP, o None), "confirmado"
        (si esa respuesta volvió al origen), "intentos" (envíos de extremo
        a extremo: 1 más las retransmisiones de TCP) y "tramo" ("ida" o
        "vuelta": dónde se perdió, o None). Un origen caído no envía nada
        (no cuenta)."""
        sim = self.sim
        if tipo is None:
            tipo = sim.cfg.get("tipo_paquete", TIPO_DEFECTO)
        if tipo not in TIPOS_PAQUETE:
            raise ValueError(f"tipo de paquete desconocido: {tipo!r}")
        a = sim.nodes.get(src_id)
        if a is None or not a.alive:
            return {"entregado": False, "camino": [src_id],
                    "causa": "origen_caido", "optimo": None, "tipo": tipo,
                    "vuelta": None, "confirmado": False, "intentos": 0,
                    "tramo": None}
        self.enviados += 1
        camino, causa, optimo = self._tramo(src_id, dst_id, tipo)
        llego = causa is None
        vuelta, confirmado, intentos, tramo = None, False, 1, None
        if tipo == "udp":
            entregado = llego
            tramo = None if llego else "ida"
        elif tipo == "icmp":
            # el destino responde con SU tabla: la vuelta puede fallar
            # aunque la ida haya llegado
            if llego:
                vuelta, causa, _ = self._tramo(dst_id, src_id, "icmp-r")
                confirmado = causa is None
                tramo = None if confirmado else "vuelta"
            else:
                tramo = "ida"
            entregado = confirmado
        else:  # tcp
            causa_ida = causa
            while True:
                if causa_ida is None:
                    llego = True
                    vuelta, causa_ack, _ = self._tramo(dst_id, src_id, "tcp-ack")
                    if causa_ack is None:
                        confirmado = True
                        break
                    ultima = causa_ack
                else:
                    ultima = causa_ida
                # sólo una pérdida de la radio puede cambiar dentro del paso
                if ultima != "enlace" or intentos > RETRANSMISIONES_TCP:
                    break
                intentos += 1
                self.por_tipo["tcp"]["retransmisiones"] += 1
                c2, causa_ida, _ = self._tramo(src_id, dst_id, "tcp")
                if causa_ida is None or not llego:
                    camino = c2
            entregado = llego
            causa = None if llego else causa_ida
            tramo = None if confirmado else ("vuelta" if llego else "ida")
        if entregado:
            self.entregados += 1
            saltos = len(camino) - 1
            self.saltos.append(saltos)
            if optimo and len(optimo) > 1:
                self.estiramientos.append(saltos / (len(optimo) - 1))
        else:
            self.perdidas[causa] += 1
        self._recientes.append((sim.t, entregado))
        cuenta = self.por_tipo[tipo]
        cuenta["enviados"] += 1
        cuenta["entregados"] += entregado
        if tipo != "udp" and not confirmado:
            cuenta["sin_respuesta"] += 1
        self._n_paquete += 1
        self.historial.append({
            "n": self._n_paquete, "t": sim.t, "tipo": tipo, "src": src_id,
            "dst": dst_id, "entregado": entregado, "causa": causa,
            "camino": list(camino), "vuelta": None if vuelta is None else list(vuelta),
            "confirmado": confirmado, "intentos": intentos, "tramo": tramo})
        return {"entregado": entregado, "camino": camino, "causa": causa,
                "optimo": optimo, "tipo": tipo, "vuelta": vuelta,
                "confirmado": confirmado, "intentos": intentos, "tramo": tramo}

    def _tramo(self, src_id, dst_id, proto):
        """Un recorrido de `src_id` a `dst_id` (la ida, o la vuelta de una
        respuesta). Devuelve (camino, causa o None si llegó, camino más
        corto por radio o None)."""
        sim = self.sim
        a = sim.nodes.get(src_id)
        optimo = sim._shortest_path(src_id, dst_id)
        camino = [src_id]
        b = sim.nodes.get(dst_id)
        causa = None
        if b is None or not b.alive:
            causa = "destino_caido"
        elif optimo is None:
            causa = "sin_camino"
        elif sim.cfg.get("protocolo_datos", "batman") == "inundacion":
            camino = self._inundar(src_id, dst_id, proto)
            if camino[-1] != dst_id:
                causa = "enlace"
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
                if not self._transmitir(actual, sig, rel, src_id, ttl, proto):
                    causa = "enlace"
                    break
                ttl -= 1
                camino.append(sig.id)
                actual = sig
        return camino, causa, optimo

    def _inundar(self, src_id, dst_id, proto=TIPO_DEFECTO):
        """Inundación: cada nodo que recibe una copia nueva la difunde una
        vez (el destino no). Devuelve el camino de la primera copia que
        llegó al destino, o [src_id] si no llegó ninguna."""
        sim = self.sim
        vivos = sorted((n for n in sim.nodes.values() if n.alive), key=lambda n: n.id)
        padre = {src_id: None}
        cola = deque([(src_id, TTL_DATOS)])
        while cola:
            nid, ttl = cola.popleft()
            if ttl == 0:
                continue
            emisor = sim.nodes[nid]
            self.transmisiones += 1
            for receptor in vivos:
                if receptor.id in padre:
                    continue
                rel = sim.medium.reliability(emisor, receptor)
                if rel > 0.0 and random.random() <= rel:
                    padre[receptor.id] = nid
                    sim.medium.packets_visual.append(
                        _Packet(emisor.x, emisor.y, receptor.x, receptor.y,
                                getattr(sim, "C_MSG", "#9B59B6"), tipo="DATA",
                                origen=src_id, ttl=ttl,
                                emisor=emisor.id, receptor=receptor.id,
                                proto=proto))
                    if receptor.id != dst_id:
                        cola.append((receptor.id, ttl - 1))
        if dst_id not in padre:
            return [src_id]
        camino, nid = [], dst_id
        while nid is not None:
            camino.append(nid)
            nid = padre[nid]
        return camino[::-1]

    def _transmitir(self, emisor, receptor, rel, origen, ttl, proto=TIPO_DEFECTO):
        """Unicast de un salto al alcance (`rel` > 0, la fiabilidad del
        RadioMedium) con los reintentos de la capa de enlace."""
        for _ in range(1 + REINTENTOS_MAC):
            self.intentos_mac += 1
            self.transmisiones += 1
            if random.random() <= rel:
                self.exitos_mac += 1
                self.sim.medium.packets_visual.append(
                    _Packet(emisor.x, emisor.y, receptor.x, receptor.y,
                            getattr(self.sim, "C_MSG", "#9B59B6"),
                            tipo="DATA", origen=origen, ttl=ttl,
                            emisor=emisor.id, receptor=receptor.id,
                            proto=proto))
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
