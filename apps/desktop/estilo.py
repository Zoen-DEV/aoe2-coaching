"""Colores, fuentes y banderas de ventana comunes al overlay y al historial."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

FUENTE = "Segoe UI"
EMOJI = "Segoe UI Emoji"

FONDO = QColor(13, 16, 22, 250)
BORDE = QColor(255, 255, 255, 26)
TARJETA = QColor(255, 255, 255, 12)
TEXTO = QColor(240, 243, 247)
SECUNDARIO = QColor(186, 194, 206)
APAGADO = QColor(128, 138, 154)
ACENTO = QColor(94, 164, 255)
BIEN = QColor(56, 204, 128)
ATENCION = QColor(255, 182, 56)
MAL = QColor(255, 96, 96)
PISTA = QColor(255, 255, 255, 20)

# Series del gráfico del historial (validadas para daltonismo sobre el fondo oscuro).
SERIE_FEUDAL = QColor("#C9692A")
SERIE_CASTILLOS = QColor("#3D8FF5")

# Ventanas que reciben clics sin quitarle el foco al juego.
BANDERAS_CLIC = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)


def color(c: QColor, alpha: int) -> QColor:
    out = QColor(c)
    out.setAlpha(alpha)
    return out


def fuente(size: float, peso=QFont.Weight.Normal, espacio: float = 0.0, familia: str = FUENTE) -> QFont:
    f = QFont(familia)
    f.setPointSizeF(size)
    f.setWeight(peso)
    if espacio:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, espacio)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return f
