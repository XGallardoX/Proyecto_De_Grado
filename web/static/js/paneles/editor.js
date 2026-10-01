// Editor de escenarios: arma un JSON con el mismo esquema que
// escenarios/*.json. La validación y el guardado los hace el servidor con
// sim/config_loader.py (acción validar_escenario / guardar_escenario):
// acá no se duplica ninguna regla.

import * as api from "../api.js";
import { bloqueComando, colorCss, esc, toast } from "../util.js";

const CAMPOS_EDIFICIO = [["ancho", "Ancho (m)"], ["alto", "Alto (m)"],
                         ["piso_h", "Alto de piso (m)"], ["n_pisos", "Pisos"]];
const CAMPOS_MEDIO = [["rango_comm", "Alcance (m)"], ["perdida_base", "Pérdida base"],
                      ["falloff", "Falloff"], ["floor_atten", "Atenuación por piso"]];
const CAMPOS_PROTOCOLO = [["timeout", "Timeout (s)"], ["beacon_cada", "Beacon cada (s)"],
                          ["batman_cada", "OGM cada (s)"], ["ttl", "TTL"],
                          ["battery_drain", "Drenaje G (%/s)"],
                          ["battery_drain_nodo", "Drenaje N (%/s)"],
                          ["move_speed", "Velocidad G (m/paso)"]];

export class Editor {
  constructor(dialogo, contenedor, alCargar) {
    this.dialogo = dialogo;
    this.c = contenedor;
    this.alCargar = alCargar;
    this.datos = null;
    this.herramienta = "G";
    this.arrastre = null;
    this.guardado = null;
    this.nombre = "mi_escenario";
  }

  async abrir(posiciones = "iniciales") {
    this.datos = await api.obtenerEscenarioActual(posiciones);
    if (!this.datos) return;
    this.datos.events = this.datos.events || [];
    this.nombre = `${this.datos.name}_editado`.replace(/[^\w.-]/g, "_");
    this.guardado = null;
    if (!this.dialogo.open) this.dialogo.showModal();
    this._construir();
  }

  vacio() {
    const b = this.datos.building;
    this.datos = { name: "nuevo", building: b, medium: this.datos.medium,
                 protocol: this.datos.protocol, nodes: [], events: [] };
    this._construir();
  }

  _etiquetas() {
    const cuenta = { G: 0, N: 0 }, et = new Map();
    for (const n of this.datos.nodes) et.set(n.id, `${n.role}${++cuenta[n.role]}`);
    return et;
  }

  _construir() {
    const e = this.datos;
    const campo = (seccion, [clave, nombre]) =>
      `<label>${nombre}<input type="number" step="any" data-seccion="${seccion}" data-clave="${clave}" value="${e[seccion][clave] ?? ""}"></label>`;
    this.c.innerHTML = `
      <div class="ed-barra">
        <strong>Editor de escenarios</strong>
        <span class="grupo" role="group" aria-label="Herramienta">
          ${[["G", "+ Gateway"], ["N", "+ Nodo"], ["mover", "Mover"], ["borrar", "Borrar"]].map(([h, t]) =>
            `<button class="ed-herr ${h === this.herramienta ? "activa" : ""}" data-h="${h}">${t}</button>`).join("")}
        </span>
        <button data-a="iniciales" title="Escenario de la sesión con las posiciones del archivo">Desde la sesión</button>
        <button data-a="actuales" title="Con las posiciones de ahora">Posiciones actuales</button>
        <button data-a="vacio">Vacío</button>
        <span class="grupo" style="margin-left:auto">
          <label class="compacto">Nombre <input id="ed-nombre" type="text" value="${esc(this.nombre)}" size="16"></label>
          <label class="compacto"><input id="ed-sobrescribir" type="checkbox"> sobrescribir</label>
          <button data-a="validar">Validar</button>
          <button data-a="guardar">Guardar en escenarios/</button>
          <button data-a="descargar">Descargar JSON</button>
          <button data-a="cerrar">Cerrar</button>
        </span>
      </div>
      <div class="ed-lienzo"><canvas aria-label="Edificio del escenario"></canvas></div>
      <div class="ed-lado">
        <div id="ed-msg"></div>
        <h3>Nodos (${e.nodes.length})</h3>
        <p class="detalle">Clic en el edificio para poner un nodo con la herramienta elegida; arrastrá para moverlo. Recordá: x horizontal, y altura (el piso sale de y).</p>
        <table class="tabla" id="ed-nodos"></table>
        <h3>Edificio</h3>${CAMPOS_EDIFICIO.map((c) => campo("building", c)).join("")}
        <h3>Medio</h3>${CAMPOS_MEDIO.map((c) => campo("medium", c)).join("")}
        <h3>Protocolo</h3>${CAMPOS_PROTOCOLO.map((c) => campo("protocol", c)).join("")}
        <label>Movilidad <select id="ed-movilidad">
          ${["seguir", "repartir"].map((m) => `<option ${e.protocol.movilidad === m ? "selected" : ""}>${m}</option>`).join("")}
        </select></label>
        <h3>Eventos <small class="detalle">wander: un Gateway se aleja hasta t = until</small></h3>
        <div id="ed-eventos"></div>
        <button data-a="evento">+ wander</button>
      </div>`;

    this.c.querySelectorAll(".ed-herr").forEach((b) => b.addEventListener("click", () => {
      this.herramienta = b.dataset.h;
      this.c.querySelectorAll(".ed-herr").forEach((x) => x.classList.toggle("activa", x === b));
    }));
    this.c.querySelectorAll("[data-a]").forEach((b) => b.addEventListener("click", () => this._accion(b.dataset.a)));
    this.c.querySelectorAll("input[data-seccion]").forEach((inp) => inp.addEventListener("change", () => {
      const v = inp.value === "" ? undefined : Number(inp.value);
      if (v === undefined) delete e[inp.dataset.seccion][inp.dataset.clave];
      else e[inp.dataset.seccion][inp.dataset.clave] = v;
      this._dibujar();
    }));
    this.c.querySelector("#ed-movilidad").addEventListener("change", (ev) => { e.protocol.movilidad = ev.target.value; });
    this.c.querySelector("#ed-nombre").addEventListener("input", (ev) => { this.nombre = ev.target.value.trim(); });

    this.canvas = this.c.querySelector("canvas");
    this._enlazarLienzo();
    new ResizeObserver(() => this._dibujar()).observe(this.canvas.parentElement);
    this._pintarNodos();
    this._pintarEventos();
    this._dibujar();
  }

  _mensaje(html, tipo) {
    this.c.querySelector("#ed-msg").innerHTML = `<div class="ed-msg ${tipo}">${html}</div>`;
  }

  async _accion(a) {
    try {
      if (a === "iniciales" || a === "actuales") await this.abrir(a);
      else if (a === "vacio") this.vacio();
      else if (a === "cerrar") this.dialogo.close();
      else if (a === "evento") {
        const g = this.datos.nodes.find((n) => n.role === "G");
        if (!g) { this._mensaje("Primero agregá un Gateway.", "error"); return; }
        this.datos.events.push({ type: "wander", node_id: g.id, until: 60 });
        this._pintarEventos();
      } else if (a === "validar") {
        const r = await api.enviarComando("validar_escenario", { escenario: this.datos });
        this._mensaje(`Válido: ${r.nodos} nodos, ${r.gateways} Gateway.`, "ok");
      } else if (a === "guardar") {
        const sobrescribir = this.c.querySelector("#ed-sobrescribir").checked;
        const r = await api.enviarComando("guardar_escenario",
          { escenario: this.datos, nombre: this.nombre, sobrescribir });
        this.guardado = r.archivo;
        this._mensaje(`Guardado en <code>${esc(r.ruta)}</code>. Para correrlo desde la terminal:
          ${bloqueComando(r.comando)}${bloqueComando(r.comando_headless)}
          <button data-cargar>Cargarlo en esta sesión</button>`, "ok");
        this.c.querySelector("[data-cargar]").addEventListener("click", async () => {
          await this.alCargar({ archivo: this.guardado });
          this.dialogo.close();
        });
      } else if (a === "descargar") {
        const blob = new Blob([JSON.stringify({ ...this.datos, name: this.nombre }, null, 2) + "\n"],
                              { type: "application/json" });
        const enlace = document.createElement("a");
        enlace.href = URL.createObjectURL(blob);
        enlace.download = `${this.nombre || "escenario"}.json`;
        enlace.click();
        setTimeout(() => URL.revokeObjectURL(enlace.href), 1000);
      }
    } catch (err) {
      this._mensaje(esc(err.message), "error");
    }
  }

  _pintarNodos() {
    const et = this._etiquetas();
    const t = this.c.querySelector("#ed-nodos");
    t.innerHTML = `<tr><th>Nodo</th><th>Rol</th><th>x</th><th>y</th><th>Bat.</th><th></th></tr>` +
      this.datos.nodes.map((n, i) => `<tr data-i="${i}">
        <td>${et.get(n.id)} <small class="detalle">id ${n.id}</small></td>
        <td><select data-k="role"><option ${n.role === "G" ? "selected" : ""}>G</option><option ${n.role === "N" ? "selected" : ""}>N</option></select></td>
        <td><input type="number" step="0.1" data-k="x" value="${n.x}" style="width:4.5em"></td>
        <td><input type="number" step="0.1" data-k="y" value="${n.y}" style="width:4.5em"></td>
        <td><input type="number" step="1" min="0" max="100" data-k="battery" value="${n.battery ?? ""}" placeholder="100" style="width:4em"></td>
        <td><button data-borrar title="Borrar">✕</button></td></tr>`).join("");
    t.querySelectorAll("tr[data-i]").forEach((tr) => {
      const n = this.datos.nodes[Number(tr.dataset.i)];
      tr.querySelectorAll("[data-k]").forEach((inp) => inp.addEventListener("change", () => {
        const k = inp.dataset.k;
        if (k === "role") n.role = inp.value;
        else if (inp.value === "") delete n[k];
        else n[k] = Number(inp.value);
        this._pintarNodos(); this._pintarEventos(); this._dibujar();
      }));
      tr.querySelector("[data-borrar]").addEventListener("click", () => this._borrar(n.id));
    });
    this.c.querySelector(".ed-lado h3").textContent = `Nodos (${this.datos.nodes.length})`;
  }

  _pintarEventos() {
    const et = this._etiquetas();
    const gs = this.datos.nodes.filter((n) => n.role === "G");
    const div = this.c.querySelector("#ed-eventos");
    div.innerHTML = this.datos.events.map((ev, i) => `<div class="fila" data-i="${i}">
      wander <select data-k="node_id">${gs.map((g) =>
        `<option value="${g.id}" ${g.id === ev.node_id ? "selected" : ""}>${et.get(g.id)}</option>`).join("")}</select>
      hasta t = <input type="number" min="0" step="1" data-k="until" value="${ev.until}" style="width:5em"> s
      <button data-borrar>✕</button></div>`).join("") || '<p class="detalle">(ninguno)</p>';
    div.querySelectorAll("[data-i]").forEach((fila) => {
      const ev = this.datos.events[Number(fila.dataset.i)];
      fila.querySelectorAll("[data-k]").forEach((inp) => inp.addEventListener("change", () => {
        ev[inp.dataset.k] = Number(inp.value);
      }));
      fila.querySelector("[data-borrar]").addEventListener("click", () => {
        this.datos.events.splice(Number(fila.dataset.i), 1);
        this._pintarEventos();
      });
    });
  }

  _borrar(id) {
    this.datos.nodes = this.datos.nodes.filter((n) => n.id !== id);
    this.datos.events = this.datos.events.filter((e) => e.node_id !== id);
    this._pintarNodos(); this._pintarEventos(); this._dibujar();
  }

  _tr() {
    const b = this.datos.building;
    const ancho = Number(b.ancho) || 40, alto = Number(b.alto) || 30;
    const r = this.canvas.getBoundingClientRect();
    const m = 2;
    const escala = Math.min(r.width / (ancho + 2 * m), r.height / (alto + 2 * m));
    const xo = (r.width - (ancho + 2 * m) * escala) / 2, yo = (r.height - (alto + 2 * m) * escala) / 2;
    return {
      ancho, alto, escala,
      w2s: (x, y) => [xo + (x + m) * escala, yo + (alto + m - y) * escala],
      s2w: (sx, sy) => [(sx - xo) / escala - m, alto + m - (sy - yo) / escala],
    };
  }

  _nodoEn(px, py) {
    const { w2s } = this._tr();
    return this.datos.nodes.find((n) => {
      const [x, y] = w2s(n.x, n.y);
      return (x - px) ** 2 + (y - py) ** 2 < 14 ** 2;
    });
  }

  _enlazarLienzo() {
    const cv = this.canvas;
    const local = (ev) => { const r = cv.getBoundingClientRect(); return [ev.clientX - r.left, ev.clientY - r.top]; };
    const redondear = (v) => Math.round(v * 10) / 10;
    cv.addEventListener("pointerdown", (ev) => {
      const [px, py] = local(ev);
      const n = this._nodoEn(px, py);
      if (n && this.herramienta === "borrar") { this._borrar(n.id); return; }
      if (n) { this.arrastre = n; cv.setPointerCapture(ev.pointerId); return; }
      if (this.herramienta === "G" || this.herramienta === "N") {
        const { s2w, ancho, alto } = this._tr();
        const [x, y] = s2w(px, py);
        if (x < 0 || x > ancho || y < 0 || y > alto) return;
        const id = Math.max(0, ...this.datos.nodes.map((m) => m.id)) + 1;
        this.datos.nodes.push({ id, role: this.herramienta, x: redondear(x), y: redondear(y) });
        this._pintarNodos(); this._pintarEventos(); this._dibujar();
      }
    });
    cv.addEventListener("pointermove", (ev) => {
      if (!this.arrastre) return;
      const { s2w, ancho, alto } = this._tr();
      const [x, y] = s2w(...local(ev));
      this.arrastre.x = redondear(Math.min(Math.max(x, 0), ancho));
      this.arrastre.y = redondear(Math.min(Math.max(y, 0), alto));
      this._dibujar();
    });
    cv.addEventListener("pointerup", () => {
      if (this.arrastre) { this.arrastre = null; this._pintarNodos(); }
    });
  }

  _dibujar() {
    if (!this.canvas || !this.dialogo.open) return;
    const cv = this.canvas, dpr = window.devicePixelRatio || 1;
    const r = cv.getBoundingClientRect();
    cv.width = r.width * dpr; cv.height = r.height * dpr;
    const ctx = cv.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const { w2s, escala, ancho, alto } = this._tr();
    const b = this.datos.building;
    const pisoH = Number(b.piso_h) || 10, nPisos = Number(b.n_pisos) || 3;
    ctx.fillStyle = colorCss("--bg"); ctx.fillRect(0, 0, r.width, r.height);
    ctx.font = "12px system-ui, sans-serif"; ctx.textAlign = "center";
    for (let p = 0; p < nPisos; p++) {
      const [x0, y0] = w2s(0, Math.min(alto, (p + 1) * pisoH));
      const [x1, y1] = w2s(ancho, p * pisoH);
      ctx.fillStyle = colorCss("--piso"); ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
      ctx.strokeStyle = colorCss("--borde"); ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
      ctx.fillStyle = colorCss("--tenue");
      ctx.fillText(`P${p + 1}`, ...w2s(-1, p * pisoH + pisoH / 2));
    }
    const rango = Number(this.datos.medium.rango_comm) || 16;
    const et = this._etiquetas();
    for (const n of this.datos.nodes) {
      const [x, y] = w2s(n.x, n.y);
      if (n.role === "G") {
        ctx.strokeStyle = "#378ADD33"; ctx.setLineDash([4, 4]);
        ctx.beginPath(); ctx.arc(x, y, rango * escala, 0, Math.PI * 2); ctx.stroke();
        ctx.setLineDash([]);
      }
    }
    for (const n of this.datos.nodes) {
      const [x, y] = w2s(n.x, n.y);
      ctx.fillStyle = n.role === "G" ? "#378ADD" : "#E24B4A";
      ctx.strokeStyle = "#fff"; ctx.lineWidth = 2;
      ctx.beginPath();
      if (n.role === "G") ctx.arc(x, y, 9, 0, Math.PI * 2);
      else { ctx.moveTo(x, y - 9); ctx.lineTo(x + 9, y); ctx.lineTo(x, y + 9); ctx.lineTo(x - 9, y); ctx.closePath(); }
      ctx.fill(); ctx.stroke();
      ctx.fillStyle = colorCss("--tinta");
      ctx.fillText(`${et.get(n.id)} (${n.x}, ${n.y})`, x, y - 14);
    }
  }
}
