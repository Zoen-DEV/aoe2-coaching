"""Partida en curso: quién juega y con qué elo. Es lo que dibuja el panel Match Info.

El modelo no depende de dónde salen los datos: los jugadores, de la cabecera de la
repetición (cabecera.py), y el elo, de un proveedor de estadísticas (estadisticas.py).
"""

from dataclasses import dataclass, field

import cabecera as CB
from estadisticas import LEADERBOARDS, Ficha

MODOS_CORTOS = {"rm": "RM", "ew": "EW", "dm": "DM"}


@dataclass(frozen=True)
class Jugador:
    perfil: int
    nombre: str
    civ: int
    color: int          # 0 a 7, ver cabecera.JugadorCabecera
    soy_yo: bool
    pais: str | None = None      # código de dos letras ("ca"), para la bandera
    rating: int | None = None    # None = sin rating en este leaderboard
    rango: int | None = None     # puesto en el leaderboard (None = sin puesto activo)
    maximo: int | None = None
    victorias: int | None = None
    derrotas: int | None = None

    @property
    def winrate(self) -> float | None:
        if self.victorias is None or self.derrotas is None or self.victorias + self.derrotas == 0:
            return None
        return self.victorias / (self.victorias + self.derrotas)


@dataclass(frozen=True)
class Equipo:
    id: int
    jugadores: tuple[Jugador, ...]

    @property
    def promedio(self) -> int | None:
        """Elo medio de los que tienen rating (None si ninguno)."""
        ratings = [j.rating for j in self.jugadores if j.rating is not None]
        return round(sum(ratings) / len(ratings)) if ratings else None


@dataclass(frozen=True)
class Partida:
    id: str                       # nombre de la repetición (una por partida)
    modo: str | None              # rm, ew o dm
    leaderboard: str | None       # rm_1v1, rm_team...: de donde sale el elo
    mapa: str
    clasificatoria: bool
    equipos: tuple[Equipo, ...] = field(default_factory=tuple)

    @property
    def jugadores(self) -> list[Jugador]:
        return [j for e in self.equipos for j in e.jugadores]

    @property
    def yo(self) -> Jugador | None:
        return next((j for j in self.jugadores if j.soy_yo), None)

    @property
    def es_1v1(self) -> bool:
        return len(self.equipos) == 2 and all(len(e.jugadores) == 1 for e in self.equipos)

    @property
    def formato(self) -> str:
        """1v1, 2v2, 4v4, 2v2v2v2..."""
        return "v".join(str(len(e.jugadores)) for e in self.equipos)

    @property
    def titulo(self) -> str:
        """«RM 1v1» (el mapa lo añade el panel, con su texto)."""
        corto = MODOS_CORTOS.get(self.modo or "")
        return f"{corto} {self.formato}" if corto else self.formato

    @property
    def rival(self) -> Jugador | None:
        """En 1v1, el otro jugador."""
        if not self.es_1v1 or self.yo is None:
            return None
        return next(j for j in self.jugadores if not j.soy_yo)

    @property
    def diferencia(self) -> int | None:
        """En 1v1, el elo del rival menos el propio (+24: el rival tiene más)."""
        yo, rival = self.yo, self.rival
        if yo is None or rival is None or yo.rating is None or rival.rating is None:
            return None
        return rival.rating - yo.rating


def leaderboard_de(cab: CB.Cabecera) -> str | None:
    """El leaderboard que corresponde al modo de la partida: rm_1v1 solo si son dos
    jugadores en dos equipos; si no, el de equipos."""
    if cab.modo is None:
        return None
    equipos = _agrupar(cab.jugadores)
    uno_contra_uno = len(equipos) == 2 and all(len(js) == 1 for js in equipos.values())
    return f"{cab.modo}_{'1v1' if uno_contra_uno else 'team'}"


def _agrupar(jugadores: list[CB.JugadorCabecera]) -> dict[int, list[CB.JugadorCabecera]]:
    """Equipos en orden de número de equipo. Sin equipo ("-"), cada jugador va solo."""
    equipos: dict[int, list[CB.JugadorCabecera]] = {}
    for j in jugadores:
        clave = 100 + j.numero if j.equipo == CB.SIN_EQUIPO else j.equipo
        equipos.setdefault(clave, []).append(j)
    return dict(sorted(equipos.items()))


def armar(cab: CB.Cabecera, id_: str, perfil_propio: int | None,
          fichas: dict[int, Ficha] | None = None) -> Partida:
    """La partida con lo que haya: sin fichas (aún buscando datos), todos sin rating."""
    lb = leaderboard_de(cab)
    lb_id = LEADERBOARDS.get(lb or "")
    equipos = []
    for clave, js in _agrupar(cab.jugadores).items():
        jugadores = []
        for j in js:
            ficha = (fichas or {}).get(j.perfil)
            r = ficha.ratings.get(lb_id) if ficha and lb_id is not None else None
            jugadores.append(Jugador(
                perfil=j.perfil, nombre=j.nombre, civ=j.civ, color=j.color,
                soy_yo=perfil_propio is not None and j.perfil == perfil_propio,
                pais=ficha.pais if ficha else None,
                rating=r.rating if r else None, rango=r.rango if r else None, maximo=r.maximo if r else None,
                victorias=r.victorias if r else None, derrotas=r.derrotas if r else None))
        equipos.append(Equipo(clave, tuple(jugadores)))
    return Partida(id_, cab.modo, lb, cab.mapa, cab.clasificatoria, tuple(equipos))


def partida_de_ejemplo(tipo: str = "1v1", mapa: str = "Arabia", cargada: bool = True) -> Partida:
    """Partida inventada para el modo simulado y las capturas: "1v1", "equipos" (4v4) o
    "sin_rating" (1v1 contra alguien que aún no tiene elo). cargada=False: sin elo aún."""
    J = Jugador
    if tipo == "equipos":
        e1 = (J(1, "Tú", 8, 0, True, "ar", 1312, 9120, 1360, 412, 371),
              J(2, "Ferrum", 24, 2, False, "es", 1405, 6233, 1471, 820, 760),
              J(3, "Kalimba", 14, 3, False, "br", 1188, 12904, 1240, 155, 160),
              J(4, "Nadir_88", 36, 4, False, None, None))
        e2 = (J(5, "Rook", 1, 1, False, "de", 1350, 8512, 1402, 640, 598),
              J(6, "Tsubame", 19, 5, False, "jp", 1290, 9875, 1333, 300, 290),
              J(7, "VelhoLobo", 32, 6, False, "pt", 1462, 5190, 1510, 1210, 1102),
              J(8, "Marlowe", 2, 7, False, "gb", 1241, 11540, 1301, 88, 92))
        equipos = (Equipo(2, e1), Equipo(3, e2))
        lb = "rm_team"
    else:
        rival = J(2, "Rook", 1, 1, False, "de", 1196, 14102, 1255, 233, 219) if tipo == "1v1" \
            else J(2, "recién_llegado", 1, 1, False, "mx")
        equipos = (Equipo(2, (J(1, "Tú", 8, 0, True, "ar", 1220, 12688, 1301, 180, 171),)), Equipo(3, (rival,)))
        lb = "rm_1v1"
    if not cargada:
        equipos = tuple(Equipo(e.id, tuple(Jugador(j.perfil, j.nombre, j.civ, j.color, j.soy_yo) for j in e.jugadores))
                        for e in equipos)
    return Partida(f"ejemplo-{tipo}", "rm", lb, mapa, True, equipos)
