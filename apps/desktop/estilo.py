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

# --- Panel e historial ---------------------------------------------------------
# Negro cálido, oro del logo y granate: la marca de la web (apps/web) en vez del azul
# genérico. El overlay de la partida sigue con los colores de arriba (se lee mejor sobre
# el juego). Los textos pasan 4.5:1 de contraste sobre P_TARJETA.
P_FONDO = QColor("#13110e")
P_LATERAL = QColor("#0d0b09")
P_TARJETA = QColor("#1b1814")
P_ELEVADA = QColor("#25211b")
P_BORDE = QColor(236, 214, 178, 26)
P_BORDE_FUERTE = QColor(236, 214, 178, 52)
P_TEXTO = QColor("#f1ebe0")
P_SECUNDARIO = QColor("#c2b7a5")
P_APAGADO = QColor("#968b7b")
ORO = QColor("#d2aa6c")
ORO_CLARO = QColor("#e9c992")
GRANATE = QColor("#86202f")
GRANATE_CLARO = QColor("#c25562")

TITULO = "Cinzel"  # fuente_titulos.py; si no carga, Qt usa una serif del sistema
_fuentes_cargadas = False


def cargar_fuentes():
    """Registra Cinzel (va dentro del código). Hace falta una QApplication."""
    global _fuentes_cargadas
    if _fuentes_cargadas:
        return
    _fuentes_cargadas = True
    from PySide6.QtCore import QByteArray
    from PySide6.QtGui import QFontDatabase
    import fuente_titulos
    QFontDatabase.addApplicationFontFromData(QByteArray(fuente_titulos.TTF))


def titulo(size: float, espacio: float = 0.0) -> QFont:
    """Letra de los títulos (Cinzel Bold)."""
    f = fuente(size, QFont.Weight.Bold, espacio, TITULO)
    f.setStyleHint(QFont.StyleHint.Serif)
    return f


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
