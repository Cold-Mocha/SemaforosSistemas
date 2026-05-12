import tkinter as tk
from main import Interseccion, LONGITUD_CARRIL, DURACION_TICK
from controlador import Controlador

CELL_SIZE   = 16
WIDTH       = 700
HEIGHT      = 700
CENTER      = WIDTH // 2
ROAD_HALF   = 80
LANE_OFFSET = 18


def _lamparas(color: str):
    """Devuelve la tupla (R, Y, G) de colores Tkinter según el color del semáforo."""
    if color == 'verde':    return ('gray20', 'gray20', 'lime green')
    if color == 'amarillo': return ('gray20', 'yellow',  'gray20')
    return ('red', 'gray20', 'gray20')  # rojo


class GUI:
    _PED_ARROW = {
        'top':    ( 9,  0),
        'bottom': (-9,  0),
        'left':   ( 0, -9),
        'right':  ( 0,  9),
    }

    def __init__(self, root):
        self.root = root
        self.root.title('Simulación de Intersección')
        self.canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg='white')
        self.canvas.pack()

        ctrl = tk.Frame(root)
        ctrl.pack(fill='x', padx=8, pady=2)
        tk.Label(ctrl, text='Velocidad (ms/tick):').pack(side='left')
        self.speed_var = tk.IntVar(value=int(DURACION_TICK * 1000))
        tk.Scale(ctrl, from_=100, to=2000, resolution=100,
                 orient='horizontal', variable=self.speed_var,
                 length=300).pack(side='left')

        self.sim = Interseccion(seed=123)
        self.running = True
        self.draw_static()
        self.update_frame()

    # ── Estático (dibujado una sola vez) ───────────────────────────

    def draw_static(self):
        c = self.canvas
        # Calles (negro)
        c.create_rectangle(0, CENTER - ROAD_HALF, WIDTH, CENTER + ROAD_HALF, fill='black')
        c.create_rectangle(CENTER - ROAD_HALF, 0, CENTER + ROAD_HALF, HEIGHT, fill='black')
        # Pasos de cebra (azul)
        cross_w = ROAD_HALF
        for i in range(-3, 4):
            x1 = CENTER - cross_w + i * 20
            c.create_rectangle(x1, CENTER - ROAD_HALF - 20, x1 + 12,
                                CENTER - ROAD_HALF - 8, fill='blue', outline='')
        for i in range(-3, 4):
            x1 = CENTER - cross_w + i * 20
            c.create_rectangle(x1, CENTER + ROAD_HALF + 8, x1 + 12,
                                CENTER + ROAD_HALF + 20, fill='blue', outline='')
        for i in range(-3, 4):
            y1 = CENTER - cross_w + i * 20
            c.create_rectangle(CENTER - ROAD_HALF - 20, y1, CENTER - ROAD_HALF - 8,
                                y1 + 12, fill='blue', outline='')
        for i in range(-3, 4):
            y1 = CENTER - cross_w + i * 20
            c.create_rectangle(CENTER + ROAD_HALF + 8, y1, CENTER + ROAD_HALF + 20,
                                y1 + 12, fill='blue', outline='')
        self._draw_signal_housings()

    def _draw_signal_housings(self):
        c = self.canvas
        # Carcasa semáforo vertical (al sur de la intersección)
        c.create_rectangle(336, 438, 364, 502, fill='#333', outline='white', width=1)
        # Carcasa semáforo horizontal (al oeste de la intersección)
        c.create_rectangle(198, 336, 262, 364, fill='#333', outline='white', width=1)

    # ── Dinámico (redibujado cada tick) ───────────────────────────

    def update_frame(self):
        self.sim.step()
        self.draw_dynamic()
        if self.running:
            self.root.after(self.speed_var.get(), self.update_frame)

    def draw_dynamic(self):
        self.canvas.delete('dyn')
        self._draw_signals()

        # Autos — dirección Norte
        for carril_idx, carril in enumerate(self.sim.norte.carriles):
            for auto in carril:
                x, y = self._pos_auto_norte(auto, carril_idx)
                self.canvas.create_rectangle(x - 8, y - 12, x + 8, y + 12,
                                             fill='magenta', outline='', tags='dyn')
                self.canvas.create_polygon(x, y - 10, x - 5, y + 6, x + 5, y + 6,
                                           fill='white', tags='dyn')

        # Autos — dirección Este
        for carril_idx, carril in enumerate(self.sim.este.carriles):
            for auto in carril:
                x, y = self._pos_auto_este(auto, carril_idx)
                self.canvas.create_rectangle(x - 12, y - 8, x + 12, y + 8,
                                             fill='magenta', outline='', tags='dyn')
                self.canvas.create_polygon(x + 10, y, x - 6, y - 5, x - 6, y + 5,
                                           fill='white', tags='dyn')

        # Personas en cada cruce
        for cruce in self.sim.cruces.values():
            for persona in cruce.personas:
                x, y = self._pos_persona(persona)
                self.canvas.create_oval(x - 6, y - 6, x + 6, y + 6,
                                        fill='green', outline='', tags='dyn')
                dx, dy = self._PED_ARROW[persona.cruce]
                if persona.sentido == -1:
                    dx, dy = -dx, -dy
                self.canvas.create_line(x, y, x + dx, y + dy,
                                        arrow=tk.LAST, fill='white', width=2,
                                        arrowshape=(6, 8, 3), tags='dyn')

        # Texto de estado con decision del controlador
        sv, sh = self.sim.semaforo_v, self.sim.semaforo_h
        dec = self.sim.ultima_decision
        dec_txt = f"{dec.accion.upper()} | {dec.razon}" if dec else "---"
        texto = (
            f"SV:{sv.color}(t={sv.timer})  SH:{sh.color}(t={sh.timer})  fase={self.sim.ticks_en_fase}t\n"
            f"Tick:{self.sim.total_ticks}  "
            f"Cruzaron:{self.sim.autos_cruzaron}v/{self.sim.peatones_cruzaron}p  "
            f"{dec_txt}"
        )
        self.canvas.create_rectangle(6, 6, 694, 46,
                                     fill='black', stipple='gray50', outline='', tags='dyn')
        self.canvas.create_text(10, 10, anchor='nw', text=texto,
                                fill='white', font=('Courier', 9, 'bold'), tags='dyn')

    def _draw_signals(self):
        c = self.canvas
        r = 7
        n_col = _lamparas(self.sim.semaforo_v.color)
        e_col = _lamparas(self.sim.semaforo_h.color)
        # Lámparas semáforo Norte (apiladas verticalmente)
        for cy, color in zip((448, 470, 492), n_col):
            c.create_oval(350 - r, cy - r, 350 + r, cy + r,
                          fill=color, outline='', tags='dyn')
        # Lámparas semáforo Este (en fila horizontal)
        for cx, color in zip((208, 230, 252), e_col):
            c.create_oval(cx - r, 350 - r, cx + r, 350 + r,
                          fill=color, outline='', tags='dyn')

    # ── Posicionamiento ────────────────────────────────────────────

    def _pos_auto_norte(self, auto, carril_idx: int):
        lane_x = CENTER - LANE_OFFSET if carril_idx == 0 else CENTER + LANE_OFFSET
        y = (CENTER + ROAD_HALF) + auto.pos * CELL_SIZE
        return lane_x, y

    def _pos_auto_este(self, auto, carril_idx: int):
        lane_y = CENTER + LANE_OFFSET if carril_idx == 0 else CENTER - LANE_OFFSET
        x = (CENTER - ROAD_HALF) - auto.pos * CELL_SIZE
        return x, lane_y

    def _pos_persona(self, persona):
        span = ROAD_HALF * 2
        dp = persona.pos if persona.sentido == 1 else 1.0 - persona.pos
        if persona.cruce == 'top':
            return CENTER - ROAD_HALF + dp * span, CENTER - ROAD_HALF - 14
        if persona.cruce == 'bottom':
            return CENTER + ROAD_HALF - dp * span, CENTER + ROAD_HALF + 14
        if persona.cruce == 'left':
            return CENTER - ROAD_HALF - 14, CENTER + ROAD_HALF - dp * span
        return CENTER + ROAD_HALF + 14, CENTER - ROAD_HALF + dp * span


if __name__ == '__main__':
    root = tk.Tk()
    app = GUI(root)
    root.mainloop()
