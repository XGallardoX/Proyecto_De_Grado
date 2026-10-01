// Cliente delgado de la API HTTP/SSE. No calcula nada del modelo: sólo
// pide y manda datos ya calculados por Python (contrato de paridad).

async function json(ruta) {
  const r = await fetch(ruta);
  if (!r.ok) return null;
  return r.json();
}

export const obtenerEstado = () => json("/api/estado");
export const obtenerNodo = (id) => json(`/api/nodo/${id}`);
export const obtenerSeries = (desde = 0, desdeEvento = 0) =>
  json(`/api/series?desde=${desde}&desde_evento=${desdeEvento}`);
export const obtenerMatriz = () => json("/api/matriz");
export const obtenerCobertura = () => json("/api/cobertura");
export const obtenerEscenarios = () => json("/api/escenarios");
export const obtenerEscenarioActual = (posiciones = "iniciales") =>
  json(`/api/escenario/actual?posiciones=${posiciones}`);

export async function obtenerInspector() {
  const r = await fetch("/api/inspector");
  return r.text();
}

export async function enviarComando(accion, datos = {}) {
  const r = await fetch("/api/comando", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ accion, ...datos }),
  });
  const cuerpo = await r.json();
  if (!cuerpo.ok) throw new Error(cuerpo.error || "error desconocido");
  return cuerpo;
}

// SSE con reconexión. onFrame recibe el frame ya parseado.
export function conectarStream(onFrame, onCambioConexion) {
  let activo = true;
  function abrir() {
    const es = new EventSource("/api/stream");
    es.addEventListener("frame", (ev) => {
      onCambioConexion?.(true);
      try { onFrame(JSON.parse(ev.data)); } catch (e) { console.error("frame inválido", e); }
    });
    es.onerror = () => {
      onCambioConexion?.(false);
      es.close();
      if (activo) setTimeout(abrir, 1000);
    };
  }
  abrir();
  return () => { activo = false; };
}
