import { esc } from "../util.js";

const TITULO = {
  vigente: "ruta vigente", obsoleta: "ruta obsoleta",
  sin_converger: "conectados por radio, sin ruta todavía",
  sin_conexion: "sin conexión física", propio: "",
};

// Matriz N×N de /api/matriz. Métrica sólo de visualización.
export function pintarMatriz(contenedor, indicador, m, alElegirFila) {
  if (!m) return;
  const pct = m.pares_conectados ? (100 * m.pares_con_ruta) / m.pares_conectados : 100;
  indicador.innerHTML = `
    <b>${m.pares_con_ruta}</b> de <b>${m.pares_conectados}</b> pares conectados por radio ya tienen una ruta vigente (${pct.toFixed(0)} %)
    <div class="barra ${pct < 50 ? "llena" : pct < 90 ? "media" : ""}"><i style="width:${pct}%"></i></div>`;
  const cab = m.nodos.map((n) => `<th>${esc(n.etiqueta)}</th>`).join("");
  const filas = m.filas.map((f) => {
    const celdas = f.celdas.map((c, j) => {
      const destino = m.nodos[j].etiqueta;
      const sinRadio = c.fisico === false;
      const titulo = c.estado === "propio" ? "" :
        `${f.etiqueta} → ${destino}: ${TITULO[c.estado]}${c.hops ? ` (${c.hops} saltos)` : ""}` +
        (sinRadio ? " — pero la radio ya no los conecta" : "");
      return `<td class="m-${c.estado}${sinRadio ? " m-sin-radio" : ""}" title="${esc(titulo)}">${c.hops ?? ""}</td>`;
    }).join("");
    return `<tr class="${f.vivo ? "" : "m-muerto"}"><th class="fila-nodo" data-id="${f.id}"
      title="Seleccionar ${esc(f.etiqueta)}">${esc(f.etiqueta)}${f.vivo ? "" : " ×"}</th>${celdas}</tr>`;
  }).join("");
  contenedor.innerHTML = `<table><tr><th></th>${cab}</tr>${filas}</table>`;
  contenedor.querySelectorAll(".fila-nodo").forEach((th) =>
    th.addEventListener("click", () => alElegirFila(Number(th.dataset.id))));
}
