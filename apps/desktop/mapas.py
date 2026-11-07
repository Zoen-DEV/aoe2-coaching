"""Arma los mapas [AoE2C] con los archivos del juego instalado.

Cada mapa es el .rms oficial (resources/_common/drs/gamedata_x2) con una cabecera que
carga el script común aoe2c_guia.xs. Su imagen de la sala es la oficial (mapicons) con
una banda "AoE2 Coaching". Así no se publican archivos de Microsoft: la app arma los
mapas en cada PC (y los vuelve a armar si el juego actualiza el oficial), y
content/guias/build.py usa estas mismas funciones.
"""

import unicodedata
from pathlib import Path

MAPAS_OFICIALES = Path("resources") / "_common" / "drs" / "gamedata_x2"
ICONOS_OFICIALES = Path("resources") / "_common" / "wpfg" / "resources" / "mapicons"
XS_COMUN = "aoe2c_guia.xs"
_qt_app = None


class MapaError(Exception):
    pass


def ascii_simple(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


def con_script(base: bytes, xs: str, titulo: str, nombre_base: str) -> bytes:
    """El .rms `base` con la cabecera que carga el script `xs`."""
    if b"#includeXS" in base:
        raise MapaError(f"{nombre_base} ya incluye un script XS; no se puede añadir la guía sin sustituirlo")
    cabecera = (
        f"#includeXS {xs}\r\n"
        f"/* {ascii_simple(titulo)}. Copia de {nombre_base} que carga el script\r\n"
        f"   {xs}. Generado por AoE2 Coaching. */\r\n"
        "\r\n"
    )
    return cabecera.encode("ascii") + base


def titulo(receta: dict) -> str:
    return f"Mapa de AoE2 Coaching ({receta['nombre']})"


def rms_oficial(juego: Path | None, receta: dict) -> Path | None:
    return Path(juego) / MAPAS_OFICIALES / receta["base"] if juego else None


def armar_rms(juego: Path | None, receta: dict) -> bytes:
    """El .rms del mapa [AoE2C] de la receta (base, nombre), con el oficial de este juego."""
    oficial = rms_oficial(juego, receta)
    if oficial is None:
        raise MapaError("no se encontró la carpeta del juego")
    try:
        base = oficial.read_bytes()
    except OSError:
        raise MapaError(f"el juego no tiene el mapa oficial {receta['base']}") from None
    return con_script(base, XS_COMUN, titulo(receta), receta["base"])


def imagen_oficial(juego: Path | None, receta: dict) -> Path | None:
    if not juego:
        return None
    nombre = receta.get("imagen") or f"rm_{Path(receta['base']).stem.lower()}.png"
    ruta = Path(juego) / ICONOS_OFICIALES / nombre
    return ruta if ruta.is_file() else None


def armar_imagen(fuente: Path, destino: Path) -> None:
    """Imagen de la sala: la del mapa oficial (420x420) con una banda "AoE2 Coaching"
    encima. El juego la toma de un .png con el mismo nombre que el .rms."""
    global _qt_app
    # Sin QT_QPA_PLATFORM=offscreen: en Windows esa plataforma no carga las fuentes del sistema.
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPen
    from PySide6.QtWidgets import QApplication
    if QGuiApplication.instance() is None:
        _qt_app = QApplication([])  # completa (no QGuiApplication): después puede haber ventanas

    img = QImage(str(fuente)).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    if img.isNull():
        raise MapaError(f"no se pudo leer la imagen {Path(fuente).name}")
    w, h = img.width(), img.height()
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    # Banda centrada, oscura y con borde dorado, como las placas del juego.
    bw, bh = w * 0.80, h * 0.20
    banda = QRectF((w - bw) / 2, (h - bh) / 2, bw, bh)
    for i in range(8, 0, -1):  # sombra
        s = QPainterPath()
        s.addRoundedRect(banda.adjusted(-i, -i + 4, i, i + 4), 12 + i, 12 + i)
        p.fillPath(s, QColor(0, 0, 0, 10))
    path = QPainterPath()
    path.addRoundedRect(banda, 12, 12)
    fondo = QLinearGradient(banda.topLeft(), banda.bottomLeft())
    fondo.setColorAt(0, QColor(32, 26, 18, 238))
    fondo.setColorAt(1, QColor(14, 12, 9, 238))
    p.fillPath(path, fondo)
    p.setPen(QPen(QColor(214, 176, 92), 3))
    p.drawPath(path)
    p.setPen(QPen(QColor(214, 176, 92, 90), 1))
    p.drawRoundedRect(banda.adjusted(6, 6, -6, -6), 8, 8)

    f = QFont("Segoe UI")
    f.setPixelSize(int(bh * 0.46))
    f.setWeight(QFont.Weight.Bold)
    p.setFont(f)
    texto = QRectF(banda.left(), banda.top() + 1, banda.width(), banda.height())
    p.setPen(QColor(0, 0, 0, 170))
    p.drawText(texto.translated(0, 2), Qt.AlignmentFlag.AlignCenter, "AoE2 Coaching")
    p.setPen(QColor(248, 232, 196))
    p.drawText(texto, Qt.AlignmentFlag.AlignCenter, "AoE2 Coaching")
    p.end()
    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    if not img.save(str(destino)):
        raise MapaError(f"no se pudo guardar {destino}")
