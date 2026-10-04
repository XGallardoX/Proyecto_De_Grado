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

export const ICONOS_EVENTO = {
  FAIL: ["✕", "#C0392B", "Caída"],
  RECOVER: ["↺", "#1D9E75", "Recuperación"],
  ALERT_ON: ["!", "#E67E22", "Alerta: un Gateway dejó de oír a otro"],
  ALERT_OFF: ["✓", "#2ECC71", "Fin de alerta"],
  PARTITION: ["⫽", "#8E44AD", "La malla se partió"],
  HEAL: ["∪", "#16A085", "La malla se reunificó"],
  PARAM: ["⚙", "#888888", "Cambio de parámetro"],
  MSG_OK: ["✉", "#9B59B6", "Mensaje entregado"],
  MSG_FAIL: ["✉", "#C0392B", "Mensaje no entregado"],
  MOVE: ["↔", "#888888", "Nodo movido"],
};
