// Dibuja el edificio y la malla en un <canvas> a 60 fps. Todo lo que
// pinta (posiciones, enlaces y su fiabilidad, grupos, rutas, vigilancia,
// paquetes, cobertura) llega ya calculado del servidor: acá sólo se
// dibuja y se interpola entre dos frames para suavizar el movimiento.
// La interpolación nunca inventa estado: las posiciones reales son las
// del último frame y la animación converge a ellas.

import { colorCss } from "./util.js";

const MARGEN = 2.5;
const RADIO = 9;
const PALETA_GRUPOS = ["#378ADD", "#E8A838", "#1D9E75", "#9B59B6",
                       "#E24B4A", "#16A085", "#D4AC0D", "#8E44AD"];

export const CAPAS = [
  ["enlaces", "Enlaces"], ["paquetes", "Paquetes"], ["estelas", "Estelas"],
  ["burbujas", "Beacons"], ["alcance", "Alcance"], ["envolventes", "Grupos"],
  ["vigilancia", "Vigilancia"], ["cobertura", "Cobertura"],
];

function colorEnlace(f) {
  return f > 0.66 ? "#1D9E75" : f > 0.33 ? "#E8A838" : "#E24B4A";
}

function lerp(a, b, t) { return a + (b - a) * t; }

function envolvente(puntos) {
  // casco convexo (cadena monótona); sólo geometría de dibujo
  const p = [...puntos].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  if (p.length < 3) return p;
  const cruz = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const inf = [], sup = [];
  for (const q of p) {
    while (inf.length >= 2 && cruz(inf.at(-2), inf.at(-1), q) <= 0) inf.pop();
    inf.push(q);
  }
  for (const q of [...p].reverse()) {
    while (sup.length >= 2 && cruz(sup.at(-2), sup.at(-1), q) <= 0) sup.pop();
    sup.push(q);
  }
  return inf.slice(0, -1).concat(sup.slice(0, -1));
}

export class Mapa {
  constructor(canvas, cb) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.cb = cb;
    this.prev = null;
    this.cur = null;
    this._prevPorId = new Map();
    this.tLlegada = 0;
    this.intervalo = 55;
    this.seleccionId = null;
    this.herramienta = "seleccionar";
    this.capas = { enlaces: true, paquetes: true, estelas: true, burbujas: true,
                   alcance: true, envolventes: true, vigilancia: true, cobertura: false };
    this.lente = null;          // {id, detalle} — "ver como este nodo"
    this.filtroOrigen = null;   // sólo los OGM de este origen
    this.paquetesOrigen = null; // ...que se piden a /api/paquetes
    this.resaltados = new Map(); // id -> hasta (ms)
    this.mensajes = [];
    this.cobertura = null;
    this._imgCobertura = null;
    this.compositor = { origen: null, destino: null };
    this.escalaUI = 1;
    this._pos = new Map();
    this._arrastre = null;
    this._tr = null;
    this.refrescarTema();
    new ResizeObserver(() => this.redimensionar()).observe(canvas.parentElement);
    this._enlazarPuntero();
    const bucle = () => { this.dibujar(); requestAnimationFrame(bucle); };
    requestAnimationFrame(bucle);
  }

  refrescarTema() {
    this._ui = {
      bg: colorCss("--bg"), tinta: colorCss("--tinta"), tenue: colorCss("--tenue"),
      borde: colorCss("--borde"), piso: colorCss("--piso"), panel: colorCss("--panel"),
    };
  }

  redimensionar() {
    const dpr = window.devicePixelRatio || 1;
    const r = this.canvas.getBoundingClientRect();
    this.canvas.width = Math.max(1, Math.round(r.width * dpr));
    this.canvas.height = Math.max(1, Math.round(r.height * dpr));
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.ancho = r.width;
    this.alto = r.height;
  }

  setFrame(f) {
    const ahora = performance.now();
    if (this.cur && f.generacion === this.cur.generacion) {
      const d = Math.min(Math.max(ahora - this.tLlegada, 16), 500);
      this.intervalo = this.intervalo * 0.8 + d * 0.2;
      this.prev = this.cur;
      this._prevPorId = new Map(this.prev.nodos.map((n) => [n.id, n]));
    } else {
      this.prev = null;
      this._prevPorId = new Map();
      this.mensajes = [];
    }
    this.cur = f;
    this.tLlegada = ahora;
  }

  setCobertura(datos) {
    this.cobertura = datos;
    this._imgCobertura = null;
    if (!datos) return;
    const { nx, ny, valores } = datos;
    const lienzo = document.createElement("canvas");
    lienzo.width = nx; lienzo.height = ny;
    const c = lienzo.getContext("2d");
    const img = c.createImageData(nx, ny);
    for (let j = 0; j < ny; j++) {
      for (let i = 0; i < nx; i++) {
        const v = valores[j * nx + i];
        const k = ((ny - 1 - j) * nx + i) * 4;   // fila 0 de la imagen = arriba
        if (v <= 0) { img.data[k + 3] = 0; continue; }
        const [r, g, b] = v > 0.66 ? [29, 158, 117] : v > 0.33 ? [232, 168, 56] : [226, 75, 74];
        img.data[k] = r; img.data[k + 1] = g; img.data[k + 2] = b;
        img.data[k + 3] = Math.round(255 * (0.18 + 0.32 * v));
      }
    }
    c.putImageData(img, 0, 0);
    this._imgCobertura = lienzo;
  }

  resaltar(ids, ms = 4000) {
    const hasta = performance.now() + ms;
    for (const id of ids) this.resaltados.set(id, hasta);
  }

  animarMensaje(ids, texto, origen, destino) {
    const saltos = Math.max(1, ids.length - 1);
    this.mensajes.push({ ids, texto, origen, destino, inicio: performance.now(),
                         dur: Math.max(1300, 700 * saltos), hold: 3200, ultimas: new Map() });
    this.mensajes = this.mensajes.slice(-4);
  }

  // ── transformación mundo <-> pantalla ──
  _transformacion(ed) {
    const wx0 = -MARGEN, wx1 = ed.ancho + MARGEN, wy0 = -MARGEN, wy1 = ed.alto + MARGEN;
    const escala = Math.min(this.ancho / (wx1 - wx0), this.alto / (wy1 - wy0));
    const xoff = (this.ancho - (wx1 - wx0) * escala) / 2;
    const yoff = (this.alto - (wy1 - wy0) * escala) / 2;
    return {
      escala,
      w2s: (x, y) => [xoff + (x - wx0) * escala, yoff + (wy1 - y) * escala],
      s2w: (sx, sy) => [(sx - xoff) / escala + wx0, wy1 - (sy - yoff) / escala],
    };
  }

  aMundo(px, py) {
    if (!this._tr) return null;
    const [x, y] = this._tr.s2w(px, py);
    const ed = this.cur.edificio;
    return [Math.min(Math.max(x, 0), ed.ancho), Math.min(Math.max(y, 0), ed.alto)];
  }

  nodoEnPunto(px, py, radio = 16) {
    let mejor = null, mejorD = radio * radio;
    for (const [id, [sx, sy]] of this._pos) {
      const d = (sx - px) ** 2 + (sy - py) ** 2;
      if (d < mejorD) { mejorD = d; mejor = id; }
    }
    return mejor;
  }

  enlaceEnPunto(px, py) {
    if (!this.cur || !this.capas.enlaces) return null;
    for (const e of this.cur.enlaces) {
      const a = this._pos.get(e[0]), b = this._pos.get(e[1]);
      if (!a || !b) continue;
      const dx = b[0] - a[0], dy = b[1] - a[1];
      const l2 = dx * dx + dy * dy || 1;
      const t = Math.max(0, Math.min(1, ((px - a[0]) * dx + (py - a[1]) * dy) / l2));
      const d = Math.hypot(px - (a[0] + t * dx), py - (a[1] + t * dy));
      if (d < 5) return e;
    }
    return null;
  }

  // ── entrada: selección, arrastre, menú, hover ──
  _enlazarPuntero() {
    const c = this.canvas;
    const local = (ev) => {
      const r = c.getBoundingClientRect();
      return [ev.clientX - r.left, ev.clientY - r.top];
    };
    c.addEventListener("pointerdown", (ev) => {
      if (ev.button !== 0 || !this.cur) return;
      const [px, py] = local(ev);
      const id = this.nodoEnPunto(px, py);
      if (this.herramienta !== "seleccionar" && id == null) {
        const w = this.aMundo(px, py);
        if (w) this.cb.agregar(this.herramienta, w[0], w[1]);
        return;
      }
      if (id != null) {
        this._arrastre = { id, x0: px, y0: py, movido: false, w: null };
        c.setPointerCapture(ev.pointerId);
      }
    });
    c.addEventListener("pointermove", (ev) => {
      const [px, py] = local(ev);
      const a = this._arrastre;
      if (a) {
        if (!a.movido && Math.hypot(px - a.x0, py - a.y0) > 4) a.movido = true;
        if (a.movido) { a.w = this.aMundo(px, py); this.cb.hover(null); }
        return;
      }
      const id = this.nodoEnPunto(px, py);
      if (id != null) this.cb.hover({ tipo: "nodo", id }, px, py);
      else {
        const e = this.enlaceEnPunto(px, py);
        this.cb.hover(e ? { tipo: "enlace", enlace: e } : null, px, py);
      }
      c.style.cursor = id != null ? "pointer" :
        (this.herramienta === "seleccionar" ? "default" : "crosshair");
    });
    c.addEventListener("pointerleave", () => this.cb.hover(null));
    c.addEventListener("pointerup", () => {
      const a = this._arrastre;
      this._arrastre = null;
      if (!a) return;
      if (a.movido && a.w) this.cb.soltar(a.id, a.w[0], a.w[1]);
      else this.cb.seleccionar(a.id);
    });
    c.addEventListener("contextmenu", (ev) => {
      ev.preventDefault();
      if (!this.cur) return;
      const [px, py] = local(ev);
      this.cb.menu(this.nodoEnPunto(px, py), ev.clientX, ev.clientY, this.aMundo(px, py));
    });
  }

  // ── dibujo ──
  dibujar() {
    const f = this.cur;
    const { ctx } = this;
    if (!f || !this.ancho) return;
    const ahora = performance.now();
    const alfa = this.prev ? Math.min(1, (ahora - this.tLlegada) / this.intervalo) : 1;
    const tr = this._transformacion(f.edificio);
    this._tr = tr;
    const { w2s, escala } = tr;
    const col = f.colores;
    const ui = this._ui;
    const k = this.escalaUI;

    // posiciones interpoladas (pantalla) de todos los nodos
    this._pos = new Map();
    const porId = new Map();
    for (const n of f.nodos) {
      const p = this._prevPorId.get(n.id);
      let x = p ? lerp(p.x, n.x, alfa) : n.x;
      let y = p ? lerp(p.y, n.y, alfa) : n.y;
      if (this._arrastre?.movido && this._arrastre.id === n.id && this._arrastre.w) {
        [x, y] = this._arrastre.w;
      }
      this._pos.set(n.id, w2s(x, y));
      porId.set(n.id, n);
    }
    const pos = (id) => this._pos.get(id);

    ctx.clearRect(0, 0, this.ancho, this.alto);
    ctx.fillStyle = ui.bg;
    ctx.fillRect(0, 0, this.ancho, this.alto);

    // edificio: pisos y hueco de escalera
    const { piso_h, n_pisos, ancho, alto, stair_xy, stair_half_w } = f.edificio;
    ctx.font = `${12 * k}px system-ui, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (let p = 0; p < n_pisos; p++) {
      const [x0, y0] = w2s(0, (p + 1) * piso_h);
      const [x1, y1] = w2s(ancho, p * piso_h);
      ctx.fillStyle = ui.piso;
      ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
      ctx.strokeStyle = ui.borde;
      ctx.lineWidth = 1;
      ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
      ctx.fillStyle = ui.tenue;
      ctx.fillText(`P${p + 1}`, ...w2s(-1.3, p * piso_h + piso_h / 2));
    }
    {
      const [sx0, sy0] = w2s(stair_xy[0] - stair_half_w, alto);
      const [sx1, sy1] = w2s(stair_xy[0] + stair_half_w, 0);
      ctx.fillStyle = "rgba(29,158,117,0.10)";
      ctx.fillRect(sx0, sy0, sx1 - sx0, sy1 - sy0);
    }

    // cobertura
    if (this.capas.cobertura && this._imgCobertura) {
      const { nx, ny, paso } = this.cobertura;
      const [x0, y0] = w2s(0, ny * paso);
      const [x1, y1] = w2s(nx * paso, 0);
      ctx.imageSmoothingEnabled = true;
      ctx.drawImage(this._imgCobertura, x0, y0, x1 - x0, y1 - y0);
    }

    const lente = this.lente?.detalle && porId.has(this.lente.id) ? this.lente.detalle : null;
    const visiblesLente = new Set();
    if (lente) {
      visiblesLente.add(lente.id);
      for (const r of lente.rutas) { visiblesLente.add(r.destino); visiblesLente.add(r.via); }
    }

    // envolventes por grupo conexo (particiones visibles)
    if (this.capas.envolventes && !lente && f.grupos.length > 1) {
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      f.grupos.forEach((g, i) => {
        const pts = g.map(pos).filter(Boolean);
        if (!pts.length) return;
        const c = PALETA_GRUPOS[i % PALETA_GRUPOS.length];
        const h = envolvente(pts);
        ctx.beginPath();
        h.forEach(([x, y], j) => (j ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
        if (h.length > 2) ctx.closePath();
        if (h.length === 1) ctx.lineTo(h[0][0] + 0.01, h[0][1]);
        ctx.strokeStyle = c + "26";
        ctx.lineWidth = 38 * k;
        ctx.stroke();
        if (h.length > 2) { ctx.fillStyle = c + "26"; ctx.fill(); }
      });
    }

    // anillo de alcance del seleccionado
    const sel = porId.get(this.seleccionId);
    if (this.capas.alcance && sel?.vivo) {
      const [cx, cy] = pos(sel.id);
      ctx.beginPath();
      ctx.arc(cx, cy, (f.cfg.rango_comm || 16) * escala, 0, Math.PI * 2);
      ctx.strokeStyle = sel.color + "66";
      ctx.setLineDash([4, 4]);
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // enlaces de radio (verdad física)
    if (this.capas.enlaces) {
      for (const [ia, ib, fiab] of f.enlaces) {
        const a = pos(ia), b = pos(ib);
        if (!a || !b) continue;
        ctx.strokeStyle = colorEnlace(fiab);
        ctx.globalAlpha = lente ? 0.08 : 0.3 + 0.4 * fiab;
        ctx.lineWidth = Math.max(1, 1 + 2 * fiab);
        ctx.beginPath(); ctx.moveTo(...a); ctx.lineTo(...b); ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }

    // estelas
    if (this.capas.estelas) {
      ctx.lineWidth = 1;
      for (const n of f.nodos) {
        if (n.estela.length < 2) continue;
        ctx.strokeStyle = n.color + (lente ? "18" : "48");
        ctx.beginPath();
        n.estela.forEach(([x, y], i) => (i ? ctx.lineTo(...w2s(x, y)) : ctx.moveTo(...w2s(x, y))));
        ctx.stroke();
      }
    }

    // paquetes en vuelo (extrapolados entre frames por el avance de t).
    // [x0, y0, x1, y1, progreso, tipo, origen, ttl]. Con un filtro de
    // origen se usan todos los OGM de ese origen (/api/paquetes); si no,
    // la muestra del frame.
    if (this.capas.paquetes) {
      const filtrado = this.filtroOrigen != null;
      const lista = filtrado ? (this.paquetesOrigen || []) : f.paquetes;
      const extra = this.prev ? alfa * Math.max(0, f.t - this.prev.t) / 1.4 : 0;
      for (const [x0, y0, x1, y1, progreso, tipo, , ttl] of lista) {
        const prog = Math.min(1, progreso + extra);
        if (prog >= 1) continue;
        const [sx, sy] = w2s(lerp(x0, x1, prog), lerp(y0, y1, prog));
        ctx.globalAlpha = Math.max(0.15, 1 - prog) * (lente && !filtrado ? 0.3 : 1);
        ctx.fillStyle = tipo === "OGM" ? col.ogm : col.bcn;
        ctx.beginPath(); ctx.arc(sx, sy, (filtrado ? 5 : 3.5) * k, 0, Math.PI * 2); ctx.fill();
        if (filtrado && ttl != null) {
          ctx.globalAlpha = 1;
          ctx.fillStyle = ui.tinta;
          ctx.font = `${10 * k}px system-ui, sans-serif`;
          ctx.fillText(`ttl ${ttl}`, sx, sy - 9 * k);
        }
      }
      ctx.globalAlpha = 1;
      if (!filtrado && f.paquetes_total > f.paquetes.length) {
        ctx.font = `${11 * k}px system-ui, sans-serif`;
        ctx.textAlign = "left";
        ctx.fillStyle = ui.tenue;
        ctx.fillText(`Paquetes: se dibuja una muestra de ${f.paquetes.length} de ${f.paquetes_total} en vuelo`,
                     8, this.alto - 10);
        ctx.textAlign = "center";
      }
    }

    // vigilancia: anillos que se llenan con el silencio contra el timeout
    if (this.capas.vigilancia && sel?.rol === "G" && sel.vivo && !lente) {
      for (const v of f.vigilancia) {
        if (v.observador !== sel.id) continue;
        const p = pos(v.observado);
        if (!p) continue;
        const frac = Math.min(1, v.silencio / v.timeout);
        const r = 16 * k;
        ctx.lineWidth = 3;
        ctx.strokeStyle = ui.borde;
        ctx.beginPath(); ctx.arc(p[0], p[1], r, 0, Math.PI * 2); ctx.stroke();
        ctx.strokeStyle = v.cree_caido ? "#C0392B" : frac > 0.66 ? "#E67E22" : "#1D9E75";
        ctx.beginPath();
        ctx.arc(p[0], p[1], r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * (v.cree_caido ? 1 : frac));
        ctx.stroke();
      }
    }

    // lente: lo que el nodo cree saber
    if (lente) this._dibujarLente(lente, pos, porId, k);

    // nodos
    ctx.textBaseline = "alphabetic";
    for (const n of f.nodos) {
      const [sx, sy] = pos(n.id);
      const tenue = lente && !visiblesLente.has(n.id);
      ctx.globalAlpha = tenue ? 0.22 : 1;
      const c = n.en_alerta ? col.alerta : (n.vivo ? n.color : col.caido);
      ctx.fillStyle = c;
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2;
      const r = RADIO * k;
      ctx.beginPath();
      if (n.rol === "G") ctx.arc(sx, sy, r, 0, Math.PI * 2);
      else { ctx.moveTo(sx, sy - r); ctx.lineTo(sx + r, sy); ctx.lineTo(sx, sy + r); ctx.lineTo(sx - r, sy); ctx.closePath(); }
      ctx.fill(); ctx.stroke();
      if (!n.vivo) {
        ctx.strokeStyle = "#fff";
        ctx.beginPath();
        ctx.moveTo(sx - 4 * k, sy - 4 * k); ctx.lineTo(sx + 4 * k, sy + 4 * k);
        ctx.moveTo(sx + 4 * k, sy - 4 * k); ctx.lineTo(sx - 4 * k, sy + 4 * k);
        ctx.stroke();
      }
      if (n.id === this.seleccionId) {
        ctx.strokeStyle = n.vivo ? n.color : col.caido;
        ctx.beginPath(); ctx.arc(sx, sy, 14 * k, 0, Math.PI * 2); ctx.stroke();
      }
      if (n.id === this.filtroOrigen) {
        ctx.strokeStyle = col.ogm;
        ctx.setLineDash([3, 3]);
        ctx.beginPath(); ctx.arc(sx, sy, 18 * k, 0, Math.PI * 2); ctx.stroke();
        ctx.setLineDash([]);
      }
      let tag = n.etiqueta + (!n.vivo ? " ×" : n.en_alerta ? " !" : "");
      tag += ` ${Math.round(n.bateria)}%`;
      ctx.font = `${n.id === this.seleccionId ? "600 " : ""}${11 * k}px system-ui, sans-serif`;
      ctx.textAlign = "center";
      ctx.fillStyle = n.en_alerta ? col.alerta : ui.tinta;
      ctx.fillText(tag, sx, sy - 14 * k);
      if (this.capas.burbujas && n.beacon && n.ultimo_mensaje && !lente) {
        ctx.font = `italic ${10 * k}px system-ui, sans-serif`;
        ctx.textAlign = "left";
        ctx.fillStyle = ui.tenue;
        ctx.fillText(`“${n.ultimo_mensaje}”`, sx + 12 * k, sy + 18 * k);
      }
    }
    ctx.globalAlpha = 1;

    // compositor: origen / destino elegidos
    for (const [id, letra] of [[this.compositor.origen, "de"], [this.compositor.destino, "a"]]) {
      const p = id != null && pos(id);
      if (!p) continue;
      ctx.strokeStyle = col.mensaje;
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(p[0], p[1], 17 * k, 0, Math.PI * 2); ctx.stroke();
      ctx.fillStyle = col.mensaje;
      ctx.font = `600 ${10 * k}px system-ui, sans-serif`;
      ctx.fillText(letra, p[0] + 20 * k, p[1] + 4 * k);
    }

    // resaltados (clic en la línea de tiempo)
    for (const [id, hasta] of this.resaltados) {
      if (hasta < ahora) { this.resaltados.delete(id); continue; }
      const p = pos(id);
      if (!p) continue;
      const pulso = 20 * k + 5 * Math.sin(ahora / 140);
      ctx.strokeStyle = "#E67E22";
      ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(p[0], p[1], pulso, 0, Math.PI * 2); ctx.stroke();
    }

    this._dibujarMensajes(pos, col, ahora, k);
  }

  _flecha(a, b, color, ancho, recorte = 12) {
    const { ctx } = this;
    const dx = b[0] - a[0], dy = b[1] - a[1];
    const l = Math.hypot(dx, dy);
    if (l < 2 * recorte) return;
    const ux = dx / l, uy = dy / l;
    const x0 = a[0] + ux * recorte, y0 = a[1] + uy * recorte;
    const x1 = b[0] - ux * recorte, y1 = b[1] - uy * recorte;
    ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = ancho;
    ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x1 - ux * 9 - uy * 5, y1 - uy * 9 + ux * 5);
    ctx.lineTo(x1 - ux * 9 + uy * 5, y1 - uy * 9 - ux * 5);
    ctx.closePath(); ctx.fill();
  }

  _dibujarLente(d, pos, porId, k) {
    const { ctx } = this;
    const yo = pos(d.id);
    if (!yo) return;
    const ui = this._ui;
    // rutas: siguiente salto (flecha) y destino final (línea punteada)
    const saltos = new Map();
    for (const r of d.rutas) {
      const color = r.obsoleta ? "#C0392B" : "#2E6FB7";
      const v = pos(r.via), dst = pos(r.destino);
      if (v && !saltos.has(r.via)) saltos.set(r.via, color);
      if (v && dst && r.via !== r.destino) {
        ctx.setLineDash([4, 5]);
        ctx.strokeStyle = color + "AA";
        ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(...v); ctx.lineTo(...dst); ctx.stroke();
        ctx.setLineDash([]);
      }
      if (dst) {
        ctx.font = `${10 * k}px system-ui, sans-serif`;
        ctx.textAlign = "center";
        const texto = `${r.hops} salto${r.hops === 1 ? "" : "s"} · TQ ${r.tq.toFixed(2)} · hace ${r.edad_s.toFixed(0)}s`;
        const w = ctx.measureText(texto).width + 8;
        ctx.fillStyle = ui.panel;
        ctx.globalAlpha = 0.9;
        ctx.fillRect(dst[0] - w / 2, dst[1] + 13 * k, w, 14 * k);
        ctx.globalAlpha = 1;
        ctx.fillStyle = r.obsoleta ? "#C0392B" : ui.tinta;
        ctx.fillText(texto, dst[0], dst[1] + 24 * k);
      }
    }
    for (const [via, color] of saltos) this._flecha(yo, pos(via), color, 2.5);
    // lo que cree caído
    for (const c of d.cree_caidos) {
      const p = pos(c.id);
      if (!p) continue;
      ctx.strokeStyle = "#C0392B"; ctx.lineWidth = 2.5;
      ctx.beginPath(); ctx.arc(p[0], p[1], 19 * k, 0, Math.PI * 2); ctx.stroke();
    }
    // lo que la radio alcanza pero el nodo todavía no conoce
    for (const a of d.alcanzables_sin_ruta) {
      const p = pos(a.id);
      if (!p) continue;
      ctx.strokeStyle = "#D9922A"; ctx.lineWidth = 2;
      ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.arc(p[0], p[1], 17 * k, 0, Math.PI * 2); ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;
      ctx.fillStyle = "#D9922A";
      ctx.font = `600 ${11 * k}px system-ui, sans-serif`;
      ctx.fillText("?", p[0] + 18 * k, p[1] - 10 * k);
    }
  }

  _dibujarMensajes(pos, col, ahora, k) {
    const { ctx } = this;
    this.mensajes = this.mensajes.filter((m) => ahora - m.inicio < m.dur + m.hold);
    for (const m of this.mensajes) {
      const pts = m.ids.map((id) => {
        const p = pos(id);
        if (p) m.ultimas.set(id, p);
        return p || m.ultimas.get(id);
      }).filter(Boolean);
      if (pts.length < 2) continue;
      ctx.strokeStyle = col.mensaje + "99";
      ctx.lineWidth = 3;
      ctx.beginPath();
      pts.forEach((p, i) => (i ? ctx.lineTo(...p) : ctx.moveTo(...p)));
      ctx.stroke();
      const el = ahora - m.inicio;
      const segs = pts.length - 1;
      let x, y;
      if (el <= m.dur) {
        const sf = (el / m.dur) * segs;
        const i = Math.min(Math.floor(sf), segs - 1);
        const t = sf - i;
        x = lerp(pts[i][0], pts[i + 1][0], t);
        y = lerp(pts[i][1], pts[i + 1][1], t);
      } else {
        [x, y] = pts.at(-1);
      }
      ctx.fillStyle = col.mensaje;
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(x, y, 6 * k, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      let texto = `${m.origen}→${m.destino}: ${m.texto}`;
      if (texto.length > 46) texto = texto.slice(0, 45) + "…";
      ctx.font = `600 ${12 * k}px system-ui, sans-serif`;
      ctx.textAlign = "left";
      const w = ctx.measureText(texto).width + 12;
      const bx = Math.min(Math.max(x + 12, 4), this.ancho - w - 4);
      const by = Math.max(y - 24 * k, 4);
      ctx.fillStyle = col.mensaje;
      ctx.beginPath();
      ctx.roundRect(bx, by, w, 18 * k, 5);
      ctx.fill();
      ctx.fillStyle = "#fff";
      ctx.fillText(texto, bx + 6, by + 13 * k);
    }
  }
}
