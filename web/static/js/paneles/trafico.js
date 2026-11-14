// Panel "Tráfico": elegir el tipo de paquete (UDP, ICMP, TCP), cuántos se
// mandan y cada cuánto, y ver qué pasó con cada uno. Nada se calcula acá:
// el recorrido y el resultado de cada paquete llegan del plano de datos
// (sim/datos.py) en frame.trafico.

import { esc } from "../util.js";

export const COLOR_TIPO = { udp: "#A855F7", icmp: "#06B6D4", tcp: "#EC4899" };

const AYUDA_TIPO = {
  udp: "Un datagrama de ida, sin confirmación: si se pierde, nadie lo reenvía.",
  icmp: "Un eco (ping): la petición va y el destino responde por su propia tabla de rutas. Cuenta como entregado sólo si la respuesta vuelve.",
  tcp: "El destino confirma cada segmento y el origen lo retransmite (hasta 3 veces) si la confirmación no vuelve.",
};

const pct = (a, b) => (b ? `${(100 * a / b).toFixed(0)} %` : "—");
// Retardo estimado (s): en ms por debajo de 1 s.
const dur = (s) => (s == null ? "—" : s < 1 ? `${(1000 * s).toFixed(0)} ms` : `${s.toFixed(2)} s`);

// Línea de tiempo de un paquete: cada envío de extremo a extremo es una
// flecha de ida (▶) y, en ICMP y TCP, una de vuelta (◀), verde si llegó y
// roja si se perdió. Entre dos envíos de TCP, la espera antes de retransmitir.
function lineaTiempo(p, rto) {
  if (!p.envios) return "";
  const flecha = (ok, txt, titulo) =>
    `<span class="tl-paso ${ok ? "tl-ok" : "tl-mal"}" title="${titulo}">${txt}${ok ? "" : "✕"}</span>`;
  const partes = p.envios.map((e, i) => {
    let html = "";
    if (i > 0) html += `<span class="tl-espera" title="Espera antes de retransmitir">⏱ ${dur(rto)}</span>`;
    html += flecha(e.ida, "▶", e.ida ? `Envío ${i + 1}: llegó al destino` : `Envío ${i + 1}: se perdió en la ida`);
    if (e.ack !== null) {
      const que = p.tipo === "tcp" ? "la confirmación (ACK)" : "la respuesta del eco";
      html += flecha(e.ack, "◀", e.ack ? `Volvió ${que}` : `Se perdió ${que}`);
    }
    return html;
  });
  return `<div class="tl">${partes.join("")}<span class="tl-total">${p.retardo == null ? "" : dur(p.retardo)}</span></div>`;
}
const chip = (tipo) =>
  `<span class="chip-tipo" style="--c:${COLOR_TIPO[tipo] || "#888"}">${esc(tipo.toUpperCase())}</span>`;

// Se construye una sola vez: el formulario no se repinta con cada frame,
// para no borrar lo que se está escribiendo.
export function construirTrafico(contenedor, enviar, quitar) {
  contenedor.innerHTML = `
    <h3>Tráfico de datos</h3>
    <p class="detalle">Cada paquete avanza salto a salto con la tabla de rutas del nodo que lo tiene. Elige el tipo, cuántos y cada cuánto.</p>
    <form id="form-trafico" class="tarjeta form-trafico">
      <label>Origen <select name="origen" required></select></label>
      <label>Destino <select name="destino" required></select></label>
      <label>Tipo de paquete
        <select name="tipo">
          <option value="udp">UDP · sin confirmación</option>
          <option value="icmp">ICMP · eco (ping)</option>
          <option value="tcp">TCP · con confirmación</option>
        </select>
      </label>
      <label title="Cuántos paquetes se mandan en total">Cantidad
        <input name="cantidad" type="number" min="1" max="1000" value="10"></label>
      <label title="Segundos simulados entre un paquete y el siguiente. Con 0 salen todos en este instante.">Cada (s)
        <input name="cada" type="number" min="0" max="600" step="0.5" value="1"></label>
      <button type="submit" class="primario">Enviar</button>
      <p class="detalle ayuda-tipo"></p>
    </form>
    <h4>Por tipo de paquete</h4>
    <div class="tr-tipos"></div>
    <h4>Flujos</h4>
    <div class="tr-flujos"></div>
    <h4>Últimos paquetes</h4>
    <div class="tr-recientes"></div>
    <div class="tr-perdidas"></div>`;
  const form = contenedor.querySelector("form");
  const ayuda = () => {
    form.querySelector(".ayuda-tipo").textContent = AYUDA_TIPO[form.tipo.value];
  };
  form.tipo.addEventListener("change", ayuda);
  ayuda();
  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    enviar({
      origen: Number(form.origen.value), destino: Number(form.destino.value),
      tipo: form.tipo.value, cantidad: Number(form.cantidad.value),
      cada: Number(form.cada.value),
    });
  });
  contenedor.querySelector(".tr-flujos").addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-quitar]");
    if (b) quitar(Number(b.dataset.quitar));
  });
}

function llenarNodos(sel, nodos, defecto) {
  const firma = nodos.map((n) => `${n.id}:${n.etiqueta}`).join(",");
  if (sel.dataset.firma === firma) return;
  const actual = sel.value;
  sel.innerHTML = nodos.map((n) =>
    `<option value="${n.id}">${esc(n.etiqueta)}</option>`).join("");
  sel.dataset.firma = firma;
  sel.value = nodos.some((n) => String(n.id) === actual) ? actual : (defecto ?? "");
}

// Retardo estimado medio de cada tipo, como barras en la misma escala: se
// ve de un vistazo cuánto pesan las esperas de retransmisión de TCP.
function barrasRetardo(t) {
  const filas = t.tipos.map(({ clave }) => [clave, t.por_tipo[clave]])
    .filter(([, c]) => c.retardo_medio != null);
  if (!filas.length) return "";
  const tope = Math.max(...filas.map(([, c]) => c.retardo_medio)) || 1;
  return `<h4 title="UDP: hasta que llega. ICMP: ida y vuelta. TCP: hasta que llega el segmento, con las esperas de retransmisión.">Retardo estimado (medio)</h4>
    <div class="tr-retardo">${filas.map(([clave, c]) => `
      <span>${chip(clave)}</span>
      <span class="tr-barra"><i style="width:${Math.max(1, 100 * c.retardo_medio / tope)}%;background:${COLOR_TIPO[clave]}"></i></span>
      <span class="tr-valor" title="máximo ${dur(c.retardo_max)}">${dur(c.retardo_medio)}</span>`).join("")}
    </div>
    <p class="detalle">Estimación: ${dur(t.retardo.intento_radio)} por cada intento de transmisión por radio y ${dur(t.retardo.rto_tcp)} de espera antes de cada retransmisión de TCP. Los saltos se resuelven dentro de un paso, así que el simulador no mide el tiempo real.</p>`;
}

export function pintarTrafico(contenedor, f) {
  const form = contenedor.querySelector("form");
  if (!form || !f.trafico) return;
  const usuarios = f.nodos.filter((n) => n.rol === "N");
  const base = usuarios.length >= 2 ? usuarios : f.nodos;
  llenarNodos(form.origen, f.nodos, base[0]?.id);
  llenarNodos(form.destino, f.nodos, base.at(-1)?.id);

  const t = f.trafico;
  contenedor.querySelector(".tr-tipos").innerHTML = `<table class="tabla">
    <tr><th>Tipo</th><th>Enviados</th><th>Entregados</th><th>Entrega</th>
        <th title="Segmentos de TCP que el origen volvió a enviar">Retransm.</th>
        <th title="Ecos sin respuesta, o segmentos de TCP sin confirmación">Sin respuesta</th></tr>
    ${t.tipos.map(({ clave }) => {
      const c = t.por_tipo[clave];
      return `<tr><td>${chip(clave)}</td><td>${c.enviados}</td><td>${c.entregados}</td>
        <td>${pct(c.entregados, c.enviados)}</td>
        <td>${clave === "tcp" ? c.retransmisiones : "—"}</td>
        <td>${clave === "udp" ? "—" : c.sin_respuesta}</td></tr>`;
    }).join("")}
    <tr><td><b>Total</b></td><td>${t.enviados}</td><td>${t.entregados}</td>
        <td>${pct(t.entregados, t.enviados)}</td>
        <td colspan="2">${t.transmisiones} transmisiones por radio</td></tr>
  </table>
  ${barrasRetardo(t)}`;

  contenedor.querySelector(".tr-flujos").innerHTML = t.flujos.length
    ? `<table class="tabla">
      <tr><th>#</th><th>Flujo</th><th>Tipo</th><th>Cada</th><th>Enviados</th><th>Entregados</th><th></th></tr>
      ${t.flujos.map((x) => `<tr class="${x.activo ? "" : "apagado"}">
        <td>${x.id}</td><td>${esc(x.origen)} → ${esc(x.destino)}</td><td>${chip(x.tipo)}</td>
        <td>${x.cada} s</td><td>${x.enviados}${x.cantidad ? ` / ${x.cantidad}` : ""}</td>
        <td>${x.entregados} (${pct(x.entregados, x.enviados)})</td>
        <td><button type="button" data-quitar="${x.id}" title="Quitar el flujo">✕</button></td></tr>`).join("")}
    </table>`
    : `<p class="detalle">No hay flujos. Crea uno con el formulario (con «Cada» mayor que 0).</p>`;

  const recientes = [...t.recientes].reverse();
  contenedor.querySelector(".tr-recientes").innerHTML = recientes.length
    ? `<table class="tabla tr-paquetes">
      <tr><th>t (s)</th><th>Tipo</th><th>Resultado</th><th>Recorrido</th></tr>
      ${recientes.map((p) => {
        const ida = p.camino.map(esc).join(" → ");
        const vuelta = p.vuelta ? `<br><span class="tr-vuelta">↩ ${p.vuelta.map(esc).join(" → ")}</span>` : "";
        let res = p.entregado ? "entregado" : `perdido${p.tramo === "vuelta" ? " (la respuesta)" : ""}: ${esc(p.motivo)}`;
        if (p.entregado && p.tipo === "tcp" && !p.confirmado) res += ", sin confirmación";
        if (p.intentos > 1) res += ` · ${p.intentos} envíos`;
        return `<tr class="${p.entregado ? "tr-ok" : "tr-mal"}"><td>${p.t.toFixed(1)}</td>
          <td>${chip(p.tipo)}</td><td>${res}${lineaTiempo(p, t.retardo.rto_tcp)}</td>
          <td>${esc(p.origen)} ⇒ ${esc(p.destino)}<br><span class="tr-ida">${ida}</span>${vuelta}</td></tr>`;
      }).join("")}
    </table>`
    : `<p class="detalle">Todavía no se envió ningún paquete de datos.</p>`;

  const perdidas = Object.entries(t.perdidas);
  contenedor.querySelector(".tr-perdidas").innerHTML = perdidas.length
    ? `<h4>Por qué se perdieron</h4><dl class="cifras">${perdidas.map(([k, v]) =>
        `<dt>${esc(k)}</dt><dd>${v}</dd>`).join("")}</dl>` : "";
}
