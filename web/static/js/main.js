// Orquesta la interfaz: recibe frames por SSE, pide lo pesado por sus
// endpoints con menos frecuencia y manda comandos. Ningún dato del
// modelo se calcula acá.

import * as api from "./api.js";
import { CAPAS, Mapa } from "./mapa.js";
import { Graficas } from "./graficas.js";
import { LineaTiempo } from "./linea_tiempo.js";
import { Log } from "./paneles/log.js";
import { pintarPanelNodo } from "./paneles/nodo.js";
import { pintarMatriz } from "./paneles/matriz.js";
import { pintarRealModelo } from "./paneles/real_modelo.js";
import { ajustePygame, construirParametros, sincronizarParametros } from "./paneles/parametros.js";
import { abrirMenu, cerrarMenu, menuAbierto } from "./paneles/menu.js";
import { prepararInicio } from "./paneles/inicio.js";
import { Editor } from "./paneles/editor.js";
import { Laboratorio } from "./paneles/laboratorio.js";
import { bloqueComando, esc, ICONOS_EVENTO, num, toast } from "./util.js";

const $ = (id) => document.getElementById(id);

let frame = null;
let escenariosPredefinidos = [];
let ultimoEventoVisto = null;

// ── comandos ──────────────────────────────────────────────────────────
async function comando(accion, datos = {}) {
  try {
    return await api.enviarComando(accion, datos);
  } catch (e) {
    toast(e.message, "alerta");
    throw e;
  }
}
const intentar = (accion, datos) => comando(accion, datos).catch(() => null);

const etiqueta = (id) => frame?.nodos.find((n) => n.id === id)?.etiqueta ?? `?${id}`;
const nodo = (id) => frame?.nodos.find((n) => n.id === id);
const panelVisible = (nombre) => $(`panel-${nombre}`).classList.contains("activo");

// ── mapa ──────────────────────────────────────────────────────────────
const mapa = new Mapa($("mapa"), {
  seleccionar: (id) => {
    if (!$("compositor").hidden) elegirEnCompositor(id);
    seleccionar(id);
  },
  soltar: (id, x, y) => intentar("mover_nodo", { id, x, y }),
  agregar: async (rol, x, y) => {
    const r = await intentar("agregar_nodo", { rol, x, y });
    if (r) seleccionar(r.id);
  },
  menu: (id, cx, cy, w) => menuMapa(id, cx, cy, w),
  hover: (info, px, py) => tooltip(info, px, py),
});

function seleccionar(id) {
  mapa.seleccionId = id;
  if (mapa.lente) activarLente(id);
  refrescarNodo();
}

// ── lente "ver como este nodo" ───────────────────────────────────────
function activarLente(id) {
  if (id == null) { toast("Selecciona un nodo primero"); return; }
  mapa.lente = { id, detalle: null };
  $("btn-lente").setAttribute("aria-pressed", "true");
  refrescarNodo();
}
function desactivarLente() {
  mapa.lente = null;
  $("btn-lente").setAttribute("aria-pressed", "false");
  $("banner-lente").hidden = true;
}
function alternarLente() {
  if (mapa.lente) desactivarLente(); else activarLente(mapa.seleccionId);
  refrescarNodo();
}
function pintarBannerLente(d) {
  const b = $("banner-lente");
  if (!mapa.lente || !d) { b.hidden = true; return; }
  const obsoletas = d.rutas.filter((r) => r.obsoleta).length;
  b.innerHTML = `<b>La red como la ve ${esc(d.etiqueta)}</b><br>
    Conoce ${d.rutas.length} destino${d.rutas.length === 1 ? "" : "s"}` +
    (obsoletas ? ` (<span class="error">${obsoletas} obsoleto${obsoletas === 1 ? "" : "s"}</span>)` : "") +
    `; cree caídos: ${d.cree_caidos.length}; alcanzables por radio que todavía no conoce:
    ${d.alcanzables_sin_ruta.length}. Flecha = siguiente salto; punteado = hasta el destino.
    <br><span class="detalle">No hay vista global: cada nodo tiene la suya.</span>`;
  b.hidden = false;
}

// ── panel nodo (y detalle para la lente) ─────────────────────────────
let pidiendoNodo = false;
async function refrescarNodo() {
  const id = mapa.lente?.id ?? mapa.seleccionId;
  if (pidiendoNodo) return;
  if (id == null) {
    pintarPanelNodo($("panel-nodo"), null, {});
    return;
  }
  pidiendoNodo = true;
  try {
    const d = await api.obtenerNodo(id);
    if (mapa.lente && mapa.lente.id === id) { mapa.lente.detalle = d; pintarBannerLente(d); }
    if (panelVisible("nodo") && mapa.seleccionId != null) {
      const sel = d && d.id === mapa.seleccionId ? d : await api.obtenerNodo(mapa.seleccionId);
      pintarPanelNodo($("panel-nodo"), sel, { lenteActiva: !!mapa.lente, etiqueta });
    }
  } finally {
    pidiendoNodo = false;
  }
}
$("panel-nodo").addEventListener("click", (ev) => {
  const a = ev.target.closest("[data-accion]")?.dataset.accion;
  const id = mapa.seleccionId;
  if (!a || id == null) return;
  if (a === "lente") alternarLente();
  else if (a === "caer" || a === "recuperar") intentar(a, { id });
  else if (a === "eliminar") intentar("eliminar_nodo", { id });
  else if (a === "msg-desde") abrirCompositor(id);
  else if (a === "filtro") filtrarOgm(id);
});

// ── tooltip ───────────────────────────────────────────────────────────
function tooltip(info, px, py) {
  const t = $("tooltip");
  if (!info || !frame) { t.hidden = true; return; }
  if (info.tipo === "nodo") {
    const n = nodo(info.id);
    if (!n) { t.hidden = true; return; }
    t.innerHTML = `<b>${esc(n.etiqueta)} · ${n.rol === "G" ? "Gateway" : "Nodo de usuario"}</b>
      ${n.vivo ? "activo" : "caído"}${n.en_alerta ? " · en alerta" : ""}<br>
      Batería ${num(n.bateria, 0)} % · piso ${n.piso} · (${num(n.x, 1)}, ${num(n.y, 1)})<br>
      ${n.n_vecinos} vecinos conocidos · ${n.n_rutas} rutas en su tabla`;
  } else {
    const [a, b, fiab, dist] = info.enlace;
    t.innerHTML = `<b>${esc(etiqueta(a))} ↔ ${esc(etiqueta(b))}</b>
      Fiabilidad ${num(fiab * 100, 0)} % (RadioMedium)<br>
      Distancia ${num(dist, 1)} m · pisos ${nodo(a)?.piso} y ${nodo(b)?.piso}`;
  }
  t.hidden = false;
  const cont = $("contenedor-canvas").getBoundingClientRect();
  t.style.left = `${Math.min(px + 14, cont.width - t.offsetWidth - 6)}px`;
  t.style.top = `${Math.min(py + 14, cont.height - t.offsetHeight - 6)}px`;
}

// ── menú contextual ───────────────────────────────────────────────────
function menuMapa(id, cx, cy, w) {
  const n = id != null ? nodo(id) : null;
  if (n) {
    seleccionar(id);
    abrirMenu(cx, cy, `${n.etiqueta} · ${n.rol === "G" ? "Gateway" : "Nodo de usuario"}`, [
      { texto: "👁 Ver la red como este nodo", accion: () => activarLente(id) },
      n.vivo ? { texto: "Caer (F)", accion: () => intentar("caer", { id }) }
             : { texto: "Recuperar (G)", accion: () => intentar("recuperar", { id }) },
      { texto: "Mensaje desde acá", accion: () => abrirCompositor(id) },
      { texto: "Mensaje hasta acá", accion: () => abrirCompositor(mapa.compositor.origen, id) },
      { texto: "Mostrar sólo sus OGM", accion: () => filtrarOgm(id) },
      { texto: "Eliminar (D)", accion: () => intentar("eliminar_nodo", { id }) },
    ]);
  } else if (w) {
    abrirMenu(cx, cy, `(${num(w[0], 1)}, ${num(w[1], 1)})`, [
      { texto: "Agregar un Gateway acá", accion: () => mapa.cb.agregar("G", w[0], w[1]) },
      { texto: "Agregar un Nodo de usuario acá", accion: () => mapa.cb.agregar("N", w[0], w[1]) },
    ]);
  }
}

// ── compositor de mensajes ───────────────────────────────────────────
function llenarSelectsCompositor() {
  for (const sel of [$("msg-origen"), $("msg-destino")]) {
    const actual = sel.value;
    sel.innerHTML = '<option value="">—</option>' + frame.nodos
      .map((n) => `<option value="${n.id}">${esc(n.etiqueta)}</option>`).join("");
    sel.value = actual;
  }
}
function abrirCompositor(origen = mapa.seleccionId, destino = null) {
  $("compositor").hidden = false;
  if (frame) llenarSelectsCompositor();
  $("msg-origen").value = origen ?? "";
  $("msg-destino").value = destino ?? "";
  sincronizarCompositor();
  $("msg-texto").focus();
}
function cerrarCompositor() {
  $("compositor").hidden = true;
  mapa.compositor = { origen: null, destino: null };
}
function sincronizarCompositor() {
  const o = $("msg-origen").value, d = $("msg-destino").value;
  mapa.compositor = { origen: o ? Number(o) : null, destino: d ? Number(d) : null };
}
function elegirEnCompositor(id) {
  const { origen, destino } = mapa.compositor;
  if (origen == null || destino != null) { $("msg-origen").value = id; $("msg-destino").value = ""; }
  else if (id !== origen) $("msg-destino").value = id;
  sincronizarCompositor();
}
$("msg-origen").addEventListener("change", sincronizarCompositor);
$("msg-destino").addEventListener("change", sincronizarCompositor);
$("msg-cerrar").addEventListener("click", cerrarCompositor);
$("compositor").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  let texto = $("msg-texto").value.trim();
  if (!/^[gGnN]?\d+\s*>/.test(texto)) {
    const { origen, destino } = mapa.compositor;
    if (origen == null || destino == null) { toast("Elige origen y destino (clic en los nodos)", "alerta"); return; }
    texto = `${etiqueta(origen)}>${etiqueta(destino)} ${texto || "hola"}`;
  }
  const r = await comando("mensaje", { texto }).catch(() => null);
  if (!r) return;
  if (r.entregado) {
    const cuerpo = texto.replace(/^\s*\S+\s*>\s*\S+\s*/, "");
    mapa.animarMensaje(r.ids, cuerpo, r.camino[0], r.camino.at(-1));
    toast(`Entregado en ${r.camino.length - 1} salto${r.camino.length === 2 ? "" : "s"} vía ` +
          `${r.camino.join(" → ")} (${r.ruta_batman_convergida ? "ruta BATMAN convergida" : "BATMAN aún no tenía la ruta"})`, "ok");
    $("msg-texto").value = "";
  } else {
    toast(`No entregado: ${r.motivo}`, "alerta");
    // el texto queda para corregirlo, pero seleccionado: lo que se
    // escriba después lo reemplaza en vez de pegarse detrás
    $("msg-texto").select();
  }
});

// ── filtro de OGM por origen ─────────────────────────────────────────
function filtrarOgm(id) {
  mapa.filtroOrigen = mapa.filtroOrigen === id ? null : id;
  mapa.paquetesOrigen = null;
  $("sel-filtro-ogm").value = mapa.filtroOrigen ?? "";
}
$("sel-filtro-ogm").addEventListener("change", (ev) => {
  mapa.filtroOrigen = ev.target.value ? Number(ev.target.value) : null;
  mapa.paquetesOrigen = null;
});
let pidiendoPaquetes = false;
async function refrescarPaquetesOrigen() {
  const origen = mapa.filtroOrigen;
  if (origen == null || pidiendoPaquetes) return;
  pidiendoPaquetes = true;
  try {
    const r = await fetch(`/api/paquetes?origen=${origen}`).then((x) => x.json());
    if (mapa.filtroOrigen === origen) mapa.paquetesOrigen = r.paquetes;
  } catch { /* se reintenta en el próximo ciclo */ } finally {
    pidiendoPaquetes = false;
  }
}

// ── leyenda y capas ───────────────────────────────────────────────────
function pintarLeyenda(col) {
  const simbolos = [
    ["●", col.gateway[0], "Gateway"], ["◆", col.nodo, "Nodo de usuario"],
    ["●", col.alerta, "En alerta"], ["●", col.caido, "Caído"],
    ["━", "#1D9E75", "Enlace fiable"], ["━", "#E24B4A", "Enlace débil"],
    ["•", col.ogm, "OGM"], ["•", col.bcn, "Beacon"],
  ];
  $("leyenda").innerHTML = `<div class="simbolos">${simbolos.map(([s, c, t]) =>
      `<span><span class="sim" style="color:${c}">${s}</span>${t}</span>`).join("")}</div>
    <div class="capas">${CAPAS.map(([k, t]) =>
      `<button data-capa="${k}" aria-pressed="${mapa.capas[k]}">${t}</button>`).join("")}</div>`;
  $("leyenda").querySelectorAll("[data-capa]").forEach((b) => b.addEventListener("click", () => {
    alternarCapa(b.dataset.capa);
  }));
}
function alternarCapa(k) {
  mapa.capas[k] = !mapa.capas[k];
  $("leyenda").querySelector(`[data-capa="${k}"]`)?.setAttribute("aria-pressed", mapa.capas[k]);
  if (k === "cobertura" && mapa.capas.cobertura) refrescarCobertura();
}
async function refrescarCobertura() {
  if (mapa.capas.cobertura) mapa.setCobertura(await api.obtenerCobertura());
}

// ── herramientas del mapa ─────────────────────────────────────────────
function elegirHerramienta(h) {
  mapa.herramienta = h;
  document.querySelectorAll(".herramienta").forEach((b) =>
    b.classList.toggle("activa", b.dataset.herramienta === h));
}
document.querySelectorAll(".herramienta").forEach((b) =>
  b.addEventListener("click", () => elegirHerramienta(b.dataset.herramienta)));

// ── frames ────────────────────────────────────────────────────────────
const log = new Log($("log"));
let leyendaPintada = false;

function alRecibirFrame(f) {
  const cambioCorrida = !frame || f.generacion !== frame.generacion;
  frame = f;
  mapa.setFrame(f);
  if (cambioCorrida) {
    log.limpiar();
    ultimoEventoVisto = f.eventos_total - 1;
    if (mapa.seleccionId != null && !nodo(mapa.seleccionId)) mapa.seleccionId = null;
    if (mapa.lente && !nodo(mapa.lente.id)) desactivarLente();
    reiniciarSeries();
    refrescarNodo();
  }
  if (!leyendaPintada) { pintarLeyenda(f.colores); leyendaPintada = true; }
  pintarBarra(f);
  log.agregar(f.log);
  avisarEventos(f);
  if (panelVisible("real")) pintarRealModelo($("panel-real"), f);
  if (panelVisible("parametros")) sincronizarParametros($("panel-parametros"), f.cfg, f.cfg_base);
  sincronizarListas(f);
}

let firmaNodos = "";
function sincronizarListas(f) {
  const firma = f.nodos.map((n) => `${n.id}:${n.etiqueta}`).join(",");
  if (firma === firmaNodos) return;
  firmaNodos = firma;
  const sel = $("sel-filtro-ogm");
  sel.innerHTML = '<option value="">todos</option>' +
    f.nodos.map((n) => `<option value="${n.id}">${esc(n.etiqueta)}</option>`).join("");
  sel.value = mapa.filtroOrigen ?? "";
  if (!$("compositor").hidden) llenarSelectsCompositor();
}

function avisarEventos(f) {
  for (const ev of f.eventos_nuevos) {
    if (ev.indice <= ultimoEventoVisto) continue;
    ultimoEventoVisto = ev.indice;
    if (ev.tipo === "PARTITION") { toast(`⫽ ${ev.texto}`, "alerta"); mapa.resaltar(ev.nodos); }
    else if (ev.tipo === "HEAL") toast(`∪ ${ev.texto}`, "ok");
    else if (ev.tipo === "ALERT_ON") toast(`! ${ev.texto}`, "alerta");
  }
}

function pintarBarra(f) {
  $("reloj").textContent = f.pausado ? `⏸ ${f.t.toFixed(0)}s` : `T+${f.t.toFixed(0)}s`;
  $("btn-semilla").textContent = `semilla ${f.semilla}`;
  const r = f.resumen;
  $("conteo-g").textContent = `Gateways ${r.aliveG}/${r.totG}`;
  $("conteo-n").textContent = `Nodos ${r.aliveN}/${r.totN}`;
  $("conteo-alcance").textContent = `Cubiertos ${f.nodos_alcanzables}/${r.totN}`;
  $("aviso-particion").hidden = r.comps <= 1;
  $("aviso-particion").textContent = `RED PARTIDA (${r.comps})`;
  $("aviso-particion").title = `La malla de Gateways está partida en ${r.comps} grupos`;
  $("aviso-intervenciones").hidden = !f.intervenciones;
  $("aviso-intervenciones").textContent = `${f.intervenciones} ${f.intervenciones === 1 ? "intervención" : "intervenciones"}`;
  $("aviso-error").hidden = !f.error;
  $("aviso-error").textContent = f.error ? `Error: ${f.error} — Reiniciar` : "";
  $("btn-pausar").textContent = f.pausado ? "▶ Reanudar" : "⏸ Pausar";
  $("btn-paso").disabled = !f.pausado;
  const vel = $("sel-velocidad");
  if (document.activeElement !== vel) vel.value = String(f.velocidad);
  const esc_ = $("sel-escenario");
  if (document.activeElement !== esc_) {
    if (!escenariosPredefinidos.includes(f.escenario)) {
      esc_.querySelector("option[data-propio]")?.remove();
      esc_.insertAdjacentHTML("afterbegin", `<option data-propio value="${esc(f.escenario)}">${esc(f.escenario)}</option>`);
    }
    esc_.value = f.escenario;
  }
}

// ── series: gráficas y línea de tiempo ───────────────────────────────
const graficas = new Graficas($("graficas"));
const linea = new LineaTiempo($("linea-tiempo"), (ev) => {
  mapa.resaltar(ev.nodos);
  const [icono, , nombre] = ICONOS_EVENTO[ev.tipo] || ["•", "", ev.tipo];
  toast(`${icono} [${ev.t.toFixed(1)} s] ${nombre}: ${ev.texto}`);
});
const series = { generacion: null, total: 0, eventosTotal: 0, datos: null, pidiendo: false };
// Tope de muestras en el navegador (memoria acotada en sesiones largas a
// velocidad máxima): "toda la corrida" muestra, como mucho, las últimas.
const MAX_MUESTRAS_CLIENTE = 50000;

function reiniciarSeries() {
  series.generacion = null;
  series.total = 0;
  series.eventosTotal = 0;
}

async function actualizarSeries() {
  if (series.pidiendo) return;
  series.pidiendo = true;
  try {
    const nuevo = series.generacion == null;
    const r = nuevo
      ? await api.obtenerSeries(0, 0, MAX_MUESTRAS_CLIENTE)
      : await api.obtenerSeries(series.total, series.eventosTotal);
    if (!r) return;
    let c = r;
    if (nuevo || r.generacion !== series.generacion || r.total < series.total) {
      if (!nuevo || r.generacion !== (frame?.generacion ?? r.generacion)) {
        c = await api.obtenerSeries(0, 0, MAX_MUESTRAS_CLIENTE);
      }
      series.datos = { series: c.series, eventos: c.eventos, timeout: c.timeout };
      series.generacion = c.generacion;
    } else {
      for (const [k, v] of Object.entries(r.series)) {
        for (const x of v) series.datos.series[k].push(x);
      }
      series.datos.eventos.push(...r.eventos);
      series.datos.timeout = r.timeout;
    }
    // cursores = lo que tiene el servidor; lo local se recorta aparte
    series.total = c.total;
    series.eventosTotal = c.eventos_total;
    const sobra = series.datos.series.t.length - MAX_MUESTRAS_CLIENTE;
    if (sobra > 0) {
      for (const k of Object.keys(series.datos.series)) series.datos.series[k].splice(0, sobra);
    }
    graficas.setDatos(series.datos);
    graficas.dibujar();
    linea.setDatos(series.datos.eventos, frame?.t ?? 0);
    linea.dibujar();
  } finally {
    series.pidiendo = false;
  }
}
$("sel-ventana").addEventListener("change", (ev) => {
  graficas.ventana = Number(ev.target.value);
  graficas.dibujar();
});

// ── matriz ────────────────────────────────────────────────────────────
async function refrescarMatriz() {
  if (!panelVisible("red")) return;
  pintarMatriz($("matriz"), $("indicador-convergencia"), await api.obtenerMatriz(), (id) => {
    seleccionar(id);
    activarLente(id);
  });
}

// ── pestañas ──────────────────────────────────────────────────────────
document.querySelectorAll(".pestana").forEach((btn) => btn.addEventListener("click", () => abrirPestana(btn.dataset.panel)));
function abrirPestana(nombre) {
  document.querySelectorAll(".pestana").forEach((b) => b.classList.toggle("activa", b.dataset.panel === nombre));
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("activo", p.id === `panel-${nombre}`));
  if (nombre === "inspector") refrescarInspector();
  if (nombre === "red") refrescarMatriz();
  if (nombre === "metricas") graficas.dibujar();
  if (nombre === "nodo") refrescarNodo();
  if (frame && nombre === "real") pintarRealModelo($("panel-real"), frame);
  if (frame && nombre === "parametros") sincronizarParametros($("panel-parametros"), frame.cfg, frame.cfg_base);
}
async function refrescarInspector() {
  $("texto-inspector").textContent = await api.obtenerInspector();
}
$("btn-refrescar-inspector").addEventListener("click", refrescarInspector);
construirParametros($("panel-parametros"), (accion, datos) => intentar(accion, datos));

// ── barra superior ────────────────────────────────────────────────────
const pausarReanudar = () => intentar(frame?.pausado ? "reanudar" : "pausar");
$("btn-pausar").addEventListener("click", pausarReanudar);
$("btn-paso").addEventListener("click", () => intentar("paso"));
$("btn-reiniciar").addEventListener("click", () => intentar("reiniciar"));
$("sel-velocidad").addEventListener("change", (ev) => {
  const v = ev.target.value;
  intentar("velocidad", { valor: v === "maxima" ? "maxima" : Number(v) });
});
$("sel-escenario").addEventListener("change", (ev) => {
  if (escenariosPredefinidos.includes(ev.target.value)) intentar("cargar", { escenario: ev.target.value });
});
$("btn-semilla").addEventListener("click", () => {
  const v = prompt("Nueva semilla (entero ≥ 1). La corrida vuelve a empezar con la misma configuración:", frame?.semilla ?? "");
  if (v) intentar("cambiar_semilla", { semilla: Number(v) });
});
$("btn-exportar").addEventListener("click", exportar);
$("btn-terminar").addEventListener("click", terminar);
$("btn-lente").addEventListener("click", alternarLente);
$("btn-presentacion").addEventListener("click", alternarPresentacion);
$("btn-ayuda").addEventListener("click", () => $("dialogo-ayuda").showModal());
$("btn-inicio").addEventListener("click", () => $("dialogo-inicio").showModal());
document.querySelectorAll(".cerrar-dialogo").forEach((b) => b.addEventListener("click", () => b.closest("dialog").close()));

async function exportar() {
  const r = await comando("exportar").catch(() => null);
  if (!r) return;
  const sub = r.carpeta.replace(/^reportes[\\/]/, "");
  $("exportado-cuerpo").innerHTML = `
    <p>Carpeta <code>${esc(r.carpeta)}</code> (lo mismo que deja la terminal, más <code>sesion_web.json</code>):</p>
    <ul>${r.archivos.map((a) => `<li><a href="/api/reportes/${encodeURI(sub)}/${encodeURIComponent(a)}" target="_blank">${esc(a)}</a></li>`).join("")}</ul>
    ${r.comando_equivalente
      ? `<p>Comando de terminal que reproduce esta corrida:</p>${bloqueComando(r.comando_equivalente)}`
        + (r.escenario_sesion ? `<p class="detalle">Las caídas y recuperaciones de la sesión quedaron como eventos <code>fail</code>/<code>recover</code> en <code>${esc(r.escenario_sesion)}</code>, que el comando usa como escenario.</p>` : "")
      : `<p class="detalle">La sesión tuvo ${r.intervenciones} ${r.intervenciones === 1 ? "intervención" : "intervenciones"} que no se pueden volver eventos del escenario (mover, agregar o eliminar nodos, mensajes, cambios de parámetros), así que no hay un comando de terminal equivalente: quedan registradas en <code>sesion_web.json</code>. Las caídas y recuperaciones solas sí se exportan como escenario.</p>`}`;
  $("dialogo-exportado").showModal();
}

async function terminar() {
  if (!confirm("¿Terminar la sesión? Se exporta el análisis y se apaga el servidor.")) return;
  await intentar("terminar");
  document.body.innerHTML = "<p style='padding:2rem'>Sesión terminada: el análisis quedó en <code>reportes/</code>. Ya puedes cerrar esta pestaña.</p>";
}

function alternarPresentacion() {
  const activo = document.body.classList.toggle("presentacion");
  mapa.escalaUI = activo ? 1.45 : 1;
}

// tema
const raiz = document.documentElement;
try { const t = localStorage.getItem("tema"); if (t) raiz.dataset.tema = t; } catch { /* sin storage */ }
$("btn-tema").addEventListener("click", () => {
  const oscuroAhora = raiz.dataset.tema
    ? raiz.dataset.tema === "oscuro"
    : matchMedia("(prefers-color-scheme: dark)").matches;
  raiz.dataset.tema = oscuroAhora ? "claro" : "oscuro";
  try { localStorage.setItem("tema", raiz.dataset.tema); } catch { /* sin storage */ }
  mapa.refrescarTema();
  graficas.dibujar();
});
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { mapa.refrescarTema(); graficas.dibujar(); });

// ── teclado (paridad con pygame + atajos nuevos) ─────────────────────
const enDialogo = () => [...document.querySelectorAll("dialog")].some((d) => d.open);
document.addEventListener("keydown", (ev) => {
  const tag = ev.target.tagName;
  if (ev.key === "Escape") {
    if (menuAbierto()) { cerrarMenu(); return; }
    if (!$("compositor").hidden) { cerrarCompositor(); return; }
    if (mapa.herramienta !== "seleccionar") { elegirHerramienta("seleccionar"); return; }
    if (mapa.lente) { desactivarLente(); return; }
    return;   // Esc no termina la sesión (sí en pygame)
  }
  if (["INPUT", "SELECT", "TEXTAREA"].includes(tag) || enDialogo() || ev.metaKey || ev.ctrlKey || ev.altKey) return;
  const id = mapa.seleccionId;
  const ids = frame ? [...frame.nodos.filter((n) => n.rol === "G"), ...frame.nodos.filter((n) => n.rol === "N")].map((n) => n.id) : [];
  const i = ids.indexOf(id);
  const k = ev.key;
  const enCuerpo = ev.target === document.body || ev.target.id === "mapa";
  if (k === " ") { ev.preventDefault(); pausarReanudar(); }
  else if ((k === "Tab" && enCuerpo) || k === "ArrowRight") {
    if (!ids.length) return;
    ev.preventDefault();
    seleccionar(ids[ev.shiftKey && k === "Tab" ? (i - 1 + ids.length) % ids.length : (i + 1) % ids.length]);
  } else if (k === "ArrowLeft") {
    if (ids.length) { ev.preventDefault(); seleccionar(ids[(i - 1 + ids.length) % ids.length]); }
  } else if (/^[1-9]$/.test(k)) {
    const g = frame?.nodos.filter((n) => n.rol === "G")[Number(k) - 1];
    if (g) seleccionar(g.id);
  } else {
    const t = k.toLowerCase();
    if (t === "f" && id != null) intentar("caer", { id });
    else if (t === "g" && id != null) intentar("recuperar", { id });
    else if (t === "a") intentar("agregar_nodo");
    else if (t === "d" && id != null) intentar("eliminar_nodo", { id });
    else if (t === "m") { ev.preventDefault(); abrirCompositor(); }
    else if (t === "i") abrirPestana("inspector");
    else if (t === "s") {
      const sig = escenariosPredefinidos[(escenariosPredefinidos.indexOf(frame?.escenario) + 1) % escenariosPredefinidos.length];
      if (sig) intentar("cargar", { escenario: sig });
    } else if (t === "p") exportar();
    else if (t === "r") intentar("reiniciar");
    else if (t === "q") terminar();
    else if (t === "l") alternarLente();
    else if (t === "o" && id != null) filtrarOgm(id);
    else if (t === "c") alternarCapa("cobertura");
    else if (t === "z") alternarPresentacion();
    else if (k === "?") $("dialogo-ayuda").showModal();
    else if (frame) {
      const ajuste = ajustePygame(frame.cfg, k);
      if (ajuste) intentar("parametro", { clave: ajuste[0], valor: ajuste[1] });
    }
  }
});

// ── editor de escenarios ─────────────────────────────────────────────
const editor = new Editor($("dialogo-editor"), $("editor"), (datos) => comando("cargar", datos));
$("btn-editor").addEventListener("click", () => editor.abrir());

// ── laboratorio de experimentos (lotes en un subproceso --batch) ──────
const laboratorio = new Laboratorio($("dialogo-laboratorio"), $("laboratorio"));
$("btn-laboratorio").addEventListener("click", () => laboratorio.abrir());

// ── arranque ──────────────────────────────────────────────────────────
(async () => {
  const escenarios = await api.obtenerEscenarios();
  escenariosPredefinidos = escenarios.predefinidos.map((e) => e.nombre);
  $("sel-escenario").innerHTML = escenariosPredefinidos.map((n) => `<option value="${n}">${n}</option>`).join("");
  prepararInicio($("dialogo-inicio"), escenarios, (datos) => api.enviarComando("cargar", datos));
  let visto = false;
  try { visto = sessionStorage.getItem("inicio_visto") === "1"; sessionStorage.setItem("inicio_visto", "1"); } catch { /* sin storage */ }
  if (!visto) $("dialogo-inicio").showModal();
})();

api.conectarStream(alRecibirFrame, (conectado) => {
  if (!conectado) $("reloj").textContent = "sin conexión…";
});
api.obtenerEstado().then((f) => f && alRecibirFrame(f));

setInterval(actualizarSeries, 500);
setInterval(refrescarPaquetesOrigen, 100);
setInterval(() => { if (panelVisible("nodo") || mapa.lente) refrescarNodo(); }, 500);
setInterval(refrescarMatriz, 1000);
setInterval(refrescarCobertura, 2000);
setInterval(() => { if (panelVisible("inspector")) refrescarInspector(); }, 2000);
