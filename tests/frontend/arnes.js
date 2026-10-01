// Ejecuta los módulos de web/static/js con datos reales generados por
// tests/test_web_frontend.py (ver ahí). Imprime las comprobaciones y los errores.
import "./rutas.js";
import "./stub.js";

const R = globalThis.__RUTAS.js;
const reg = globalThis.__registro;
const d = globalThis.__datos;
const ok = [];
function chequear(cond, texto) {
  if (cond) ok.push(texto); else reg.errores.push(`FALLA: ${texto}`);
}
async function paso(nombre, f) {
  try { await f(); } catch (e) { reg.errores.push(`${nombre}: ${e}\n${e.stack}`); }
}

// 1) main.js completo, con frames reales por el SSE simulado
await paso("main.js", async () => {
  await import(R + "main.js");
  for (let i = 0; i < 5; i++) await Promise.resolve();
  const es = reg.fuentes[0];
  chequear(es && es.url === "/api/stream", "main.js abre /api/stream");
  es.l.frame({ data: JSON.stringify(d.frame) });
  es.l.frame({ data: JSON.stringify(d.frame2) });
  for (const [f] of reg.intervalos) await f();
  for (let i = 0; i < 20; i++) await Promise.resolve();
  for (let i = 0; i < 3; i++) reg.raf.at(-1)();
  chequear(document.getElementById("reloj").textContent === `T+${d.frame2.t.toFixed(0)}s`, "reloj muestra t");
  const r = d.frame2.resumen;
  chequear(document.getElementById("conteo-g").textContent === `Gateways ${r.aliveG}/${r.totG}`, "conteo de Gateways");
  chequear(reg.llamadasCanvas > 100, `el mapa dibuja (${reg.llamadasCanvas} llamadas al canvas)`);
});

// 2) el mapa con todas las capas, la lente, filtro de OGM, mensajes, cobertura
const { Mapa } = await import(R + "mapa.js");
await paso("mapa", async () => {
  const llamadas = [];
  const cb = { seleccionar: (id) => llamadas.push(["sel", id]), soltar: (...a) => llamadas.push(["soltar", ...a]),
               agregar: (...a) => llamadas.push(["agregar", ...a]), menu: (...a) => llamadas.push(["menu", a[0]]),
               hover: () => {} };
  const canvas = new Elemento("canvas");
  const m = new Mapa(canvas, cb);
  m.redimensionar();
  m.setFrame(d.frame);
  m.setFrame(d.frame2);
  m.seleccionId = 1;
  for (const k of Object.keys(m.capas)) m.capas[k] = true;
  m.setCobertura(d.cobertura);
  m.resaltar([1, 2]);
  m.animarMensaje([1, 2, 3], "hola", "G1", "G3");
  m.compositor = { origen: 1, destino: 2 };
  const antes = reg.llamadasCanvas;
  m.dibujar();
  chequear(reg.llamadasCanvas > antes + 50, "dibujo con todas las capas");
  // grupos partidos -> envolventes
  const partido = { ...d.frame2, grupos: [[1, 2], [3], [5, 6, 7]] };
  m.setFrame(partido);
  m.dibujar();
  // lente "ver como este nodo"
  m.lente = { id: 1, detalle: d.nodo };
  m.dibujar();
  // filtro de OGM por origen
  m.lente = null;
  m.filtroOrigen = 1;
  m.paquetesOrigen = d.paquetes.paquetes;
  m.escalaUI = 1.45;
  m.dibujar();
  // selección, arrastre y menú con el puntero, sobre la posición real de G1
  m.filtroOrigen = null; m.escalaUI = 1;
  m.dibujar();
  const [sx, sy] = m._pos.get(1);
  canvas.disparar("pointerdown", { button: 0, clientX: sx, clientY: sy, pointerId: 1 });
  canvas.disparar("pointerup", {});
  chequear(llamadas.some((l) => l[0] === "sel" && l[1] === 1), "clic sobre G1 lo selecciona");
  canvas.disparar("pointerdown", { button: 0, clientX: sx, clientY: sy, pointerId: 1 });
  canvas.disparar("pointermove", { clientX: sx + 60, clientY: sy + 30 });
  m.dibujar();
  canvas.disparar("pointerup", {});
  const s = llamadas.find((l) => l[0] === "soltar");
  chequear(s && s[1] === 1 && Number.isFinite(s[2]) && Number.isFinite(s[3]), "arrastrar G1 da una posición válida");
  m.herramienta = "G";
  canvas.disparar("pointerdown", { button: 0, clientX: 450, clientY: 300, pointerId: 1 });
  chequear(llamadas.some((l) => l[0] === "agregar" && l[1] === "G"), "herramienta + Gateway agrega donde se hace clic");
  m.dibujar();
  canvas.disparar("contextmenu", { clientX: sx, clientY: sy, preventDefault() {} });
  chequear(llamadas.some((l) => l[0] === "menu" && l[1] === 1), "clic derecho abre el menú del nodo");
  const e = d.frame.enlaces[0];
  const [ax, ay] = m._pos.get(e[0]), [bx, by] = m._pos.get(e[1]);
  chequear(m.enlaceEnPunto((ax + bx) / 2, (ay + by) / 2) !== null, "hover sobre un enlace lo encuentra");
});

// 3) gráficas (los 6 paneles) y línea de tiempo
await paso("graficas", async () => {
  const { Graficas } = await import(R + "graficas.js");
  const g = new Graficas(new Elemento());
  g.setDatos({ series: d.series.series, eventos: d.series.eventos, timeout: d.series.timeout });
  for (const v of [60, 200, 0]) { g.ventana = v; g.dibujar(); }
  chequear(g.paneles.length === 6 && g.paneles.every((p) => p.geo), "los 6 paneles dibujan");
  g._tooltip(g.paneles[2], { offsetX: 150 });
  chequear(!g.paneles[2].tip.hidden && g.paneles[2].tip.innerHTML.includes("TQ"), "tooltip de la gráfica 3");
  const { LineaTiempo } = await import(R + "linea_tiempo.js");
  let elegido = null;
  const cont = new Elemento();
  const l = new LineaTiempo(cont, (ev) => { elegido = ev; });
  l.setDatos(d.series.eventos, d.frame.t);
  l.dibujar();
  const botones = cont.children.filter((c) => c.tagName === "BUTTON");
  chequear(botones.length === d.series.eventos.length, `línea de tiempo con ${botones.length} eventos`);
  botones[0].click();
  chequear(elegido && Array.isArray(elegido.nodos), "clic en un evento entrega sus nodos");
});

// 4) paneles
await paso("paneles", async () => {
  const { pintarMatriz } = await import(R + "paneles/matriz.js");
  const c = new Elemento(), ind = new Elemento();
  pintarMatriz(c, ind, d.matriz, () => {});
  chequear(c.innerHTML.includes("m-vigente"), "matriz con celdas vigentes");
  chequear(ind.innerHTML.includes("pares conectados"), "indicador de convergencia");
  const { pintarRealModelo } = await import(R + "paneles/real_modelo.js");
  const rm = new Elemento();
  pintarRealModelo(rm, d.frame);
  chequear(rm.innerHTML.includes("receive_ogm"), "panel real / modelo");
  const { pintarPanelNodo } = await import(R + "paneles/nodo.js");
  const pn = new Elemento();
  pintarPanelNodo(pn, d.nodo, { lenteActiva: true, etiqueta: (id) => `X${id}` });
  chequear(pn.innerHTML.includes("Tabla de rutas") && pn.innerHTML.includes("FaultManager"), "panel nodo (Gateway)");
  const { construirParametros, ajustePygame } = await import(R + "paneles/parametros.js");
  construirParametros(new Elemento(), () => {});
  chequear(JSON.stringify(ajustePygame(d.frame.cfg, "+")) === JSON.stringify(["rango_comm", d.frame.cfg.rango_comm + 1]), "tecla + como pygame");
  chequear(ajustePygame({ falloff: 0, rango_comm: 4 }, "[")[1] === 0 && ajustePygame({ falloff: 0, rango_comm: 4 }, "-")[1] === 4, "topes de [ y - como pygame");
});

// 5) editor
await paso("editor", async () => {
  const { Editor } = await import(R + "paneles/editor.js");
  const dlg = new Elemento("dialog"), cont = new Elemento();
  const ed = new Editor(dlg, cont, async () => {});
  await ed.abrir();
  chequear(dlg.open && ed.datos.nodes.length === d.escenario.nodes.length, "editor abre el escenario de la sesión");
  ed._dibujar();
  await ed._accion("validar");
  await ed._accion("guardar");
  chequear(reg.comandos.some((c) => c.accion === "guardar_escenario" && c.escenario.nodes.length), "guardar manda el escenario");
  ed.vacio();
  chequear(ed.datos.nodes.length === 0, "escenario vacío");
});

print(`\n✓ ${ok.length} comprobaciones:`);
for (const o of ok) print(`   ✓ ${o}`);
print(`\n${reg.errores.length ? "✗" : "✓"} errores: ${reg.errores.length}`);
for (const e of reg.errores.slice(0, 30)) print(`   ✗ ${e}`);
