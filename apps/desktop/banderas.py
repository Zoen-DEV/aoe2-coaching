"""Banderas de los países para el panel de la partida en curso.

Se dibujan como SVG a partir del código de país de dos letras que da la API ("ca"): los
emojis de banderas no se ven en Windows. Los SVG van dentro de banderas_datos.py (la
app empaquetada no lleva archivos sueltos); mientras ese módulo no esté, o para un país
que no tenga, se dibuja un recuadro con el código.
"""

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QFont, QPainter, QPainterPath
from PySide6.QtSvg import QSvgRenderer

from estilo import APAGADO, TEXTO, color, fuente

try:
    from banderas_datos import SVG  # código de país -> SVG (bytes)
except ImportError:
    SVG: dict[str, bytes] = {}

_renderers: dict[str, QSvgRenderer | None] = {}


def _renderer(codigo: str) -> QSvgRenderer | None:
    if codigo not in _renderers:
        datos = SVG.get(codigo)
        r = QSvgRenderer(QByteArray(datos)) if datos else None
        _renderers[codigo] = r if r is not None and r.isValid() else None
    return _renderers[codigo]


def pintar(p: QPainter, r: QRectF, codigo: str | None) -> None:
    """La bandera en r (proporción 4:3), con las esquinas un poco redondeadas. Sin país, nada."""
    if not codigo:
        return
    codigo = codigo.lower()
    borde = QPainterPath()
    borde.addRoundedRect(r, 2, 2)
    svg = _renderer(codigo)
    p.save()
    if svg:
        p.setClipPath(borde)
        svg.render(p, r)
        p.setClipping(False)
        p.setPen(color(TEXTO, 40))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(borde)
    else:
        p.fillPath(borde, color(TEXTO, 22))
        p.setFont(fuente(6.5, QFont.Weight.Bold))
        p.setPen(APAGADO)
        p.drawText(r, int(Qt.AlignmentFlag.AlignCenter.value), codigo.upper())
    p.restore()
