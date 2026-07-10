class Recorder:
    def __init__(self):
        self.t = []
        self.alive_G = []
        self.alive_N = []
        self.comp_G = []            
        self.node_reach = []        
        self.avg_tq = []
        self.avg_hops = []
        self.max_silence = []       
        self.deliver_ratio = []     
        self.alerts_active = []
        self.bandwidth = []
        self.events = []            

    def event(self, t, tipo, texto):
        self.events.append((t, tipo, texto))

    def sample(self, sim, medium):
        self.t.append(sim.t)
        gateways = [n for n in sim.nodes.values() if n.role == 'G']
        nodes = [n for n in sim.nodes.values() if n.role == 'N']
        self.alive_G.append(sum(1 for n in gateways if n.alive))
        self.alive_N.append(sum(1 for n in nodes if n.alive))
        self.comp_G.append(sim.gateway_components())
        self.node_reach.append(sim.nodes_in_mesh())

        tqs, hops = [], []
        for n in gateways + nodes:
            if not n.alive:
                continue
            with n.router._lock:
                for r in n.router.routes.values():
                    tqs.append(r.tq)
                    hops.append(r.hops)
        self.avg_tq.append(sum(tqs) / len(tqs) if tqs else 0.0)
        self.avg_hops.append(sum(hops) / len(hops) if hops else 0.0)

        # cuánto lleva el gateway más "callado" sin que otro lo oiga
        sil = 0.0
        for n in gateways:
            if not n.alive:
                continue
            for m in gateways:
                if m is n or not m.alive:
                    continue
                p = m.router.peers.get(n.id)
                if p is not None:
                    sil = max(sil, sim.t - p.last_seen)
        self.max_silence.append(sil)

        at, dl = medium._step_attempt, medium._step_deliver
        self.deliver_ratio.append(dl / at if at else 1.0)

        self.alerts_active.append(sum(
            1 for n in gateways + nodes if n.alive
            for p in n.router.peers.values() if p.in_alert))

        
        total_bw = 0.0
        for n in nodes:
            if n.alive:
                min_dist = float('inf')
                for g in gateways:
                    if g.alive:
                        dist = ((n.x - g.x)**2 + (n.y - g.y)**2)**0.5
                        if dist < min_dist:
                            min_dist = dist
                if min_dist != float('inf'):
                    # Max BW = 100 Mbps, atenuación 5 Mbps por metro
                    bw = max(0.0, 100.0 - min_dist * 5.0)
                    total_bw += bw
        self.bandwidth.append(total_bw)
