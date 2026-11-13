"""Imágenes y fuente del instalador, con la misma marca que el panel (estilo.py).

Las dibuja Qt al empaquetar, igual que el logo, así no hay imágenes sueltas en el repo:
  - fondo-<ancho>.png   fondo de las páginas del asistente (proporción 497:360)
  - lateral-<ancho>.png franja izquierda de la bienvenida y el final (proporción 164:314),
                        como la barra lateral del panel
  - cabecera-<lado>.png logo de la esquina en las demás páginas (cuadrado)
  - cinzel.ttf          la letra de los títulos del panel

Cada imagen va en varios tamaños: Inno Setup elige la que mejor encaja con los DPI.
"""
from __future__ import annotations

import sys
from pathlib import Path

DESKTOP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DESKTOP))

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QRadialGradient  # noqa: E402

import estilo  # noqa: E402
import logo  # noqa: E402

FONDOS = ((596, 432), (994, 720), (1272, 922), (1630, 1148))
LATERALES = ((202, 386), (336, 643), (430, 824), (534, 1022))
CABECERAS = (58, 97, 124, 159)


def _lienzo(ancho: int, alto: int, color: QColor) -> tuple[QImage, QPainter]:
    img = QImage(ancho, alto, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(color)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    return img, p


def _brillo(p: QPainter, centro: QPointF, radio: float, c: QColor, alpha: int) -> None:
    g = QRadialGradient(centro, radio)
    g.setColorAt(0, estilo.color(c, alpha))
    g.setColorAt(1, estilo.color(c, 0))
    p.fillRect(QRectF(0, 0, p.device().width(), p.device().height()), g)


def fondo(ancho: int, alto: int) -> QImage:
    """Negro cálido del panel con un brillo dorado arriba y uno granate abajo."""
    img, p = _lienzo(ancho, alto, estilo.P_FONDO)
    _brillo(p, QPointF(ancho * 0.92, -alto * 0.1), ancho * 0.55, estilo.ORO, 22)
    _brillo(p, QPointF(ancho * 0.05, alto * 1.1), ancho * 0.6, estilo.GRANATE, 46)
    p.end()
    return img


def lateral(ancho: int, alto: int) -> QImage:
    """La barra lateral del panel: el escudo, el nombre en Cinzel dorado y el borde fino."""
    img, p = _lienzo(ancho, alto, estilo.P_LATERAL)
    arriba = QLinearGradient(0, 0, 0, alto * 0.6)
    arriba.setColorAt(0, estilo.color(estilo.GRANATE, 70))
    arriba.setColorAt(1, estilo.color(estilo.GRANATE, 0))
    p.fillRect(QRectF(0, 0, ancho, alto), arriba)
    _brillo(p, QPointF(ancho / 2, alto * 0.36), ancho * 0.7, estilo.ORO, 18)

    lado = ancho * 0.56
    p.drawImage(QRectF((ancho - lado) / 2, alto * 0.36 - lado / 2, lado, lado), logo.imagen(int(lado)))

    escala = ancho / 202
    p.setPen(estilo.ORO_CLARO)
    p.setFont(_cinzel(15 * escala, 2.4 * escala))
    p.drawText(QRectF(0, alto * 0.36 + lado * 0.58, ancho, 30 * escala), Qt.AlignmentFlag.AlignCenter, "AOE2")
    p.setPen(estilo.ORO)
    p.setFont(_cinzel(9.5 * escala, 3.2 * escala))
    p.drawText(QRectF(0, alto * 0.36 + lado * 0.58 + 26 * escala, ancho, 20 * escala),
               Qt.AlignmentFlag.AlignCenter, "COACHING")

    p.fillRect(QRectF(ancho - max(1.0, escala), 0, max(1.0, escala), alto), estilo.P_BORDE_FUERTE)
    p.end()
    return img


def _cinzel(px: float, espacio: float) -> QFont:
    f = QFont(estilo.TITULO)
    f.setPixelSize(max(1, round(px)))
    f.setWeight(QFont.Weight.Bold)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, espacio)
    f.setStyleHint(QFont.StyleHint.Serif)
    return f


def exportar(carpeta: Path) -> None:
    from PySide6.QtGui import QGuiApplication
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)  # noqa: F841
    estilo.cargar_fuentes()
    destino = carpeta / "instalador"
    destino.mkdir(parents=True, exist_ok=True)
    for ancho, alto in FONDOS:
        fondo(ancho, alto).save(str(destino / f"fondo-{ancho}.png"))
    for ancho, alto in LATERALES:
        lateral(ancho, alto).save(str(destino / f"lateral-{ancho}.png"))
    for lado in CABECERAS:
        logo.imagen(lado).save(str(destino / f"cabecera-{lado}.png"))
    import fuente_titulos
    (destino / "cinzel.ttf").write_bytes(fuente_titulos.TTF)
    print(f"marca del instalador en {destino}")


if __name__ == "__main__":
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    exportar(DESKTOP.parent.parent / "build" / "marca")
