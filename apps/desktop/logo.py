"""Logo de AoE2 Coaching: escudo granate con un cheurón dorado.

El SVG vive aquí (y no en un archivo aparte) para que el .exe no dependa de datos extra.
Ejecutado solo, exporta el logo a build/marca: logo.svg, PNG en varios tamaños y
aoe2c.ico con varios tamaños (para el .exe, el instalador y la web).
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

GRANATE = "#86202F"         # mitad izquierda (la iluminada)
GRANATE_OSCURO = "#6C1A2B"  # mitad derecha
DORADO = "#C79D63"

# Escudo de 600 x 740, centrado en un lienzo cuadrado.
SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-80 -10 760 760">
  <path d="M300 0 L0 48 L0 430 C0 590 180 665 300 740 Z" fill="{GRANATE}"/>
  <path d="M300 0 L600 48 L600 430 C600 590 420 665 300 740 Z" fill="{GRANATE_OSCURO}"/>
  <path d="M300 200 L552 445 Q546 495 510 533 L300 330 L90 533 Q54 495 48 445 Z" fill="{DORADO}"/>
</svg>
"""

TAMANOS = (16, 20, 24, 32, 40, 48, 64, 128, 256)

_icono: QIcon | None = None


def imagen(lado: int) -> QImage:
    """El logo en un cuadrado de `lado` píxeles, con fondo transparente."""
    img = QImage(lado, lado, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(SVG.encode())).render(p, QRectF(0, 0, lado, lado))
    p.end()
    return img


def icono() -> QIcon:
    """QIcon con el logo dibujado en cada tamaño (nítido en la bandeja y en la barra de tareas)."""
    global _icono
    if _icono is None:
        _icono = QIcon()
        for lado in TAMANOS:
            _icono.addPixmap(QPixmap.fromImage(imagen(lado)))
    return _icono


def exportar(carpeta: Path) -> None:
    from PySide6.QtGui import QGuiApplication
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)  # noqa: F841 (QSvgRenderer la necesita)
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "logo.svg").write_text(SVG, encoding="utf-8")
    for lado in (32, 64, 128, 256, 512, 1024):
        imagen(lado).save(str(carpeta / f"logo-{lado}.png"))
    guardar_ico(carpeta / "aoe2c.ico")
    print(f"logo exportado en {carpeta}")


def guardar_ico(destino: Path, tamanos=(16, 20, 24, 32, 40, 48, 64, 128, 256)) -> None:
    """Un .ico con el logo en varios tamaños (cada uno en PNG), para que Windows use el
    nítido en cada sitio (barra de tareas, menú Inicio, escritorio). Qt solo guarda uno."""
    import struct
    from PySide6.QtCore import QBuffer, QIODevice
    pngs = []
    for lado in tamanos:
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        imagen(lado).save(buf, "PNG")
        pngs.append((lado, bytes(buf.data())))
    cabecera = struct.pack("<HHH", 0, 1, len(pngs))
    entradas, datos, desplazamiento = b"", b"", 6 + 16 * len(pngs)
    for lado, png in pngs:
        b = 0 if lado >= 256 else lado  # 0 = 256 en el formato .ico
        entradas += struct.pack("<BBBBHHII", b, b, 0, 0, 1, 32, len(png), desplazamiento + len(datos))
        datos += png
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(cabecera + entradas + datos)


if __name__ == "__main__":
    exportar(Path(__file__).resolve().parent.parent.parent / "build" / "marca")
