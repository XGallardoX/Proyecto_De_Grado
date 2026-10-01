// Cliente delgado de la API HTTP/SSE. No calcula nada del modelo: sólo
// pide y manda datos ya calculados por Python (ver sección 3 del prompt
// de encargo, "contrato de paridad").

export async function obtenerEstado() {
  const r = await fetch("/api/estado");
  return r.json();
}

export async function obtenerNodo(id) {
  const r = await fetch(`/api/nodo/${id}`);
  if (!r.ok) return null;
  return r.json();
}

export async function obtenerSeries() {
  const r = await fetch("/api/series");
  return r.json();
}

export async function obtenerInspector() {
  const r = await fetch("/api/inspector");
  return r.text();
}

export async function obtenerEscenarios() {
  const r = await fetch("/api/escenarios");
  return r.json();
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

// SSE con reconexión simple. onFrame recibe el frame ya parseado.
export function conectarStream(onFrame, onError) {
  let activo = true;
  function abrir() {
    const es = new EventSource("/api/stream");
    es.addEventListener("frame", (ev) => {
      try {
        onFrame(JSON.parse(ev.data));
      } catch (e) {
        console.error("frame inválido", e);
      }
    });
    es.onerror = () => {
      if (onError) onError();
      es.close();
      if (activo) setTimeout(abrir, 1000);
    };
  }
  abrir();
  return () => { activo = false; };
}
