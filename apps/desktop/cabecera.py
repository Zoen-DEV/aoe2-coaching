"""Cabecera de una repetición (.aoe2record) de AoE2 DE: quién juega la partida.

El juego crea la repetición al empezar la partida, en la carpeta savegame del perfil,
y la cabecera (comprimida con zlib al principio del archivo) ya trae la sala: el mapa,
el tipo de partida, si es clasificatoria y, por jugador, su nombre, su ID de perfil
(el mismo que usa la API del juego), su equipo, su color y su civilización.

Solo se lee el archivo; nada del juego se toca. El formato no es público: sigue al de
mgz (github.com/happyleavesaoc/aoc-mgz, licencia MIT), comprobado con repeticiones de
la versión 101.103 del juego (versión de guardado 68.9), que añade una cadena al final
de cada jugador. Si algo no cuadra, CabeceraError, y el panel no muestra la partida.
"""

import re
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path

SEPARADOR = b"\x60\x0a"  # delante de cada cadena de la cabecera
MAX_CABECERA = 64 * 1024 * 1024
HUMANO = 2  # tipo de jugador (1 = IA... 2 = persona; 4 = persona en algunas versiones)
TIPOS_PERSONA = (2, 4)
SIN_EQUIPO = 1  # equipo "-": cada uno va solo
VERSION_MINIMA = 61.5  # versiones de guardado más viejas (2021) no se leen

# Tipo de partida (game_type de la sala) -> modo del leaderboard.
MODOS = {0: "rm", 2: "dm", 13: "ew"}

# "Ubicación: Arabia" / "Location: Arabia" en el resumen de la sala (en el idioma del juego).
RE_UBICACION = re.compile(rb"(?:Ubicaci\xc3\xb3n|Location): ([^\x00-\x1f]+)")


class CabeceraError(Exception):
    pass


@dataclass(frozen=True)
class JugadorCabecera:
    numero: int        # número de jugador en la partida (1 a 8)
    nombre: str
    perfil: int        # ID de perfil (0 si no tiene, por ejemplo una IA)
    equipo: int        # 1 = sin equipo; 2 a 5 = equipos 1 a 4
    color: int         # 0 a 7 (azul, rojo, verde, amarillo, cian, morado, gris, naranja)
    civ: int           # ID de civilización (el de tecnologias.json)


@dataclass
class Cabecera:
    version: float                 # versión de guardado (68.9)
    tipo: int                      # tipo de partida (0 = mapa aleatorio)
    mapa_id: int                   # ID del mapa (9 = Arabia)
    mapa: str                      # nombre del mapa en el idioma del juego ("" si no se encuentra)
    multijugador: bool
    clasificatoria: bool
    jugadores: list[JugadorCabecera] = field(default_factory=list)

    @property
    def modo(self) -> str | None:
        """rm, ew o dm (mapa aleatorio, guerras imperiales, a muerte); None si no tiene ranked."""
        return MODOS.get(self.tipo)


class _Lector:
    def __init__(self, datos: bytes):
        self.d = datos
        self.i = 0

    def leer(self, formato: str):
        try:
            valores = struct.unpack_from("<" + formato, self.d, self.i)
        except struct.error:
            raise CabeceraError("la cabecera se corta antes de tiempo") from None
        self.i += struct.calcsize("<" + formato)
        return valores[0] if len(valores) == 1 else valores

    def saltar(self, n: int):
        self.i += n
        if self.i > len(self.d):
            raise CabeceraError("la cabecera se corta antes de tiempo")

    def cadena(self) -> str:
        if self.d[self.i:self.i + 2] != SEPARADOR:
            raise CabeceraError(f"se esperaba una cadena en la posición {self.i}")
        self.i += 2
        n = self.leer("H")
        texto = self.d[self.i:self.i + n]
        if len(texto) != n:
            raise CabeceraError("la cabecera se corta antes de tiempo")
        self.i += n
        return texto.decode("utf-8", "replace")

    def hay_cadena(self) -> bool:
        return self.d[self.i:self.i + 2] == SEPARADOR


def descomprimir(datos: bytes) -> bytes:
    """La cabecera sin comprimir. CabeceraError si el archivo aún no la tiene entera."""
    if len(datos) < 8:
        raise CabeceraError("archivo demasiado corto")
    tam = struct.unpack_from("<I", datos)[0]
    if not 8 < tam <= min(len(datos), MAX_CABECERA):
        raise CabeceraError("la cabecera aún no está escrita entera")
    try:
        return zlib.decompress(datos[8:tam], -15)
    except zlib.error as e:
        raise CabeceraError(f"cabecera dañada: {e}") from None


def leer(datos: bytes) -> Cabecera:
    """Lee la cabecera de los bytes de una repetición (basta con el principio del archivo)."""
    r = _Lector(descomprimir(datos))
    juego = r.leer("8s")
    if not juego.startswith(b"VER 9."):
        raise CabeceraError(f"no es una repetición de AoE2 DE ({juego!r})")
    version = r.leer("f")
    if version == -1:
        version = r.leer("I") / (1 << 16)
    version = round(version, 2)
    if version < VERSION_MINIMA:
        raise CabeceraError(f"versión de repetición no soportada: {version}")

    r.saltar(4 + 4 + 12)                         # build, hora, versiones de opciones
    r.saltar(4 * r.leer("I"))                    # DLC
    r.saltar(4 + 4 + 4)                          # dataset, tamaño del mapa, mapa elegido
    mapa_id = r.leer("I")                        # mapa resuelto (el aleatorio, si se eligió así)
    r.saltar(4 + 4 + 4 + 4 + 4)                  # revelar mapa, victoria, recursos, edad inicial y final
    tipo = r.leer("I")
    r.saltar(8 + 4 + 4 + 4)                      # separadores, velocidad, tratado, población
    num = r.leer("I")
    if not 1 <= num <= 8:
        raise CabeceraError(f"número de jugadores imposible: {num}")
    r.saltar(14 + 1 + 2 + 1 + 2)                 # ..., dificultad, posiciones, tecnologías, bloqueos
    multijugador = r.leer("b") == 1
    r.saltar(7 + 12 + 1 + 1)                     # trucos... posiciones de equipo, y relleno

    jugadores = []
    for _ in range(8):
        r.saltar(4)                              # DLC
        color = r.leer("i")
        r.saltar(2)                              # color y equipo elegidos en la sala
        equipo = r.leer("b")                     # equipo resuelto
        r.saltar(9)                              # CRC de los datos y versión
        civ = r.leer("I")
        r.saltar(4 * r.leer("I"))                # selección de civilizaciones propia
        r.cadena()                               # tipo de IA
        r.saltar(1)
        r.cadena()                               # nombre de la IA
        r.cadena()                               # nombre censurado
        nombre = r.cadena()
        tipo_jugador = r.leer("I")
        perfil = r.leer("I")
        r.saltar(4)
        numero = r.leer("i")
        r.saltar(1 + 1 + 8 + 4)                  # civ aleatoria preferida, ..., hándicap
        if r.hay_cadena():
            r.cadena()                           # versión 68.9: una cadena más (vacía)
        if tipo_jugador in TIPOS_PERSONA:
            if not 1 <= numero <= 8 or not 0 <= color <= 7:
                raise CabeceraError(f"jugador imposible: número {numero}, color {color}")
            jugadores.append(JugadorCabecera(numero, nombre, perfil, equipo, color, civ))
    r.saltar(12 + 4)
    clasificatoria = r.leer("b") == 1

    if not jugadores:
        raise CabeceraError("la repetición no tiene jugadores")
    m = RE_UBICACION.search(r.d)
    mapa = m.group(1).decode("utf-8", "replace").strip() if m else ""
    return Cabecera(version, tipo, mapa_id, mapa, multijugador, clasificatoria,
                    sorted(jugadores, key=lambda j: j.numero))


def leer_archivo(ruta: Path) -> Cabecera:
    """Lee la cabecera de una repetición, aunque el juego la siga escribiendo."""
    try:
        with open(ruta, "rb") as f:
            inicio = f.read(8)
            if len(inicio) < 8:
                raise CabeceraError("archivo demasiado corto")
            tam = struct.unpack_from("<I", inicio)[0]
            if not 8 < tam <= MAX_CABECERA:
                raise CabeceraError("la cabecera aún no está escrita entera")
            return leer(inicio + f.read(tam - 8))
    except OSError as e:
        raise CabeceraError(f"no se pudo leer {Path(ruta).name}: {e}") from None


def _cadena(texto: str) -> bytes:
    b = texto.encode("utf-8")
    return SEPARADOR + struct.pack("<H", len(b)) + b


def escribir_prueba(ruta: Path, jugadores: list[JugadorCabecera], clasificatoria: bool = True, tipo: int = 0,
                    mapa_id: int = 9, mapa: str = "Arabia", multijugador: bool = True) -> Path:
    """Una repetición de prueba con la cabecera de la versión 68.9 (para las pruebas y el
    modo simulado). Solo trae lo que lee leer(); el resto va a cero."""
    p = struct.pack
    raw = b"VER 9.4\x00" + p("<fI", -1.0, round(68.9 * (1 << 16)))
    raw += bytes(4 + 4 + 12) + p("<I", 0)                       # build, hora, versiones; sin DLC
    raw += bytes(12) + p("<I", mapa_id) + bytes(20) + p("<I", tipo) + bytes(20)
    raw += p("<I", len(jugadores)) + bytes(20) + p("<b", 1 if multijugador else 0) + bytes(21)
    por_numero = {j.numero: j for j in jugadores}
    for n in range(1, 9):
        j = por_numero.get(n)
        tipo_j, color, equipo, civ, perfil, nombre = (HUMANO, j.color, j.equipo, j.civ, j.perfil, j.nombre) if j \
            else (0, -1, 0, 0, 0, "")
        raw += p("<Ii", 0, color) + bytes(2) + p("<b", equipo) + bytes(9) + p("<II", civ, 0)
        raw += _cadena("") + bytes(1) + _cadena("") + _cadena(nombre) + _cadena(nombre)
        raw += p("<IIIi", tipo_j, perfil, 0, n if j else -1) + bytes(14) + _cadena("")
    raw += bytes(16) + p("<b", 1 if clasificatoria else 0) + bytes(40)
    raw += f"Ubicación: {mapa}\n".encode("utf-8") + bytes(64)
    comp = zlib.compressobj(9, zlib.DEFLATED, -15)
    cuerpo = comp.compress(raw) + comp.flush()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(struct.pack("<II", len(cuerpo) + 8, 0) + cuerpo + bytes(256))  # + el resto de la partida
    return ruta
