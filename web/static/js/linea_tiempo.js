// Línea de tiempo de eventos (FAIL, RECOVER, ALERT_ON/OFF, PARTITION,
// HEAL, PARAM, MSG_OK/FAIL, MOVE) con iconos. Un clic en un evento
// avisa a `alElegir(evento)` para resaltar los nodos implicados.

import { ICONOS_EVENTO } from "./util.js";

export class LineaTiempo {
  constructor(contenedor, alElegir) {
    this.contenedor = contenedor;
    this.alElegir = alElegir;
    this.eventos = [];
    this.t = 0;
    this._firma = "";
  }

  setDatos(eventos, t) {
    this.eventos = eventos;
    this.t = t;
  }

  dibujar() {
    const tmax = Math.max(this.t, 10);
    // redibujar sólo si cambió algo visible (evita rehacer el DOM a 60 Hz)
    const firma = `${this.eventos.length}|${Math.round(tmax / 5)}`;
    if (firma === this._firma) return;
    this._firma = firma;
    const c = this.contenedor;
    c.replaceChildren();
    const eje = document.createElement("div");
    eje.className = "eje";
    c.append(eje);
    // un paso "redondo" que deje como mucho ~12 marcas
    const pasoMarca = [10, 20, 30, 60, 120, 300, 600, 1200, 1800, 3600, 7200]
      .find((p) => tmax / p <= 12) ?? Math.ceil(tmax / 12 / 3600) * 3600;
    for (let s = 0; s <= tmax; s += pasoMarca) {
      const m = document.createElement("span");
      m.className = "marca-t";
      m.style.left = `${(s / tmax) * 100}%`;
      m.textContent = `${s}s`;
      c.append(m);
    }
    for (const ev of this.eventos) {
      const [icono, color, nombre] = ICONOS_EVENTO[ev.tipo] || ["•", "#888", ev.tipo];
      const b = document.createElement("button");
      b.className = "ev";
      b.style.left = `${(ev.t / tmax) * 100}%`;
      b.style.background = color;
      b.textContent = icono;
      b.title = `[${ev.t.toFixed(1)} s] ${nombre}: ${ev.texto}`;
      b.setAttribute("aria-label", b.title);
      b.addEventListener("click", () => this.alElegir(ev));
      c.append(b);
    }
  }
}
