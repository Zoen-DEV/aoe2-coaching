"""Vigilante de partidas: se entera de cuándo empieza y acaba una partida clasificatoria.

El juego crea la repetición de cada partida en savegame al empezarla y la va escribiendo
mientras se juega. El vigilante mira esa carpeta (actualizar(), cada pocos segundos,
desde el overlay): una repetición multijugador reciente cuya cabecera dice
«clasificatoria» es una partida en curso. Acaba cuando la repetición deja de crecer
o aparece otra.

Al empezar, la partida se ve enseguida con los nombres (estado BUSCANDO) y el elo se
pide en segundo plano, una sola vez: es una foto del inicio y no cambia mientras se
juega. Los avisos (al_empezar, al_terminar) llegan siempre desde actualizar(), en el
hilo de la interfaz.
"""

import logging
import threading
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path

import cabecera as CB
from estadisticas import Estadisticas, EstadisticasError
from partida_en_curso import Partida, armar

log = logging.getLogger("aoe2c")

SIN_ESCRITURA = 45.0   # segundos sin crecer la repetición para dar la partida por acabada
REPETICIONES_PERFIL = 10  # las últimas repeticiones multijugador que mira perfil_propio()

OCULTO, BUSCANDO, CARGADO, ERROR = "oculto", "buscando", "cargado", "error"


def repeticiones(carpeta: Path | None) -> list[Path]:
    """Repeticiones de la carpeta, de la más reciente a la más vieja."""
    if not carpeta:
        return []
    try:
        archivos = [(p.stat().st_mtime, p) for p in Path(carpeta).glob("*.aoe2record")]
    except OSError:
        return []
    return [p for _, p in sorted(archivos, key=lambda x: x[0], reverse=True)]


def perfil_propio(carpeta: Path | None) -> int | None:
    """El ID de perfil del jugador: el que está en todas sus repeticiones multijugador
    recientes (hacen falta al menos dos, con rivales distintos)."""
    vistos: Counter[int] = Counter()
    leidas = 0
    for ruta in repeticiones(carpeta):
        if leidas >= REPETICIONES_PERFIL:
            break
        try:
            cab = CB.leer_archivo(ruta)
        except CB.CabeceraError:
            continue
        if not cab.multijugador:
            continue
        leidas += 1
        vistos.update({j.perfil for j in cab.jugadores if j.perfil > 0})
    comunes = [p for p, n in vistos.items() if n == leidas]
    return comunes[0] if leidas >= 2 and len(comunes) == 1 else None


def en_hilo(funcion: Callable[[], None]) -> None:
    threading.Thread(target=funcion, daemon=True).start()


class Vigilante:
    def __init__(self, carpeta: Callable[[], Path | None], estadisticas: Estadisticas,
                 perfil: Callable[[], int | None], ahora: Callable[[], float] = time.time,
                 en_segundo_plano: Callable[[Callable[[], None]], None] = en_hilo):
        self.carpeta = carpeta              # savegame del perfil en uso
        self.estadisticas = estadisticas
        self.perfil = perfil                # ID de perfil propio (o None si no se sabe)
        self.ahora = ahora                  # reloj de pared: se compara con la fecha de los archivos
        self.en_segundo_plano = en_segundo_plano
        self.al_empezar: Callable[[Partida], None] | None = None
        self.al_terminar: Callable[[], None] | None = None
        self.partida: Partida | None = None
        self.en_curso = False               # hay una partida en curso, de cualquier tipo (no solo clasificatoria)
        self.estado = OCULTO
        self.error = ""
        self._ruta: Path | None = None
        self._cabecera: CB.Cabecera | None = None
        self._ignoradas: set[str] = set()   # repeticiones ya vistas que no son clasificatorias
        self._lock = threading.Lock()
        self._resultado: tuple[str, object] | None = None  # (id de la partida, fichas o error)
        self._pidiendo = False
        self._reintento = 0.0

    # Lo llama el overlay cada pocos segundos.
    def actualizar(self) -> None:
        self._recoger_resultado()
        lista = repeticiones(self.carpeta())
        ultima = lista[0] if lista else None
        self.en_curso = ultima is not None and self._reciente(ultima)
        if self._ruta is not None:
            if ultima is None or ultima != self._ruta or not self._reciente(ultima):
                self._terminar()
            else:
                self._pedir_si_toca()
                return
        if ultima is None or ultima.name in self._ignoradas or not self._reciente(ultima):
            return
        try:
            cab = CB.leer_archivo(ultima)
        except CB.CabeceraError as e:
            if "aún no" not in str(e):  # si el juego aún la está escribiendo, se prueba luego
                log.info("repetición %s: %s", ultima.name, e)
                self._ignoradas.add(ultima.name)
            return
        if not (cab.multijugador and cab.clasificatoria):
            self._ignoradas.add(ultima.name)
            return
        self._empezar(ultima, cab)

    @property
    def ruta(self) -> Path | None:
        """La repetición de la partida clasificatoria en curso."""
        return self._ruta

    @property
    def cabecera(self) -> CB.Cabecera | None:
        return self._cabecera

    def _reciente(self, ruta: Path) -> bool:
        try:
            return self.ahora() - ruta.stat().st_mtime < SIN_ESCRITURA
        except OSError:
            return False

    def _empezar(self, ruta: Path, cab: CB.Cabecera) -> None:
        self._ruta, self._cabecera = ruta, cab
        self.partida = armar(cab, ruta.name, self.perfil())
        self.estado, self.error, self._reintento = BUSCANDO, "", 0.0
        log.info("partida clasificatoria: %s (%s, %s jugadores)", ruta.name, self.partida.leaderboard,
                 len(cab.jugadores))
        if self.al_empezar:
            self.al_empezar(self.partida)
        self._pedir_si_toca()

    def _terminar(self) -> None:
        if self._ruta is not None:
            self._ignoradas.add(self._ruta.name)  # la misma repetición no vuelve a empezar
        self._ruta = self._cabecera = self.partida = None
        self.estado, self.error = OCULTO, ""
        if self.al_terminar:
            self.al_terminar()

    def _pedir_si_toca(self) -> None:
        if self.estado == CARGADO or self._pidiendo or self._cabecera is None:
            return
        if self.estado == ERROR and self.ahora() < self._reintento:
            return
        id_ = self._ruta.name if self._ruta else ""
        perfiles = [j.perfil for j in self._cabecera.jugadores]
        self._pidiendo = True

        def trabajo():
            try:
                resultado: object = self.estadisticas.fichas(perfiles)
            except EstadisticasError as e:
                resultado = e
            with self._lock:
                self._resultado = (id_, resultado)

        self.en_segundo_plano(trabajo)
        self._recoger_resultado()  # si se hizo en este hilo (las pruebas), ya está

    def _recoger_resultado(self) -> None:
        with self._lock:
            hecho, self._resultado = self._resultado, None
        if hecho is None:
            return
        self._pidiendo = False
        id_, resultado = hecho
        if self._ruta is None or id_ != self._ruta.name or self._cabecera is None:
            return  # de una partida que ya acabó
        if isinstance(resultado, EstadisticasError):
            self.estado, self.error = ERROR, str(resultado)
            espera = 120.0  # un error que no es pasajero (respuesta rara): se reintenta poco
            if resultado.reintentable:
                espera = max(5.0, self.estadisticas.no_antes_de - self.estadisticas.ahora())
            self._reintento = self.ahora() + espera
            log.warning("estadísticas de la partida: %s", resultado)
        elif isinstance(resultado, dict):
            self.partida = armar(self._cabecera, id_, self.perfil(), resultado)
            self.estado = CARGADO


# --- Partida simulada (aoe2c.py --demo-match y pruebas) ---------------------------------


class ProveedorDeEjemplo:
    """Las fichas de una partida de ejemplo (partida_en_curso.partida_de_ejemplo), sin red.
    retraso: segundos que tarda en «responder», para ver el estado «buscando datos»."""

    def __init__(self, partida: Partida, retraso: float = 0.0):
        from estadisticas import LEADERBOARDS, Ficha, Rating
        self.retraso = retraso
        lb = LEADERBOARDS.get(partida.leaderboard or "")
        self._fichas = {}
        for j in partida.jugadores:
            ratings = {}
            if lb is not None and j.rating is not None:
                ratings[lb] = Rating(j.rating, j.rango, j.maximo, j.victorias or 0, j.derrotas or 0)
            self._fichas[j.perfil] = Ficha(j.perfil, j.nombre, j.pais, ratings)

    def fichas(self, perfiles):
        if self.retraso:
            time.sleep(self.retraso)
        return {p: self._fichas[p] for p in perfiles if p in self._fichas}


def simular(carpeta: Path, tipo: str = "1v1") -> tuple[Path, ProveedorDeEjemplo, int]:
    """Escribe en carpeta la repetición de una partida clasificatoria de ejemplo. Devuelve
    (repetición, proveedor con su elo, perfil propio). Para que siga «en curso», hay que
    ir escribiendo en ella o actualizando su fecha (como hace el juego al escribir)."""
    from partida_en_curso import partida_de_ejemplo
    partida = partida_de_ejemplo(tipo)
    jugadores, n = [], 0
    for e in partida.equipos:
        for j in e.jugadores:
            n += 1
            jugadores.append(CB.JugadorCabecera(n, j.nombre, j.perfil, e.id, j.color, j.civ))
    from reloj_vivo import EscritorPrueba
    # Con el principio del cuerpo, como la de una partida que empieza: el reloj en vivo
    # (reloj_vivo.py) la sigue si se le van añadiendo sincronizaciones.
    ruta = EscritorPrueba(Path(carpeta) / f"MP Replay simulada {tipo} @{time.strftime('%H%M%S')}.aoe2record",
                          jugadores, mapa=partida.mapa).ruta
    yo = partida.yo
    return ruta, ProveedorDeEjemplo(partida, retraso=2.0), yo.perfil if yo else 0
