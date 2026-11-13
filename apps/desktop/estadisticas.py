"""Elo de los jugadores de una partida, desde la API pública del juego.

ProveedorEstadisticas es lo que necesita el resto de la app; ApiOficial lo cumple con
el backend de Relic/World's Edge (aoe-api.worldsedgelink.com, sin cuenta ni clave):
una sola petición trae a todos los jugadores de la partida. Si un día hace falta otra
fuente, basta otro proveedor con el mismo método.

Estadisticas pone delante una caché de 10 minutos por jugador y espera cada vez más
(30 s, 1 min, 2 min... hasta 10 min) tras un 429 o un error del servidor, para no
insistir. La respuesta se valida campo a campo: si no es lo esperado, EstadisticasError.
"""

import json
import re
import time
import urllib.error
import urllib.parse
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

import catalogo as K

URL_ESTADISTICAS = "https://aoe-api.worldsedgelink.com/community/leaderboard/getPersonalStat"
MAX_RESPUESTA = 1024 * 1024
CADUCIDAD = 600.0  # segundos que vale lo guardado de cada jugador
ESPERA_MINIMA, ESPERA_MAXIMA = 30.0, 600.0

# Leaderboards de la API oficial. 3 y 4 (RM) y 14 (EW por equipos) comprobados con la
# respuesta real (pruebas/datos); 13 (EW 1v1) y 1 y 2 (DM), según la documentación conocida.
LEADERBOARDS = {"rm_1v1": 3, "rm_team": 4, "ew_1v1": 13, "ew_team": 14, "dm_1v1": 1, "dm_team": 2}
RE_PAIS = re.compile(r"[a-z]{2}")


class EstadisticasError(Exception):
    def __init__(self, mensaje: str, reintentable: bool = False):
        super().__init__(mensaje)
        self.reintentable = reintentable  # 429 o error del servidor: probar más tarde


@dataclass(frozen=True)
class Rating:
    rating: int
    rango: int | None       # None si la API da -1 (sin puesto activo)
    maximo: int | None      # None si la API da 0 (no lo sabe)
    victorias: int
    derrotas: int


@dataclass(frozen=True)
class Ficha:
    perfil: int
    alias: str
    pais: str | None
    ratings: dict[int, Rating] = field(default_factory=dict)  # por ID de leaderboard


class ProveedorEstadisticas(Protocol):
    def fichas(self, perfiles: Sequence[int]) -> dict[int, Ficha]:
        """Ficha de cada perfil que la fuente conozca. EstadisticasError si falla."""
        ...


# --- Validación de la respuesta --------------------------------------------------------


def _entero(d: dict[str, object], clave: str) -> int:
    v = d.get(clave)
    if not isinstance(v, int) or isinstance(v, bool):
        raise EstadisticasError(f"respuesta inesperada: {clave} no es un número")
    return v


def _texto(d: dict[str, object], clave: str) -> str:
    v = d.get(clave)
    if not isinstance(v, str):
        raise EstadisticasError(f"respuesta inesperada: {clave} no es texto")
    return v


def _dicts(d: dict[str, object], clave: str) -> list[dict[str, object]]:
    v = d.get(clave)
    if not isinstance(v, list) or not all(isinstance(x, dict) for x in v):
        raise EstadisticasError(f"respuesta inesperada: {clave} no es una lista")
    return v


def leer_fichas(respuesta: object) -> dict[int, Ficha]:
    """Fichas de una respuesta de getPersonalStat (ya pasada por json.loads)."""
    if not isinstance(respuesta, dict):
        raise EstadisticasError("respuesta inesperada: no es un objeto")
    resultado = respuesta.get("result")
    if not isinstance(resultado, dict) or resultado.get("code") != 0:
        mensaje = resultado.get("message") if isinstance(resultado, dict) else None
        raise EstadisticasError(f"la API respondió con un error: {mensaje or resultado!r}")
    fichas: dict[int, Ficha] = {}
    grupo_de: dict[int, int] = {}  # statgroup -> perfil (solo los grupos de un jugador)
    for g in _dicts(respuesta, "statGroups"):
        miembros = _dicts(g, "members")
        if len(miembros) != 1:
            continue  # grupos de equipos prefabricados: no son de un jugador
        m = miembros[0]
        perfil = _entero(m, "profile_id")
        pais = m.get("country")
        fichas[perfil] = Ficha(perfil, _texto(m, "alias"),
                               pais if isinstance(pais, str) and RE_PAIS.fullmatch(pais) else None, {})
        grupo_de[_entero(g, "id")] = perfil
    for s in _dicts(respuesta, "leaderboardStats"):
        perfil = grupo_de.get(_entero(s, "statgroup_id"))
        if perfil is None:
            continue
        rango, maximo = _entero(s, "rank"), _entero(s, "highestrating")
        fichas[perfil].ratings[_entero(s, "leaderboard_id")] = Rating(
            _entero(s, "rating"), rango if rango > 0 else None, maximo if maximo > 0 else None,
            _entero(s, "wins"), _entero(s, "losses"))
    return fichas


# --- La API oficial ----------------------------------------------------------------------


def _pedir_url(url: str) -> bytes:
    """GET con el User-Agent de la app (el mismo que usa el catálogo)."""
    try:
        with K._pedir(url, "application/json") as r:
            datos = r.read(MAX_RESPUESTA + 1)
    except urllib.error.HTTPError as e:
        raise EstadisticasError(f"la API respondió {e.code}", reintentable=e.code == 429 or e.code >= 500) from None
    except OSError as e:
        raise EstadisticasError(f"sin conexión con la API: {getattr(e, 'reason', None) or e}",
                                reintentable=True) from None
    if len(datos) > MAX_RESPUESTA:
        raise EstadisticasError("la respuesta de la API es demasiado grande")
    return datos


class ApiOficial:
    def __init__(self, pedir: Callable[[str], bytes] = _pedir_url):
        self.pedir = pedir  # las pruebas lo cambian por uno que lee los fixtures

    @staticmethod
    def url(perfiles: Sequence[int]) -> str:
        ids = json.dumps([int(p) for p in perfiles], separators=(",", ":"))
        return f"{URL_ESTADISTICAS}?{urllib.parse.urlencode({'title': 'age2', 'profile_ids': ids})}"

    def fichas(self, perfiles: Sequence[int]) -> dict[int, Ficha]:
        if not perfiles:
            return {}
        try:
            respuesta = json.loads(self.pedir(self.url(perfiles)))
        except ValueError:
            raise EstadisticasError("la API devolvió algo que no es JSON") from None
        return leer_fichas(respuesta)


# --- Caché y esperas -----------------------------------------------------------------------


class Estadisticas:
    """Fichas con caché por jugador y espera creciente ante errores pasajeros."""

    def __init__(self, proveedor: ProveedorEstadisticas, ahora: Callable[[], float] = time.monotonic):
        self.proveedor = proveedor
        self.ahora = ahora
        self._cache: dict[int, tuple[float, Ficha | None]] = {}  # None = la fuente no lo conoce
        self._espera = 0.0
        self.no_antes_de = 0.0  # tras un error pasajero, no se pide nada antes de esta hora

    def fichas(self, perfiles: Sequence[int]) -> dict[int, Ficha]:
        ahora = self.ahora()
        faltan = [p for p in dict.fromkeys(perfiles) if p > 0
                  and (p not in self._cache or ahora - self._cache[p][0] > CADUCIDAD)]
        if faltan:
            if ahora < self.no_antes_de:
                raise EstadisticasError("esperando antes de volver a pedir", reintentable=True)
            try:
                nuevas = self.proveedor.fichas(faltan)
            except EstadisticasError as e:
                if e.reintentable:
                    self._espera = min(ESPERA_MAXIMA, max(ESPERA_MINIMA, self._espera * 2))
                    self.no_antes_de = ahora + self._espera
                raise
            self._espera = 0.0
            for p in faltan:
                self._cache[p] = (ahora, nuevas.get(p))
        return {p: f for p in perfiles if p in self._cache and (f := self._cache[p][1]) is not None}
