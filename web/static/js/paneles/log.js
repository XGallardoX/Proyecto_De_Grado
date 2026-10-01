export class Log {
  constructor(contenedor) {
    this.contenedor = contenedor;
    this.vistos = new Set();
  }

  // Recibe las últimas líneas del frame (t, texto, tipo). Como
  // log_lines se recorta por el servidor con pop(0), no hay un cursor
  // fiable: deduplicamos por contenido+t, que alcanza en la práctica.
  agregar(lineas) {
    for (const { t, texto, tipo } of lineas) {
      const clave = `${t}|${texto}`;
      if (this.vistos.has(clave)) continue;
      this.vistos.add(clave);
      const div = document.createElement("div");
      div.className = `linea log-${tipo}`;
      div.innerHTML = `<span class="t">[${t.toFixed(0)}s]</span><span>${escapar(texto)}</span>`;
      this.contenedor.appendChild(div);
    }
    while (this.contenedor.children.length > 300) {
      this.contenedor.removeChild(this.contenedor.firstChild);
    }
    this.contenedor.scrollTop = this.contenedor.scrollHeight;
  }
}

function escapar(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}
