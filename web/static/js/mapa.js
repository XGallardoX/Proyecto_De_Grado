// Dibuja el edificio y la malla en un <canvas>. Sólo pinta lo que ya
// viene calculado en el frame (nodos, enlaces, paquetes, grupos): nada
// del modelo se recalcula acá (ver contrato de paridad).

const MARGEN = 2.5;

export class Mapa {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.seleccionId = null;
    this.ultimoFrame = null;
    this._nodosPantalla = [];
    window.addEventListener("resize", () => this.redimensionar());
    this.redimensionar();
  }

  redimensionar() {
    const dpr = window.devicePixelRatio || 1;
    const rect = this.canvas.getBoundingClientRect();
    this.canvas.width = Math.max(1, Math.round(rect.width * dpr));
    this.canvas.height = Math.max(1, Math.round(rect.height * dpr));
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.anchoCss = rect.width;
    this.altoCss = rect.height;
    if (this.ultimoFrame) this.dibujar(this.ultimoFrame);
  }

  _transformacion(edificio) {
    const wx0 = -MARGEN, wx1 = edificio.ancho + MARGEN;
    const wy0 = -MARGEN, wy1 = edificio.alto + MARGEN;
    const sx = this.anchoCss / (wx1 - wx0);
    const sy = this.altoCss / (wy1 - wy0);
    const escala = Math.min(sx, sy);
    const xoff = (this.anchoCss - (wx1 - wx0) * escala) / 2;
    const yoff = (this.altoCss - (wy1 - wy0) * escala) / 2;
    return {
      escala,
      w2s: (wx, wy) => [xoff + (wx - wx0) * escala, yoff + (wy1 - wy) * escala],
    };
  }

  // Nodo más cercano a un punto de pantalla (clic de selección), o null.
  nodoEnPunto(px, py, radio = 16) {
    let mejor = null, mejorD = radio * radio;
    for (const n of this._nodosPantalla) {
      const d = (n.sx - px) ** 2 + (n.sy - py) ** 2;
      if (d < mejorD) { mejorD = d; mejor = n.id; }
    }
    return mejor;
  }

  dibujar(frame) {
    this.ultimoFrame = frame;
    const { ctx } = this;
    const { escala, w2s } = this._transformacion(frame.edificio);
    const col = frame.colores;

    ctx.clearRect(0, 0, this.anchoCss, this.altoCss);
    ctx.fillStyle = col.fondo;
    ctx.fillRect(0, 0, this.anchoCss, this.altoCss);

    // pisos
    const { piso_h, n_pisos, ancho } = frame.edificio;
    ctx.font = "12px system-ui, sans-serif";
    for (let p = 0; p < n_pisos; p++) {
      const y0 = p * piso_h;
      const [x0, y0s] = w2s(0, y0 + piso_h);
      const [x1, y1s] = w2s(ancho, y0);
      ctx.fillStyle = col.piso + "80";
      ctx.fillRect(x0, y0s, x1 - x0, y1s - y0s);
      ctx.strokeStyle = col.pared;
      ctx.strokeRect(x0, y0s, x1 - x0, y1s - y0s);
      ctx.fillStyle = "#5F5E5A";
      ctx.textAlign = "center";
      const [lx, ly] = w2s(-1.4, y0 + piso_h / 2);
      ctx.fillText(`P${p + 1}`, lx, ly);
    }

    // anillo de alcance del nodo seleccionado
    const nodos = frame.nodos;
    const sel = nodos.find((n) => n.id === this.seleccionId);
    if (sel && sel.vivo) {
      const [cx, cy] = w2s(sel.x, sel.y);
      const r = (frame.cfg.rango_comm || 16) * escala;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.strokeStyle = sel.color + "66";
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    // enlaces, coloreados por fiabilidad (mismos umbrales que pygame)
    const porId = Object.fromEntries(nodos.map((n) => [n.id, n]));
    for (const e of frame.enlaces) {
      const a = porId[e.a], b = porId[e.b];
      if (!a || !b) continue;
      const base = e.fiabilidad > 0.66 ? "#1D9E75"
                 : e.fiabilidad > 0.33 ? "#E8A838" : "#E24B4A";
      ctx.strokeStyle = base;
      ctx.globalAlpha = 0.3 + 0.4 * e.fiabilidad;
      ctx.lineWidth = Math.max(1, 1 + 2 * e.fiabilidad);
      const [ax, ay] = w2s(a.x, a.y), [bx, by] = w2s(b.x, b.y);
      ctx.beginPath();
      ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.stroke();
      ctx.globalAlpha = 1;
    }

    // estelas
    for (const n of nodos) {
      if (n.estela.length < 2) continue;
      ctx.strokeStyle = n.color + "48";
      ctx.lineWidth = 1;
      ctx.beginPath();
      n.estela.forEach(([wx, wy], i) => {
        const [sx, sy] = w2s(wx, wy);
        i === 0 ? ctx.moveTo(sx, sy) : ctx.lineTo(sx, sy);
      });
      ctx.stroke();
    }

    // paquetes en vuelo
    for (const p of frame.paquetes) {
      const ox = p.origen_x + (p.destino_x - p.origen_x) * p.progreso;
      const oy = p.origen_y + (p.destino_y - p.origen_y) * p.progreso;
      const [sx, sy] = w2s(ox, oy);
      const color = p.tipo === "OGM" ? col.ogm
                  : p.tipo === "BCN" ? col.bcn : col.mensaje;
      ctx.fillStyle = color;
      ctx.globalAlpha = Math.max(0.1, 1 - p.progreso);
      ctx.beginPath();
      ctx.arc(sx, sy, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = 1;
    }

    // nodos
    this._nodosPantalla = [];
    for (const n of nodos) {
      const [sx, sy] = w2s(n.x, n.y);
      this._nodosPantalla.push({ id: n.id, sx, sy });
      const color = n.en_alerta ? col.alerta : (n.vivo ? n.color : col.caido);
      ctx.fillStyle = color;
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2;
      if (n.rol === "G") {
        ctx.beginPath(); ctx.arc(sx, sy, 9, 0, Math.PI * 2);
        ctx.fill(); ctx.stroke();
      } else {
        ctx.beginPath();
        ctx.moveTo(sx, sy - 9); ctx.lineTo(sx + 9, sy);
        ctx.lineTo(sx, sy + 9); ctx.lineTo(sx - 9, sy);
        ctx.closePath(); ctx.fill(); ctx.stroke();
      }
      if (n.id === this.seleccionId && n.vivo) {
        ctx.beginPath(); ctx.arc(sx, sy, 14, 0, Math.PI * 2);
        ctx.strokeStyle = n.color; ctx.lineWidth = 2; ctx.stroke();
      }
      let tag = n.etiqueta;
      if (!n.vivo) tag += " ×";
      else if (n.en_alerta) tag += " !";
      tag += ` ${Math.round(n.bateria)}%`;
      ctx.fillStyle = color;
      ctx.textAlign = "center";
      ctx.fillText(tag, sx, sy - 14);
      if (n.beacon && n.ultimo_mensaje) {
        ctx.fillStyle = "#555";
        ctx.font = "italic 11px system-ui, sans-serif";
        ctx.textAlign = "left";
        ctx.fillText(`"${n.ultimo_mensaje}"`, sx + 12, sy + 18);
        ctx.font = "12px system-ui, sans-serif";
      }
    }
  }
}
