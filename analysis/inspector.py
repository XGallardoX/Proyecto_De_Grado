def snapshot_red(sim):
    nodes = sim.nodes
    lbl = sim.label_of
    G = [n for n in nodes.values() if n.role == 'G']
    N = [n for n in nodes.values() if n.role == 'N']
    aliveG = sum(1 for n in G if n.alive)
    aliveN = sum(1 for n in N if n.alive)
    deliv, att = sim.medium.delivered, sim.medium.attempted
    pct = (100.0 * deliv / att) if att else 100.0

    out = []
    w = out.append

    def tabla(headers, rows, indent="    "):
        cols = len(headers)
        wid = [len(str(h)) for h in headers]
        for r in rows:
            for i in range(cols):
                wid[i] = max(wid[i], len(str(r[i])))
        ls = [indent + "  ".join(str(headers[i]).ljust(wid[i]) for i in range(cols)),
              indent + "  ".join("-" * wid[i] for i in range(cols))]
        for r in rows:
            ls.append(indent + "  ".join(str(r[i]).ljust(wid[i]) for i in range(cols)))
        return ls

    w("=" * 72)
    w(f" RED AD-HOC - INSTANTANEA  .  escenario '{sim.escenario}'  .  t = {sim.t:.1f} s")
    w(f" Gateways vivos: {aliveG}/{len(G)}   "
      f"Nodos vivos: {aliveN}/{len(N)}")
    w(f" Paquetes de radio (acumulado): {deliv}/{att} entregados ({pct:.0f}%)")
    w("=" * 72)
    w("")

    w("[ CONECTIVIDAD DE LA MALLA ]")
    w(f"  Componentes de gateways : {sim.gateway_components()}   "
      f"(1 = malla entera, >1 = partida)")
    w(f"  Nodos alcanzables : {sim.nodes_in_mesh()}/{len(N)}")
    alive, find, idx = sim._union_find()
    groups = {}
    for n in alive:
        groups.setdefault(find(idx[n.id]), []).append(n)
    glist = sorted(groups.values(), key=lambda g: (-len(g), min(x.id for x in g)))
    w("  Grupos conexos (se alcanzan entre si por radio):")
    for gi, g in enumerate(glist, 1):
        ids = sorted(g, key=lambda n: (n.role, sim.local_index[n.id]))
        w(f"    grupo {gi}: " + ", ".join(lbl(n.id) for n in ids))
    w("")

    w("[ ENLACES DE RADIO - verdad fisica (fiabilidad %) ]")
    al = sorted((n for n in nodes.values() if n.alive),
                key=lambda n: (n.role, sim.local_index[n.id]))
    pares = []
    for i, a in enumerate(al):
        for b in al[i + 1:]:
            rel = sim.medium.reliability(a, b)
            if rel > 0:
                pares.append((lbl(a.id), lbl(b.id), rel))
    if pares:
        for (la, lb, rel) in pares:
            w(f"    {la:>3} <-> {lb:<3} : {rel * 100:3.0f}%")
    else:
        w("    (no hay enlaces; todos fuera de rango)")
    w("")

    for n in sorted(nodes.values(), key=lambda n: (n.role, sim.local_index[n.id])):
        w("-" * 72)
        w(f" {lbl(n.id)}   ip {n.ip}   piso {n.piso}   "
          f"bateria {n.battery:.0f}%   {'VIVO' if n.alive else 'CAIDO'}")
        w("-" * 72)
        if not n.alive:
            w("  (nodo caido - no participa en la malla)")
            w("")
            continue
        with n.router._lock:
            peers = list(n.router.peers.values())
            routes = list(n.router.routes.values())
            failed = set(n.fault.failed)
        w("  Vecinos conocidos por el protocolo (PeerInfo):")
        if peers:
            rows = [[lbl(p.node_id), f"{sim.t - p.last_seen:.1f}s",
                     f"{p.tq:.2f}", p.hops, f"{p.battery:.0f}%",
                     "ALERTA" if p.in_alert else "-"]
                    for p in sorted(peers, key=lambda p: p.node_id)]
            out.extend(tabla(["vecino", "ult.visto", "TQ", "hops", "bat%", "estado"], rows))
        else:
            w("    (ninguno todavia)")
        w("  Tabla de rutas BATMAN (a quien / por quien / con que calidad):")
        if routes:
            rows = [[lbl(rt.dest), lbl(rt.via_id), rt.hops, f"{rt.tq:.2f}",
                     rt.seq, f"{sim.t - rt.last_seen:.1f}s"]
                    for rt in sorted(routes, key=lambda r: r.dest)]
            out.extend(tabla(["destino", "via(sig.salto)", "hops", "TQ", "seq", "edad"], rows))
        else:
            w("    (sin rutas todavia)")
        w("  Cree caidos (FaultManager.failed): " +
          (", ".join(lbl(i) for i in sorted(failed)) if failed else "(ninguno)"))
        w("")

    w("Leyenda: TQ = calidad de ruta (mayor mejor) . via = siguiente salto .")
    w("hops = saltos . edad/ult.visto = hace cuanto se supo del nodo.")
    return "\n".join(out)
