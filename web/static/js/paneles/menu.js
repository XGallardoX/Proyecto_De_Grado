import { esc } from "../util.js";

const menu = document.getElementById("menu-contextual");

// items: [{texto, accion}] o "-" (separador ignorado) ; titulo opcional
export function abrirMenu(x, y, titulo, items) {
  menu.innerHTML = (titulo ? `<div class="titulo">${esc(titulo)}</div>` : "") +
    items.map((it, i) => `<button role="menuitem" data-i="${i}">${esc(it.texto)}</button>`).join("");
  menu.hidden = false;
  const r = menu.getBoundingClientRect();
  menu.style.left = `${Math.min(x, window.innerWidth - r.width - 8)}px`;
  menu.style.top = `${Math.min(y, window.innerHeight - r.height - 8)}px`;
  menu.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
    cerrarMenu();
    items[Number(b.dataset.i)].accion();
  }));
  menu.querySelector("button")?.focus();
}

export function cerrarMenu() { menu.hidden = true; }
export function menuAbierto() { return !menu.hidden; }

document.addEventListener("pointerdown", (ev) => {
  if (!menu.hidden && !menu.contains(ev.target)) cerrarMenu();
});
