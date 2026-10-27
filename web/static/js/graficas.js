// Los 6 paneles de la figura de análisis (analysis/visualizer.py,
// build_analysis_figure) en vivo: mismos títulos, mismas series del
// Recorder y las mismas marcas de eventos. Los datos llegan de
// /api/series; acá sólo se dibujan.

import { colorCss, esc } from "./util.js";

const ESTILO_EVENTO = {
  FAIL: ["#C0392B", []], RECOVER: ["#1D9E75", []],
  ALERT_ON: ["#E67E22", [2, 3]], ALERT_OFF: ["#2ECC71", [2, 3]],
  PARTITION: ["#8E44AD", [6, 3, 2, 3]], HEAL: ["#16A085", [6, 3, 2, 3]],
  SCENARIO: ["#555555", []], PARAM: ["#999999", [2, 3]],
};

const PANELES = [
  { titulo: "1 · Nodos activos en el tiempo",
    series: [{ campo: "alive_G", color: "#378ADD", nombre: "Gateways vivos", escalon: true },
             { campo: "alive_N", color: "#E24B4A", nombre: "Nodos de usuario vivos", escalon: true }],
    eventos: ["FAIL", "RECOVER"], desdeCero: true },
  { titulo: "2 · Auto-reorganización de la malla (1 = unida; >1 = partida)",
    series: [{ campo: "comp_G", color: "#8E44AD", nombre: "Componentes de la malla de gateways", escalon: true },
             { campo: "node_reach", color: "#E24B4A", nombre: "Nodos de usuario alcanzables", escalon: true }],
    sombra: { campo: "comp_G", si: (v) => v > 1, color: "#8E44AD2E" },
    lineaH: () => ({ valor: 1, color: "#16A085" }),
    eventos: ["PARTITION", "HEAL"], desdeCero: true },
  { titulo: "3 · Enrutamiento BATMAN: calidad (TQ) y longitud de ruta",
    series: [{ campo: "avg_tq", color: "#1D9E75", nombre: "TQ medio de rutas" },
             { campo: "avg_hops", color: "#E8A838", nombre: "Saltos medios", derecho: true, punteada: true }],
    eventos: ["FAIL", "RECOVER", "PARTITION", "HEAL"], desdeCero: true,
    nota: "TQ calculado por el BatmanRouter real: fracción de OGM recibidos de las últimas 16 secuencias, salto a salto. La calidad del medio está en el panel 5." },
  { titulo: "4 · Detección de gateway perdido (regla de timeout)",
    series: [{ campo: "max_silence", color: "#C0392B", nombre: "Máx. s sin oír a un gateway" }],
    sombra: { campo: "alerts_active", si: (v) => v > 0, color: "#E67E2226" },
    lineaH: (d) => ({ valor: d.timeout, color: null, nombre: `Umbral de caída (${d.timeout}s)` }),
    desdeCero: true },
  { titulo: "5 · Calidad del medio radio (paquetes entregados / intentados)",
    series: [{ campo: "deliver_ratio", color: "#88888888", nombre: "Ratio de entrega (por paso)", fino: true, sinLeyenda: true },
             { campo: "deliver_ratio", color: "#2980B9", nombre: "Media móvil", movil: 9 }],
    ymin: -0.02, ymax: 1.05 },
  { titulo: "6 · Ancho de banda total de la red",
    series: [{ campo: "bandwidth", color: "#1D9E75", nombre: "Ancho de banda total", escalon: true }],
    eventos: ["FAIL", "RECOVER", "SCENARIO"], desdeCero: true,
    nota: "Estimación heurística (100 − 5·d Mbps hacia el Gateway más cercano): no sale del medio radio." },
  { titulo: "7 · Plano de datos: entrega por BATMAN (últimos 20 s)",
    series: [{ campo: "entrega_datos", color: "#A855F7", nombre: "Paquetes de datos entregados / enviados" }],
    eventos: ["FAIL", "RECOVER", "PARTITION", "HEAL"], ymin: -0.02, ymax: 1.05,
    soloSi: (s) => (s.datos_enviados?.at(-1) ?? 0) > 0,
    nota: "Cada paquete avanza salto a salto con la tabla de rutas del nodo que lo tiene. Sólo aparece si hay tráfico (flujos del escenario, --trafico o mensajes)." },
  { titulo: "8 · Descentralización: lo que cada nodo cree y los puntos únicos de falla",
    series: [{ campo: "exactitud", color: "#0E9F6E", nombre: "Exactitud del conocimiento de rutas" },
             { campo: "rutas_fantasma", color: "#E0393E", nombre: "Pares con ruta fantasma", fino: true },
             { campo: "rutas_faltantes", color: "#C27803", nombre: "Pares con ruta faltante", fino: true },
             { campo: "nodos_criticos", color: "#7C5CFF", nombre: "Nodos críticos", derecho: true, punteada: true, escalon: true }],
    eventos: ["FAIL", "RECOVER", "PARTITION", "HEAL"], ymin: -0.02, ymax: 1.05,
    nota: "Exactitud: fracción de pares (a, b) en que a tiene ruta vigente hacia b si y sólo si la radio los conecta. Fantasma: cree tener ruta y la radio ya no los conecta; faltante: al revés. Nodos críticos: los que, si caen, parten la malla (puntos de articulación)." },
];

// Igual que np.convolve(x, ones(k)/k, mode='same') de la figura.
function mediaMovil(x, k) {
  if (x.length < k) return null;
  const m = Math.floor(k / 2), out = new Array(x.length);
  for (let i = 0; i < x.length; i++) {
    let s = 0;
    for (let j = i - m; j <= i + m; j++) if (j >= 0 && j < x.length) s += x[j];
    out[i] = s / k;
  }
  return out;
}

export class Graficas {
  constructor(contenedor) {
    this.contenedor = contenedor;
    this.datos = null;
    this.ventana = 200;
    this.paneles = PANELES.map((p) => {
      const div = document.createElement("div");
      div.className = "grafica";
      const titulo = document.createElement("div");
      titulo.className = "titulo-grafica";
      titulo.textContent = p.titulo;
      const leyenda = document.createElement("div");
      leyenda.className = "series-grafica";
      leyenda.innerHTML = p.series.filter((se) => !se.sinLeyenda).map((se) =>
        `<span><i style="background:${se.color}"></i>${esc(se.nombre)}</span>`).join("");
      div.append(titulo, leyenda);
      const canvas = document.createElement("canvas");
      const tip = document.createElement("div");
      tip.className = "tip";
      tip.hidden = true;
      div.append(canvas, tip);
      if (p.nota) {
        const nota = document.createElement("p");
        nota.className = "detalle";
        nota.textContent = p.nota;
        div.append(nota);
      }
      contenedor.append(div);
      const panel = { spec: p, canvas, tip, geo: null, div };
      canvas.addEventListener("mousemove", (ev) => this._tooltip(panel, ev));
      canvas.addEventListener("mouseleave", () => { tip.hidden = true; });
      return panel;
    });
  }

  setDatos(datos) { this.datos = datos; }

  visible() { return this.contenedor.offsetParent !== null; }

  dibujar() {
    if (!this.datos || !this.visible()) return;
    for (const p of this.paneles) {
      const ver = !p.spec.soloSi || p.spec.soloSi(this.datos.series);
      p.div.hidden = !ver;
      if (ver) this._dibujarPanel(p);
    }
  }

  _rango() {
    const t = this.datos.series.t;
    if (!t.length) return null;
    const tmax = t.at(-1);
    const tmin = this.ventana ? Math.max(t[0], tmax - this.ventana) : t[0];
    let i0 = 0;
    while (i0 < t.length - 1 && t[i0] < tmin) i0++;
    return { tmin, tmax: Math.max(tmax, tmin + 1), i0 };
  }

  _dibujarPanel(panel) {
    const { canvas, spec } = panel;
    const dpr = window.devicePixelRatio || 1;
    const W = canvas.clientWidth || 360, H = 128;
    canvas.width = W * dpr; canvas.height = H * dpr;
    canvas.style.height = `${H}px`;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const tinta = colorCss("--tinta"), tenue = colorCss("--tenue"), borde = colorCss("--borde");
    ctx.clearRect(0, 0, W, H);

    const r = this._rango();
    if (!r) return;
    const s = this.datos.series;
    const tieneDerecho = spec.series.some((x) => x.derecho);
    const L = 34, R = tieneDerecho ? 34 : 8, T = 6, B = 18;
    const pw = W - L - R, ph = H - T - B;
    const t = s.t.slice(r.i0);
    const X = (v) => L + ((v - r.tmin) / (r.tmax - r.tmin)) * pw;

    const valores = {};
    for (const se of spec.series) {
      let v = s[se.campo].slice(r.i0);
      if (se.movil) {
        const m = mediaMovil(s[se.campo], se.movil);
        v = m ? m.slice(r.i0) : null;
      }
      valores[se.nombre] = v;
    }
    const escala = (derecho) => {
      let lo = Infinity, hi = -Infinity;
      for (const se of spec.series) {
        if (!!se.derecho !== derecho || !valores[se.nombre]) continue;
        for (const v of valores[se.nombre]) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
      }
      if (!derecho && spec.lineaH) hi = Math.max(hi, spec.lineaH(this.datos).valor);
      if (spec.ymin != null && !derecho) { lo = spec.ymin; hi = spec.ymax; }
      if (!isFinite(lo)) { lo = 0; hi = 1; }
      if (spec.desdeCero) lo = Math.min(0, lo);
      if (hi - lo < 1e-9) hi = lo + 1;
      if (spec.ymin == null || derecho) hi += (hi - lo) * 0.1;
      return { lo, hi, Y: (v) => T + ph - ((v - lo) / (hi - lo)) * ph };
    };
    const izq = escala(false), der = tieneDerecho ? escala(true) : null;
    panel.geo = { L, pw, X, t, i0: r.i0, valores, izq, der };

    // cuadrícula (tres líneas) y ejes
    ctx.strokeStyle = borde; ctx.lineWidth = 1;
    ctx.setLineDash([2, 4]);
    for (const fr of [0, 0.5, 1]) {
      const y = Math.round(T + ph * fr) + 0.5;
      ctx.beginPath(); ctx.moveTo(L, y); ctx.lineTo(L + pw, y); ctx.stroke();
    }
    ctx.setLineDash([]);
    ctx.fillStyle = tenue; ctx.font = "500 10px Inter, system-ui, sans-serif";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    const fmt = (v) => (Math.abs(v) >= 10 ? v.toFixed(0) : v.toFixed(2));
    ctx.fillText(fmt(izq.hi), L - 5, T + 1);
    ctx.fillText(fmt((izq.hi + izq.lo) / 2), L - 5, T + ph / 2);
    ctx.fillText(fmt(izq.lo), L - 5, T + ph);
    if (der) {
      ctx.textAlign = "left";
      ctx.fillText(fmt(der.hi), L + pw + 5, T + 1);
      ctx.fillText(fmt(der.lo), L + pw + 5, T + ph);
    }
    ctx.textBaseline = "alphabetic";
    ctx.textAlign = "left";
    ctx.fillText(`${r.tmin.toFixed(0)} s`, L, H - 3);
    ctx.textAlign = "right";
    ctx.fillText(`${r.tmax.toFixed(0)} s`, L + pw, H - 3);

    ctx.save();
    ctx.beginPath(); ctx.rect(L, T, pw, ph); ctx.clip();

    // sombreado (partición / alerta activa)
    if (spec.sombra) {
      const v = s[spec.sombra.campo].slice(r.i0);
      ctx.fillStyle = spec.sombra.color;
      for (let i = 0; i < t.length; i++) {
        if (spec.sombra.si(v[i])) {
          const x0 = X(t[i]), x1 = i + 1 < t.length ? X(t[i + 1]) : x0 + 2;
          ctx.fillRect(x0, T, Math.max(1, x1 - x0), ph);
        }
      }
    }
    // eventos
    for (const ev of this.datos.eventos) {
      if (!spec.eventos?.includes(ev.tipo) || ev.t < r.tmin) continue;
      const [c, guion] = ESTILO_EVENTO[ev.tipo] || ["#888", [2, 3]];
      ctx.strokeStyle = c + "8C"; ctx.setLineDash(guion);
      ctx.beginPath(); ctx.moveTo(X(ev.t), T); ctx.lineTo(X(ev.t), T + ph); ctx.stroke();
    }
    ctx.setLineDash([]);
    // línea horizontal de referencia
    if (spec.lineaH) {
      const l = spec.lineaH(this.datos);
      ctx.strokeStyle = l.color || tinta; ctx.setLineDash([5, 4]);
      ctx.beginPath(); ctx.moveTo(L, izq.Y(l.valor)); ctx.lineTo(L + pw, izq.Y(l.valor)); ctx.stroke();
      ctx.setLineDash([]);
    }
    // series (la primera, con un relleno degradado debajo)
    const paso = Math.max(1, Math.floor(t.length / (pw * 2)));
    spec.series.forEach((se, k) => {
      const v = valores[se.nombre];
      if (!v) return;
      const { Y } = se.derecho ? der : izq;
      ctx.strokeStyle = se.color; ctx.lineWidth = se.fino ? 0.8 : 2;
      ctx.lineJoin = "round";
      ctx.setLineDash(se.punteada ? [5, 3] : []);
      ctx.beginPath();
      let xUlt = L;
      for (let i = 0; i < t.length; i += paso) {
        const x = X(t[i]), y = Y(v[i]);
        if (i === 0) ctx.moveTo(x, y);
        else if (se.escalon) { ctx.lineTo(x, Y(v[i - paso])); ctx.lineTo(x, y); }
        else ctx.lineTo(x, y);
        xUlt = x;
      }
      ctx.stroke();
      if (k === 0 && !se.fino && !se.derecho) {
        const g = ctx.createLinearGradient(0, T, 0, T + ph);
        g.addColorStop(0, se.color.slice(0, 7) + "40");
        g.addColorStop(1, se.color.slice(0, 7) + "00");
        ctx.lineTo(xUlt, T + ph); ctx.lineTo(X(t[0]), T + ph); ctx.closePath();
        ctx.fillStyle = g;
        ctx.fill();
      }
    });
    ctx.restore();
    ctx.setLineDash([]);
  }

  _tooltip(panel, ev) {
    const g = panel.geo;
    if (!g || !g.t.length) return;
    const x = ev.offsetX;
    let mejor = 0, d = Infinity;
    for (let i = 0; i < g.t.length; i++) {
      const di = Math.abs(g.X(g.t[i]) - x);
      if (di < d) { d = di; mejor = i; }
    }
    const lineas = [`t = ${g.t[mejor].toFixed(1)} s`];
    for (const se of panel.spec.series) {
      const v = g.valores[se.nombre];
      if (v) lineas.push(`${se.nombre}: ${Number(v[mejor]).toFixed(se.escalon ? 0 : 3)}`);
    }
    panel.tip.innerHTML = lineas.join("<br>");
    panel.tip.hidden = false;
    panel.tip.style.left = `${Math.min(x + 10, panel.canvas.clientWidth - 170)}px`;
    panel.tip.style.top = "48px";
  }
}
