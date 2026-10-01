import { esc } from "../util.js";

// Pantalla de inicio: elegir escenario (con su descripción), un archivo
// de escenarios/ o una red aleatoria, más static / movilidad / semilla.
export function prepararInicio(dialogo, escenarios, cargar) {
  const lista = dialogo.querySelector("#lista-escenarios");
  const error = dialogo.querySelector("#ini-error");
  const opciones = () => {
    const o = {};
    o.static = dialogo.querySelector("#ini-static").checked;
    const mov = dialogo.querySelector("#ini-movilidad").value;
    if (mov) o.movilidad = mov;
    const semilla = dialogo.querySelector("#ini-semilla").value;
    if (semilla) o.semilla = Number(semilla);
    return o;
  };
  const intentar = async (datos) => {
    error.hidden = true;
    try {
      await cargar({ ...datos, ...opciones() });
      dialogo.close();
    } catch (e) {
      error.textContent = e.message;
      error.hidden = false;
    }
  };
  lista.innerHTML = escenarios.predefinidos.map((e) =>
    `<button data-esc="${esc(e.nombre)}"><b>${esc(e.nombre)}</b><small>${esc(e.descripcion)}</small></button>`).join("");
  lista.querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => intentar({ escenario: b.dataset.esc })));
  const archivo = dialogo.querySelector("#ini-archivo");
  archivo.innerHTML = '<option value="">—</option>' +
    escenarios.archivos.map((a) => `<option>${esc(a)}</option>`).join("");
  archivo.addEventListener("change", () => { if (archivo.value) intentar({ archivo: archivo.value }); });
  dialogo.querySelector("#ini-aleatoria").addEventListener("click", () => intentar({
    n_nodes: Number(dialogo.querySelector("#ini-n").value),
    n_gateways: Number(dialogo.querySelector("#ini-g").value),
  }));
}
