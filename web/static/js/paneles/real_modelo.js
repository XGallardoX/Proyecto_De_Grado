// Panel "Qué es real y qué es modelo": deja explícito qué corre el
// código del protocolo de mesh/ y qué aporta la simulación.

const fmt = (n) => Number(n).toLocaleString("es");

export function pintarRealModelo(contenedor, f) {
  const c = f.contadores;
  const entrega = c.paquetes_intentados
    ? (100 * c.paquetes_entregados / c.paquetes_intentados).toFixed(1) : "—";
  const movilidad = f.cfg.move_speed <= 0 ? "nodos fijos"
    : `${f.cfg.movilidad} · ${f.cfg.move_speed} m por paso`;
  contenedor.innerHTML = `
    <div class="dos-col">
      <div class="tarjeta real">
        <h4>Real · mesh/</h4>
        <p class="detalle">Las mismas clases que correrían en un nodo con Wi-Fi ad-hoc.</p>
        <b>BatmanRouter</b>
        <dl class="cifras">
          <dt>OGMs procesados por receive_ogm()</dt><dd>${fmt(c.ogms_procesados)}</dd>
          <dt>…nuevos (se reenvían)</dt><dd>${fmt(c.ogms_nuevos)}</dd>
          <dt>Beacons procesados</dt><dd>${fmt(c.beacons_procesados)}</dd>
          <dt>Rutas en las tablas</dt><dd>${fmt(c.rutas_en_tablas)}</dd>
        </dl>
        <b>FaultManager</b>
        <dl class="cifras">
          <dt>Chequeos (check())</dt><dd>${fmt(c.chequeos_fallo)}</dd>
          <dt>Caídas que cree detectadas</dt><dd>${fmt(c.caidas_detectadas)}</dd>
        </dl>
      </div>
      <div class="tarjeta modelo">
        <h4>Modelo · sim/</h4>
        <p class="detalle">Lo único simulado: el medio y el movimiento.</p>
        <b>RadioMedium</b>
        <dl class="cifras">
          <dt>Paquetes intentados</dt><dd>${fmt(c.paquetes_intentados)}</dd>
          <dt>Entregados</dt><dd>${fmt(c.paquetes_entregados)}</dd>
          <dt>Tasa de entrega</dt><dd>${entrega} %</dd>
          <dt>Alcance / falloff</dt><dd>${f.cfg.rango_comm} m / ${f.cfg.falloff}</dd>
          <dt>Atenuación por piso</dt><dd>×${f.cfg.floor_atten}</dd>
        </dl>
        <b>Movilidad</b>
        <dl class="cifras"><dt>Modo</dt><dd>${movilidad}</dd></dl>
      </div>
    </div>
    <h4>Lo que hay que saber al leer los números</h4>
    <ul class="detalle">
      <li>El TQ lo calcula el BatmanRouter real: la fracción de OGM recibidos de las últimas 16 secuencias de cada vecino, multiplicada salto a salto. La calidad del medio, sin pasar por el protocolo, es la tasa de entrega.</li>
      <li>Grupos, particiones y nodos alcanzables se miden sobre los enlaces de radio, no sobre las tablas de rutas.</li>
      <li>Los mensajes viajan por el camino más corto en la malla de radio (BFS); se indica si la ruta BATMAN ya había convergido.</li>
      <li>El ancho de banda es una heurística (100 − 5·d Mbps), no sale del medio radio.</li>
    </ul>`;
}
