"""Guía de ritmo en las partidas clasificatorias: une el vigilante (qué partida es y con qué
civilización), el reloj en vivo de su repetición (reloj_vivo.py) y los objetivos de cada
paso (objetivos.py). El overlay la consulta cada fotograma con estado().

No marca pasos como hechos: dice qué paso toca a esta hora y, si se sabe, cómo va el
jugador en los clics de edad (lo único de la partida en curso que se mira de él).
"""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import historial as H
import objetivos as O
from lector import adaptar_a_civ
from reloj_vivo import RelojVivo

log = logging.getLogger("aoe2c")

FIN_GUIA = 20.0  # segundos de juego que la guía sigue a la vista tras el último objetivo
HITOS = ((2, "feudal"), (3, "castillos"))  # edad del clic -> nombre de la edad en historial.py


@dataclass
class EstadoRitmo:
    guia: dict                    # adaptada a la civilización del jugador
    objetivos: list[O.Objetivo]
    tiempo: float                 # segundos de juego (extrapolado)
    paso: int                     # el que toca (len(objetivos) = ya pasaron todos)
    diferencia: int | None = None  # segundos respecto al objetivo del último clic de edad (+ = tarde)
    clics: dict[int, float] = field(default_factory=dict)


def en_hilo(funcion: Callable[[], None]) -> None:
    threading.Thread(target=funcion, daemon=True).start()


class GuiaRitmo:
    def __init__(self, historial: H.Historial | None, guias: dict, config: dict,
                 clics_ranked: Callable[[int | None], list[float]] = lambda _yo: [],
                 en_segundo_plano: Callable[[Callable[[], None]], None] = en_hilo,
                 ahora: Callable[[], float] = time.monotonic):
        self.historial = historial
        self.guias = guias                  # id -> manifiesto (las instaladas; el overlay lo cambia si cambian)
        self.config = config
        self.clics_ranked = clics_ranked    # clics en Feudal del jugador en sus ranked terminadas
        self.en_segundo_plano = en_segundo_plano
        self.ahora = ahora
        self.reloj: RelojVivo | None = None
        self.civ = 0
        self._ruta: Path | None = None
        self._clics: list[float] = []
        self._cache: tuple | None = None    # (clave, objetivos)

    @property
    def activa(self) -> bool:
        return self.reloj is not None

    def guia_elegida(self) -> dict | None:
        guias = self.guias or {}
        id_ = self.config.get("ritmo_guia") or self.config.get("guia_activa")
        return guias.get(id_) if id_ else None

    # Lo llama el overlay cada segundo con lo que sabe el vigilante.
    def seguir(self, ruta: Path | None, cabecera, perfil: int | None) -> None:
        """Empieza con una partida nueva, sigue la que hay o termina (ruta None)."""
        if ruta is None or cabecera is None:
            if self.reloj is not None:
                log.info("guía de ritmo: fin (%s s de juego leídos)", round(self.reloj.leido))
            self.reloj, self._ruta, self._cache = None, None, None
            return
        if ruta != self._ruta:
            yo = next((j for j in cabecera.jugadores if perfil and j.perfil == perfil), None)
            self._ruta, self.civ, self._clics, self._cache = ruta, yo.civ if yo else 0, [], None
            # Sin saber quién es uno, no se mira ningún comando: solo el reloj.
            self.reloj = RelojVivo(ruta, jugador=yo.numero if yo else None,
                                   velocidad=getattr(cabecera, "velocidad", 0.0), ahora=self.ahora)
            log.info("guía de ritmo: %s (civ %s, jugador %s)", ruta.name, self.civ, yo.numero if yo else "?")

            def trabajo(r=ruta):
                try:
                    clics = self.clics_ranked(perfil)
                except Exception:  # noqa: BLE001 — sin el ajuste a ranked la guía sigue
                    log.exception("clics en Feudal de las clasificatorias")
                    clics = []
                if self._ruta == r:
                    self._clics = clics
            self.en_segundo_plano(trabajo)
        self.reloj.actualizar()

    def objetivos(self, guia: dict, elo: int | None) -> list[O.Objetivo]:
        registros = self.historial.registros if self.historial else []
        clave = (guia.get("id"), guia.get("version_guia"), self.civ, elo, tuple(self._clics), len(registros),
                 registros[-1]["id"] if registros else None)
        if self._cache is None or self._cache[0] != clave:
            self._cache = (clave, O.calcular(guia, registros, self.civ, elo, self._clics))
        return self._cache[1]

    def estado(self, elo: int | None = None) -> EstadoRitmo | None:
        """Lo que hay que dibujar ahora, o None (sin partida, sin guía o ya pasada)."""
        guia = self.guia_elegida()
        if self.reloj is None or guia is None or self.reloj.segundos_sin_datos() is None:
            return None  # aún no ha llegado ninguna sincronización
        objetivos = self.objetivos(guia, elo)
        if not objetivos:
            return None
        tiempo = self.reloj.tiempo()
        if tiempo > objetivos[-1].segundos + FIN_GUIA:
            return None
        adaptada = adaptar_a_civ(guia, self.civ) if self.civ else guia
        e = EstadoRitmo(adaptada, objetivos, tiempo, O.paso_actual(objetivos, tiempo), clics=dict(self.reloj.edades))
        e.diferencia = diferencia_hitos(adaptada, objetivos, e.clics, tiempo, self.reloj.jugador is not None)
        return e


def diferencia_hitos(guia: dict, objetivos: list[O.Objetivo], clics: dict[int, float], tiempo: float,
                     se_mira: bool) -> int | None:
    """Cómo va el jugador en el último clic de edad que ya toca: + segundos tarde, − antes.
    Si el objetivo de un clic ya pasó y aún no lo hizo, lo que lleva de retraso."""
    if not se_mira:
        return None
    diferencia = None
    for edad, nombre in HITOS:
        i = H.paso_del_hito(guia, nombre, 1)
        if i is None or i >= len(objetivos):
            continue
        objetivo = objetivos[i].segundos
        if edad in clics:
            diferencia = round(clics[edad] - objetivo)
        elif tiempo > objetivo:
            diferencia = round(tiempo - objetivo)
            break  # sin este clic, los siguientes aún no cuentan
        else:
            break
    return diferencia
