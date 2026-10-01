import * as api from "./api.js";
import { Mapa } from "./mapa.js";
import { pintarPanelNodo } from "./paneles/nodo.js";
import { Log } from "./paneles/log.js";

const mapa = new Mapa(document.getElementById("mapa"));
const log = new Log(document.getElementById("log"));
let ultimoFrame = null;
let panelNodoSucio = true;
let leyendaPintada = false;

// ── escenarios (selector superior) ──────────────────────────────────
async function cargarListaEscenarios() {
  const sel = document.getElementById("sel-escenario");
  const { predefinidos } = await api.obtenerEscenarios();
  sel.innerHTML = predefinidos
    .map((e) => `<option value="${e.nombre}">${e.nombre}</option>`)
    .join("");
  sel.addEventListener("change", async () => {
    await api.enviarComando("cargar", { escenario: sel.value });
  });
}

// ── pestañas del panel lateral ──────────────────────────────────────
for (const btn of document.querySelectorAll(".pestana")) {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".pestana").forEach((b) => b.classList.remove("activa"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("activo"));
    btn.classList.add("activa");
    document.getElementById(`panel-${btn.dataset.panel}`).classList.add("activo");
    if (btn.dataset.panel === "inspector") refrescarInspector();
  });
}

// ── frame entrante (SSE) ─────────────────────────────────────────────
function alRecibirFrame(frame) {
  ultimoFrame = frame;
  mapa.dibujar(frame);
  pintarBarra(frame);
  log.agregar(frame.log);
  graficarMetrica(frame);
  if (!leyendaPintada) { pintarLeyenda(frame.colores); leyendaPintada = true; }
  if (panelNodoSucio && document.getElementById("panel-nodo").classList.contains("activo")) {
    pintarPanelNodo(document.getElementById("panel-nodo"), mapa.seleccionId);
  }
}

function pintarLeyenda(colores) {
  const items = [
    ["●", colores.gateway[0], "Gateway"],
    ["◆", colores.nodo, "Nodo de usuario"],
    ["●", colores.alerta, "Alerta"],
    ["—", "#1D9E75", "Enlace bueno"],
    ["—", "#E24B4A", "Enlace débil"],
    ["—", colores.ogm, "OGM"],
    ["—", colores.bcn, "Beacon"],
  ];
  document.getElementById("leyenda").innerHTML = items
    .map(([s, c, t]) => `<span><span style="color:${c}">${s}</span>${t}</span>`)
    .join("");
}

function pintarBarra(frame) {
  document.getElementById("reloj").textContent =
    frame.pausado ? "PAUSADO" : `T+${frame.t.toFixed(0)}s`;
  document.getElementById("etq-semilla").textContent = `semilla ${frame.semilla}`;
  const r = frame.resumen;
  document.getElementById("conteo-g").textContent = `Gateways ${r.aliveG}/${r.totG}`;
  document.getElementById("conteo-n").textContent = `Nodos ${r.aliveN}/${r.totN}`;
  const particionado = r.comps > 1;
  const chip = document.getElementById("aviso-particion");
  chip.hidden = !particionado;
  if (particionado) chip.textContent = `RED PARTIDA (${r.comps})`;
  const err = document.getElementById("aviso-error");
  err.hidden = !frame.error;
  if (frame.error) err.textContent = frame.error;
  document.getElementById("btn-pausar").textContent = frame.pausado ? "▶ Reanudar" : "⏸ Pausar";
}

// ── mini gráfica de calidad (entrega / TQ / partición) ──────────────
const bufferMetricas = [];
function graficarMetrica(frame) {
  const m = frame.ultima_muestra;
  if (!m) return;
  bufferMetricas.push({ dr: m.deliver_ratio, tq: m.avg_tq, comp: m.comp_g });
  if (bufferMetricas.length > 160) bufferMetricas.shift();
  const cv = document.getElementById("grafica-metricas");
  const ctx = cv.getContext("2d");
  ctx.clearRect(0, 0, cv.width, cv.height);
  const n = bufferMetricas.length;
  if (n < 2) return;
  const X = (i) => (i / (n - 1)) * cv.width;
  const Y = (v) => cv.height - Math.max(0, Math.min(1, v)) * cv.height;
  ctx.fillStyle = "#8E44AD33";
  bufferMetricas.forEach((p, i) => {
    if (p.comp > 1) ctx.fillRect(X(i), 0, cv.width / n + 1, cv.height);
  });
  const linea = (campo, color) => {
    ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.beginPath();
    bufferMetricas.forEach((p, i) => {
      const x = X(i), y = Y(p[campo]);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.stroke();
  };
  linea("dr", "#2980B9");
  linea("tq", "#1D9E75");
}

// ── selección de nodo ─────────────────────────────────────────────────
function idsSeleccionables() {
  if (!ultimoFrame) return [];
  const gs = ultimoFrame.nodos.filter((n) => n.rol === "G").map((n) => n.id);
  const ns = ultimoFrame.nodos.filter((n) => n.rol === "N").map((n) => n.id);
  return [...gs, ...ns];
}

function seleccionar(id) {
  mapa.seleccionId = id;
  panelNodoSucio = true;
  if (document.getElementById("panel-nodo").classList.contains("activo")) {
    pintarPanelNodo(document.getElementById("panel-nodo"), id);
  }
  if (ultimoFrame) mapa.dibujar(ultimoFrame);
}

document.getElementById("mapa").addEventListener("click", (ev) => {
  const rect = ev.target.getBoundingClientRect();
  const id = mapa.nodoEnPunto(ev.clientX - rect.left, ev.clientY - rect.top);
  if (id != null) seleccionar(id);
});

// ── barra superior: controles ────────────────────────────────────────
document.getElementById("btn-pausar").addEventListener("click", async () => {
  await api.enviarComando(ultimoFrame?.pausado ? "reanudar" : "pausar");
});
document.getElementById("btn-paso").addEventListener("click", () => api.enviarComando("paso").catch(mostrarError));
document.getElementById("btn-reiniciar").addEventListener("click", () => api.enviarComando("reiniciar").catch(mostrarError));
document.getElementById("sel-velocidad").addEventListener("change", (ev) => {
  api.enviarComando("velocidad", { valor: ev.target.value === "maxima" ? "maxima" : Number(ev.target.value) });
});
document.getElementById("btn-exportar").addEventListener("click", async () => {
  try {
    const r = await api.enviarComando("exportar");
    alert(`Exportado en ${r.carpeta}` + (r.comando_equivalente ? `\n\nComando equivalente:\n${r.comando_equivalente}` : "\n\n(hubo intervenciones: no hay comando equivalente)"));
  } catch (e) { mostrarError(e); }
});
document.getElementById("btn-terminar").addEventListener("click", async () => {
  if (!confirm("¿Terminar la sesión? Se exporta el análisis y se apaga el servidor.")) return;
  await api.enviarComando("terminar");
  document.body.innerHTML = "<p style='padding:2rem'>Sesión terminada. Ya podés cerrar esta pestaña.</p>";
});

// ── tema ──────────────────────────────────────────────────────────────
const raiz = document.documentElement;
const temaGuardado = localStorage.getItem("tema");
if (temaGuardado) raiz.dataset.tema = temaGuardado;
document.getElementById("btn-tema").addEventListener("click", () => {
  const actual = raiz.dataset.tema === "oscuro" ? "claro" : "oscuro";
  raiz.dataset.tema = actual;
  localStorage.setItem("tema", actual);
});

// ── ayuda ─────────────────────────────────────────────────────────────
const dialogoAyuda = document.getElementById("dialogo-ayuda");
document.getElementById("btn-ayuda").addEventListener("click", () => dialogoAyuda.showModal());
document.getElementById("btn-cerrar-ayuda").addEventListener("click", () => dialogoAyuda.close());

// ── panel red: mensajes y acciones sobre el nodo seleccionado ───────
document.getElementById("form-mensaje").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const input = document.getElementById("in-mensaje");
  const resultado = document.getElementById("mensaje-resultado");
  try {
    const r = await api.enviarComando("mensaje", { texto: input.value });
    resultado.textContent = r.entregado
      ? `Entregado vía ${r.camino.join(" → ")}`
      : "No entregado (ver log).";
    input.value = "";
  } catch (e) { resultado.textContent = `Error: ${e.message}`; }
});
document.getElementById("btn-caer").addEventListener("click", () => accionSobreSeleccion("caer"));
document.getElementById("btn-recuperar").addEventListener("click", () => accionSobreSeleccion("recuperar"));
document.getElementById("btn-eliminar").addEventListener("click", () => accionSobreSeleccion("eliminar_nodo"));
document.getElementById("btn-agregar").addEventListener("click", () => api.enviarComando("agregar_nodo").catch(mostrarError));

function accionSobreSeleccion(accion) {
  if (mapa.seleccionId == null) return;
  api.enviarComando(accion, { id: mapa.seleccionId }).catch(mostrarError);
}

// ── parámetros en vivo ────────────────────────────────────────────────
function enlazarParametro(idRango, idSalida, clave) {
  const rango = document.getElementById(idRango);
  const salida = document.getElementById(idSalida);
  rango.addEventListener("input", () => { salida.textContent = rango.value; });
  rango.addEventListener("change", () => {
    api.enviarComando("parametro", { clave, valor: Number(rango.value) }).catch(mostrarError);
  });
}
enlazarParametro("param-rango", "param-rango-val", "rango_comm");
enlazarParametro("param-falloff", "param-falloff-val", "falloff");

function sincronizarParametros(frame) {
  const rango = document.getElementById("param-rango");
  const falloff = document.getElementById("param-falloff");
  if (document.activeElement !== rango) {
    rango.value = frame.cfg.rango_comm;
    document.getElementById("param-rango-val").textContent = frame.cfg.rango_comm;
  }
  if (document.activeElement !== falloff) {
    falloff.value = frame.cfg.falloff;
    document.getElementById("param-falloff-val").textContent = frame.cfg.falloff;
  }
}

// ── inspector ────────────────────────────────────────────────────────
async function refrescarInspector() {
  document.getElementById("texto-inspector").textContent = await api.obtenerInspector();
}
document.getElementById("btn-refrescar-inspector").addEventListener("click", refrescarInspector);

// ── teclado (paridad con pygame, ver tabla del prompt sección 4) ───
document.addEventListener("keydown", (ev) => {
  if (ev.target.tagName === "INPUT" || ev.target.tagName === "SELECT") return;
  const ids = idsSeleccionables();
  const idx = ids.indexOf(mapa.seleccionId);
  switch (ev.key) {
    case " ":
      ev.preventDefault();
      api.enviarComando(ultimoFrame?.pausado ? "reanudar" : "pausar");
      break;
    case "Tab": case "ArrowRight":
      ev.preventDefault();
      if (ids.length) seleccionar(ids[(idx + 1 + ids.length) % ids.length]);
      break;
    case "ArrowLeft":
      ev.preventDefault();
      if (ids.length) seleccionar(ids[(idx - 1 + ids.length) % ids.length]);
      break;
    case "f": case "F": accionSobreSeleccion("caer"); break;
    case "g": case "G": accionSobreSeleccion("recuperar"); break;
    case "a": case "A": api.enviarComando("agregar_nodo").catch(mostrarError); break;
    case "d": case "D": accionSobreSeleccion("eliminar_nodo"); break;
    case "m": case "M": {
      document.querySelector('[data-panel="red"]').click();
      document.getElementById("in-mensaje").focus();
      break;
    }
    case "i": case "I":
      document.querySelector('[data-panel="inspector"]').click();
      break;
    case "s": case "S": {
      const sel = document.getElementById("sel-escenario");
      const opciones = [...sel.options].map((o) => o.value);
      const actual = opciones.indexOf(ultimoFrame?.escenario);
      sel.value = opciones[(actual + 1 + opciones.length) % opciones.length];
      api.enviarComando("cargar", { escenario: sel.value });
      break;
    }
    case "+": case "=":
      ajustarParametro("param-rango", 1);
      break;
    case "-":
      ajustarParametro("param-rango", -1);
      break;
    case "]":
      ajustarParametro("param-falloff", 0.05);
      break;
    case "[":
      ajustarParametro("param-falloff", -0.05);
      break;
    case "p": case "P":
      document.getElementById("btn-exportar").click();
      break;
    case "r": case "R":
      api.enviarComando("reiniciar").catch(mostrarError);
      break;
    case "q": case "Q": case "Escape":
      if (dialogoAyuda.open) { dialogoAyuda.close(); break; }
      document.getElementById("btn-terminar").click();
      break;
    case "?":
      dialogoAyuda.showModal();
      break;
    default:
      if (/^[1-9]$/.test(ev.key)) {
        const gateways = (ultimoFrame?.nodos || []).filter((n) => n.rol === "G");
        const n = gateways[Number(ev.key) - 1];
        if (n) seleccionar(n.id);
      }
  }
});

function ajustarParametro(id, delta) {
  const rango = document.getElementById(id);
  const valor = Number(rango.value) + delta;
  rango.value = valor;
  rango.dispatchEvent(new Event("input"));
  rango.dispatchEvent(new Event("change"));
}

function mostrarError(e) {
  console.error(e);
  alert(e.message || String(e));
}

// ── arranque ──────────────────────────────────────────────────────────
cargarListaEscenarios();
api.conectarStream(
  (frame) => { alRecibirFrame(frame); sincronizarParametros(frame); },
  () => console.warn("stream desconectado, reintentando..."),
);
api.obtenerEstado().then((frame) => { alRecibirFrame(frame); sincronizarParametros(frame); });
