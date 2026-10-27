export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

export function toast(texto, tipo = "") {
  const caja = document.getElementById("toasts");
  const div = document.createElement("div");
  div.className = `toast ${tipo}`;
  div.textContent = texto;
  caja.appendChild(div);
  setTimeout(() => div.remove(), 4500);
  while (caja.children.length > 4) caja.firstChild.remove();
}

export function num(v, dec = 2) {
  return v == null || Number.isNaN(v) ? "—" : Number(v).toFixed(dec);
}

// Colores de la UI tomados de las variables CSS (cambian con el tema).
export function colorCss(nombre) {
  return getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();
}

export async function copiar(texto) {
  try {
    await navigator.clipboard.writeText(texto);
    toast("Copiado al portapapeles", "ok");
  } catch {
    toast("No se pudo copiar: selecciona el texto a mano");
  }
}

export function bloqueComando(texto) {
  return `<div class="comando"><code>${esc(texto)}</code>` +
    `<button type="button" data-copiar="${esc(texto)}">Copiar</button></div>`;
}

document.addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-copiar]");
  if (b) copiar(b.dataset.copiar);
});

// Ícono del sprite de index.html (<symbol id="i-...">).
export function icono(nombre) {
  return `<svg class="ico" aria-hidden="true"><use href="#i-${nombre}"/></svg>`;
}

export const ICONOS_EVENTO = {
  FAIL: ["✕", "#EF4444", "Caída"],
  RECOVER: ["↺", "#10B981", "Recuperación"],
  ALERT_ON: ["!", "#F59E0B", "Alerta: un Gateway dejó de oír a otro"],
  ALERT_OFF: ["✓", "#22C55E", "Fin de alerta"],
  PARTITION: ["⫽", "#8B5CF6", "La malla se partió"],
  HEAL: ["∪", "#14B8A6", "La malla se reunificó"],
  PARAM: ["⚙", "#64748B", "Cambio de parámetro"],
  MSG_OK: ["✉", "#A855F7", "Mensaje entregado"],
  MSG_FAIL: ["✉", "#EF4444", "Mensaje no entregado"],
  MOVE: ["↔", "#64748B", "Nodo movido"],
};
