import { esc, icono, num } from "../util.js";

// Panel "Nodo": estado interno del BatmanRouter y del FaultManager reales
// del nodo seleccionado.
export function pintarPanelNodo(contenedor, n, opciones) {
  if (!n) {
    contenedor.innerHTML = `<div class="tarjeta vacio" style="text-align:center;padding:2rem 1rem">
      ${icono("cursor")}<p>Selecciona un nodo: clic en el mapa, <kbd>Tab</kbd> o <kbd>1</kbd>–<kbd>9</kbd>.</p></div>`;
    return;
  }
  const { lenteActiva } = opciones;
  const esG = n.rol === "G";
  const color = (esG && opciones.color?.(n.id)) || "var(--nodo-usuario)";
  const enAlerta = opciones.enAlerta?.(n.id);
  const pill = !n.vivo ? '<span class="estado-pill caido">inactivo</span>'
    : enAlerta ? '<span class="estado-pill alerta">en alerta</span>'
    : '<span class="estado-pill vivo">activo</span>';
  const bat = Math.max(0, Math.min(100, n.bateria));
  const rutas = n.rutas.map((r) => `
    <tr class="${r.obsoleta ? "obsoleta" : ""}">
      <td><b>${esc(r.destino_etiqueta)}</b></td><td>${esc(r.via_etiqueta)}</td>
      <td>${r.hops}</td><td>${num(r.tq)}</td><td>${num(r.edad_s, 0)}s</td>
    </tr>`).join("");
  const vecinos = n.vecinos.map((v) => `
    <tr class="${v.en_alerta ? "obsoleta" : ""}">
      <td><b>${esc(v.etiqueta)}</b></td><td>${num(v.ultimo_visto_s, 1)}s</td>
      <td>${num(v.tq)}</td><td>${v.hops}</td><td>${num(v.bateria, 0)}%</td>
      <td>${v.en_alerta ? "ALERTA" : "—"}</td>
    </tr>`).join("");
  const vigilancia = n.vigilancia.map((v) => {
    const frac = Math.min(1, v.silencio / v.timeout);
    const clase = v.cree_caido ? "llena" : frac > 0.66 ? "media" : "";
    return `<tr>
      <td><b>${esc(opciones.etiqueta(v.observado))}</b></td>
      <td style="width:45%"><div class="barra ${clase}"><i style="width:${(v.cree_caido ? 1 : frac) * 100}%"></i></div></td>
      <td>${num(v.silencio, 0)} / ${num(v.timeout, 0)} s</td>
      <td>${v.cree_caido ? "caído" : ""}</td></tr>`;
  }).join("");
  const chips = (lista) => lista.length
    ? `<div class="etiquetas">${lista.map((c) => `<span class="chip">${esc(c.etiqueta)}</span>`).join("")}</div>`
    : '<p class="detalle">(ninguno)</p>';

  contenedor.innerHTML = `
    <div class="nodo-cabecera">
      <div class="nodo-avatar ${esG ? "" : "usuario"}" style="background:${n.vivo ? color : "var(--suave)"}">
        ${icono(esG ? "gateway" : "nodo")}</div>
      <div class="nodo-titulo">
        <h3>${esc(n.etiqueta)} ${pill}</h3>
        <span class="rol">${esG ? "Gateway" : "Nodo de usuario"} · piso ${n.piso} · (${num(n.x, 1)}, ${num(n.y, 1)})</span>
      </div>
    </div>
    <div class="nodo-datos">
      <div class="dato"><small>Batería</small><b>${num(n.bateria, 0)}%</b>
        <div class="barra ${bat < 20 ? "llena" : bat < 45 ? "media" : ""}"><i style="width:${bat}%"></i></div></div>
      <div class="dato"><small>Rutas</small><b>${n.rutas.length}</b></div>
      <div class="dato"><small>Vecinos</small><b>${n.vecinos.length}</b></div>
    </div>
    <div class="botones">
      <button data-accion="lente" aria-pressed="${lenteActiva}">${icono("ojo")}Ver como este nodo</button>
      <button data-accion="${n.vivo ? "caer" : "recuperar"}">${icono(n.vivo ? "caer" : "recuperar")}${n.vivo ? "Caer (F)" : "Recuperar (G)"}</button>
      <button data-accion="msg-desde">${icono("mensaje")}Mensaje</button>
      <button data-accion="filtro">${icono("filtro")}Sus OGM</button>
      <button data-accion="eliminar" class="peligro">${icono("borrar")}Eliminar</button>
    </div>
    <h4>Tabla de rutas BATMAN (BatmanRouter real)</h4>
    ${n.rutas.length ? `<div class="marco-tabla"><table class="tabla">
      <tr><th>Dest</th><th>Vía</th><th>Saltos</th><th>TQ</th><th>Edad</th></tr>${rutas}</table></div>`
      : '<p class="detalle">Sin rutas todavía (esperando OGMs).</p>'}
    <p class="detalle">En rojo, rutas obsoletas: ningún OGM las refrescó en el último timeout (la columna Edad). Es el mismo criterio de la métrica de reconvergencia de rutas. Las rutas de BatmanRouter no expiran solas.</p>
    <h4>Alcanzables por radio que todavía no conoce</h4>
    ${chips(n.alcanzables_sin_ruta)}
    <h4>Vecinos (PeerInfo)</h4>
    ${n.vecinos.length ? `<div class="marco-tabla"><table class="tabla">
      <tr><th>Vecino</th><th>Oído</th><th>TQ</th><th>Saltos</th><th>Bat.</th><th></th></tr>${vecinos}</table></div>`
      : '<p class="detalle">(ninguno todavía)</p>'}
    ${esG ? `<h4>Detección de fallos (FaultManager real)</h4>
      ${n.vigilancia.length ? `<div class="marco-tabla"><table class="tabla">${vigilancia}</table></div>` : '<p class="detalle">Todavía no oyó a ningún otro Gateway.</p>'}
      <p class="detalle">FaultManager revisa cada 5 s: la alerta puede llegar hasta 5 s después de que la barra se llena. Sólo vigila a los Gateway que alguna vez oyó.</p>
      <h4>Cree caídos</h4>
      ${chips(n.cree_caidos)}` : ""}
  `;
}
