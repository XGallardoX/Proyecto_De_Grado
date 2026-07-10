
import math
import time
import matplotlib
import numpy as np
from matplotlib import pyplot as plt
from analysis.inspector import snapshot_red
matplotlib.use('Agg')

EVENT_STYLE = {
    'FAIL':      ('#C0392B', '-'),
    'RECOVER':   ('#1D9E75', '-'),
    'ALERT_ON':  ('#E67E22', ':'),
    'ALERT_OFF': ('#2ECC71', ':'),
    'FOUND':     ('#2980B9', '--'),
    'PARTITION': ('#8E44AD', '-.'),
    'HEAL':      ('#16A085', '-.'),
    'SCENARIO':  ('#555', '-'),
    'PARAM':     ('#999', ':'),
}

def _mark_events(ax, events, tipos):
    for (t, tipo, _txt) in events:
        if tipo in tipos:
            col, ls = EVENT_STYLE.get(tipo, ('#888', ':'))
            ax.axvline(t, color=col, linestyle=ls, linewidth=1.0, alpha=0.55)

def build_analysis_figure(sim):
    """Construye la figura de 6 paneles que explica el comportamiento de
    la red a lo largo del tiempo y la guarda como PNG."""
    rec = sim.recorder
    t = np.array(rec.t)
    if len(t) < 2:
        return None

    fig = plt.figure(figsize=(16, 10), facecolor=sim.C_BG)
    fig.suptitle(
        f"Análisis de la red ad-hoc BATMAN · escenario '{sim.escenario}' · "
        f"timeout={sim.cfg['timeout']:.0f}s  rango={sim.cfg['rango_comm']:.0f}m  "
        f"falloff={sim.cfg['falloff']:.2f}",
        fontsize=13, y=0.985)
    gs = fig.add_gridspec(3, 2, hspace=0.42, wspace=0.20,
                          left=0.07, right=0.97, top=0.92, bottom=0.06)

    # 1) Nodos vivos en el tiempo
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.step(t, rec.alive_G, where='post', color='#378ADD',
             label='Gateways vivos', linewidth=1.8)
    ax1.step(t, rec.alive_N, where='post', color='#E24B4A',
             label='Nodos de Usuario (nodo) vivos', linewidth=1.4)
    _mark_events(ax1, rec.events, {'FAIL', 'RECOVER'})
    ax1.set_title("1 · Nodos activos en el tiempo "
                  "(líneas: caída roja / recuperación verde)")
    ax1.set_ylabel("nº de nodos")
    ax1.set_xlabel("tiempo (s)")
    ax1.legend(fontsize=8, loc='lower left')
    ax1.grid(alpha=0.25)

    # 2) Conectividad de la malla de rescatistas + supervivientes
    #    alcanzables por la red
    ax2 = fig.add_subplot(gs[0, 1])
    comp = np.array(rec.comp_G)
    ax2.step(t, comp, where='post', color='#8E44AD', linewidth=1.8,
             label='Componentes de la malla de gateways')
    ax2.fill_between(t, 1, comp, step='post', where=comp > 1,
                     color='#8E44AD', alpha=0.18, label='Malla partida')
    ax2.axhline(1, color='#16A085', linestyle='--', linewidth=1,
                label='Malla unida (1 grupo)')
    ax2.step(t, rec.node_reach, where='post', color='#E24B4A',
             linewidth=1.3, label='Nodos de usuario alcanzables por la malla')
    _mark_events(ax2, rec.events, {'PARTITION', 'HEAL'})
    ax2.set_title("2 · Auto-reorganización de la malla "
                  "(1 = equipo conectado; >1 = partición BATMAN)")
    ax2.set_ylabel("nº")
    ax2.set_xlabel("tiempo (s)")
    ax2.legend(fontsize=7, loc='upper left')
    ax2.grid(alpha=0.25)

    # 3) Calidad de enrutamiento BATMAN: TQ medio y saltos medios
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.plot(t, rec.avg_tq, color='#1D9E75', linewidth=1.6,
             label='TQ medio de rutas')
    ax3.set_ylabel("TQ medio", color='#1D9E75')
    ax3.tick_params(axis='y', labelcolor='#1D9E75')
    ax3.set_xlabel("tiempo (s)")
    ax3b = ax3.twinx()
    ax3b.plot(t, rec.avg_hops, color='#E8A838', linewidth=1.4,
              linestyle='--', label='Saltos medios')
    ax3b.set_ylabel("saltos medios", color='#E8A838')
    ax3b.tick_params(axis='y', labelcolor='#E8A838')
    _mark_events(ax3, rec.events, {'FAIL', 'RECOVER', 'PARTITION', 'HEAL'})
    ax3.set_title("3 · Enrutamiento BATMAN: calidad (TQ) y longitud de ruta")
    ax3.grid(alpha=0.25)

    # 4) Silencio máximo entre rescatistas vs umbral de timeout
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.plot(t, rec.max_silence, color='#C0392B', linewidth=1.5,
             label='Máx. s sin oír a un gateway')
    ax4.axhline(sim.cfg['timeout'], color='#000', linestyle='--',
                linewidth=1.2,
                label=f"Umbral caída ({sim.cfg['timeout']:.0f}s)")
    alerts = np.array(rec.alerts_active)
    ax4.fill_between(t, 0, ax4.get_ylim()[1], where=alerts > 0,
                     color='#E67E22', alpha=0.15,
                     label='Alerta activa', step='post')
    ax4.set_title("4 · Detección de gateway perdido (regla del heartbeat)")
    ax4.set_ylabel("segundos")
    ax4.set_xlabel("tiempo (s)")
    ax4.legend(fontsize=8, loc='upper left')
    ax4.grid(alpha=0.25)

    # 5) Calidad del medio: ratio de entrega de paquetes
    ax5 = fig.add_subplot(gs[2, 0])
    dr = np.array(rec.deliver_ratio)
    ax5.plot(t, dr, color='#888', linewidth=0.7, alpha=0.5,
             label='Ratio entrega (por paso)')
    if len(dr) >= 9:
        k = 9
        mov = np.convolve(dr, np.ones(k) / k, mode='same')
        ax5.plot(t, mov, color='#2980B9', linewidth=1.8,
                 label='Media móvil')
    ax5.set_ylim(-0.02, 1.05)
    ax5.set_title("5 · Calidad del medio radio "
                  "(paquetes entregados / intentados)")
    ax5.set_ylabel("ratio de entrega")
    ax5.set_xlabel("tiempo (s)")
    ax5.legend(fontsize=8, loc='lower left')
    ax5.grid(alpha=0.25)

    # 6) Ancho de banda total (acumulado) + eventos
    ax6 = fig.add_subplot(gs[2, 1])
    ax6.step(t, rec.bandwidth, where='post', color='#1D9E75',
             linewidth=2.0, label='Ancho de banda total')
    _mark_events(ax6, rec.events,
                 {'FAIL', 'RECOVER', 'SCENARIO'})
    for (et, tipo, txt) in rec.events:
        if tipo == 'FOUND':
            ax6.annotate(txt.split(' hallado')[0], (et, 0),
                         rotation=90, fontsize=6, color='#2980B9',
                         va='bottom', ha='right')
    ax6.set_title("6 · Ancho de banda total de la red")
    ax6.set_ylabel("Ancho de banda")
    ax6.set_xlabel("tiempo (s)")
    ax6.legend(fontsize=8, loc='upper left')
    ax6.grid(alpha=0.25)

    ts = time.strftime('%Y%m%d_%H%M%S')
    fname = f"analisis_red_{sim.escenario}_{ts}.png"
    fig.savefig(fname, dpi=110)
    return fname


# ══════════════════════════════════════════════════════════════════════════
#  VISUALIZADOR 
# ══════════════════════════════════════════════════════════════════════════
class Visualizer:


    W, H = 1400, 800
    # ventana del mundo (deja sitio a las etiquetas P1/P2/P3 y márgenes)
    WX0, WX1 = -3.0, 44.0
    WY0, WY1 = -3.0, 35.0
    STEP_DT = 1.0 / 18.0      # ritmo de simulación 

    def __init__(self, sim):
        global pygame
        import pygame as _pg
        pygame = _pg
        self.sim = sim
        self.sel_idx = 0
        self._refresh_sel_ids()
        self._acc = 0.0
        self._running = True
        self.input_active = False
        self.input_text = ""
        self.messages = []          # animaciones de mensajes en vuelo (M)

        # zonas de pantalla
        self.map_rect = pygame.Rect(10, 40, 850, self.H - 90)
        px = 870
        pw = self.W - px - 12
        self.tab_rect = pygame.Rect(px, 10, pw, 250)
        self.q_rect = pygame.Rect(px, 270, pw, 230)
        self.log_rect = pygame.Rect(px, 510, pw, self.H - 510 - 34)

        # escala mundo→pantalla uniforme (equivalente a aspect='equal')
        sx = self.map_rect.w / (self.WX1 - self.WX0)
        sy = self.map_rect.h / (self.WY1 - self.WY0)
        self.scale = min(sx, sy)
        self._xoff = (self.map_rect.w - (self.WX1 - self.WX0) * self.scale) / 2
        self._yoff = (self.map_rect.h - (self.WY1 - self.WY0) * self.scale) / 2

        # colores RGB precomputados
        self.c_bg = self._rgb(sim.C_BG)
        self.c_wall = self._rgb(sim.C_WALL)
        self.c_floor = self._rgb(sim.C_FLOOR)
        self.c_slab = self._rgb('#5F5E5A')
        self.c_stair = self._rgb('#1D9E75')
        self.c_debris = self._rgb('#9C9A8E')
        self.c_alert = self._rgb(sim.C_ALERT)
        self.c_ink = self._rgb('#2C2C2A')
        self.c_dim = self._rgb('#888780')

    # ── color: hex→RGB y mezcla con el fondo (simula alpha) ──
    @staticmethod
    def _rgb(h):
        h = h.lstrip('#')
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    def _blend(self, rgb, a, bg=None):
        bg = bg if bg is not None else self.c_bg
        a = max(0.0, min(1.0, a))
        return (int(rgb[0] * a + bg[0] * (1 - a)),
                int(rgb[1] * a + bg[1] * (1 - a)),
                int(rgb[2] * a + bg[2] * (1 - a)))

    # ── selección de nodos ──
    def _refresh_sel_ids(self):
        self.sel_ids = [n.id for n in self.sim.nodes.values()
                        if n.role == 'G'] + \
                       [n.id for n in self.sim.nodes.values()
                        if n.role == 'N']
        if self.sel_ids:
            self.sel_idx = min(self.sel_idx, len(self.sel_ids) - 1)
        else:
            self.sel_idx = 0

    @property
    def sel_node(self):
        if not self.sel_ids:
            return None
        return self.sim.nodes.get(self.sel_ids[self.sel_idx])

    # ── transformación mundo→pantalla (y invertida: pygame crece hacia abajo)
    def _w2s(self, wx, wy):
        x = self.map_rect.x + self._xoff + (wx - self.WX0) * self.scale
        y = self.map_rect.y + self._yoff + (self.WY1 - wy) * self.scale
        return (int(x), int(y))

    def _text(self, surf, font, s, x, y, color,
              center=False, right=False):
        img = font.render(s, True, color)
        r = img.get_rect()
        if center:
            r.midtop = (x, y)
        elif right:
            r.topright = (x, y)
        else:
            r.topleft = (x, y)
        surf.blit(img, r)
        return r

    # ── formas auxiliares ──
    def _diamond(self, surf, c, r, col, border):
        cx, cy = c
        pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, border, pts, 2)

    def _dashed_line(self, surf, col, a, b, width, dash=6):
        x1, y1 = a
        x2, y2 = b
        dist = math.hypot(x2 - x1, y2 - y1)
        if dist == 0:
            return
        ux, uy = (x2 - x1) / dist, (y2 - y1) / dist
        n = int(dist // dash)
        for i in range(0, n + 1, 2):
            sa = (x1 + ux * dash * i, y1 + uy * dash * i)
            sb = (x1 + ux * dash * (i + 1), y1 + uy * dash * (i + 1))
            pygame.draw.line(surf, col, sa, sb, width)

    def _bubble(self, surf, s, x, y):
        img = self.f_ital.render(s, True, self._rgb('#555555'))
        r = img.get_rect(topleft=(x, y))
        pygame.draw.rect(surf, (255, 255, 255), r.inflate(8, 4),
                         border_radius=4)
        surf.blit(img, r)

    # ── dibujo del edificio + malla ──
    def _draw_map(self, surf):
        surf.set_clip(self.map_rect)
        # pisos
        for piso in range(self.sim.N_PISOS):
            y0 = piso * self.sim.PISO_H
            tl = self._w2s(0, y0 + self.sim.PISO_H)
            br = self._w2s(self.sim.ANCHO, y0)
            rect = pygame.Rect(tl[0], tl[1], br[0] - tl[0], br[1] - tl[1])
            pygame.draw.rect(surf, self._blend(self.c_floor, 0.5), rect)
            pygame.draw.rect(surf, self.c_wall, rect, 1)
            lx, ly = self._w2s(-1.4, y0 + self.sim.PISO_H / 2)
            self._text(surf, self.f_sm, f"P{piso + 1}", lx, ly,
                       self.c_slab, center=True)
       

        nodes = [n for n in self.sim.nodes.values() if n.alive]
        sel = self.sel_node

        # anillo de rango del nodo seleccionado
        if sel and sel.alive:
            c = self._w2s(sel.x, sel.y)
            rr = int(self.sim.cfg['rango_comm'] * self.scale)
            pygame.draw.circle(surf, self._blend(self._rgb(sel.color()), 0.30),
                               c, rr, 1)

        # enlaces de radio coloreados por fiabilidad
        for i, a in enumerate(nodes):
            for b in nodes[i + 1:]:
                rel = self.sim.medium.reliability(a, b)
                if rel <= 0:
                    continue
                base = (29, 158, 117) if rel > 0.66 else (
                    (232, 168, 56) if rel > 0.33 else (226, 75, 74))
                col = self._blend(base, 0.30 + 0.4 * rel)
                w = max(1, int(round(1 + 2 * rel)))
                pygame.draw.line(surf, col, self._w2s(a.x, a.y),
                                 self._w2s(b.x, b.y), w)

        # estelas (historial reciente)
        for n in self.sim.nodes.values():
            h = n.history[-40:]
            if len(h) > 1:
                col = self._blend(self._rgb(n.color()), 0.28)
                pygame.draw.lines(surf, col, False,
                                  [self._w2s(hx, hy) for (hx, hy) in h], 1)

        # paquetes en vuelo (se desvanecen con la edad)
        for p in self.sim.medium.packets_visual:
            pos = p.pos
            col = self._blend(self._rgb(p.color), max(0.05, 1 - p.progress))
            pygame.draw.circle(surf, col, self._w2s(pos[0], pos[1]), 4)

        # nodos + etiquetas
        for n in self.sim.nodes.values():
            in_alert = (n.role == 'G' and n.alive and any(
                pp.in_alert for pp in n.router.peers.values()))
            col = self.c_alert if in_alert else self._rgb(n.color())
            c = self._w2s(n.x, n.y)
            if n.role == 'G':
                pygame.draw.circle(surf, col, c, 9)
                pygame.draw.circle(surf, (255, 255, 255), c, 9, 2)
            else:
                self._diamond(surf, c, 9, col, (255, 255, 255))
            if n is sel and n.alive:
                pygame.draw.circle(surf, self._rgb(n.color()), c, 14, 2)
            tag = n.label
            if not n.alive:
                tag += " X"
            elif in_alert:
                tag += " !"
            tag += f" {n.battery:.0f}%"
            self._text(surf, self.f_xs, tag, c[0], c[1] - 26, col,
                       center=True)
            if n.alive and n.last_msg and (self.sim.t - n.t_beacon) < 1.4:
                self._bubble(surf, f'"{n.last_msg}"', c[0] + 12, c[1] + 6)

        # mensajes personalizados (M) viajando por la malla
        self._draw_messages(surf)

        surf.set_clip(None)
        self._draw_legend(surf)
        self._draw_map_title(surf)

    def _draw_legend(self, surf):
        items = [
            ('o', '#378ADD', 'Rescatista'),
            ('d', self.sim.C_SURV, 'Superviviente'),
            ('d', self.sim.C_SURV_OK, 'Superv. hallado'),
            ('o', self.sim.C_ALERT, 'Alerta'),
            ('l', '#1D9E75', 'Enlace bueno'),
            ('l', '#E24B4A', 'Enlace débil'),
            ('l', self.sim.C_OGM, 'OGM'),
            ('l', self.sim.C_HB, '"estoy bien"'),
            ('l', self.sim.C_MSG, 'Mensaje (M)'),
        ]
        pad, lh, cols = 6, 16, 2
        rows = (len(items) + cols - 1) // cols
        bw, bh = 256, rows * lh + 2 * pad
        bx = self.map_rect.right - bw - 6
        by = self.map_rect.top + 6
        s = pygame.Surface((bw, bh), pygame.SRCALPHA)
        s.fill((255, 255, 255, 220))
        surf.blit(s, (bx, by))
        pygame.draw.rect(surf, self.c_wall, pygame.Rect(bx, by, bw, bh), 1)
        colw = bw // cols
        for idx, (kind, color, label) in enumerate(items):
            ix = bx + pad + (idx % cols) * colw
            iy = by + pad + (idx // cols) * lh + lh // 2
            rgb = self._rgb(color)
            if kind == 'o':
                pygame.draw.circle(surf, rgb, (ix + 5, iy), 5)
            elif kind == 'd':
                self._diamond(surf, (ix + 5, iy), 5, rgb, (255, 255, 255))
            else:
                pygame.draw.line(surf, rgb, (ix, iy), (ix + 12, iy), 3)
            self._text(surf, self.f_xs, label, ix + 18, iy - 7, self.c_ink)

    def _draw_map_title(self, surf):
        s = self.sim.summary()
        estado = "PAUSADO" if self.sim.paused else f"T+{s['t']:.0f}s"
        part = "" if s['comps'] <= 1 else f"   ·   RED PARTIDA ({s['comps']})"
        txt = (f"{estado}   ·   Gateways {s['aliveG']}/{s['totG']}"
               f"   ·   Nodos {s['aliveN']}/{s['totN']}"
               f"   ·   escenario: {self.sim.escenario}{part}")
        col = self.c_alert if s['comps'] > 1 else self.c_ink
        self._text(surf, self.f_title, txt, self.map_rect.x, 10, col)

    # ── marco común de los paneles ──
    def _panel_bg(self, surf, rect, title, title_col=None):
        pygame.draw.rect(surf, (255, 255, 255), rect)
        pygame.draw.rect(surf, self.c_wall, rect, 1)
        self._text(surf, self.f_bold, title, rect.x + 8, rect.y + 6,
                   title_col or self.c_ink)

    # ── panel: tabla de rutas BATMAN del nodo seleccionado ──
    def _draw_table(self, surf):
        rect = self.tab_rect
        self._panel_bg(surf, rect, "Tabla de rutas BATMAN")
        n = self.sel_node
        if not n:
            return
        self._text(surf, self.f_sm,
                   f"{n.label} ({'activo' if n.alive else 'INACTIVO'})",
                   rect.x + 8, rect.y + 26, self._rgb(n.color()))
        cols = [("Dest", 0.03), ("Via", 0.26), ("Hops", 0.46),
                ("TQ", 0.62), ("Visto", 0.80)]
        hy = rect.y + 48
        for label, fx in cols:
            self._text(surf, self.f_xs, label,
                       rect.x + int(fx * rect.w), hy, self.c_ink)
        with n.router._lock:
            rutas = sorted(n.router.routes.values(), key=lambda r: r.dest)
            peers = dict(n.router.peers)
        if not rutas:
            self._text(surf, self.f_sm, "Sin rutas todavía (esperando OGMs)",
                       rect.x + 8, rect.y + 72, self._rgb('#888888'))
            return
        c444 = self._rgb('#444444')
        for i, r in enumerate(rutas[:9]):
            y = rect.y + 66 + i * 17
            p = peers.get(r.dest)
            alert = p.in_alert if p else False
            lost = p.is_lost(self.sim.t, self.sim.cfg['timeout']) if p else False
            col = self.c_alert if (alert or lost) else self.c_ink
            ago = self.sim.t - r.last_seen
            row = [(self.sim.label_of(r.dest), 0.03, col),
                   (self.sim.label_of(r.via_id), 0.26, c444),
                   (str(r.hops), 0.46, c444),
                   (f"{r.tq:.2f}", 0.62, c444),
                   (f"{ago:.0f}s", 0.80, col)]
            for txt, fx, cc in row:
                self._text(surf, self.f_mono_sm, txt,
                           rect.x + int(fx * rect.w), y, cc)

    # ── panel: calidad de enlace y métricas (sparklines) ──
    def _draw_quality(self, surf):
        rect = self.q_rect
        self._panel_bg(surf, rect, "Calidad de red (ventana reciente)")
        rec = self.sim.recorder
        plot = pygame.Rect(rect.x + 34, rect.y + 30, rect.w - 44, rect.h - 56)
        pygame.draw.rect(surf, self._rgb('#DDDDDD'), plot, 1)
        self._text(surf, self.f_xs, "1", plot.x - 16, plot.y - 6, self.c_dim)
        self._text(surf, self.f_xs, "0", plot.x - 16, plot.bottom - 8,
                   self.c_dim)
        dr = rec.deliver_ratio[-160:]
        tq = rec.avg_tq[-160:]
        comp = rec.comp_G[-160:]
        nP = len(dr)
        if nP >= 2:
            def X(i):
                return plot.x + int(i / (nP - 1) * plot.w)

            def Y(v):
                return plot.bottom - int(max(0, min(1, v)) * plot.h)
            # sombreado de particiones
            for i, cc in enumerate(comp):
                if cc and cc > 1:
                    x0 = X(i)
                    x1 = X(min(i + 1, nP - 1))
                    band = pygame.Surface((max(1, x1 - x0), plot.h),
                                          pygame.SRCALPHA)
                    band.fill((142, 68, 173, 45))
                    surf.blit(band, (x0, plot.y))
            pygame.draw.lines(surf, self._rgb('#2980B9'), False,
                              [(X(i), Y(v)) for i, v in enumerate(dr)], 2)
            pygame.draw.lines(surf, self._rgb('#1D9E75'), False,
                              [(X(i), Y(v)) for i, v in enumerate(tq)], 2)
        self._text(surf, self.f_xs, "Entrega", plot.x + 2, rect.bottom - 18,
                   self._rgb('#2980B9'))
        self._text(surf, self.f_xs, "TQ", plot.x + 66, rect.bottom - 18,
                   self._rgb('#1D9E75'))
        self._text(surf, self.f_xs, "Partición", plot.x + 100,
                   rect.bottom - 18, self._rgb('#8E44AD'))

    # ── panel: log ──
    def _fit(self, font, s, maxpx):
        """Recorta s con '…' para que quepa en maxpx px con la fuente dada
        (usa el ancho real del texto, no un nº fijo de caracteres)."""
        if maxpx <= 0 or font.size(s)[0] <= maxpx:
            return s
        while s and font.size(s + "…")[0] > maxpx:
            s = s[:-1]
        return s + "…"

    def _draw_log(self, surf):
        rect = self.log_rect
        self._panel_bg(surf, rect, "Log de eventos de la red")
        cmap = {"info": self._rgb('#5F5E5A'), "ok": self._rgb('#0F6E56'),
                "warn": self._rgb('#854F0B'), "error": self._rgb('#A32D2D')}
        maxlines = max(1, (rect.h - 34) // 16)
        maxpx = rect.w - 78          # de rect.x+70 hasta rect.right-8
        y = rect.y + 30
        for (tt, msg, tipo) in self.sim.log_lines[-maxlines:]:
            self._text(surf, self.f_mono_sm, f"[{tt:5.0f}s]",
                       rect.x + 8, y, self._rgb('#888888'))
            self._text(surf, self.f_mono_sm, self._fit(self.f_mono_sm, msg,
                       maxpx), rect.x + 70, y,
                       cmap.get(tipo, self._rgb('#5F5E5A')))
            y += 16

    def _draw_help(self, surf):
        txt = ("ESPACIO pausa · TAB/←→ o clic seleccionar · 1-9 rescatista · "
               "F caer · G revivir · M mensaje · I inspeccionar (terminal) · "
               "S escenario · +/- rango · [ ] pérdida · P análisis · A añadir · D borrar · "
               "R reinicia · Q salir")
        self._text(surf, self.f_sm, txt, self.W // 2, self.H - 26,
                   self.c_dim, center=True)

    # ── tipografías ──
    def _setup_fonts(self):
        def mk(name, size, bold=False, italic=False):
            try:
                f = pygame.font.SysFont(name, size, bold=bold, italic=italic)
                if f:
                    return f
            except Exception:
                pass
            return pygame.font.Font(None, size)
        self.f_title = mk("segoeui", 20, bold=True)
        self.f = mk("segoeui", 15)
        self.f_sm = mk("segoeui", 13)
        self.f_xs = mk("segoeui", 11)
        self.f_bold = mk("segoeui", 14, bold=True)
        self.f_ital = mk("segoeui", 12, italic=True)
        self.f_mono = mk("consolas", 14)
        self.f_mono_sm = mk("consolas", 12)

    # ── bucle principal ──
    def run(self):
        pygame.init()
        pygame.display.set_caption(
            "Red Ad-Hoc BATMAN (código real) · Rescate en edificio")
        screen = pygame.display.set_mode((self.W, self.H))
        clock = pygame.time.Clock()
        self._setup_fonts()
        while self._running:
            dt = clock.tick(60) / 1000.0
            self._handle_events()
            # avanzar la simulación a ritmo fijo, sea cual sea el fps
            if not self.sim.paused and not self.input_active:
                self._acc += dt
                steps = 0
                while self._acc >= self.STEP_DT and steps < 6:
                    self.sim.step()
                    self._acc -= self.STEP_DT
                    steps += 1
            else:
                self._acc = 0.0
            self._render(screen)
            pygame.display.flip()
        try:
            fn = build_analysis_figure(self.sim)
            if fn:
                print(f"[análisis] figura guardada al salir: {fn}")
        except Exception as e:
            print(f"[análisis] no se pudo guardar la figura: {e}")
        pygame.quit()

    def _render(self, screen):
        screen.fill(self.c_bg)
        self._draw_map(screen)
        self._draw_table(screen)
        self._draw_quality(screen)
        self._draw_log(screen)
        self._draw_help(screen)
        if self.input_active:
            self._draw_input(screen)

    # ── eventos ──
    def _handle_events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self._running = False
            elif e.type == pygame.KEYDOWN:
                if self.input_active:
                    self._key_input(e)
                else:
                    self._key_control(e)
            elif (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1
                  and not self.input_active):
                self._click_select(e.pos)

    def _click_select(self, pos):
        best, bestd = None, 20 ** 2
        for i, nid in enumerate(self.sel_ids):
            n = self.sim.nodes.get(nid)
            if not n:
                continue
            sx, sy = self._w2s(n.x, n.y)
            d = (sx - pos[0]) ** 2 + (sy - pos[1]) ** 2
            if d < bestd:
                bestd, best = d, i
        if best is not None:
            self.sel_idx = best

    def _key_control(self, e):
        sim = self.sim
        k, u = e.key, e.unicode
        if k == pygame.K_SPACE:
            sim.paused = not sim.paused
            sim.log("Simulación " +
                    ("PAUSADA" if sim.paused else "REANUDADA"), "warn")
        elif k in (pygame.K_TAB, pygame.K_RIGHT):
            if self.sel_ids:
                self.sel_idx = (self.sel_idx + 1) % len(self.sel_ids)
        elif k == pygame.K_LEFT:
            if self.sel_ids:
                self.sel_idx = (self.sel_idx - 1) % len(self.sel_ids)
        elif k == pygame.K_a:
            sim.add_node()
            self._refresh_sel_ids()
        elif k == pygame.K_d:
            n = self.sel_node
            if n:
                sim.remove_node(n.id)
                self._refresh_sel_ids()
        elif k == pygame.K_f:
            n = self.sel_node
            if n:
                sim.fail_node(n.id)
        elif k == pygame.K_g:
            n = self.sel_node
            if n:
                sim.recover_node(n.id)
        elif k == pygame.K_s:
            i = SCENARIOS.index(sim.escenario)
            sim.escenario = SCENARIOS[(i + 1) % len(SCENARIOS)]
            sim._build_world()
            self._refresh_sel_ids()
            self.messages.clear()
        elif k == pygame.K_m:
            self._open_input()
        elif k == pygame.K_p:
            fn = build_analysis_figure(sim)
            sim.log(f"Análisis guardado: {fn}", "ok")
            print(f"[análisis] figura guardada: {fn}")
        elif k == pygame.K_i:
            print(snapshot_red(sim))
            sim.log("Instantánea de la red impresa en la terminal "
                    "(tabla de rutas, vecinos, conectividad)", "info")
        elif k == pygame.K_r:
            sim._build_world()
            self._refresh_sel_ids()
            self.messages.clear()
        elif k in (pygame.K_q, pygame.K_ESCAPE):
            self._running = False
        elif u in ('+', '='):
            sim.set_param('rango_comm',
                          round(sim.cfg['rango_comm'] + 1.0, 1))
        elif u == '-':
            sim.set_param('rango_comm',
                          max(4.0, round(sim.cfg['rango_comm'] - 1.0, 1)))
        elif u == ']':
            sim.set_param('falloff',
                          min(1.5, round(sim.cfg['falloff'] + 0.05, 2)))
        elif u == '[':
            sim.set_param('falloff',
                          max(0.0, round(sim.cfg['falloff'] - 0.05, 2)))
        elif u and u in '123456789':
            i = int(u) - 1
            rs = [n.id for n in sim.nodes.values() if n.role == 'G']
            if i < len(rs):
                self.sel_idx = self.sel_ids.index(rs[i])

    # ── composición de mensajes (entrada de texto en la propia ventana) ──
    def _open_input(self):
        if len(self.sim.nodes) < 2:
            self.sim.log("Hacen falta al menos 2 nodos.", "warn")
            return
        self.input_active = True
        self.input_text = ""

    def _key_input(self, e):
        if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            raw = self.input_text.strip()
            self.input_active = False
            self.input_text = ""
            if raw:
                self._resolve_and_send(raw)
        elif e.key == pygame.K_ESCAPE:
            self.input_active = False
            self.input_text = ""
        elif e.key == pygame.K_BACKSPACE:
            self.input_text = self.input_text[:-1]
        else:
            ch = e.unicode
            if ch and ch.isprintable() and len(self.input_text) < 120:
                self.input_text += ch

    def _resolve_and_send(self, raw):
        """Interpreta 'R1 > R3 texto' / 'S2 > R1 texto' / '1>3 texto' y
        manda el mensaje por la malla BATMAN."""
        import re
        resc_ids = sorted(n.id for n in self.sim.nodes.values()
                          if n.role == 'G')
        surv_ids = sorted(n.id for n in self.sim.nodes.values()
                          if n.role == 'N')
        m = re.match(r"\s*([rRsS]?)(\d+)\s*>\s*([rRsS]?)(\d+)\s+(.+)", raw)
        if not m:
            self.sim.log(f"Formato inválido: '{raw}'. Usa "
                         f"R1>R3 texto  o  S2>R1 texto", "warn")
            return
        rol_from, idx_from = m.group(1).upper() or 'G', int(m.group(2))
        rol_to = m.group(3).upper() or 'G'
        idx_to, texto = int(m.group(4)), m.group(5)

        def resolver(rol, idx):
            lista = resc_ids if rol == 'G' else surv_ids
            if not (1 <= idx <= len(lista)):
                return None
            return lista[idx - 1]

        from_id = resolver(rol_from, idx_from)
        to_id = resolver(rol_to, idx_to)
        if from_id is None or to_id is None:
            self.sim.log(f"Índice fuera de rango (R: {len(resc_ids)}, "
                         f"S: {len(surv_ids)}).", "warn")
            return
        path = self.sim.send_unicast(from_id, to_id, texto.strip())
        if path and len(path) >= 2:
            self._enqueue_message(path, texto.strip(),
                                  self.sim.label_of(from_id),
                                  self.sim.label_of(to_id))

    def _enqueue_message(self, path_ids, text, src_label, dst_label):
        """Registra una animación de mensaje con reloj de pared (independiente
        del paso de simulación) para que SE VEA viajar salto a salto y el
        texto quede visible varios segundos al llegar al destino."""
        now = pygame.time.get_ticks() / 1000.0
        segs = max(1, len(path_ids) - 1)
        pts0 = [(self.sim.nodes[i].x, self.sim.nodes[i].y)
                for i in path_ids]                 # snapshot por si un nodo cae
        self.messages.append({
            'ids': list(path_ids),
            'pts0': pts0,
            'text': text,
            'src': src_label,
            'dst': dst_label,
            'start': now,
            'dur': max(1.3, 0.7 * segs),           # ~0.7 s por salto
            'hold': 3.2,                           # texto fijo en el destino
        })
        self.messages = self.messages[-4:]         # a lo sumo 4 en vuelo

    def _msg_point(self, msg, i):
        """Posición en pantalla del i-ésimo nodo del camino (sigue al nodo
        vivo; si cayó, usa la posición capturada al enviar)."""
        n = self.sim.nodes.get(msg['ids'][i])
        if n is not None and n.alive:
            return self._w2s(n.x, n.y)
        wx, wy = msg['pts0'][i]
        return self._w2s(wx, wy)

    def _draw_messages(self, surf):
        """Dibuja los mensajes en vuelo: ruta resaltada, marcador que viaja
        salto a salto y un globo con el texto que se fija en el destino."""
        if not self.messages:
            return
        now = pygame.time.get_ticks() / 1000.0
        pulse = 3 if (pygame.time.get_ticks() // 250) % 2 == 0 else 0
        alive = []
        for msg in self.messages:
            el = now - msg['start']
            dur, hold = msg['dur'], msg['hold']
            if el >= dur + hold:
                continue
            alive.append(msg)
            pts = [self._msg_point(msg, i) for i in range(len(msg['ids']))]
            if len(pts) >= 2:                      # ruta resaltada
                pygame.draw.lines(surf, self._blend(self._rgb(self.sim.C_MSG), 0.55),
                                  False, pts, 3)
            segs = len(pts) - 1
            if el <= dur:                          # viajando
                seg_f = (el / dur) * segs
                i = min(int(seg_f), segs - 1)
                local = seg_f - i
                ax, ay = pts[i]
                bx, by = pts[i + 1]
                mx = int(ax + (bx - ax) * local)
                my = int(ay + (by - ay) * local)
            else:                                  # llegó: fijo en destino
                mx, my = pts[-1]
            pygame.draw.circle(surf, self._blend(self._rgb(self.sim.C_MSG), 0.35),
                               (mx, my), 6 + int(3 * pulso), max(1, int(3 * (1 - pulso))))
            pygame.draw.circle(surf, self._rgb(self.sim.C_MSG), (mx, my), 6)
            pygame.draw.circle(surf, (255, 255, 255), (mx, my), 6, 2)
            label = f"{msg['src']}→{msg['dst']}: {msg['text']}"
            if len(label) > 46:
                label = label[:45] + "…"
            self._msg_bubble(surf, label, mx + 12, my - 10)
        self.messages = alive

    def _msg_bubble(self, surf, s, x, y):
        """Globo prominente (relleno color mensaje, texto blanco) que se
        mantiene dentro del mapa."""
        img = self.f_bold.render(s, True, (255, 255, 255))
        r = img.get_rect(topleft=(x + 6, y + 3))
        bg = r.inflate(14, 8)
        if bg.right > self.map_rect.right - 4:
            d = bg.right - (self.map_rect.right - 4)
            bg.move_ip(-d, 0)
            r.move_ip(-d, 0)
        if bg.left < self.map_rect.left + 4:
            d = (self.map_rect.left + 4) - bg.left
            bg.move_ip(d, 0)
            r.move_ip(d, 0)
        if bg.top < self.map_rect.top + 4:
            d = (self.map_rect.top + 4) - bg.top
            bg.move_ip(0, d)
            r.move_ip(0, d)
        pygame.draw.rect(surf, self._rgb(self.sim.C_MSG), bg, border_radius=5)
        pygame.draw.rect(surf, (255, 255, 255), bg, 1, border_radius=5)
        surf.blit(img, r)

    def _draw_input(self, surf):
        dim = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        dim.fill((20, 20, 25, 150))
        surf.blit(dim, (0, 0))
        bw, bh = 740, 236
        bx, by = (self.W - bw) // 2, (self.H - bh) // 2
        box = pygame.Rect(bx, by, bw, bh)
        pygame.draw.rect(surf, (255, 255, 255), box, border_radius=8)
        pygame.draw.rect(surf, self.c_slab, box, 2, border_radius=8)
        self._text(surf, self.f_title, "Mensaje personalizado (R o S)",
                   bx + 20, by + 16, self.c_ink)
        resc = ", ".join(self.sim.label_of(i) for i in sorted(
            n.id for n in self.sim.nodes.values() if n.role == 'G'))
        surv = ", ".join(self.sim.label_of(i) for i in sorted(
            n.id for n in self.sim.nodes.values() if n.role == 'N'))
        info = [f"Rescatistas: {resc}",
                f"Supervivientes: {surv}",
                "Formato:  R1 > R3 cuidado con los escombros",
                "          S2 > R1 estoy atrapado en el piso 2",
                "(emisor > destino, espacio, texto)"]
        yy = by + 52
        for ln in info:
            self._text(surf, self.f_sm, ln, bx + 20, yy, self._rgb('#555555'))
            yy += 20
        inp = pygame.Rect(bx + 20, by + bh - 46, bw - 40, 30)
        pygame.draw.rect(surf, self._rgb('#F2F1EC'), inp)
        pygame.draw.rect(surf, self.c_dim, inp, 1)
        cur = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
        self._text(surf, self.f_mono, self.input_text + cur,
                   inp.x + 6, inp.y + 6, self.c_ink)
        self._text(surf, self.f_xs, "Enter envía · Esc cancela",
                   inp.right, inp.bottom + 4, self.c_dim, right=True)


# ══════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════
def main():
    p = argparse.ArgumentParser(
        description="Simulación de red ad-hoc con BATMAN real (rescate).")
    p.add_argument('--escenario', default='base', choices=SCENARIOS)
    p.add_argument('--headless', action='store_true',
                   help="Sin ventana: corre y guarda el análisis en PNG")
    p.add_argument('--duracion', type=float, default=200.0,
                   help="Segundos simulados en modo headless")
    p.add_argument('--timeout', type=float, default=DEFAULTS['timeout'],
                   help="Segundos sin señal para marcar rescatista caído")
    p.add_argument('--rango', type=float, default=DEFAULTS['rango_comm'],
                   help="Alcance de radio en metros")
    p.add_argument('--falloff', type=float, default=DEFAULTS['falloff'],
                   help="Degradación de fiabilidad con la distancia (0-1.5)")
    p.add_argument('--seed', type=int, default=None,
                   help="Semilla aleatoria (reproducibilidad)")
    p.add_argument('--inspect', action='store_true',
                   help="Imprime en TEXTO el estado interno de la red "
                        "(tabla de rutas, vecinos, conectividad) y sale. "
                        "Corre --duracion segundos antes del volcado.")
    args = p.parse_args()

    if args.seed is not None:
        random.seed(args.seed)
        np.random.seed(args.seed)

    cfg = dict(timeout=args.timeout, rango_comm=args.rango,
               falloff=args.falloff)
    sim = Simulation(escenario=args.escenario, cfg=cfg)

    print("=" * 68)
    print("  Red Ad-Hoc · BATMAN REAL (batman_node.py) en simulación")
    print(f"  Escenario: {args.escenario}  ·  timeout={args.timeout:.0f}s  "
          f"·  rango={args.rango:.0f}m")
    print("=" * 68)

    if args.inspect:
        pasos = int(args.duracion / DT)
        for _ in range(pasos):
            sim.step()
        print(snapshot_red(sim))
        return

    if args.headless:
        pasos = int(args.duracion / DT)
        for _ in range(pasos):
            sim.step()
        fn = build_analysis_figure(sim)
        s = sim.summary()
        print(f"\n  Tiempo simulado     : {s['t']:.0f} s")
        print(f"  Gateways activos : {s['aliveG']}/{s['totG']}")
        print(f"  Nodos      : {s['aliveN']}/{s['totN']}")
        print(f"  Componentes finales : {s['comps']}")
        print(f"  Eventos registrados : {len(sim.recorder.events)}")
        print(f"  Paquetes radio      : {sim.medium.delivered}/"
              f"{sim.medium.attempted} entregados")
        print(f"\n  Figura de análisis  : {fn}\n")
        for (et, tipo, txt) in sim.recorder.events:
            print(f"    [{et:6.1f}s] {tipo:10s} {txt}")
    else:
        viz = Visualizer(sim)
        viz.run()
        s = sim.summary()
        print(f"\n  Resumen: t={s['t']:.0f}s · "
              f"gateways {s['aliveG']}/{s['totG']} · "
              f"nodos {s['aliveN']}/{s['totN']}")


if __name__ == "__main__":
    main()
