"""
Algoritmo de decision adaptativo para la interseccion.

El Controlador observa el ESTADO actual (cuantos autos/peatones esperan
en cada lado y cuanto tiempo lleva la fase en verde) y decide si
MANTENER o CAMBIAR la fase activa.

Reglas de decision (en orden de prioridad):
  1. Minimo de verde: no cambiar antes de min_verde ticks.
  2. Maximo de verde: cambiar si se supera max_verde ticks.
  3. Presion alterna: cambiar si el lado que espera tiene mucha mas presion.
  4. Por defecto: mantener.
"""
from dataclasses import dataclass
from typing import Dict


@dataclass
class Estado:
    autos_norte: int
    autos_este: int
    peatones: Dict[str, int]  # {'top': n, 'bottom': n, 'left': n, 'right': n}
    fase_verde: str           # 'vertical' o 'horizontal'
    ticks_en_fase: int


@dataclass
class Decision:
    accion: str               # 'mantener' o 'cambiar'
    razon: str
    presion_actual: float
    presion_alterna: float


class Controlador:
    def __init__(
        self,
        peso_auto: float = 1.0,
        peso_peaton: float = 0.8,
        min_verde: int = 3,
        max_verde: int = 12,
        umbral_cambio: float = 1.5,
    ):
        self.peso_auto     = peso_auto
        self.peso_peaton   = peso_peaton
        self.min_verde     = min_verde
        self.max_verde     = max_verde
        self.umbral_cambio = umbral_cambio

    def _presion(self, n_autos: int, n_peatones: int) -> float:
        return n_autos * self.peso_auto + n_peatones * self.peso_peaton

    def _presiones(self, estado: Estado):
        peds = estado.peatones
        if estado.fase_verde == 'vertical':
            return (
                self._presion(estado.autos_norte, peds['left'] + peds['right']),
                self._presion(estado.autos_este,  peds['top']  + peds['bottom']),
            )
        return (
            self._presion(estado.autos_este,  peds['top']  + peds['bottom']),
            self._presion(estado.autos_norte, peds['left'] + peds['right']),
        )

    def decidir(self, estado: Estado) -> Decision:
        p_actual, p_alterna = self._presiones(estado)
        t = estado.ticks_en_fase

        if t < self.min_verde:
            return Decision('mantener',
                            f"Minimo no cumplido ({t}/{self.min_verde} ticks en verde)",
                            p_actual, p_alterna)

        if t >= self.max_verde:
            return Decision('cambiar',
                            f"Maximo superado ({t} >= {self.max_verde} ticks), cambio forzado",
                            p_actual, p_alterna)

        if p_alterna > p_actual * self.umbral_cambio:
            return Decision('cambiar',
                            f"Presion alterna {p_alterna:.1f} > "
                            f"actual {p_actual:.1f} x{self.umbral_cambio} "
                            f"(umbral={p_actual * self.umbral_cambio:.1f})",
                            p_actual, p_alterna)

        return Decision('mantener',
                        f"Presion actual {p_actual:.1f} suficiente "
                        f"(alterna {p_alterna:.1f}, umbral={p_actual * self.umbral_cambio:.1f})",
                        p_actual, p_alterna)
