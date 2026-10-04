// Laboratorio de experimentos: arma un lote (escenarios × semillas, el
// formato de lotes/*.json) y lo corre en el servidor con
// `python main.py --batch` en un subproceso. Acá sólo se arma el lote y se
// muestran el progreso y el resumen agregado que calcula Python.
import { bloqueComando, colorCss, esc, num } from "../util.js";

const ESTADOS = {
  inactivo: "sin correr", corriendo: "corriendo…", cancelando: "cancelando…",
  terminado: "terminado", cancelado: "cancelado", error: "error",
};

async function pedir(ruta, cuerpo) {
  const r = await fetch(ruta, cuerpo === undefined ? undefined : {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cuerpo),
  });
  const datos = await r.json();
  if (cuerpo !== undefined && !datos.ok) throw new Error(datos.error || "error desconocido");
  return datos;
}

export class Laboratorio {
  constructor(dialogo, contenedor) {
    this.dialogo = dialogo;
    this.c = contenedor;
    this.lote = { nombre: "mi_experimento", duracion: 200, semillas: 10,
                  escenarios: [{ escenario: "base" }] };
    this.fuentes = null;
    this.lotes = [];
    this.estado = null;
    this.metrica = "tiempo_reconvergencia_rutas_s";
    this.temporizador = null;
    this.dialogo.addEventListener("close", () => this._dejarDeSondear());
  }

  async abrir() {
    if (!this.fuentes) {
      const [esc_, lotes] = await Promise.all([pedir("/api/escenarios"), pedir("/api/lotes")]);
      this.fuentes = [
        ...esc_.predefinidos.map((p) => ({ valor: `e:${p.nombre}`, texto: p.nombre })),
        ...esc_.archivos.map((a) => ({ valor: `c:${a}`, texto: `archivo: ${a}` })),
      ];
      this.lotes = lotes.lotes;
    }
    if (!this.dialogo.open) this.dialogo.showModal();
    this._construir();
    await this._sondear();
  }

  // ── estructura ─────────────────────────────────────────────────────
  _construir() {
    this.c.innerHTML = `
      <div class="lab-barra">
        <strong>Laboratorio de experimentos</strong>
        <label>Cargar <select id="lab-cargar"><option value="">— un lote de lotes/ —</option>
          ${this.lotes.map((l, i) => `<option value="${i}">${esc(l.archivo)}</option>`).join("")}</select></label>
        <span class="separador"></span>
        <button id="lab-correr" class="primario">▶ Correr</button>
        <button id="lab-cancelar">■ Cancelar</button>
        <button id="lab-cerrar">Cerrar</button>
      </div>
      <div class="lab-armado">
        <p class="detalle">Cada entrada corre con cada semilla, igual que
          <code>python main.py --batch</code> (en un subproceso, así que no
          toca la sesión en vivo). La duración y las semillas de una entrada,
          si las trae un lote cargado, pisan las del lote.</p>
        <label>Nombre <input id="lab-nombre" value="${esc(this.lote.nombre || "")}"></label>
        <label>Duración (s) <input id="lab-duracion" type="number" min="1" step="10" value="${esc(this.lote.duracion ?? 200)}"></label>
        <label>Semillas (1…N) <input id="lab-semillas" type="number" min="1" step="1" value="${esc(Number.isInteger(this.lote.semillas) ? this.lote.semillas : 10)}"></label>
        <h3>Entradas</h3>
        <div id="lab-entradas"></div>
        <button id="lab-agregar">+ entrada</button>
        <div id="lab-msg"></div>
      </div>
      <div class="lab-resultados">
        <div id="lab-progreso"></div>
        <div id="lab-resumen"></div>
      </div>`;
    const $ = (s) => this.c.querySelector(s);
    $("#lab-cerrar").addEventListener("click", () => this.dialogo.close());
    $("#lab-correr").addEventListener("click", () => this._correr());
    $("#lab-cancelar").addEventListener("click", () => this._cancelar());
    $("#lab-agregar").addEventListener("click", () => {
      this.lote.escenarios.push({ escenario: "base" });
      this._pintarEntradas();
    });
    $("#lab-cargar").addEventListener("change", (ev) => {
      const l = this.lotes[Number(ev.target.value)];
      if (!l) return;
      this.lote = JSON.parse(JSON.stringify(l.lote));
      this._construir();
      this._pintarEstado();
    });
    $("#lab-nombre").addEventListener("input", (ev) => { this.lote.nombre = ev.target.value.trim(); });
    $("#lab-duracion").addEventListener("change", (ev) => { this.lote.duracion = Number(ev.target.value); });
    $("#lab-semillas").addEventListener("change", (ev) => { this.lote.semillas = Number(ev.target.value); });
    this._pintarEntradas();
    this._pintarEstado();
  }

  _pintarEntradas() {
    const div = this.c.querySelector("#lab-entradas");
    div.innerHTML = this.lote.escenarios.map((e, i) => {
      const fuente = e.config != null ? `c:${String(e.config).replace(/^escenarios\//, "")}` : `e:${e.escenario}`;
      const extra = [e.semillas != null ? `semillas ${Array.isArray(e.semillas) ? e.semillas.join(",") : e.semillas}` : "",
                     e.duracion != null ? `${e.duracion} s` : ""].filter(Boolean).join(" · ");
      return `<div class="lab-entrada" data-i="${i}">
        <select data-k="fuente">${this.fuentes.map((f) =>
          `<option value="${esc(f.valor)}" ${f.valor === fuente ? "selected" : ""}>${esc(f.texto)}</option>`).join("")}</select>
        <input data-k="etiqueta" placeholder="etiqueta (opcional)" value="${esc(e.etiqueta || "")}">
        <label class="compacto"><input type="checkbox" data-k="static" ${e.static ? "checked" : ""}> fijos</label>
        <select data-k="movilidad" title="Movilidad">
          ${["", "seguir", "repartir"].map((m) => `<option value="${m}" ${(e.movilidad || "") === m ? "selected" : ""}>${m || "movilidad del escenario"}</option>`).join("")}
        </select>
        ${extra ? `<small class="detalle">${esc(extra)}</small>` : ""}
        <button data-borrar title="Quitar">✕</button>
      </div>`;
    }).join("") || '<p class="detalle">(sin entradas)</p>';
    div.querySelectorAll(".lab-entrada").forEach((fila) => {
      const e = this.lote.escenarios[Number(fila.dataset.i)];
      fila.querySelector('[data-k="fuente"]').addEventListener("change", (ev) => {
        const v = ev.target.value;
        delete e.escenario; delete e.config;
        if (v.startsWith("e:")) e.escenario = v.slice(2); else e.config = v.slice(2);
      });
      fila.querySelector('[data-k="etiqueta"]').addEventListener("input", (ev) => {
        const t = ev.target.value.trim();
        if (t) e.etiqueta = t; else delete e.etiqueta;
      });
      fila.querySelector('[data-k="static"]').addEventListener("change", (ev) => {
        if (ev.target.checked) e.static = true; else delete e.static;
      });
      fila.querySelector('[data-k="movilidad"]').addEventListener("change", (ev) => {
        if (ev.target.value) e.movilidad = ev.target.value; else delete e.movilidad;
      });
      fila.querySelector("[data-borrar]").addEventListener("click", () => {
        this.lote.escenarios.splice(Number(fila.dataset.i), 1);
        this._pintarEntradas();
      });
    });
  }

  _mensaje(texto, tipo = "error") {
    this.c.querySelector("#lab-msg").innerHTML = texto ? `<div class="ed-msg ${tipo}">${esc(texto)}</div>` : "";
  }

  // ── acciones ───────────────────────────────────────────────────────
  async _correr() {
    this._mensaje("");
    try {
      this.estado = await pedir("/api/laboratorio", { accion: "iniciar", lote: this.lote });
      this._pintarEstado();
      this._sondear();
    } catch (e) {
      this._mensaje(e.message);
    }
  }

  async _cancelar() {
    try {
      this.estado = await pedir("/api/laboratorio", { accion: "cancelar" });
      this._pintarEstado();
    } catch (e) {
      this._mensaje(e.message);
    }
  }

  async _sondear() {
    this._dejarDeSondear();
    try {
      this.estado = await pedir("/api/laboratorio");
    } catch { return; }
    this._pintarEstado();
    if (this.dialogo.open && ["corriendo", "cancelando"].includes(this.estado.estado)) {
      this.temporizador = setTimeout(() => this._sondear(), 500);
    }
  }

  _dejarDeSondear() {
    clearTimeout(this.temporizador);
    this.temporizador = null;
  }

  // ── progreso y resultados ──────────────────────────────────────────
  _pintarEstado() {
    const s = this.estado;
    const prog = this.c.querySelector("#lab-progreso");
    if (!s || !prog) return;
    const corriendo = ["corriendo", "cancelando"].includes(s.estado);
    this.c.querySelector("#lab-correr").disabled = corriendo;
    this.c.querySelector("#lab-cancelar").disabled = s.estado !== "corriendo";
    const pct = s.total ? Math.round(100 * s.hechas / s.total) : 0;
    prog.innerHTML = s.estado === "inactivo"
      ? '<p class="detalle">Todavía no se corrió ningún lote en esta sesión.</p>'
      : `<h3>${esc(s.nombre || "")} — ${ESTADOS[s.estado] || esc(s.estado)}</h3>
         <div class="lab-barra-progreso" role="progressbar" aria-valuemin="0" aria-valuemax="${s.total}" aria-valuenow="${s.hechas}">
           <div style="width:${pct}%"></div></div>
         <p class="detalle">${s.hechas} de ${s.total} corridas${s.segundos != null ? ` · ${s.segundos} s` : ""}</p>
         ${s.comando ? `<p class="detalle">Lo mismo en la terminal:</p>${bloqueComando(s.comando)}` : ""}
         ${s.error ? `<pre class="lab-log error">${esc(s.error)}</pre>` : ""}
         ${corriendo ? `<pre class="lab-log">${esc(s.lineas.slice(-6).join("\n"))}</pre>` : ""}`;
    this._pintarResumen(s.estado === "terminado" ? s.resultado : null);
  }

  _pintarResumen(r) {
    const div = this.c.querySelector("#lab-resumen");
    if (!r) { div.innerHTML = ""; return; }
    const sub = r.carpeta.replace(/^reportes[\\/]/, "");
    const celda = (m, met) => {
      const v = m?.[met.clave];
      if (!v || v.n === 0) return '<td class="na">no aplica</td>';
      const desv = v.desv == null ? "" : ` ± ${num(v.desv, met.decimales)}`;
      return `<td>${num(v.media, met.decimales)}${desv} <small>(n=${v.n})</small></td>`;
    };
    if (!r.metricas.some((m) => m.clave === this.metrica)) this.metrica = r.metricas[0].clave;
    div.innerHTML = `
      <h3>Resumen (media ± desviación estándar muestral)</h3>
      <div class="lab-tabla"><table>
        <thead><tr><th>Métrica</th>${r.escenarios.map((e) => `<th>${esc(e.etiqueta)}</th>`).join("")}</tr></thead>
        <tbody>${r.metricas.map((met) => `<tr data-clave="${met.clave}" class="${met.clave === this.metrica ? "elegida" : ""}">
          <th>${esc(met.etiqueta)}</th>${r.escenarios.map((e) => celda(e.metricas, met)).join("")}</tr>`).join("")}</tbody>
      </table></div>
      <p class="detalle">Clic en una métrica para graficarla. Archivos en <code>${esc(r.carpeta)}</code>:
        ${r.archivos.map((a) => `<a href="/api/reportes/${encodeURI(sub)}/${encodeURIComponent(a)}" target="_blank">${esc(a)}</a>`).join(" · ")}</p>
      <canvas id="lab-grafica" height="260"></canvas>`;
    div.querySelectorAll("tbody tr").forEach((tr) => tr.addEventListener("click", () => {
      this.metrica = tr.dataset.clave;
      this._pintarResumen(r);
    }));
    this._graficar(r);
  }

  // Barras con la media y bigotes de ± una desviación estándar, una por
  // entrada del lote. Los números vienen tal cual del resumen de Python.
  _graficar(r) {
    const canvas = this.c.querySelector("#lab-grafica");
    const met = r.metricas.find((m) => m.clave === this.metrica);
    const dpr = window.devicePixelRatio || 1;
    const ancho = canvas.clientWidth || 600, alto = 260;
    canvas.width = ancho * dpr; canvas.height = alto * dpr;
    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    const tinta = colorCss("--tinta"), tenue = colorCss("--tenue"), acento = colorCss("--acento");
    const datos = r.escenarios.map((e) => ({ etiqueta: e.etiqueta, v: e.metricas[met.clave] }));
    const maximo = Math.max(1e-9, ...datos.map((d) => (d.v?.n ? d.v.media + (d.v.desv || 0) : 0)));
    const m = { izq: 52, der: 12, arriba: 26, abajo: 46 };
    const w = ancho - m.izq - m.der, h = alto - m.arriba - m.abajo;
    ctx.font = "12px system-ui, sans-serif";
    ctx.fillStyle = tinta;
    ctx.fillText(met.etiqueta, m.izq, 16);
    ctx.strokeStyle = tenue; ctx.fillStyle = tenue; ctx.lineWidth = 1;
    for (let k = 0; k <= 4; k++) {
      const y = m.arriba + h - (h * k) / 4;
      ctx.globalAlpha = 0.25;
      ctx.beginPath(); ctx.moveTo(m.izq, y); ctx.lineTo(m.izq + w, y); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.textAlign = "right";
      ctx.fillText(num((maximo * k) / 4, met.decimales), m.izq - 6, y + 4);
    }
    const paso = w / Math.max(1, datos.length);
    const barra = Math.min(60, paso * 0.6);
    datos.forEach((d, i) => {
      const x = m.izq + paso * i + (paso - barra) / 2;
      ctx.textAlign = "center";
      ctx.fillStyle = tinta;
      const etiqueta = d.etiqueta.length > 18 ? d.etiqueta.slice(0, 17) + "…" : d.etiqueta;
      ctx.fillText(etiqueta, x + barra / 2, m.arriba + h + 16);
      if (!d.v?.n) {
        ctx.fillStyle = tenue;
        ctx.fillText("no aplica", x + barra / 2, m.arriba + h - 6);
        return;
      }
      const alturaBarra = (h * d.v.media) / maximo;
      ctx.fillStyle = acento;
      ctx.fillRect(x, m.arriba + h - alturaBarra, barra, alturaBarra);
      if (d.v.desv) {
        const cx = x + barra / 2;
        const y1 = m.arriba + h - (h * Math.max(0, d.v.media - d.v.desv)) / maximo;
        const y2 = m.arriba + h - (h * (d.v.media + d.v.desv)) / maximo;
        ctx.strokeStyle = tinta; ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(cx, y1); ctx.lineTo(cx, y2);
        ctx.moveTo(cx - 6, y1); ctx.lineTo(cx + 6, y1);
        ctx.moveTo(cx - 6, y2); ctx.lineTo(cx + 6, y2); ctx.stroke();
      }
      ctx.fillStyle = tenue;
      ctx.fillText(`n=${d.v.n}`, x + barra / 2, m.arriba + h + 32);
    });
  }
}
