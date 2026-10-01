import { esc } from "../util.js";

export class Log {
  constructor(contenedor) {
    this.contenedor = contenedor;
    this.vistos = new Set();
    this.orden = [];   // para olvidar las claves viejas (memoria acotada)
  }

  limpiar() {
    this.vistos.clear();
    this.orden = [];
    this.contenedor.replaceChildren();
  }

  // Recibe las últimas líneas del frame. log_lines se recorta en el
  // servidor con pop(0), así que su índice no sirve de cursor: se
  // deduplica por t + texto.
  agregar(lineas) {
    let nuevas = false;
    for (const { t, texto, tipo } of lineas) {
      const clave = `${t}|${texto}`;
      if (this.vistos.has(clave)) continue;
      this.vistos.add(clave);
      this.orden.push(clave);
      if (this.orden.length > 2000) this.vistos.delete(this.orden.shift());
      nuevas = true;
      const div = document.createElement("div");
      div.className = `linea log-${tipo}`;
      div.innerHTML = `<span class="t">[${t.toFixed(0)}s]</span><span>${esc(texto)}</span>`;
      this.contenedor.appendChild(div);
    }
    if (!nuevas) return;
    while (this.contenedor.children.length > 300) this.contenedor.firstChild.remove();
    this.contenedor.scrollTop = this.contenedor.scrollHeight;
  }
}
