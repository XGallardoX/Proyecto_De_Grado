import { esc } from "../util.js";

// Misma lista blanca que web/sesion.py (PARAMETROS): sólo claves que el
// núcleo vuelve a leer de sim.cfg en cada paso.
export const PARAMETROS = [
  ["Medio radio", [
    ["rango_comm", "Alcance de radio (m)", 4, 60, 1],
    ["falloff", "Degradación con la distancia", 0, 1.5, 0.05],
    ["perdida_base", "Pérdida base (a 0 m)", 0, 1, 0.01],
    ["floor_atten", "Atenuación por piso (factor)", 0, 1, 0.05],
  ]],
  ["Protocolo", [
    ["timeout", "Timeout de caída (s)", 1, 300, 1],
    ["ttl", "TTL de los OGM (saltos)", 1, 20, 1],
    ["beacon_cada", "Beacon cada (s)", 0.5, 30, 0.5],
    ["batman_cada", "OGM propio cada (s)", 0.5, 30, 0.5],
  ]],
  ["Batería y movilidad", [
    ["battery_drain", "Drenaje Gateway (%/s)", 0, 5, 0.005],
    ["battery_drain_nodo", "Drenaje Nodo de usuario (%/s)", 0, 5, 0.005],
    ["move_speed", "Velocidad de los Gateway (m/paso, 0 = fijos)", 0, 2, 0.02],
    ["movilidad", "Movilidad", ["seguir", "repartir"]],
  ]],
];

export function construirParametros(contenedor, enviar) {
  contenedor.innerHTML = PARAMETROS.map(([grupo, lista]) => `
    <h3>${grupo}</h3>
    ${lista.map(([clave, nombre, min, max, paso]) => `
      <div class="param" data-clave="${clave}">
        <div class="cabecera"><span>${esc(nombre)}</span><b class="valor"></b></div>
        ${Array.isArray(min)
          ? `<select aria-label="${esc(nombre)}">${min.map((o) => `<option>${o}</option>`).join("")}</select>`
          : `<input type="range" min="${min}" max="${max}" step="${paso}" aria-label="${esc(nombre)}">`}
        <div class="pie"><span class="base"></span><button type="button" class="restaurar">restaurar</button></div>
      </div>`).join("")}`).join("") +
    '<p class="detalle">Cada cambio queda en el log como un evento PARAM y como intervención de la sesión.</p>';

  contenedor.querySelectorAll(".param").forEach((div) => {
    const clave = div.dataset.clave;
    const control = div.querySelector("input, select");
    control.addEventListener("input", () => { div.querySelector(".valor").textContent = control.value; });
    control.addEventListener("change", () => {
      const valor = control.tagName === "SELECT" ? control.value : Number(control.value);
      enviar("parametro", { clave, valor });
    });
    div.querySelector(".restaurar").addEventListener("click", () => enviar("restaurar_parametro", { clave }));
  });
}

export function sincronizarParametros(contenedor, cfg, base) {
  contenedor.querySelectorAll(".param").forEach((div) => {
    const clave = div.dataset.clave;
    const control = div.querySelector("input, select");
    if (document.activeElement !== control) control.value = cfg[clave];
    div.querySelector(".valor").textContent = cfg[clave];
    div.querySelector(".base").textContent = `por defecto: ${base[clave]}`;
    div.classList.toggle("modificado", cfg[clave] !== base[clave]);
  });
}

// Teclas +/- y [/] de pygame: los mismos pasos y topes.
export function ajustePygame(cfg, tecla) {
  if (tecla === "+" || tecla === "=") return ["rango_comm", Math.round((cfg.rango_comm + 1) * 10) / 10];
  if (tecla === "-") return ["rango_comm", Math.max(4, Math.round((cfg.rango_comm - 1) * 10) / 10)];
  if (tecla === "]") return ["falloff", Math.min(1.5, Math.round((cfg.falloff + 0.05) * 100) / 100)];
  if (tecla === "[") return ["falloff", Math.max(0, Math.round((cfg.falloff - 0.05) * 100) / 100)];
  return null;
}
