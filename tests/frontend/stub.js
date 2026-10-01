// Lo usa tests/test_web_frontend.py. DOM mínimo para ejecutar los módulos del frontend en JavaScriptCore
// (jsc) con datos reales del servidor. Registra cualquier llamada al
// canvas con números no finitos (NaN/Infinity): señal de un dato que no
// llegó o de una cuenta mal hecha.
const D = globalThis.__RUTAS.datos;
const leer = (f) => readFile(D + f);
const registro = { errores: [], llamadasCanvas: 0, comandos: [] };
globalThis.__registro = registro;
globalThis.__datos = {
  frame: JSON.parse(leer("frame.json")), frame2: JSON.parse(leer("frame2.json")),
  series: JSON.parse(leer("series.json")), matriz: JSON.parse(leer("matriz.json")),
  nodo: JSON.parse(leer("nodo.json")), cobertura: JSON.parse(leer("cobertura.json")),
  escenario: JSON.parse(leer("escenario.json")),
  escenarios: JSON.parse(leer("escenarios.json")), paquetes: JSON.parse(leer("paquetes.json")),
  inspector: leer("inspector.txt"),
};

function ctx2d() {
  const estado = {};
  return new Proxy(estado, {
    get(t, p) {
      if (p in t) return t[p];
      if (p === "measureText") return (s) => ({ width: String(s).length * 6 });
      if (p === "createImageData") return (w, h) => ({ width: w, height: h, data: new Uint8ClampedArray(w * h * 4) });
      return (...args) => {
        registro.llamadasCanvas++;
        for (const a of args) {
          const malo = (typeof a === "number" && !Number.isFinite(a)) ||
            (typeof a === "string" && /NaN|undefined|null|\[object/.test(a));
          if (malo) {
            registro.errores.push(`ctx.${String(p)}(${args.join(", ")})`);
            break;
          }
        }
      };
    },
    set(t, p, v) {
      if (typeof v === "number" && !Number.isFinite(v)) registro.errores.push(`ctx.${String(p)} = ${v}`);
      t[p] = v; return true;
    },
  });
}

class ClassList {
  constructor() { this.s = new Set(); }
  add(...c) { c.forEach((x) => this.s.add(x)); }
  remove(...c) { c.forEach((x) => this.s.delete(x)); }
  contains(c) { return this.s.has(c); }
  toggle(c, f) { const on = f === undefined ? !this.s.has(c) : f; on ? this.s.add(c) : this.s.delete(c); return on; }
}

class Elemento {
  constructor(tag = "div", id = "") {
    Object.assign(this, { tagName: tag.toUpperCase(), id, children: [], style: {}, dataset: {},
      hidden: false, _html: "", value: "", textContent: "", attributes: {}, listeners: {},
      clientWidth: 360, offsetWidth: 120, offsetHeight: 40, offsetParent: {}, open: false,
      checked: false, disabled: false, scrollTop: 0, scrollHeight: 0, options: [], _padre: null,
      width: 0, height: 0 });
    this.classList = new ClassList();
  }
  get parentElement() { return this._padre || (this._padre = new Elemento()); }
  set innerHTML(v) {
    this._html = String(v);
    if (/undefined|NaN|\[object Object\]/.test(this._html)) {
      registro.errores.push(`innerHTML de #${this.id || this.tagName} contiene undefined/NaN/[object Object]: ` +
        this._html.match(/.{0,60}(undefined|NaN|\[object Object\]).{0,30}/s)?.[0]);
    }
  }
  get innerHTML() { return this._html; }
  addEventListener(t, f) { (this.listeners[t] ||= []).push(f); }
  disparar(t, ev = {}) {
    for (const f of this.listeners[t] || []) f({ target: this, preventDefault() {}, ...ev });
  }
  querySelector() { const e = new Elemento(); e._padre = this; return e; }
  querySelectorAll() { return []; }
  getContext() { return ctx2d(); }
  getBoundingClientRect() { return { width: 900, height: 600, left: 0, top: 0 }; }
  appendChild(c) { this.children.push(c); c._padre = this; return c; }
  append(...c) { c.forEach((x) => this.appendChild(x)); }
  replaceChildren() { this.children = []; }
  remove() {}
  get firstChild() { return this.children[0]; }
  removeChild(c) { this.children.splice(this.children.indexOf(c), 1); }
  setAttribute(k, v) { this.attributes[k] = v; }
  getAttribute(k) { return this.attributes[k]; }
  closest() { return null; }
  contains() { return false; }
  focus() {} showModal() { this.open = true; } close() { this.open = false; }
  setPointerCapture() {} insertAdjacentHTML() {} click() { this.disparar("click"); }
}
globalThis.Elemento = Elemento;

const porId = new Map();
globalThis.document = {
  documentElement: new Elemento("html"), body: new Elemento("body"),
  activeElement: null,
  getElementById(id) { if (!porId.has(id)) porId.set(id, new Elemento("div", id)); return porId.get(id); },
  querySelector() { return new Elemento(); },
  querySelectorAll() { return []; },
  createElement(t) { return new Elemento(t); },
  addEventListener() {},
};
document.activeElement = document.body;
document.getElementById("panel-nodo").classList.add("activo");

globalThis.window = { devicePixelRatio: 2, innerWidth: 1400, innerHeight: 900, addEventListener() {} };
globalThis.getComputedStyle = () => ({ getPropertyValue: () => " #ffffff" });
globalThis.matchMedia = () => ({ matches: false, addEventListener() {} });
globalThis.performance = { now: () => Date.now() };
globalThis.localStorage = { getItem: () => null, setItem() {} };
globalThis.sessionStorage = { getItem: () => "1", setItem() {} };
globalThis.navigator = { clipboard: { writeText: async () => {} } };
globalThis.alert = globalThis.confirm = () => true;
globalThis.prompt = () => null;
globalThis.Blob = class {};
globalThis.URL = { createObjectURL: () => "blob:x", revokeObjectURL() {} };
globalThis.ResizeObserver = class { constructor(f) { this.f = f; } observe() { this.f(); } };

registro.raf = [];
registro.intervalos = [];
globalThis.requestAnimationFrame = (f) => registro.raf.push(f);
globalThis.setInterval = (f, ms) => registro.intervalos.push([f, ms]);
globalThis.setTimeout = () => 0;

registro.fuentes = [];
globalThis.EventSource = class {
  constructor(url) { this.url = url; this.l = {}; registro.fuentes.push(this); }
  addEventListener(t, f) { this.l[t] = f; }
  close() {}
};

const respuesta = (cuerpo) => Promise.resolve({
  ok: true, json: () => Promise.resolve(cuerpo), text: () => Promise.resolve(cuerpo),
});
globalThis.fetch = (url, opciones) => {
  const d = globalThis.__datos;
  if (url.startsWith("/api/comando")) {
    const c = JSON.parse(opciones.body);
    registro.comandos.push(c);
    if (c.accion === "mensaje") return respuesta({ ok: true, entregado: true, camino: ["G1", "G2"], ids: [1, 2], ruta_batman_convergida: true });
    if (c.accion === "exportar") return respuesta({ ok: true, carpeta: "reportes/base_x", archivos: ["a.png"], intervenciones: 0, comando_equivalente: "python main.py --headless" });
    if (c.accion === "agregar_nodo") return respuesta({ ok: true, id: 1 });
    if (c.accion === "guardar_escenario") return respuesta({ ok: true, archivo: "x.json", ruta: "escenarios/x.json", comando: "c", comando_headless: "h" });
    if (c.accion === "validar_escenario") return respuesta({ ok: true, nodos: 3, gateways: 1 });
    return respuesta({ ok: true });
  }
  const tabla = [["/api/estado", d.frame], ["/api/series", d.series], ["/api/matriz", d.matriz],
    ["/api/nodo/", d.nodo], ["/api/cobertura", d.cobertura], ["/api/escenario/actual", d.escenario],
    ["/api/escenarios", d.escenarios], ["/api/inspector", d.inspector], ["/api/paquetes", d.paquetes]];
  for (const [prefijo, cuerpo] of tabla) if (url.startsWith(prefijo)) return respuesta(cuerpo);
  registro.errores.push(`fetch a una ruta no prevista: ${url}`);
  return respuesta({});
};
