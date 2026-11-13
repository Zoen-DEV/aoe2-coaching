"""Iconos de tecnologías y unidades, leídos del juego instalado (no van con la app).

Están en widgetui/textures/ingame como .dds de 256x256 (RGBA sin comprimir, DXT1 o
DXT5); qué icono va con cada ID lo dice nombres_juego.py (ICONOS_TECNOLOGIAS e
ICONOS_UNIDADES). Qt no lee .dds: aquí se leen a mano y se reducen a TAM píxeles. Los
comprimidos se reducen bloque a bloque (cada bloque de 4x4 es un píxel con la media de
sus 16), así no hace falta descomprimirlos enteros. Se guardan en memoria y en
%APPDATA%\\AoE2Coaching\\iconos como .png, para no volver a leerlos.

Sin juego o con un icono que no está, devuelve None: quien pinta deja el hueco vacío.
"""

import struct
import threading
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

import nombres_juego
import rutas

TAM = 64
CARPETA = Path("widgetui") / "textures" / "ingame"
CACHE = rutas.DATOS / "iconos"

_juego: Path | None = None
_buscado = False
_memoria: dict[str, QImage | None] = {}
_cerrojo = threading.Lock()


def poner_juego(carpeta: Path | None) -> None:
    """Carpeta del juego en uso (la que elige rutas.py o el panel)."""
    global _juego, _buscado
    _juego, _buscado = (Path(carpeta) if carpeta else None), carpeta is not None


def juego() -> Path | None:
    global _juego, _buscado
    if not _buscado:
        _juego, _buscado = rutas.buscar_juego(rutas.carpeta_steam()), True
    return _juego


def ruta_tecnologia(id_: int) -> str | None:
    return nombres_juego.ICONOS_TECNOLOGIAS.get(id_)


def ruta_unidad(id_: int) -> str | None:
    return nombres_juego.ICONOS_UNIDADES.get(id_)


def en_memoria(ruta: str | None) -> QImage | None:
    """El icono si ya está leído (no lee nada: para pintar sin esperar)."""
    return _memoria.get(ruta) if ruta else None


def leido(ruta: str | None) -> bool:
    return not ruta or ruta in _memoria


def icono(ruta: str | None) -> QImage | None:
    """El icono (TAMxTAM) de esa ruta de nombres_juego.py, o None."""
    if not ruta:
        return None
    with _cerrojo:
        if ruta in _memoria:
            return _memoria[ruta]
    img = _cargar(ruta)
    with _cerrojo:
        _memoria[ruta] = img
    return img


def _cargar(ruta: str) -> QImage | None:
    cache = CACHE / (ruta.replace("/", "_").rsplit(".", 1)[0] + ".png")
    if cache.is_file():
        img = QImage(str(cache))
        if not img.isNull():
            return img
    base = juego()
    if base is None:
        return None
    try:
        img = leer_dds((base / CARPETA / ruta).read_bytes())
    except (OSError, ValueError, struct.error):
        return None
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        img.save(str(cache))
    except OSError:
        pass
    return img


# --- .dds ---------------------------------------------------------------------

def leer_dds(d: bytes, tam: int = TAM) -> QImage:
    if d[:4] != b"DDS ":
        raise ValueError("no es un .dds")
    alto, ancho = struct.unpack_from("<II", d, 12)
    flags, fourcc, bits, r_mask = struct.unpack_from("<I4sII", d, 80)
    datos = d[128:]
    if fourcc in (b"DXT1", b"DXT5"):
        img = _reducir_dxt(datos, ancho, alto, fourcc == b"DXT5")
    elif flags & 0x40 and bits == 32:
        formato = QImage.Format.Format_RGBA8888 if r_mask == 0xFF else QImage.Format.Format_ARGB32
        img = QImage(datos[:ancho * alto * 4], ancho, alto, ancho * 4, formato).copy()
    else:
        raise ValueError(f"formato .dds no soportado ({fourcc!r}, {bits} bits)")
    return img.scaled(tam, tam, Qt.AspectRatioMode.IgnoreAspectRatio,
                      Qt.TransformationMode.SmoothTransformation).convertToFormat(QImage.Format.Format_ARGB32)


def _color565(c: int) -> tuple[int, int, int]:
    r, g, b = (c >> 11) & 31, (c >> 5) & 63, c & 31
    return (r << 3 | r >> 2, g << 2 | g >> 4, b << 3 | b >> 2)


def _reducir_dxt(datos: bytes, ancho: int, alto: int, dxt5: bool) -> QImage:
    """Un píxel por bloque de 4x4, con la media de los 16 del bloque."""
    bw, bh = max(1, (ancho + 3) // 4), max(1, (alto + 3) // 4)
    paso = 16 if dxt5 else 8
    out = bytearray(bw * bh * 4)
    for k in range(bw * bh):
        o = k * paso
        if dxt5:
            a0, a1 = datos[o], datos[o + 1]
            if a0 > a1:
                alfas = [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
            else:
                alfas = [a0, a1] + [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)] + [0, 255]
            indices_a = int.from_bytes(datos[o + 2:o + 8], "little")
            alfa = [alfas[(indices_a >> (3 * i)) & 7] for i in range(16)]
            o += 8
        c0, c1, indices = struct.unpack_from("<HHI", datos, o)
        p0, p1 = _color565(c0), _color565(c1)
        if c0 > c1 or dxt5:
            paleta = [p0, p1, tuple((2 * a + b) // 3 for a, b in zip(p0, p1)),
                      tuple((a + 2 * b) // 3 for a, b in zip(p0, p1))]
            transparente = -1
        else:
            paleta = [p0, p1, tuple((a + b) // 2 for a, b in zip(p0, p1)), (0, 0, 0)]
            transparente = 3
        r = g = b = a = 0
        for i in range(16):
            n = (indices >> (2 * i)) & 3
            al = alfa[i] if dxt5 else (0 if n == transparente else 255)
            c = paleta[n]
            r, g, b, a = r + c[0] * al, g + c[1] * al, b + c[2] * al, a + al
        if a:  # media ponderada por la opacidad (sin halos oscuros en los bordes)
            out[4 * k:4 * k + 4] = bytes((r // a, g // a, b // a, a // 16))
    return QImage(bytes(out), bw, bh, bw * 4, QImage.Format.Format_RGBA8888).copy()
