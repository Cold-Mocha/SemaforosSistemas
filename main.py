#!/usr/bin/env python3
"""
Simulador de interseccion con controlador adaptativo.

Clases de dominio:
  Auto, Persona, Semaforo, Direccion, Cruce, Interseccion

Algoritmo de decision:
  Controlador (en controlador.py): observa el estado actual y decide
  si mantener o cambiar la fase verde segun presion de cola.

Ejecucion: python main.py [ticks]
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import random, sys, time

from controlador import Controlador, Estado, Decision

# ─── Constantes ────────────────────────────────────────────────────
VERDE_DURACION    = 5    # ticks iniciales de verde (el controlador puede extender)
AMARILLO_DURACION = 2    # ticks de amarillo (fijo, siempre el mismo)
DURACION_TICK     = 1    # segundos/tick en modo tiempo real
LONGITUD_CARRIL   = 8    # celdas desde el spawn hasta la interseccion
VELOCIDAD_AUTO    = 1    # celdas/tick
VELOCIDAD_PEATON  = 0.4  # progreso/tick (0.0 a 1.0)
PROB_AUTO         = 0.4
PROB_PEATON       = 0.2

_uid = 0
def nuevo_id() -> int:
    global _uid
    _uid += 1
    return _uid


# ─── Entidades ─────────────────────────────────────────────────────

@dataclass
class Auto:
    id: int
    pos: int          # distancia a la interseccion; 0 = frontera
    carril: int       # 0 o 1
    rumbo: str        # 'N' o 'E'
    velocidad: int = VELOCIDAD_AUTO


@dataclass
class Persona:
    id: int
    cruce: str        # 'top', 'bottom', 'left', 'right'
    pos: float        # progreso 0.0..1.0
    sentido: int      # +1 o -1 (solo afecta renderizado)
    velocidad: float = VELOCIDAD_PEATON


@dataclass
class Semaforo:
    id: int
    nombre: str
    color: str              # 'verde', 'amarillo', 'rojo'
    timer: int
    duracion_verde: int    = VERDE_DURACION
    duracion_amarillo: int = AMARILLO_DURACION

    @property
    def es_verde(self) -> bool:
        return self.color == 'verde'

    @property
    def es_amarillo(self) -> bool:
        return self.color == 'amarillo'

    @property
    def es_rojo(self) -> bool:
        return self.color == 'rojo'


@dataclass
class Direccion:
    nombre: str
    rumbo: str
    longitud: int
    num_carriles: int
    semaforo: Semaforo
    carriles: List[List[Auto]] = field(default_factory=lambda: [[], []])

    def total_autos(self) -> int:
        return sum(len(c) for c in self.carriles)

    def autos_en_espera(self) -> int:
        return sum(1 for lane in self.carriles for a in lane if a.pos == 0)


@dataclass
class Cruce:
    nombre: str
    semaforo: Semaforo
    ancho: float = 1.0
    personas: List[Persona] = field(default_factory=list)

    @property
    def peatones_pueden_cruzar(self) -> bool:
        return self.semaforo.color in ('verde', 'amarillo')


# ─── Interseccion ──────────────────────────────────────────────────

class Interseccion:
    """
    Orquesta la simulacion usando un Controlador adaptativo.

    Cada tick en fase verde, el controlador evalua el estado actual
    (cuantos autos y peatones esperan en cada lado, cuanto tiempo
    llevamos en verde) y decide si MANTENER o CAMBIAR la fase.
    """

    def __init__(self, seed: int = None, controlador: Controlador = None):
        self.r = random.Random(seed)

        # Dos semaforos coordinados
        self.semaforo_v = Semaforo(id=1, nombre='vertical',
                                   color='verde', timer=VERDE_DURACION)
        self.semaforo_h = Semaforo(id=2, nombre='horizontal',
                                   color='rojo',  timer=VERDE_DURACION)

        # Calles de aproximacion
        self.norte = Direccion('Norte', 'N', LONGITUD_CARRIL, 2, self.semaforo_v)
        self.este  = Direccion('Este',  'E', LONGITUD_CARRIL, 2, self.semaforo_h)

        # Cruces peatonales
        self.cruces: Dict[str, Cruce] = {
            'top':    Cruce('top',    self.semaforo_h),
            'bottom': Cruce('bottom', self.semaforo_h),
            'left':   Cruce('left',   self.semaforo_v),
            'right':  Cruce('right',  self.semaforo_v),
        }

        # Controlador de decision (usa parametros por defecto si no se pasa uno)
        self.controlador: Controlador = controlador or Controlador()

        # Estado del ciclo de semaforos
        self.ticks_en_fase: int = 0           # ticks acumulados en el verde actual
        self.ultima_decision: Optional[Decision] = None

        # Estadisticas
        self.autos_cruzaron    = 0
        self.peatones_cruzaron = 0
        self.total_ticks       = 0

    @property
    def semaforos(self) -> List[Semaforo]:
        return [self.semaforo_v, self.semaforo_h]

    # ── Captura de estado ──────────────────────────────────────────

    def capturar_estado(self) -> Estado:
        """
        Lee la situacion actual de la interseccion y la empaqueta
        en un Estado que el Controlador puede evaluar.
        """
        fase = 'vertical' if self.semaforo_v.es_verde else 'horizontal'
        return Estado(
            autos_norte=self.norte.total_autos(),
            autos_este=self.este.total_autos(),
            peatones={nombre: len(cruce.personas)
                      for nombre, cruce in self.cruces.items()},
            fase_verde=fase,
            ticks_en_fase=self.ticks_en_fase,
        )

    # ── Spawn ──────────────────────────────────────────────────────

    def _spawn(self):
        for direccion in (self.norte, self.este):
            for carril_idx in range(direccion.num_carriles):
                if self.r.random() < PROB_AUTO:
                    direccion.carriles[carril_idx].append(
                        Auto(nuevo_id(), direccion.longitud, carril_idx, direccion.rumbo)
                    )
        for cruce in self.cruces.values():
            if self.r.random() < PROB_PEATON:
                sentido = self.r.choice((-1, 1))
                cruce.personas.append(
                    Persona(nuevo_id(), cruce.nombre, 0.0, sentido)
                )

    # ── Movimiento ─────────────────────────────────────────────────

    def _mover_autos(self, direccion: Direccion):
        for idx, carril in enumerate(direccion.carriles):
            carril.sort(key=lambda a: -a.pos)
            for auto in carril:
                puede = True
                if auto.pos == 0 and not direccion.semaforo.es_verde:
                    puede = False
                adelante = [b for b in carril if b is not auto and b.pos < auto.pos]
                if adelante:
                    cercano = max(adelante, key=lambda x: x.pos)
                    if cercano.pos >= auto.pos - auto.velocidad:
                        puede = False
                if puede:
                    auto.pos = max(0, auto.pos - auto.velocidad)

            salieron = [a for a in carril if a.pos == 0 and direccion.semaforo.es_verde]
            self.autos_cruzaron += len(salieron)
            direccion.carriles[idx] = [
                a for a in carril
                if not (a.pos == 0 and direccion.semaforo.es_verde)
            ]

    def _mover_peatones(self):
        for cruce in self.cruces.values():
            terminados = []
            for persona in cruce.personas:
                if cruce.peatones_pueden_cruzar:
                    persona.pos += persona.velocidad
                if persona.pos >= 1.0:
                    terminados.append(persona)
            self.peatones_cruzaron += len(terminados)
            cruce.personas = [p for p in cruce.personas if p not in terminados]

    # ── Semaforos adaptativos ──────────────────────────────────────

    def _tick_semaforos(self):
        """
        Gestiona el ciclo de semaforos con decision adaptativa.

        Durante AMARILLO: transicion fija, no hay decision.
        Durante VERDE: el Controlador evalua el estado y decide si cambiar.
        """
        sv, sh = self.semaforo_v, self.semaforo_h

        # Fase amarillo: siempre transiciona, no hay decision
        if sv.es_amarillo:
            sv.timer -= 1
            if sv.timer <= 0:
                sv.color = 'rojo'
                sh.color = 'verde'
                self.ticks_en_fase = 0
            return
        if sh.es_amarillo:
            sh.timer -= 1
            if sh.timer <= 0:
                sh.color = 'rojo'
                sv.color = 'verde'
                self.ticks_en_fase = 0
            return

        # Fase verde: pedir decision al controlador
        self.ticks_en_fase += 1
        estado = self.capturar_estado()
        decision = self.controlador.decidir(estado)
        self.ultima_decision = decision

        if decision.accion == 'cambiar':
            activo = sv if sv.es_verde else sh
            activo.color = 'amarillo'
            activo.timer = activo.duracion_amarillo

    # ── Paso de simulacion ─────────────────────────────────────────

    def step(self):
        self._spawn()
        self._mover_autos(self.norte)
        self._mover_autos(self.este)
        self._mover_peatones()
        self._tick_semaforos()
        self.total_ticks += 1

    # ── Estado para consola ────────────────────────────────────────

    def status(self) -> str:
        sv, sh = self.semaforo_v, self.semaforo_h
        dec = self.ultima_decision
        lines = [
            f"-- Tick {self.total_ticks} {'-'*30}",
            f"  Semaforo {sv.nombre:11s} [{sv.id}]: {sv.color:8s} (timer={sv.timer})",
            f"  Semaforo {sh.nombre:11s} [{sh.id}]: {sh.color:8s} (timer={sh.timer})",
            f"  Ticks en fase  : {self.ticks_en_fase}",
            f"  Cruzaron       : {self.autos_cruzaron} autos, {self.peatones_cruzaron} peatones",
        ]
        if dec:
            lines.append(
                f"  Decision       : {dec.accion.upper()} | {dec.razon}"
            )
            lines.append(
                f"  Presion        : actual={dec.presion_actual:.1f}  alterna={dec.presion_alterna:.1f}"
            )
        for dir_obj in (self.norte, self.este):
            for i, carril in enumerate(dir_obj.carriles):
                pos_str = ', '.join(str(a.pos) for a in carril) or '-'
                lines.append(f"  {dir_obj.nombre} carril{i}: [{pos_str}]")
        for cruce in self.cruces.values():
            estado_str = 'CRUZA' if cruce.peatones_pueden_cruzar else 'ESPERA'
            lines.append(
                f"  Cruce {cruce.nombre:6s}: {len(cruce.personas)} peatones [{estado_str}]"
            )
        return '\n'.join(lines)


# ─── Punto de entrada ───────────────────────────────────────────────

def run(ticks: int = 60, seed: int = 123, realtime: bool = False):
    sim = Interseccion(seed)
    for _ in range(ticks):
        print(sim.status())
        sim.step()
        if realtime:
            time.sleep(DURACION_TICK)


if __name__ == '__main__':
    ticks = 60
    if len(sys.argv) > 1:
        try:
            ticks = int(sys.argv[1])
        except ValueError:
            pass
    run(ticks=ticks)
