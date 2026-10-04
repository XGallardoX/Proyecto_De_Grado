import { esc, num } from "../util.js";

// Panel "Nodo": estado interno del BatmanRouter y del FaultManager reales
// del nodo seleccionado.
export function pintarPanelNodo(contenedor, n, opciones) {
  if (!n) {
    contenedor.innerHTML = '<p class="vacio">Selecciona un nodo: clic en el mapa, Tab o 1-9.</p>';
    return;
  }
  const { lenteActiva } = opciones;
  const rutas = n.rutas.map((r) => `
    <tr class="${r.obsoleta ? "obsoleta" : ""}">
      <td>${esc(r.destino_etiqueta)}</td><td>${esc(r.via_etiqueta)}</td>
      <td>${r.hops}</td><td>${num(r.tq)}</td><td>${num(r.edad_s, 0)}s</td>
    </tr>`).join("");
  const vecinos = n.vecinos.map((v) => `
    <tr class="${v.en_alerta ? "obsoleta" : ""}">
      <td>${esc(v.etiqueta)}</td><td>${num(v.ultimo_visto_s, 1)}s</td>
      <td>${num(v.tq)}</td><td>${v.hops}</td><td>${num(v.bateria, 0)}%</td>
      <td>${v.en_alerta ? "ALERTA" : "—"}</td>
    </tr>`).join("");
  const vigilancia = n.vigilancia.map((v) => {
    const frac = Math.min(1, v.silencio / v.timeout);
    const clase = v.cree_caido ? "llena" : frac > 0.66 ? "media" : "";
    return `<tr>
      <td>${esc(opciones.etiqueta(v.observado))}</td>
      <td style="width:45%"><div class="barra ${clase}"><i style="width:${(v.cree_caido ? 1 : frac) * 100}%"></i></div></td>
      <td>${num(v.silencio, 0)} / ${num(v.timeout, 0)} s</td>
      <td>${v.cree_caido ? "caído" : ""}</td></tr>`;
  }).join("");
  const caidos = n.cree_caidos.map((c) => esc(c.etiqueta)).join(", ") || "(ninguno)";
  const sinRuta = n.alcanzables_sin_ruta.map((c) => esc(c.etiqueta)).join(", ") || "(ninguno)";

  contenedor.innerHTML = `
    <h3>${esc(n.etiqueta)} · ${n.rol === "G" ? "Gateway" : "Nodo de usuario"} ·
        ${n.vivo ? "activo" : "INACTIVO"} · ${num(n.bateria, 0)}% · piso ${n.piso}</h3>
    <div class="botones">
      <button data-accion="lente" aria-pressed="${lenteActiva}">👁 Ver como este nodo</button>
      <button data-accion="${n.vivo ? "caer" : "recuperar"}">${n.vivo ? "Caer (F)" : "Recuperar (G)"}</button>
      <button data-accion="msg-desde">Mensaje desde acá</button>
      <button data-accion="filtro">OGM de este origen</button>
      <button data-accion="eliminar">Eliminar (D)</button>
    </div>
    <h4>Tabla de rutas BATMAN (BatmanRouter real)</h4>
    ${n.rutas.length ? `<table class="tabla">
      <tr><th>Dest</th><th>Vía</th><th>Saltos</th><th>TQ</th><th>Edad</th></tr>${rutas}</table>`
      : '<p class="detalle">Sin rutas todavía (esperando OGMs).</p>'}
    <p class="detalle">En rojo, rutas obsoletas: ningún OGM las refrescó en el último timeout (la columna Edad). Es el mismo criterio de la métrica de reconvergencia de rutas. Las rutas de BatmanRouter no expiran solas.</p>
    <h4>Alcanzables por radio que todavía no conoce</h4>
    <p class="detalle">${sinRuta}</p>
    <h4>Vecinos (PeerInfo)</h4>
    ${n.vecinos.length ? `<table class="tabla">
      <tr><th>Vecino</th><th>Oído</th><th>TQ</th><th>Saltos</th><th>Bat.</th><th></th></tr>${vecinos}</table>`
      : '<p class="detalle">(ninguno todavía)</p>'}
    ${n.rol === "G" ? `<h4>Detección de fallos (FaultManager real)</h4>
      ${n.vigilancia.length ? `<table class="tabla">${vigilancia}</table>` : '<p class="detalle">Todavía no oyó a ningún otro Gateway.</p>'}
      <p class="detalle">FaultManager revisa cada 5 s: la alerta puede llegar hasta 5 s después de que la barra se llena. Sólo vigila a los Gateway que alguna vez oyó.</p>
      <p class="detalle">Cree caídos: ${caidos}</p>` : ""}
  `;
}
