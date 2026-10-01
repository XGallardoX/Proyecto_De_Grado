import { obtenerNodo } from "../api.js";

export async function pintarPanelNodo(contenedor, id) {
  if (id == null) {
    contenedor.innerHTML = '<p class="vacio">Seleccioná un nodo (clic, Tab o 1-9).</p>';
    return;
  }
  const n = await obtenerNodo(id);
  if (!n) {
    contenedor.innerHTML = '<p class="vacio">Ese nodo ya no existe.</p>';
    return;
  }
  const filasRutas = n.rutas.map((r) => `
    <tr class="${r.obsoleta ? "obsoleta" : ""}">
      <td>${r.destino_etiqueta}</td><td>${r.via_etiqueta}</td>
      <td>${r.hops}</td><td>${r.tq.toFixed(2)}</td>
      <td>${r.edad_s.toFixed(0)}s</td>
    </tr>`).join("");
  const filasVecinos = n.vecinos.map((v) => `
    <tr class="${v.en_alerta ? "obsoleta" : ""}">
      <td>${v.etiqueta}</td><td>${v.ultimo_visto_s.toFixed(1)}s</td>
      <td>${v.tq.toFixed(2)}</td><td>${v.hops}</td>
      <td>${v.bateria.toFixed(0)}%</td>
      <td>${v.en_alerta ? "ALERTA" : "-"}</td>
    </tr>`).join("");
  const caidos = n.cree_caidos.length
    ? n.cree_caidos.map((c) => c.etiqueta).join(", ")
    : "(ninguno)";

  contenedor.innerHTML = `
    <h3>${n.etiqueta} · ${n.vivo ? "activo" : "INACTIVO"} · ${n.bateria.toFixed(0)}% · piso ${n.piso}</h3>
    <h4>Tabla de rutas BATMAN</h4>
    ${n.rutas.length ? `<table class="tabla-datos">
      <tr><th>Dest</th><th>Via</th><th>Hops</th><th>TQ</th><th>Edad</th></tr>
      ${filasRutas}
    </table>` : '<p class="detalle">Sin rutas todavía (esperando OGMs).</p>'}
    <h4>Vecinos (PeerInfo)</h4>
    ${n.vecinos.length ? `<table class="tabla-datos">
      <tr><th>Vecino</th><th>Visto</th><th>TQ</th><th>Hops</th><th>Bat%</th><th>Estado</th></tr>
      ${filasVecinos}
    </table>` : '<p class="detalle">(ninguno todavía)</p>'}
    <h4>Cree caídos (FaultManager)</h4>
    <p class="detalle">${caidos}</p>
  `;
}
