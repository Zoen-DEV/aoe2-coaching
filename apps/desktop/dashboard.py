"""Panel de AoE2C: la ventana principal del programa, al estilo de las apps
compañeras de los juegos competitivos.

Es una ventana normal de Windows (sale en la barra de tareas y no se pone encima del
juego). La ✕ la esconde: el programa sigue en la bandeja del sistema, y se cierra del
todo con «Cerrar AoE2C» (aquí o en el menú del icono de la bandeja).

Páginas:
- Inicio: la guía activa, el estado del juego, tus números con esa guía y la última partida.
- Estadísticas: el historial de partidas por guía (el mismo contenido que la ventana
  que se abre al acabar una partida).
- Guías: instalar guías del catálogo, elegir la que cargan los mapas [AoE2C] y ver sus pasos.
- Mapas: armar en el juego los mapas del catálogo, quitarlos o guardar una copia.
- MODs: instalar, actualizar, activar y quitar los mods de AoE2 Coaching.
- Ajustes: idioma, inicio con Windows y cómo se ve la guía en la partida.

El catálogo (catalogo.py) se descarga en segundo plano al abrir el panel; mientras
tanto, y sin conexión, se usa la última copia guardada.
"""

import logging
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, QPointF, QRectF, QSize, Qt, QTimer, Signal, Slot
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QGuiApplication, QIcon, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap)
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QComboBox, QDialog, QFileDialog, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QPushButton, QRadioButton, QScrollArea, QSizePolicy, QSlider,
                               QStackedWidget, QVBoxLayout, QWidget)

import actualizacion as A
import catalogo as K
import config as C
import instalador as I
import repeticiones
import rutas
import soporte
import textos
from estilo import ATENCION, BIEN, GRANATE, GRANATE_CLARO, MAL, ORO_CLARO, P_BORDE_FUERTE, P_ELEVADA
from estilo import ORO as ACENTO
from estilo import P_APAGADO as APAGADO
from estilo import P_BORDE as BORDE
from estilo import P_SECUNDARIO as SECUNDARIO
from estilo import P_TARJETA as TARJETA
from estilo import P_TEXTO as TEXTO
from estilo import cargar_fuentes, color, fuente, titulo
from historial import (Historial, nombre_hito, pasos_hechos, principal, reloj, resumen_hito, valor_principal,
                       vista_de_guia)
from historial_ui import ContenidoHistorial, desfase, fecha_corta, mapa_corto
from textos import de, t
from version import VERSION

FONDO_PANEL = "#13110e"
FONDO_LATERAL = "#0d0b09"
# Monograma de cada guía y mod dentro de un escudo (en vez de emojis).
ICONO_GUIA = {"fast_castle": "FC", "scouts": "SC"}
ICONO_MOD = {"icono-ovejas": "OV"}
PROXIMAS = [("arqueros", "AR"), ("drush_fc", "DF"), ("hombres_armas", "HA"), ("aguilas", "AG")]
PAGINAS = ["inicio", "estadisticas", "guias", "mapas", "mods", "ajustes"]
ROMANOS = ["I", "II", "III", "IV", "V"]


def rgba(c: QColor, alpha: int) -> str:
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"


ESTILO = f"""
#raiz {{ background: {FONDO_PANEL}; }}
#lateral {{ background: {FONDO_LATERAL}; border-right: 1px solid {rgba(BORDE, 26)}; }}
QLabel {{ color: {TEXTO.name()}; background: transparent; }}
QToolTip {{ color: {TEXTO.name()}; background: {P_ELEVADA.name()}; border: 1px solid {rgba(P_BORDE_FUERTE, 90)};
           padding: 5px 8px; font-family: 'Segoe UI'; font-size: 9pt; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {rgba(TEXTO, 36)}; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {rgba(TEXTO, 70)}; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ height: 0; background: none; }}
QPushButton {{ color: {TEXTO.name()}; background: transparent; border: 1px solid {rgba(P_BORDE_FUERTE, 70)};
              border-radius: 4px; padding: 7px 16px; font-family: 'Segoe UI'; font-size: 9.5pt; font-weight: 600; }}
QPushButton:hover {{ background: {rgba(ACENTO, 22)}; border-color: {rgba(ACENTO, 140)}; color: {ORO_CLARO.name()}; }}
QPushButton:pressed {{ background: {rgba(ACENTO, 40)}; }}
QPushButton:focus {{ border-color: {ACENTO.name()}; }}
QPushButton:disabled {{ color: {APAGADO.name()}; background: transparent; border-color: {rgba(BORDE, 30)}; }}
QPushButton#primario {{ color: #1c140a; background: {ACENTO.name()}; border: 1px solid {ACENTO.name()}; }}
QPushButton#primario:hover {{ background: {ORO_CLARO.name()}; border-color: {ORO_CLARO.name()}; }}
QPushButton#primario:pressed {{ background: #b88f52; border-color: #b88f52; }}
QPushButton#primario:focus {{ border-color: {ORO_CLARO.name()}; }}
QPushButton#primario:disabled {{ color: {APAGADO.name()}; background: {rgba(ACENTO, 30)}; border-color: transparent; }}
QPushButton#salir {{ color: {GRANATE_CLARO.name()}; background: transparent; border: 1px solid {rgba(GRANATE, 120)};
                    text-align: left; padding: 9px 14px; }}
QPushButton#salir:hover {{ color: #ffffff; background: {GRANATE.name()}; border-color: {GRANATE.name()}; }}
QPushButton#chip {{ border-radius: 3px; padding: 6px 14px; font-size: 9pt; color: {SECUNDARIO.name()};
                   border-color: {rgba(P_BORDE_FUERTE, 60)}; }}
QPushButton#chip:checked {{ color: {ORO_CLARO.name()}; background: {rgba(ACENTO, 28)}; border-color: {ACENTO.name()}; }}
QPushButton#enlace {{ background: transparent; border: none; color: {ACENTO.name()}; padding: 2px 0; text-align: left; }}
QPushButton#enlace:hover {{ color: {ORO_CLARO.name()}; text-decoration: underline; }}
QComboBox {{ color: {TEXTO.name()}; background: {P_ELEVADA.name()}; border: 1px solid {rgba(P_BORDE_FUERTE, 70)};
            border-radius: 4px; padding: 6px 12px; font-family: 'Segoe UI'; font-size: 9.5pt; min-width: 140px; }}
QComboBox:hover, QComboBox:focus {{ border-color: {rgba(ACENTO, 160)}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ color: {TEXTO.name()}; background: {P_ELEVADA.name()};
                              border: 1px solid {rgba(P_BORDE_FUERTE, 90)};
                              selection-background-color: {rgba(ACENTO, 70)}; outline: none; padding: 4px; }}
QSlider::groove:horizontal {{ height: 3px; background: {rgba(TEXTO, 30)}; border-radius: 1px; }}
QSlider::sub-page:horizontal {{ background: {ACENTO.name()}; border-radius: 1px; }}
QSlider::handle:horizontal {{ background: {ORO_CLARO.name()}; width: 14px; height: 14px; margin: -6px 0;
                              border-radius: 7px; }}
"""


# --- Piezas ------------------------------------------------------------------


def pintor(w: QWidget) -> QPainter:
    p = QPainter(w)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    return p


def caja(p: QPainter, r: QRectF, radio: float, relleno, borde=None):
    path = QPainterPath()
    path.addRoundedRect(r, radio, radio)
    p.fillPath(path, relleno)
    if borde is not None:
        p.setPen(QPen(borde, 1))
        p.drawPath(path)


def nombre_perfil(p: "rutas.Perfil") -> str:
    """«Zoen · 63 partidas · 06/11/2026» para elegir entre carpetas de perfil."""
    nombre = p.nombre or (t("perfil_sin_conexion") if p.id == "0" else p.id)
    fecha = time.strftime("%d/%m/%Y", time.localtime(p.ultimo_uso)) if p.ultimo_uso else "—"
    return t("perfil_etiqueta", nombre=nombre, partidas=p.repeticiones, fecha=fecha)


def etiqueta(texto: str, tam: float = 10, peso=QFont.Weight.Normal, c: QColor = TEXTO, espacio: float = 0.0,
             envolver: bool = False) -> QLabel:
    lab = QLabel(texto)
    lab.setFont(fuente(tam, peso, espacio))
    lab.setStyleSheet(f"color: {c.name()};")
    lab.setWordWrap(envolver)
    return lab


def boton(texto: str, al_pulsar=None, tipo: str = "", consejo: str = "") -> QPushButton:
    b = QPushButton(texto)
    if tipo:
        b.setObjectName(tipo)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if consejo:
        b.setToolTip(consejo)
    if al_pulsar:
        b.clicked.connect(al_pulsar)
    return b


def pastilla(texto: str, c: QColor = SECUNDARIO) -> QLabel:
    """Etiqueta pequeña de estado: esquinas casi rectas, como un sello."""
    lab = QLabel(texto)
    lab.setFont(fuente(8, QFont.Weight.DemiBold, 0.3))
    lab.setStyleSheet(f"color: {c.name()}; background: {rgba(c, 22)}; border: 1px solid {rgba(c, 70)}; "
                      "border-radius: 2px; padding: 2px 7px;")
    lab.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    return lab


def rotulo(texto: str, c: QColor = APAGADO) -> QLabel:
    """Rótulo de sección en versalitas espaciadas."""
    return etiqueta(texto.upper(), 7.5, QFont.Weight.Bold, c, 1.6)


def meta(*partes: str) -> QLabel:
    """Datos secundarios en una línea, separados por un rombo (en vez de una fila de pastillas)."""
    lab = etiqueta("   ◆   ".join(p for p in partes if p), 9, QFont.Weight.Medium, SECUNDARIO, envolver=True)
    lab.setTextFormat(Qt.TextFormat.PlainText)
    return lab


def fila(*widgets, espacio: int = 8, estirar: bool = True) -> QHBoxLayout:
    f = QHBoxLayout()
    f.setContentsMargins(0, 0, 0, 0)
    f.setSpacing(espacio)
    for w in widgets:
        if isinstance(w, QWidget):
            f.addWidget(w)
        else:
            f.addLayout(w)
    if estirar:
        f.addStretch(1)
    return f


def desplazable(contenido: QWidget) -> QScrollArea:
    s = QScrollArea()
    s.setWidget(contenido)
    s.setWidgetResizable(True)
    s.setFrameShape(QFrame.Shape.NoFrame)
    s.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    return s


def esquinas(p: QPainter, r: QRectF, c: QColor, largo: float = 12):
    """Cuatro escuadras en las esquinas, como el marco de un pergamino (tarjeta destacada)."""
    p.save()
    p.setPen(QPen(c, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap))
    x0, y0, x1, y1 = r.left() + 0.5, r.top() + 0.5, r.right() - 0.5, r.bottom() - 0.5
    for x, y, dx, dy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        p.drawLine(QPointF(x, y), QPointF(x + dx * largo, y))
        p.drawLine(QPointF(x, y), QPointF(x, y + dy * largo))
    p.restore()


class Tarjeta(QFrame):
    """Caja con borde fino y esquinas casi rectas; `acento` la destaca con un fondo cálido
    y escuadras doradas en las esquinas."""

    RADIO = 5

    def __init__(self, acento: QColor | None = None, relleno: QColor = TARJETA, margen: int = 18):
        super().__init__()
        self.acento = acento
        self.relleno = relleno
        self.capa = QVBoxLayout(self)
        self.capa.setContentsMargins(margen, margen - 2, margen, margen)
        self.capa.setSpacing(8)

    def paintEvent(self, _):
        p = pintor(self)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self.acento:
            fondo = QLinearGradient(r.topLeft(), r.bottomRight())
            fondo.setColorAt(0, color(self.acento, 26))
            fondo.setColorAt(0.55, self.relleno)
            fondo.setColorAt(1, self.relleno)
            caja(p, r, self.RADIO, self.relleno)
            caja(p, r, self.RADIO, QBrush(fondo), color(self.acento, 60))
            esquinas(p, r.adjusted(3, 3, -3, -3), self.acento)
        else:
            caja(p, r, self.RADIO, self.relleno, BORDE)
        p.end()


def dibujar_icono(p: QPainter, nombre: str, r: QRectF, c: QColor):
    """Iconos de la barra lateral, dibujados con líneas (se ven nítidos a cualquier escala)."""
    p.save()
    p.setPen(QPen(c, 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    if nombre == "inicio":
        p.drawPolyline([QPointF(x + 2, y + h * 0.48), QPointF(x + w / 2, y + 2), QPointF(x + w - 2, y + h * 0.48)])
        p.drawPolyline([QPointF(x + 4.5, y + h * 0.4), QPointF(x + 4.5, y + h - 2), QPointF(x + w - 4.5, y + h - 2),
                        QPointF(x + w - 4.5, y + h * 0.4)])
        p.drawRect(QRectF(x + w / 2 - 2.5, y + h - 8, 5, 6))
    elif nombre == "estadisticas":
        for k, alto in enumerate((0.45, 0.8, 0.6)):
            bx = x + 3 + k * (w - 6) / 3
            p.drawRoundedRect(QRectF(bx, y + h - 2 - (h - 4) * alto, (w - 6) / 3 - 3, (h - 4) * alto), 1.5, 1.5)
    elif nombre == "guias":
        p.drawRoundedRect(QRectF(x + 3, y + 2, w - 6, h - 4), 2.5, 2.5)
        for k in range(3):
            yy = y + 6.5 + k * 4.5
            p.drawLine(QPointF(x + 7, yy), QPointF(x + 8.5, yy + 1.5))
            p.drawLine(QPointF(x + 8.5, yy + 1.5), QPointF(x + 10.5, yy - 1))
            p.drawLine(QPointF(x + 12.5, yy), QPointF(x + w - 6, yy))
    elif nombre == "mapas":
        pts = [QPointF(x + 2, y + 4), QPointF(x + w / 3, y + 2), QPointF(x + 2 * w / 3, y + 4),
               QPointF(x + w - 2, y + 2), QPointF(x + w - 2, y + h - 4), QPointF(x + 2 * w / 3, y + h - 2),
               QPointF(x + w / 3, y + h - 4), QPointF(x + 2, y + h - 2)]
        p.drawPolygon(pts)
        p.drawLine(pts[1], pts[6])
        p.drawLine(pts[2], pts[5])
    elif nombre == "mods":  # pieza de puzle
        p.drawRoundedRect(QRectF(x + 2.5, y + 5.5, w - 8, h - 8), 2.5, 2.5)
        p.setBrush(QColor(FONDO_LATERAL))
        p.drawEllipse(QPointF(x + w / 2 - 1.5, y + 5.5), 2.6, 2.6)
        p.drawEllipse(QPointF(x + w - 5.5, y + h / 2 + 1.5), 2.6, 2.6)
        p.setBrush(Qt.BrushStyle.NoBrush)
    elif nombre == "ajustes":
        centro = r.center()
        p.drawEllipse(centro, w * 0.17, w * 0.17)
        p.drawEllipse(centro, w * 0.34, w * 0.34)
        for k in range(8):
            p.save()
            p.translate(centro)
            p.rotate(k * 45)
            p.drawLine(QPointF(0, -w * 0.34), QPointF(0, -w * 0.46))
            p.restore()
    p.restore()


class BotonLateral(QAbstractButton):
    """Entrada de la barra lateral: icono y nombre de la página."""

    def __init__(self, icono: str, texto: str):
        super().__init__()
        self.icono = icono
        self.setText(texto)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(42)
        self.encima = False

    def sizeHint(self):
        return QSize(190, 42)

    def enterEvent(self, _):
        self.encima = True
        self.update()

    def leaveEvent(self, _):
        self.encima = False
        self.update()

    def paintEvent(self, _):
        p = pintor(self)
        r = QRectF(self.rect()).adjusted(0, 1, 0, -1)
        if self.isChecked():
            fondo = QLinearGradient(r.topLeft(), r.topRight())
            fondo.setColorAt(0, color(ACENTO, 38))
            fondo.setColorAt(1, color(ACENTO, 0))
            p.fillRect(r, QBrush(fondo))
            p.fillRect(QRectF(r.x(), r.y(), 2, r.height()), ACENTO)
        elif self.encima:
            p.fillRect(r, color(TEXTO, 10))
        if self.hasFocus():
            p.setPen(QPen(color(ACENTO, 160), 1))
            p.drawRect(r.adjusted(0.5, 0.5, -0.5, -0.5))
        tinta = ORO_CLARO if self.isChecked() else (TEXTO if self.encima else SECUNDARIO)
        dibujar_icono(p, self.icono, QRectF(16, r.center().y() - 9, 18, 18), ACENTO if self.isChecked() else tinta)
        p.setFont(fuente(10, QFont.Weight.DemiBold if self.isChecked() else QFont.Weight.Medium, 0.2))
        p.setPen(tinta)
        p.drawText(QRectF(46, r.y(), r.width() - 52, r.height()), int(Qt.AlignmentFlag.AlignVCenter.value), self.text())
        p.end()


class Interruptor(QAbstractButton):
    """Interruptor de encendido y apagado."""

    def __init__(self, activo: bool, al_cambiar):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(activo)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(44, 24)
        self.toggled.connect(al_cambiar)

    def paintEvent(self, _):
        p = pintor(self)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if self.isChecked():
            caja(p, r, r.height() / 2, ACENTO)
        else:
            caja(p, r, r.height() / 2, color(TEXTO, 14), color(P_BORDE_FUERTE, 110))
        if self.hasFocus():
            caja(p, r.adjusted(-1, -1, 1, 1), r.height() / 2 + 1, QBrush(Qt.BrushStyle.NoBrush), ORO_CLARO)
        d = r.height() - 6
        x = r.right() - 3 - d if self.isChecked() else r.x() + 3
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#1c140a") if self.isChecked() else SECUNDARIO)
        p.drawEllipse(QRectF(x, r.y() + 3, d, d))
        p.end()


class Dato(QWidget):
    """Número grande con su nombre y una línea de detalle. Va dentro de un Libro: sin caja
    propia, separado del siguiente por una línea vertical."""

    def __init__(self, nombre: str):
        super().__init__()
        self.nombre = nombre
        self.valor = "—"
        self.detalle = ""
        self.color_detalle = APAGADO
        self.setFixedHeight(104)
        self.setMinimumWidth(150)

    def poner(self, valor: str, detalle: str = "", c: QColor = APAGADO):
        self.valor, self.detalle, self.color_detalle = valor, detalle, c
        self.update()

    def paintEvent(self, _):
        p = pintor(self)
        r = QRectF(self.rect())
        x, w = 22, r.width() - 40
        izq = int(Qt.AlignmentFlag.AlignLeft.value)
        p.setFont(fuente(7.5, QFont.Weight.Bold, 1.6))
        p.setPen(APAGADO)
        p.drawText(QRectF(x, 16, w, 16), izq, self.nombre.upper())
        p.setFont(titulo(21))
        p.setPen(TEXTO if self.valor != "—" else APAGADO)
        p.drawText(QRectF(x, 32, w, 38), izq | int(Qt.AlignmentFlag.AlignVCenter.value), self.valor)
        f = fuente(8.5, QFont.Weight.DemiBold)
        p.setFont(f)
        p.setPen(self.color_detalle)
        p.drawText(QRectF(x, 74, w, 18), izq, QFontMetricsF(f).elidedText(self.detalle, Qt.TextElideMode.ElideRight, w))
        p.end()


class Libro(QWidget):
    """Una sola caja con varios Dato en fila, separados por líneas finas (como un libro de cuentas)."""

    def __init__(self, datos: list[Dato]):
        super().__init__()
        self.datos = datos
        capa = QHBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(0)
        for d in datos:
            capa.addWidget(d, 1)

    def paintEvent(self, _):
        p = pintor(self)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        caja(p, r, Tarjeta.RADIO, TARJETA, BORDE)
        p.setPen(QPen(BORDE, 1))
        for d in self.datos[1:]:
            x = d.geometry().left() + 0.5
            p.drawLine(QPointF(x, r.top() + 18), QPointF(x, r.bottom() - 18))
        p.end()


def ruta_escudo(r: QRectF) -> QPainterPath:
    """Escudo heráldico (la forma del logo) dentro de r."""
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    path = QPainterPath()
    path.moveTo(x + w / 2, y)
    path.lineTo(x + w, y + h * 0.07)
    path.lineTo(x + w, y + h * 0.56)
    path.cubicTo(x + w, y + h * 0.78, x + w * 0.7, y + h * 0.9, x + w / 2, y + h)
    path.cubicTo(x + w * 0.3, y + h * 0.9, x, y + h * 0.78, x, y + h * 0.56)
    path.lineTo(x, y + h * 0.07)
    path.closeSubpath()
    return path


class Emblema(QWidget):
    """Escudo granate con el monograma dorado de la guía o el mod (FC, SC…)."""

    def __init__(self, monograma: str, tam: int = 56, c: QColor = ACENTO, apagado: bool = False):
        super().__init__()
        self.emoji, self.c, self.apagado = monograma, c, apagado  # .emoji: el nombre de siempre
        self.setFixedSize(tam, tam)

    def paintEvent(self, _):
        p = pintor(self)
        lado = self.height() - 2
        r = QRectF((self.width() - lado * 0.82) / 2, 1, lado * 0.82, lado)
        escudo = ruta_escudo(r)
        if self.apagado:
            p.fillPath(escudo, color(TEXTO, 8))
            p.setPen(QPen(color(TEXTO, 50), 1.2))
            p.drawPath(escudo)
            tinta = APAGADO
        else:
            mitad = QLinearGradient(r.topLeft(), r.topRight())
            mitad.setColorAt(0, GRANATE)
            mitad.setColorAt(0.5, GRANATE)
            mitad.setColorAt(0.5001, QColor("#6c1a2b"))
            mitad.setColorAt(1, QColor("#6c1a2b"))
            p.fillPath(escudo, QBrush(mitad))
            p.setPen(QPen(color(self.c, 150), 1.2))
            p.drawPath(escudo)
            tinta = ORO_CLARO
        p.setFont(titulo(lado * 0.22))
        p.setPen(tinta)
        p.drawText(r.adjusted(0, -lado * 0.08, 0, -lado * 0.08), int(Qt.AlignmentFlag.AlignCenter.value), self.emoji)
        p.end()


class ImagenMapa(QWidget):
    """Imagen del mapa recortada al ancho de la tarjeta, con las esquinas de arriba redondeadas."""

    def __init__(self, ruta: Path | None, alto: int = 150):
        super().__init__()
        self.pix = QPixmap(str(ruta)) if ruta else QPixmap()
        self.setFixedHeight(alto)

    def paintEvent(self, _):
        p = pintor(self)
        r = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(r.adjusted(0, 0, 0, 14), Tarjeta.RADIO, Tarjeta.RADIO)
        p.setClipPath(path)
        if self.pix.isNull():
            p.fillRect(r, color(TEXTO, 14))
            p.setPen(APAGADO)
            p.setFont(fuente(9, QFont.Weight.Medium))
            p.drawText(r, int(Qt.AlignmentFlag.AlignCenter.value), t("mapas_sin_imagen"))
        else:
            escala = max(r.width() / self.pix.width(), r.height() / self.pix.height())
            w, h = self.pix.width() * escala, self.pix.height() * escala
            p.drawPixmap(QRectF(r.center().x() - w / 2, r.center().y() - h / 2, w, h), self.pix,
                         QRectF(self.pix.rect()))
        p.end()


class PuntoEstado(QWidget):
    def __init__(self):
        super().__init__()
        self.c = APAGADO
        self.setFixedSize(12, 12)

    def poner(self, c: QColor):
        self.c = c
        self.update()

    def paintEvent(self, _):
        p = pintor(self)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color(self.c, 60))
        p.drawEllipse(QRectF(0, 0, 12, 12))
        p.setBrush(self.c)
        p.drawEllipse(QRectF(3, 3, 6, 6))
        p.end()


class Filete(QWidget):
    """Línea dorada bajo el título de la página: se desvanece hacia la derecha y empieza
    con un rombo."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(9)

    def paintEvent(self, _):
        p = pintor(self)
        y = self.height() / 2
        linea = QLinearGradient(QPointF(0, y), QPointF(self.width(), y))
        linea.setColorAt(0, color(ACENTO, 170))
        linea.setColorAt(0.35, color(ACENTO, 50))
        linea.setColorAt(1, color(ACENTO, 0))
        p.fillRect(QRectF(12, y - 0.5, self.width() - 12, 1), QBrush(linea))
        rombo = QPainterPath()
        rombo.moveTo(0, y)
        rombo.lineTo(4.5, y - 4.5)
        rombo.lineTo(9, y)
        rombo.lineTo(4.5, y + 4.5)
        rombo.closeSubpath()
        p.fillPath(rombo, ACENTO)
        p.end()


class Trabajo(QObject):
    """Una tarea en otro hilo. El resultado vuelve por una señal, así que al_terminar se
    ejecuta en el hilo de la ventana (Qt no deja tocar la ventana desde otro hilo)."""
    listo = Signal(object, object)

    def __init__(self, al_terminar, al_acabar):
        super().__init__()
        self.al_terminar, self.al_acabar = al_terminar, al_acabar
        self.listo.connect(self._terminar)

    def ejecutar(self, funcion):
        try:
            resultado, error = funcion(), None
        except Exception as e:  # noqa: BLE001 - se muestra en el panel
            resultado, error = None, e
        self.listo.emit(resultado, error)

    @Slot(object, object)
    def _terminar(self, resultado, error):
        self.al_acabar(self)
        self.al_terminar(resultado, error)


def monograma(id_: str | None, nombre: str, tabla: dict | None = None) -> str:
    """Las dos letras del escudo: las de la tabla o las iniciales del nombre."""
    if id_ in (tabla or ICONO_GUIA):
        return (tabla or ICONO_GUIA)[id_]
    palabras = [p for p in nombre.replace("-", " ").split() if p[:1].isalpha() and len(p) > 2]  # sin «de», «la»
    return "".join(p[0] for p in palabras[:2]).upper() or nombre[:2].upper()


def datos_guia(guia: dict) -> str:
    """«Intermedia ◆ 16 pasos ◆ Meta: Edad de los Castillos · 15:55»."""
    return "   ◆   ".join((t(f"nivel_{guia.get('nivel', 'media')}"), t("n_pasos", n=len(guia["pasos"])),
                           t("meta_a", meta=de(guia["pasos"][-1], "titulo"), hora=reloj(guia["pasos"][-1]["referencia"]))))


def nombre_tarjeta(texto: str, tam: float = 12.5) -> QLabel:
    """Nombre de una guía, un mapa o un mod (Cinzel)."""
    lab = QLabel(texto)
    lab.setFont(titulo(tam, 0.3))
    lab.setStyleSheet(f"color: {TEXTO.name()};")
    return lab


def titulo_seccion(texto: str) -> QLabel:
    lab = QLabel(texto)
    lab.setFont(titulo(11.5, 0.5))
    lab.setStyleSheet(f"color: {TEXTO.name()};")
    return lab


def limpiar(capa):
    """Quita todos los widgets de un layout."""
    while capa.count():
        item = capa.takeAt(0)
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        elif item.layout() is not None:
            limpiar(item.layout())


# --- Ventana ------------------------------------------------------------------


class Panel(QWidget):
    def __init__(self, config: dict, historial: Historial, guias: dict[str, dict], instalador: I.Instalador,
                 overlay=None, icono: QIcon | None = None, al_salir=None, al_ocultar=None,
                 guardar_config=None, comprobar_juego: bool = True, perfiles: list | None = None,
                 al_cambiar_perfil=None, preguntar_perfil: bool = False, fuente_catalogo: str | None = None,
                 segundo_plano: bool = True, al_cambiar_guias=None):
        super().__init__(None, Qt.WindowType.Window)
        # Catálogo: la última copia guardada ya, y el actual en segundo plano al mostrar el panel.
        # fuente_catalogo=None no descarga nada (pruebas y capturas).
        self.fuente_catalogo = fuente_catalogo
        self.segundo_plano = segundo_plano  # False: las descargas se hacen en el acto (pruebas)
        self.al_cambiar_guias = al_cambiar_guias or (lambda guias: None)
        if instalador.catalogo is None:
            instalador.catalogo = K.cargar_copia(instalador.contenido)
        self.estado_catalogo = ("copia", "") if instalador.catalogo else ("nunca", "")
        self.descargando: set[tuple[str, str]] = set()
        # Actualización de la app (GitHub Releases): solo la app instalada y con catálogo real.
        self.actualizacion: A.Actualizacion | None = None
        self.estado_actualizacion = ("sin_buscar" if fuente_catalogo is not None and A.buscar_activa()
                                     else "desde_codigo", "")
        self._progreso_act = 0
        self._trabajos: set = set()
        self._primera_vez = True
        self.perfiles: list[rutas.Perfil] = perfiles or []  # carpetas de perfil encontradas (rutas.py)
        self.al_cambiar_perfil = al_cambiar_perfil or (lambda carpeta: None)
        self._preguntar_perfil = preguntar_perfil  # se pregunta la primera vez que se muestra
        self.config = config
        self.historial = historial
        self.guias = guias
        self.instalador = instalador
        self.overlay = overlay  # para saber si hay partida en curso (puede ser None)
        self.al_salir = al_salir or (lambda: None)
        self.al_ocultar = al_ocultar or (lambda: None)  # se llama la primera vez que la ✕ lo esconde
        self.guardar_config = guardar_config or (lambda: C.guardar(self.config))
        self.comprobar_juego = comprobar_juego
        self.juego = False
        self._ultima_comprobacion = 0.0
        self._firma = None
        self._mensaje_hasta = 0.0
        self.pagina = "inicio"
        textos.poner_idioma(config.get("idioma", "es"))
        cargar_fuentes()
        if icono:
            self.setWindowIcon(icono)
        self.setWindowTitle("AoE2 Coaching")
        self.setMinimumSize(1060, 700)
        self.resize(1240, 800)
        self.setStyleSheet(ESTILO)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setObjectName("raiz")
        self.capa = QHBoxLayout(self)
        self.capa.setContentsMargins(0, 0, 0, 0)
        self.capa.setSpacing(0)
        self.construir()
        self.temporizador = QTimer(self, interval=1000, timeout=self.tick)

    # --- Construcción ---
    def construir(self):
        limpiar(self.capa)
        self.capa.addWidget(self._lateral())
        derecha = QWidget()
        dc = QVBoxLayout(derecha)
        dc.setContentsMargins(36, 28, 36, 24)
        dc.setSpacing(0)
        cab = QHBoxLayout()
        textos_cab = QVBoxLayout()
        textos_cab.setSpacing(4)
        self.titulo = QLabel("")
        self.titulo.setFont(titulo(21, 0.6))
        self.titulo.setStyleSheet(f"color: {TEXTO.name()};")
        self.subtitulo = etiqueta("", 10, QFont.Weight.Normal, SECUNDARIO)
        textos_cab.addWidget(self.titulo)
        textos_cab.addWidget(self.subtitulo)
        cab.addLayout(textos_cab, 1)
        self.mensaje = pastilla("", BIEN)
        self.mensaje.hide()
        cab.addWidget(self.mensaje, 0, Qt.AlignmentFlag.AlignVCenter)
        cab.addSpacing(12)
        self.boton_jugar = boton(t("jugar"), self.jugar, "primario")
        self.boton_jugar.setMinimumWidth(150)
        cab.addWidget(self.boton_jugar, 0, Qt.AlignmentFlag.AlignVCenter)
        dc.addLayout(cab)
        dc.addSpacing(18)
        dc.addWidget(Filete())
        dc.addSpacing(20)
        self.paginas = QStackedWidget()
        self.p_inicio = PaginaInicio(self)
        self.p_estadisticas = PaginaEstadisticas(self)
        self.p_guias = PaginaGuias(self)
        self.p_mapas = PaginaMapas(self)
        self.p_mods = PaginaMods(self)
        self.p_ajustes = PaginaAjustes(self)
        for pag in (self.p_inicio, self.p_estadisticas, self.p_guias, self.p_mapas, self.p_mods, self.p_ajustes):
            self.paginas.addWidget(pag)
        dc.addWidget(self.paginas, 1)
        self.capa.addWidget(derecha, 1)
        self.ir(self.pagina)

    def _lateral(self) -> QWidget:
        lat = QWidget()
        lat.setObjectName("lateral")
        lat.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        lat.setFixedWidth(232)
        lc = QVBoxLayout(lat)
        lc.setContentsMargins(16, 26, 16, 20)
        lc.setSpacing(2)
        marca = QHBoxLayout()
        marca.setContentsMargins(4, 0, 0, 0)
        marca.setSpacing(10)
        logo = QLabel()
        icono = self.windowIcon()
        if not icono.isNull():
            logo.setPixmap(icono.pixmap(38, 38))
        marca.addWidget(logo)
        nombres = QVBoxLayout()
        nombres.setSpacing(1)
        nombre_app = QLabel("AoE2 Coaching")
        nombre_app.setFont(titulo(11.5, 0.4))
        nombre_app.setStyleSheet(f"color: {ORO_CLARO.name()};")
        nombres.addWidget(nombre_app)
        nombres.addWidget(etiqueta(t("lema"), 8.5, QFont.Weight.Medium, APAGADO))
        marca.addLayout(nombres, 1)
        lc.addLayout(marca)
        lc.addSpacing(30)
        self.grupo = QButtonGroup(self)
        self.grupo.setExclusive(True)
        self.botones_lateral = {}
        for nombre in PAGINAS:
            b = BotonLateral(nombre, t(f"pagina_{nombre}"))
            b.clicked.connect(lambda _=False, n=nombre: self.ir(n))
            self.grupo.addButton(b)
            self.botones_lateral[nombre] = b
            lc.addWidget(b)
        lc.addStretch(1)
        # Versión nueva disponible (se muestra al encontrarla).
        self.boton_actualizar = boton("", self.actualizar_app, "primario", t("act_boton_consejo"))
        self.boton_actualizar.hide()
        lc.addWidget(self.boton_actualizar)
        lc.addSpacing(10)
        self._mostrar_actualizacion()
        # Estado del juego.
        estado = QHBoxLayout()
        estado.setSpacing(8)
        self.punto = PuntoEstado()
        estado.addWidget(self.punto)
        self.texto_estado = etiqueta("", 8.5, QFont.Weight.DemiBold, SECUNDARIO, envolver=True)
        estado.addWidget(self.texto_estado, 1)
        lc.addLayout(estado)
        lc.addSpacing(14)
        salir = boton("⏻   " + t("cerrar_programa"), self.al_salir, "salir", t("cerrar_programa_consejo"))
        lc.addWidget(salir)
        lc.addSpacing(6)
        lc.addWidget(etiqueta(f"v{VERSION} · " + t("x_esconde"), 7.5, QFont.Weight.Medium, APAGADO, envolver=True))
        return lat

    # --- Navegación ---
    def ir(self, nombre: str):
        self.pagina = nombre
        self.botones_lateral[nombre].setChecked(True)
        pag = {"inicio": self.p_inicio, "estadisticas": self.p_estadisticas, "guias": self.p_guias,
               "mapas": self.p_mapas, "mods": self.p_mods, "ajustes": self.p_ajustes}[nombre]
        self.paginas.setCurrentWidget(pag)
        self.titulo.setText(t(f"pagina_{nombre}"))
        self.subtitulo.setText(t(f"sub_{nombre}"))
        pag.refrescar()
        self.actualizar_estado(forzar=True)

    def ver_partida(self, registro: dict):
        self.ir("estadisticas")
        self.p_estadisticas.elegir_guia(registro["guia"])
        self.p_estadisticas.contenido.elegir(registro["id"])

    def ver_estadisticas(self, nombre_guia: str | None):
        self.ir("estadisticas")
        if nombre_guia:
            self.p_estadisticas.elegir_guia(nombre_guia)

    def avisar(self, texto: str, c: QColor = BIEN):
        """Mensaje breve junto al título (por ejemplo, «Guía activada»)."""
        self.mensaje.setText(texto)
        self.mensaje.setStyleSheet(f"color: {c.name()}; background: {rgba(c, 22)}; border: 1px solid {rgba(c, 80)}; "
                                   "border-radius: 3px; padding: 4px 10px;")
        self.mensaje.show()
        self._mensaje_hasta = time.monotonic() + 4

    # --- Datos ---
    def guia_activa(self) -> dict | None:
        return self.guias.get(self.config.get("guia_activa")) or next(iter(self.guias.values()), None)

    def nombre_guia(self, id_: str) -> str:
        g = self.guias.get(id_)
        if g:
            return g["nombre"]
        e = self.instalador.catalogo.buscar("guia", id_) if self.instalador.catalogo else None
        return e.texto("nombre", textos.idioma()) if e else id_

    def descripcion(self, guia: dict) -> str:
        return guia.get("descripcion_en" if textos.idioma() == "en" else "descripcion") or guia.get("descripcion", "")

    def usar_guia(self, id_: str, aviso: bool = True):
        guia = self.guias.get(id_)
        if not guia:
            return
        error = self.instalador.activar_guia(guia)
        self.config["guia_activa"] = id_
        self.guardar_config()
        if error:
            self.avisar(t("guia_error", error=error), MAL)
        elif aviso:
            self.avisar(t("guia_activada", nombre=guia["nombre"]))
        self.paginas.currentWidget().refrescar()

    # --- Catálogo ---
    def en_segundo_plano(self, funcion, al_terminar):
        """Ejecuta funcion() fuera de la ventana (descargas) y llama a al_terminar(resultado,
        error) en el hilo de la ventana."""
        if not self.segundo_plano:
            try:
                resultado, error = funcion(), None
            except Exception as e:  # noqa: BLE001 - se muestra en el panel
                resultado, error = None, e
            al_terminar(resultado, error)
            return
        trabajo = Trabajo(al_terminar, self._trabajos.discard)
        self._trabajos.add(trabajo)
        threading.Thread(target=trabajo.ejecutar, args=(funcion,), daemon=True).start()

    def actualizar_catalogo(self):
        if self.fuente_catalogo is None or self.estado_catalogo[0] == "buscando":
            return
        self.estado_catalogo = ("buscando", "")
        self.refrescar_contenido()
        fuente = self.fuente_catalogo

        def listo(resultado, error):
            if error is not None:
                logging.getLogger("aoe2c").warning("catálogo: %s", error)
                self.estado_catalogo = ("sin_conexion" if self.instalador.catalogo else "nunca", str(error))
            else:
                cat, datos = resultado
                K.guardar_copia(datos, cat.origen, self.instalador.contenido)
                self.instalador.catalogo = cat
                self.estado_catalogo = ("al_dia", "")
                self.reparar_mapas()
            self.refrescar_contenido()

        self.en_segundo_plano(lambda: K.descargar(fuente), listo)

    # --- Actualización de la app ---
    def buscar_actualizacion(self):
        if self.estado_actualizacion[0] in ("desde_codigo", "buscando", "descargando"):
            return
        self.estado_actualizacion = ("buscando", "")
        self._refrescar_actualizacion()

        def listo(resultado, error):
            if error is not None:
                logging.getLogger("aoe2c").warning("actualización: %s", error)
                self.estado_actualizacion = ("error", str(error))
            else:
                self.actualizacion = resultado
                self.estado_actualizacion = ("disponible" if resultado else "al_dia", "")
            self._refrescar_actualizacion()

        self.en_segundo_plano(A.buscar, listo)

    def actualizar_app(self):
        """Descarga el instalador de la versión nueva, lo abre en silencio y cierra AoE2C
        (el instalador pone la versión nueva y la vuelve a abrir)."""
        a = self.actualizacion
        if a is None or self.estado_actualizacion[0] == "descargando":
            return
        if self.overlay is not None and getattr(self.overlay, "en_partida", False):
            self.avisar(t("act_en_partida"), ATENCION)
            return
        self.estado_actualizacion = ("descargando", "")
        self._progreso_act = 0
        self._refrescar_actualizacion()

        def progreso(bajado, total):
            self._progreso_act = int(100 * bajado / total) if total else 0  # lo pinta tick()

        def listo(instalador, error):
            if error is None:
                try:
                    A.lanzar(instalador)
                except OSError as e:
                    error = e
            if error is not None:
                logging.getLogger("aoe2c").warning("no se pudo actualizar a %s: %s", a.version, error)
                self.estado_actualizacion = ("disponible", "")
                self.avisar(t("act_fallo", error=error), MAL)
                self._refrescar_actualizacion()
                return
            logging.getLogger("aoe2c").info("actualizando a la versión %s", a.version)
            self.al_salir()

        self.en_segundo_plano(lambda: A.descargar(a, progreso=progreso), listo)

    def texto_actualizacion(self) -> str:
        estado, error = self.estado_actualizacion
        nueva = self.actualizacion.version if self.actualizacion else ""
        return t(f"act_{estado}", version=VERSION, nueva=nueva, error=error, porcentaje=self._progreso_act)

    def _mostrar_actualizacion(self):
        estado = self.estado_actualizacion[0]
        b = self.boton_actualizar
        if estado in ("disponible", "descargando") and self.actualizacion:
            b.setText(t("act_boton_lateral", nueva=self.actualizacion.version) if estado == "disponible"
                      else f"{self._progreso_act}%")
            b.setEnabled(estado == "disponible")
            b.show()
        else:
            b.hide()

    def _refrescar_actualizacion(self):
        self._mostrar_actualizacion()
        if self.pagina == "ajustes":
            self.p_ajustes.refrescar()

    def refrescar_contenido(self):
        if self.pagina in ("guias", "mapas", "mods"):
            self.paginas.currentWidget().refrescar()

    def reparar_mapas(self):
        """Vuelve a armar los mapas instalados si el juego actualizó el oficial."""
        reparados = self.instalador.reparar_mapas()
        if reparados:
            self.avisar(t("mapas_reparados", mapas=", ".join(reparados)))

    def recargar_guias(self):
        self.guias = self.instalador.guias()
        self.al_cambiar_guias(self.guias)

    def instalar_elemento(self, e: K.Elemento):
        """Descarga el paquete de una guía o un mod (comprobando su hash) y lo instala."""
        cat = self.instalador.catalogo
        if cat is None or (e.tipo, e.id) in self.descargando:
            return
        if not e.compatible():
            self.avisar(t("necesita_app_consejo", version=VERSION, minima=e.app_minima), MAL)
            return
        nombre = e.texto("nombre", textos.idioma())
        if e.tipo == "mod" and self.juego and self.instalador.mods_locales is not None \
                and (self.instalador.mods_locales / e.datos["carpeta"]).exists():
            self.avisar(t("mod_cerrar_juego", nombre=nombre), ATENCION)
            return
        actualizando = e.tipo == "guia" and e.id in self.guias
        self.descargando.add((e.tipo, e.id))
        self.refrescar_contenido()
        carpeta = self.instalador.descargas

        def listo(paquete, error):
            self.descargando.discard((e.tipo, e.id))
            if error is None:
                try:
                    error = (self.instalador.instalar_guia(e, paquete) if e.tipo == "guia"
                             else self.instalador.instalar_mod(e, paquete, self.juego))
                finally:
                    paquete.unlink(missing_ok=True)
            if error is not None:
                logging.getLogger("aoe2c").warning("no se pudo instalar %s %s: %s", e.tipo, e.id, error)
                self.avisar(t("descarga_error", error=error), MAL)
            elif e.tipo == "guia":
                self.recargar_guias()
                activa = self.config.get("guia_activa")
                if e.id == activa or activa not in self.guias or self.instalador.guia_instalada(self.guias) is None:
                    self.usar_guia(e.id, aviso=False)  # la primera guía, o la activa recién actualizada
                self.avisar(t("guia_actualizada_ok", nombre=nombre, version=e.version) if actualizando
                            else t("guia_instalada_ok", nombre=nombre))
            else:
                self.avisar(t("mod_instalado_ok", nombre=nombre))
                self.aplicar_pendientes()
            self.refrescar_contenido()

        self.en_segundo_plano(lambda: K.descargar_paquete(cat, e, carpeta), listo)

    def quitar_guia(self, guia: dict):
        error = self.instalador.quitar_guia(guia)
        self.recargar_guias()
        self.avisar(t("descarga_error", error=error) if error else t("guia_quitada", nombre=guia["nombre"]),
                    MAL if error else APAGADO)
        self.refrescar_contenido()

    def quitar_mod(self, e: K.Elemento):
        nombre = e.texto("nombre", textos.idioma())
        error = self.instalador.quitar_mod(e, self.juego)
        if error == I.JUEGO_ABIERTO:
            self.avisar(t("mod_cerrar_juego", nombre=nombre), ATENCION)
        elif error:
            self.avisar(t("mod_activar_error", mods=nombre, error=error), MAL)
        else:
            self.avisar(t("mod_quitado", nombre=nombre), APAGADO)
        self.refrescar_contenido()

    def activar_mod(self, e: K.Elemento):
        self.instalador.activar_mod(e.datos["carpeta"], e.datos["titulo"], juego_abierto=True)  # solo lo deja pendiente
        self.aplicar_pendientes()
        self.refrescar_contenido()

    def aplicar_pendientes(self):
        """Activa en mod-status.json lo pendiente, si el juego está cerrado."""
        pendientes = self.instalador.pendientes()
        if self.juego or not pendientes:
            return
        aplicados, error = self.instalador.aplicar_pendientes(False)
        activados = [p["titulo"] for p in aplicados if p["accion"] == "activar"]
        if error:
            logging.getLogger("aoe2c").warning("mod-status.json: %s", error)
            self.avisar(t("mod_activar_error", mods=", ".join(p["titulo"] for p in pendientes), error=error), MAL)
        elif activados:
            self.avisar(t("mod_activado", mods=", ".join(activados)))
        self.refrescar_contenido()

    def firma_historial(self):
        r = self.historial.registros
        return len(r), r[-1]["id"] if r else None, r[-1]["duracion"] if r else None

    # --- Estado del juego ---
    def en_partida(self) -> tuple[bool, str]:
        o = self.overlay
        if o is not None and getattr(o, "en_partida", False) and getattr(o, "vista", None) is not None:
            v = o.vista
            if v.terminada:
                return True, t("estado_partida_fin", guia=v.nombre)
            return True, t("estado_partida", guia=v.nombre, paso=v.paso + 1, total=v.total)
        return False, ""

    def actualizar_estado(self, forzar: bool = False):
        ahora = time.monotonic()
        if self.comprobar_juego and (forzar or ahora - self._ultima_comprobacion > 3):
            self._ultima_comprobacion = ahora
            self.juego = I.juego_abierto()
            if not self.juego and self.instalador.pendientes():
                self.aplicar_pendientes()  # lo que esperaba a que se cerrara el juego
        jugando, texto = self.en_partida()
        if jugando:
            c = BIEN
        elif self.juego:
            c, texto = ACENTO, t("estado_juego_abierto")
        else:
            c, texto = APAGADO, t("estado_juego_cerrado")
        self.punto.poner(c)
        self.texto_estado.setText(texto)
        self.boton_jugar.setEnabled(not self.juego and not jugando and self.instalador.juego_instalado())
        self.boton_jugar.setText(t("jugando") if (self.juego or jugando) else t("jugar"))
        if self.mensaje.isVisible() and ahora > self._mensaje_hasta:
            self.mensaje.hide()

    def jugar(self):
        try:
            I.abrir_juego()
            self.avisar(t("abriendo_juego"), ACENTO)
        except OSError as e:
            self.avisar(str(e), MAL)

    def tick(self):
        self.actualizar_estado()
        if self.estado_actualizacion[0] == "descargando":
            self._mostrar_actualizacion()  # el porcentaje de la descarga
        firma = self.firma_historial()
        if firma != self._firma:
            self._firma = firma
            if self.pagina in ("inicio", "estadisticas"):
                self.paginas.currentWidget().refrescar()
        elif self.pagina == "inicio":
            self.p_inicio.refrescar_estado()

    # --- Idioma ---
    def cambiar_idioma(self, idioma: str):
        if idioma == self.config.get("idioma"):
            return
        self.config["idioma"] = idioma
        self.guardar_config()
        textos.poner_idioma(idioma)
        self.construir()

    # --- Ventana ---
    def mostrar(self):
        self.historial.cargar()
        self._firma = None
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()
        self.tick()
        self.temporizador.start()
        if self._primera_vez:
            self._primera_vez = False
            self.reparar_mapas()
            self.actualizar_catalogo()
            self.buscar_actualizacion()
        if self._preguntar_perfil:
            self._preguntar_perfil = False
            QTimer.singleShot(250, self.pedir_perfil)

    # --- Carpetas ---
    def cambiar_perfil(self, carpeta: Path):
        self.instalador.perfil = Path(carpeta)
        repeticiones.poner_perfil(Path(carpeta))
        self.config["perfil"] = str(carpeta)
        self.guardar_config()
        self.al_cambiar_perfil(Path(carpeta))
        self.construir()
        self.avisar(t("perfil_cambiado"))

    def cambiar_juego(self, carpeta: Path) -> bool:
        if not rutas.es_carpeta_juego(Path(carpeta)):
            self.avisar(t("juego_no_valido"), MAL)
            return False
        self.instalador.juego = Path(carpeta)
        self.config["juego"] = str(carpeta)
        self.guardar_config()
        self.construir()
        self.avisar(t("juego_cambiado"))
        return True

    def pedir_perfil(self):
        """Ventana para elegir entre varias carpetas de perfil con uso."""
        if len(self.perfiles) < 2:
            return
        dialogo = QDialog(self)
        dialogo.setWindowTitle("AoE2 Coaching")
        dialogo.setStyleSheet(ESTILO + f" QDialog {{ background: {FONDO_PANEL}; }}"
                              f" QRadioButton {{ color: {TEXTO.name()}; padding: 6px 0; }}")
        capa = QVBoxLayout(dialogo)
        capa.setContentsMargins(28, 24, 28, 24)
        capa.setSpacing(12)
        capa.addWidget(etiqueta(t("perfil_titulo"), 14, QFont.Weight.Bold, envolver=True))
        capa.addWidget(etiqueta(t("perfil_texto"), 9.5, QFont.Weight.Normal, SECUNDARIO, envolver=True))
        grupo = QButtonGroup(dialogo)
        actual = self.instalador.perfil
        for i, p in enumerate(self.perfiles):
            r = QRadioButton(nombre_perfil(p))
            r.setFont(fuente(10, QFont.Weight.Medium))
            r.setChecked(p.carpeta == actual if actual else i == 0)
            grupo.addButton(r, i)
            capa.addWidget(r)
        b = boton(t("usar_perfil"), dialogo.accept, "primario")
        capa.addWidget(b, 0, Qt.AlignmentFlag.AlignRight)
        dialogo.setMinimumWidth(620)
        if dialogo.exec() and grupo.checkedId() >= 0:
            self.cambiar_perfil(self.perfiles[grupo.checkedId()].carpeta)

    def showEvent(self, e):
        super().showEvent(e)
        barra_oscura(self)
        self.temporizador.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.temporizador.stop()

    def closeEvent(self, e):
        # La ✕ no cierra el programa: lo deja en la bandeja.
        e.ignore()
        self.hide()
        if not self.config.get("aviso_bandeja_visto"):
            self.config["aviso_bandeja_visto"] = True
            self.guardar_config()
            self.al_ocultar()


def barra_oscura(w: QWidget):
    """Barra de título de Windows oscura y del mismo color que el panel (Windows 10/11)."""
    try:
        import ctypes
        hwnd = int(w.winId())
        dwm = ctypes.windll.dwmapi
        si = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(si), ctypes.sizeof(si))  # modo oscuro
        fondo = QColor(FONDO_PANEL)
        colorref = ctypes.c_int(fondo.red() | fondo.green() << 8 | fondo.blue() << 16)
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(colorref), ctypes.sizeof(colorref))  # color de la barra
    except (OSError, AttributeError, ValueError):
        pass


# --- Páginas ------------------------------------------------------------------


class Pagina(QWidget):
    def __init__(self, panel: Panel, desplazar: bool = True):
        super().__init__()
        self.panel = panel
        externa = QVBoxLayout(self)
        externa.setContentsMargins(0, 0, 0, 0)
        cuerpo = QWidget()
        self.capa = QVBoxLayout(cuerpo)
        self.capa.setContentsMargins(0, 0, 12 if desplazar else 0, 8)
        self.capa.setSpacing(16)
        externa.addWidget(desplazable(cuerpo) if desplazar else cuerpo)

    def refrescar(self):
        pass


class PaginaInicio(Pagina):
    def __init__(self, panel: Panel):
        super().__init__(panel)
        arriba = QHBoxLayout()
        arriba.setSpacing(16)

        # Guía activa: la tarjeta destacada (escuadras doradas en las esquinas).
        self.tarjeta_guia = Tarjeta(ACENTO, margen=26)
        tg = self.tarjeta_guia.capa
        tg.setSpacing(10)
        cab = QHBoxLayout()
        cab.setSpacing(20)
        self.emblema = Emblema("FC", 76)
        cab.addWidget(self.emblema, 0, Qt.AlignmentFlag.AlignTop)
        tx = QVBoxLayout()
        tx.setSpacing(5)
        tx.addWidget(rotulo(t("guia_activa"), ACENTO))
        self.nombre_guia = QLabel("")
        self.nombre_guia.setFont(titulo(19, 0.4))
        tx.addWidget(self.nombre_guia)
        self.desc_guia = etiqueta("", 10, QFont.Weight.Normal, SECUNDARIO, envolver=True)
        tx.addWidget(self.desc_guia)
        tx.addSpacing(2)
        self.meta_guia = meta()
        self.meta_guia.setStyleSheet(f"color: {APAGADO.name()};")
        tx.addWidget(self.meta_guia)
        cab.addLayout(tx, 1)
        tg.addLayout(cab)
        self.aviso_guia = etiqueta("", 9, QFont.Weight.DemiBold, ATENCION, envolver=True)
        self.aviso_guia.setStyleSheet(f"color: {ATENCION.name()}; background: {rgba(ATENCION, 16)}; "
                                      f"border-left: 2px solid {ATENCION.name()}; padding: 6px 10px;")
        tg.addWidget(self.aviso_guia)
        tg.addStretch(1)
        tg.addLayout(fila(boton(t("cambiar_guia"), lambda: panel.ir("guias"), "primario"),
                          boton(t("ver_estadisticas"), lambda: panel.ver_estadisticas(
                              (panel.guia_activa() or {}).get("nombre")))))
        arriba.addWidget(self.tarjeta_guia, 3)

        # Estado del juego.
        self.tarjeta_estado = Tarjeta(margen=24)
        te = self.tarjeta_estado.capa
        te.setSpacing(10)
        te.addWidget(rotulo(t("estado")))
        filae = QHBoxLayout()
        filae.setSpacing(10)
        self.punto = PuntoEstado()
        filae.addWidget(self.punto, 0, Qt.AlignmentFlag.AlignVCenter)
        self.titulo_estado = etiqueta("", 13, QFont.Weight.DemiBold, envolver=True)
        filae.addWidget(self.titulo_estado, 1)
        te.addLayout(filae)
        self.texto_estado = etiqueta("", 9.5, QFont.Weight.Normal, SECUNDARIO, envolver=True)
        te.addWidget(self.texto_estado)
        te.addStretch(1)
        arriba.addWidget(self.tarjeta_estado, 2)
        self.capa.addLayout(arriba)

        # Números con la guía activa: una sola caja con cuatro columnas.
        self.capa.addSpacing(8)
        self.titulo_numeros = QLabel("")
        self.titulo_numeros.setFont(titulo(11.5, 0.5))
        self.titulo_numeros.setStyleSheet(f"color: {TEXTO.name()};")
        self.capa.addWidget(self.titulo_numeros)
        self.d_partidas = Dato(t("dato_partidas"))
        self.d_mejor = Dato(t("dato_mejor"))
        self.d_media = Dato(t("dato_media"))
        self.d_completadas = Dato(t("dato_completadas"))
        self.capa.addWidget(Libro([self.d_partidas, self.d_mejor, self.d_media, self.d_completadas]))
        self.capa.addSpacing(8)

        abajo = QHBoxLayout()
        abajo.setSpacing(16)
        # Última partida.
        self.tarjeta_ultima = Tarjeta(margen=22)
        tu = self.tarjeta_ultima.capa
        tu.addWidget(rotulo(t("ultima_partida")))
        tu.addSpacing(2)
        self.ultima_titulo = etiqueta("", 13, QFont.Weight.DemiBold, envolver=True)
        tu.addWidget(self.ultima_titulo)
        self.ultima_detalle = etiqueta("", 9.5, QFont.Weight.Normal, SECUNDARIO, envolver=True)
        tu.addWidget(self.ultima_detalle)
        tu.addStretch(1)
        self.boton_ultima = boton(t("ver_detalle"), self._ver_ultima, "enlace")
        tu.addWidget(self.boton_ultima, 0, Qt.AlignmentFlag.AlignLeft)
        abajo.addWidget(self.tarjeta_ultima, 1)
        # Cómo jugar: pasos numerados con números romanos.
        como = Tarjeta(margen=22)
        como.capa.setSpacing(10)
        como.capa.addWidget(rotulo(t("como_jugar")))
        for n in range(1, 4):
            f = QHBoxLayout()
            f.setSpacing(12)
            num = QLabel(ROMANOS[n - 1])
            num.setFont(titulo(11))
            num.setStyleSheet(f"color: {ACENTO.name()};")
            num.setFixedWidth(26)
            num.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            f.addWidget(num, 0, Qt.AlignmentFlag.AlignTop)
            f.addWidget(etiqueta(t(f"como_{n}"), 9.5, QFont.Weight.Normal, SECUNDARIO, envolver=True), 1)
            como.capa.addLayout(f)
        como.capa.addStretch(1)
        abajo.addWidget(como, 1)
        self.capa.addLayout(abajo)
        self.capa.addStretch(1)
        self.ultima: dict | None = None

    def refrescar(self):
        panel = self.panel
        guia = panel.guia_activa()
        if guia:
            self.emblema.emoji = monograma(guia.get("id"), guia["nombre"])
            self.emblema.update()
            self.nombre_guia.setText(guia["nombre"])
            self.desc_guia.setText(panel.descripcion(guia))
            self.meta_guia.setText(datos_guia(guia))
            self.meta_guia.show()
            instalada = panel.instalador.guia_instalada(panel.guias)
            if instalada != guia.get("id"):
                self.aviso_guia.setText(t("guia_pendiente"))
                self.aviso_guia.show()
            else:
                self.aviso_guia.hide()
        else:  # aún no hay ninguna guía instalada
            self.emblema.emoji = "?"
            self.emblema.update()
            self.nombre_guia.setText(t("sin_guia"))
            self.desc_guia.setText(t("sin_guia_texto"))
            self.meta_guia.hide()
            self.aviso_guia.hide()
        self.refrescar_estado()
        self._numeros(guia)
        self._ultima()

    def refrescar_estado(self):
        panel = self.panel
        jugando, texto = panel.en_partida()
        if jugando:
            self.punto.poner(BIEN)
            self.titulo_estado.setText(t("estado_titulo_partida"))
            self.texto_estado.setText(texto)
        elif panel.juego:
            self.punto.poner(ACENTO)
            self.titulo_estado.setText(t("estado_titulo_abierto"))
            self.texto_estado.setText(t("estado_texto_abierto"))
        else:
            self.punto.poner(APAGADO)
            self.titulo_estado.setText(t("estado_titulo_cerrado"))
            self.texto_estado.setText(t("estado_texto_cerrado"))

    def _numeros(self, guia: dict | None):
        nombre = guia["nombre"] if guia else None
        regs = self.panel.historial.de_guia(nombre) if nombre else []
        self.titulo_numeros.setText(t("tus_numeros", guia=nombre or "—"))
        vista = vista_de_guia(guia) if guia else {"principal": "castillos", "nombre_meta": ""}
        clave = vista["principal"]
        etiqueta_hito = de(vista, "nombre_meta") if clave == "meta" else t(f"hito_{clave}")
        res = resumen_hito(regs, clave)
        semana = sum(1 for r in regs if r["fecha"] >= time.strftime("%Y-%m-%d", time.localtime(time.time() - 7 * 86400)))
        self.d_partidas.poner(str(len(regs)), t("esta_semana", n=semana) if regs else t("sin_partidas_aun"))
        self.d_mejor.nombre = t("dato_mejor_de", hito=etiqueta_hito)
        self.d_mejor.poner(reloj(res["mejor"]) if res["mejor"] is not None else "—",
                           t("referencia_a", hora=reloj(guia["pasos"][-1]["referencia"])) if guia else "")
        if res["media"] is not None:
            detalle, c = (t("vs_anteriores", dif=desfase(res["media"] - res["media_anterior"])[0]),
                          desfase(res["media"] - res["media_anterior"])[1]) if res["media_anterior"] is not None \
                else (t("ultimas_n", n=min(10, res["cuenta"])), APAGADO)
            self.d_media.poner(reloj(res["media"]), detalle, c)
        else:
            self.d_media.poner("—", t("sin_datos"))
        completas = sum(1 for r in regs if r.get("completada"))
        self.d_completadas.poner(f"{round(100 * completas / len(regs))}%" if regs else "—",
                                 t("completadas_de", n=completas, total=len(regs)) if regs else t("sin_datos"))

    def _ultima(self):
        regs = self.panel.historial.registros
        self.ultima = regs[-1] if regs else None
        if not self.ultima:
            self.ultima_titulo.setText(t("sin_partidas"))
            self.ultima_detalle.setText(t("sin_partidas_texto"))
            self.boton_ultima.hide()
            return
        r = self.ultima
        clave = principal(r)
        valor = valor_principal(r)
        self.ultima_titulo.setText(f"{r['guia']} · {mapa_corto(r['mapa'])}")
        partes = [fecha_corta(r["fecha"])]
        if valor is not None:
            partes.append(f"{nombre_hito(r, clave)} {reloj(valor)}")
            ref = r["referencias"].get(clave)
            if ref is not None:
                partes.append(t("vs_ref", dif=desfase(valor - ref)[0] or "±0 s"))
        else:
            partes.append(t("hasta_paso", n=pasos_hechos(r), total=len(r["pasos"])))
        self.ultima_detalle.setText(" · ".join(partes))
        self.boton_ultima.show()

    def _ver_ultima(self):
        if self.ultima:
            self.panel.ver_partida(self.ultima)


class PaginaEstadisticas(Pagina):
    def __init__(self, panel: Panel):
        super().__init__(panel, desplazar=False)
        self.chips = QHBoxLayout()
        self.chips.setSpacing(8)
        self.capa.addLayout(self.chips)
        self.contenido = ContenidoHistorial(panel.historial)
        self.capa.addWidget(self.contenido, 1)
        self.grupo = QButtonGroup(self)
        self.guia: str | None = None

    def elegir_guia(self, nombre: str | None):
        self.guia = nombre
        self.refrescar()

    def refrescar(self):
        panel = self.panel
        con_partidas = dict(panel.historial.guias())
        nombres = list(con_partidas) + [g["nombre"] for g in panel.guias.values() if g["nombre"] not in con_partidas]
        if self.guia not in nombres:
            self.guia = nombres[0] if nombres else None
        limpiar(self.chips)
        for b in self.grupo.buttons():
            self.grupo.removeButton(b)
        for nombre in nombres:
            n = con_partidas.get(nombre, 0)
            b = boton(f"{nombre}  ·  {n}", None, "chip")
            b.setCheckable(True)
            b.setChecked(nombre == self.guia)
            b.clicked.connect(lambda _=False, x=nombre: self.elegir_guia(x))
            self.grupo.addButton(b)
            self.chips.addWidget(b)
        self.chips.addStretch(1)
        self.contenido.mostrar_guia(self.guia)


def boton_descarga(panel: Panel, e: K.Elemento, texto: str) -> QPushButton:
    """Botón que descarga e instala una guía o un mod (o explica por qué no se puede)."""
    if (e.tipo, e.id) in panel.descargando:
        b = boton(t("descargando"), None, "primario")
        b.setEnabled(False)
    elif not e.compatible():
        b = boton(t("necesita_app"), None, "primario", t("necesita_app_consejo", version=VERSION, minima=e.app_minima))
        b.setEnabled(False)
    else:
        b = boton(texto, lambda: panel.instalar_elemento(e), "primario")
    return b


def barra_catalogo(panel: Panel) -> QHBoxLayout:
    """Estado del catálogo (al día, buscando, sin conexión) y el botón «Buscar novedades»."""
    estado, error = panel.estado_catalogo
    textos_estado = {"al_dia": (t("catalogo_al_dia"), BIEN), "buscando": (t("catalogo_buscando"), ACENTO),
                     "copia": (t("catalogo_copia"), APAGADO),
                     "sin_conexion": (t("catalogo_sin_conexion", error=error), ATENCION),
                     "nunca": (t("catalogo_nunca", error=error or "—"), ATENCION)}
    texto, c = textos_estado[estado]
    f = QHBoxLayout()
    f.setSpacing(10)
    f.addWidget(etiqueta(texto, 8.5, QFont.Weight.DemiBold, c, envolver=True), 1)
    if panel.fuente_catalogo is not None:
        b = boton(t("buscar_novedades"), panel.actualizar_catalogo)
        b.setEnabled(estado != "buscando")
        f.addWidget(b, 0, Qt.AlignmentFlag.AlignVCenter)
    return f


def rejilla_de(tarjetas: list[QWidget], columnas: int) -> QGridLayout:
    rejilla = QGridLayout()
    rejilla.setSpacing(16)
    for k, w in enumerate(tarjetas):
        rejilla.addWidget(w, k // columnas, k % columnas, Qt.AlignmentFlag.AlignTop)
    for c in range(columnas):
        rejilla.setColumnStretch(c, 1)
    return rejilla


class TarjetaGuia(Tarjeta):
    def __init__(self, panel: Panel, guia: dict, activa: bool, instalada: bool, nueva: K.Elemento | None = None):
        super().__init__(ACENTO if activa else None, color(ACENTO, 16) if activa else TARJETA, margen=20)
        self.panel = panel
        cab = QHBoxLayout()
        cab.setSpacing(14)
        cab.addWidget(Emblema(monograma(guia["id"], guia["nombre"]), 58), 0, Qt.AlignmentFlag.AlignTop)
        tx = QVBoxLayout()
        tx.setSpacing(3)
        nombre = QHBoxLayout()
        nombre.setSpacing(8)
        nombre.addWidget(nombre_tarjeta(guia["nombre"], 14))
        if activa:
            nombre.addWidget(pastilla("✓ " + t("activa"), BIEN))
        nombre.addStretch(1)
        tx.addLayout(nombre)
        tx.addWidget(etiqueta(panel.descripcion(guia), 9.5, QFont.Weight.Normal, SECUNDARIO, envolver=True))
        cab.addLayout(tx, 1)
        self.capa.addLayout(cab)
        version = panel.instalador.version_guia(guia["id"])
        self.capa.addWidget(meta(datos_guia(guia), f"v{version}" if version else ""))
        mapas = [m["nombre"] for m in panel.instalador.mapas() if m["id"] in guia.get("mapas_recomendados", [])]
        if mapas:
            self.capa.addWidget(etiqueta(t("mapas_recomendados", mapas=", ".join(mapas)), 9, QFont.Weight.Medium,
                                         APAGADO, envolver=True))
        # Pasos (plegables).
        self.pasos = etiqueta("\n".join(f"{i + 1:>2}.  {de(p, 'titulo')}  ·  {reloj(p['referencia'])}"
                                        for i, p in enumerate(guia["pasos"])), 9.5, QFont.Weight.Normal, SECUNDARIO)
        self.pasos.setStyleSheet(f"color: {SECUNDARIO.name()}; background: {rgba(TEXTO, 6)}; "
                                 f"border-left: 2px solid {rgba(ACENTO, 120)}; padding: 10px 14px;")
        self.pasos.hide()
        self.capa.addWidget(self.pasos)
        self.boton_pasos = boton(t("ver_pasos"), self.alternar_pasos)
        acciones = [self.boton_pasos]
        if activa and instalada:
            usar = boton(t("en_uso"), None, "primario")
            usar.setEnabled(False)
        elif activa:
            usar = boton(t("instalar_ahora"), lambda: panel.usar_guia(guia["id"]), "primario")
        else:
            usar = boton(t("usar_guia"), lambda: panel.usar_guia(guia["id"]), "primario")
        acciones.insert(0, usar)
        acciones.append(boton(t("ver_estadisticas"), lambda: panel.ver_estadisticas(guia["nombre"])))
        self.capa.addSpacing(4)
        self.capa.addLayout(fila(*acciones))
        extra = []
        if nueva is not None:
            extra.append(boton_descarga(panel, nueva, t("actualizar_a", version=nueva.version)))
        if not activa:
            extra.append(boton(t("quitar"), lambda: panel.quitar_guia(guia), consejo=t("quitar_guia_consejo")))
        if extra:
            self.capa.addLayout(fila(*extra))

    def alternar_pasos(self):
        self.pasos.setVisible(not self.pasos.isVisible())
        self.boton_pasos.setText(t("ocultar_pasos") if self.pasos.isVisible() else t("ver_pasos"))


class TarjetaDisponible(Tarjeta):
    """Una guía del catálogo que aún no está instalada."""

    def __init__(self, panel: Panel, e: K.Elemento):
        super().__init__(margen=20)
        idioma = textos.idioma()
        cab = QHBoxLayout()
        cab.setSpacing(14)
        cab.addWidget(Emblema(monograma(e.id, e.texto("nombre", idioma)), 52), 0, Qt.AlignmentFlag.AlignTop)
        tx = QVBoxLayout()
        tx.setSpacing(3)
        tx.addWidget(nombre_tarjeta(e.texto("nombre", idioma)))
        tx.addWidget(etiqueta(e.texto("descripcion", idioma), 9.5, QFont.Weight.Normal, SECUNDARIO, envolver=True))
        cab.addLayout(tx, 1)
        self.capa.addLayout(cab)
        self.capa.addWidget(meta(t(f"nivel_{e.datos.get('nivel', 'media')}"), f"v{e.version}"))
        mapas = [m["nombre"] for m in panel.instalador.mapas() if m["id"] in e.datos.get("mapas_recomendados", [])]
        if mapas:
            self.capa.addWidget(etiqueta(t("mapas_recomendados", mapas=", ".join(mapas)), 9, QFont.Weight.Medium,
                                         APAGADO, envolver=True))
        self.capa.addSpacing(4)
        self.capa.addLayout(fila(boton_descarga(panel, e, t("instalar"))))


class TarjetaProxima(Tarjeta):
    def __init__(self, id_: str, emoji: str):
        super().__init__(margen=18)
        cab = QHBoxLayout()
        cab.setSpacing(12)
        cab.addWidget(Emblema(emoji, 46, APAGADO, apagado=True), 0, Qt.AlignmentFlag.AlignTop)
        tx = QVBoxLayout()
        tx.setSpacing(2)
        tx.addLayout(fila(etiqueta(t(f"proxima_{id_}"), 11, QFont.Weight.Bold, SECUNDARIO),
                          pastilla(t("proximamente"), APAGADO), espacio=8))
        tx.addWidget(etiqueta(t(f"proxima_{id_}_desc"), 9, QFont.Weight.Normal, APAGADO, envolver=True))
        cab.addLayout(tx, 1)
        self.capa.addLayout(cab)


class PaginaGuias(Pagina):
    def refrescar(self):
        limpiar(self.capa)
        panel = self.panel
        cat = panel.instalador.catalogo
        activa = (panel.guia_activa() or {}).get("id")
        instalada = panel.instalador.guia_instalada(panel.guias)
        self.capa.addWidget(etiqueta(t("guias_intro"), 10, QFont.Weight.Normal, SECUNDARIO, envolver=True))
        self.capa.addLayout(barra_catalogo(panel))
        # Instaladas.
        if panel.guias:
            tarjetas = []
            for id_, guia in panel.guias.items():
                e = cat.buscar("guia", id_) if cat else None
                version = panel.instalador.version_guia(id_)
                nueva = e if e is not None and (version is None or K.mas_nueva(e.version, version)) else None
                tarjetas.append(TarjetaGuia(panel, guia, id_ == activa, id_ == instalada, nueva))
            self.capa.addLayout(rejilla_de(tarjetas, 2))
        else:
            self.capa.addWidget(etiqueta(t("guias_ninguna"), 10, QFont.Weight.DemiBold, ATENCION, envolver=True))
        # Del catálogo, sin instalar.
        disponibles = [e for e in (cat.de("guia") if cat else []) if e.id not in panel.guias]
        if disponibles:
            self.capa.addSpacing(6)
            self.capa.addWidget(titulo_seccion(t("guias_disponibles")))
            self.capa.addLayout(rejilla_de([TarjetaDisponible(panel, e) for e in disponibles], 2))
        proximas = [(i, emoji) for i, emoji in PROXIMAS if not (cat and cat.buscar("guia", i))]
        if proximas:
            self.capa.addSpacing(6)
            self.capa.addWidget(titulo_seccion(t("proximamente_titulo")))
            rejilla = rejilla_de([TarjetaProxima(i, emoji) for i, emoji in proximas], 2)
            rejilla.setSpacing(12)
            self.capa.addLayout(rejilla)
        self.capa.addStretch(1)


class TarjetaMapa(QFrame):
    ESTADOS = {"instalado": BIEN, "desactualizado": ATENCION, "no_instalado": APAGADO, "sin_juego": MAL,
               "necesita_app": MAL}

    def __init__(self, panel: Panel, em: I.EstadoMapa):
        super().__init__()
        self.panel, self.em = panel, em
        m = em.mapa
        idioma = textos.idioma()
        capa = QVBoxLayout(self)
        capa.setContentsMargins(1, 1, 1, 16)
        capa.setSpacing(8)
        capa.addWidget(ImagenMapa(em.imagen))
        cuerpo = QVBoxLayout()
        cuerpo.setContentsMargins(16, 4, 16, 0)
        cuerpo.setSpacing(6)
        cuerpo.addLayout(fila(nombre_tarjeta(m["nombres"].get(idioma, m["nombre"])),
                              pastilla(m["tipo"].get(idioma, m["tipo"]["es"]))))
        cuerpo.addWidget(etiqueta(m["descripcion"].get(idioma, m["descripcion"]["es"]), 9, QFont.Weight.Normal,
                                  SECUNDARIO, envolver=True))
        guias = ", ".join(panel.nombre_guia(g) for g in m.get("guias", []))
        if guias:
            cuerpo.addWidget(etiqueta(t("guias_recomendadas", guias=guias), 8.5, QFont.Weight.Medium, APAGADO,
                                      envolver=True))
        cuerpo.addWidget(etiqueta(Path(m["archivo"]).stem, 8.5, QFont.Weight.DemiBold, APAGADO))
        cuerpo.addStretch(1)
        estado = pastilla(("● " if em.estado == "instalado" else "") + t(f"mapa_{em.estado}"), self.ESTADOS[em.estado])
        acciones = []
        if em.estado in ("no_instalado", "desactualizado"):
            b = boton(t("instalar") if em.estado == "no_instalado" else t("actualizar"), self.instalar, "primario")
            if not panel.guias:
                b.setEnabled(False)
                b.setToolTip(t("mapa_sin_guia"))
            acciones.append(b)
        elif em.estado == "instalado":
            acciones.append(boton(t("quitar"), self.quitar))
        if em.estado in ("instalado", "desactualizado", "no_instalado"):
            acciones.append(boton("⤓", self.exportar, consejo=t("guardar_copia")))
        f = QHBoxLayout()
        f.setSpacing(8)
        f.addWidget(estado)
        f.addStretch(1)
        for a in acciones:
            f.addWidget(a)
        cuerpo.addLayout(f)
        capa.addLayout(cuerpo, 1)
        self.setMinimumHeight(360)

    def paintEvent(self, _):
        p = pintor(self)
        caja(p, QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), Tarjeta.RADIO, TARJETA, BORDE)
        p.end()

    def instalar(self):
        error = self.panel.instalador.instalar_mapa(self.em.mapa, self.panel.guia_activa())
        self.panel.avisar(t("mapa_error", error=error) if error else t("mapa_instalado_ok", mapa=self.em.mapa["nombre"]),
                          MAL if error else BIEN)
        self.panel.aplicar_pendientes()
        self.panel.p_mapas.refrescar()

    def quitar(self):
        error = self.panel.instalador.quitar_mapa(self.em.mapa)
        self.panel.avisar(t("mapa_error", error=error) if error else t("mapa_quitado", mapa=self.em.mapa["nombre"]),
                          MAL if error else APAGADO)
        self.panel.p_mapas.refrescar()

    def exportar(self):
        carpeta = QFileDialog.getExistingDirectory(self, t("guardar_copia"), str(Path.home() / "Downloads"))
        if not carpeta:
            return
        error = self.panel.instalador.exportar_mapa(self.em.mapa, Path(carpeta))
        self.panel.avisar(t("mapa_error", error=error) if error else t("mapa_guardado", carpeta=carpeta),
                          MAL if error else BIEN)


class PaginaMapas(Pagina):
    def refrescar(self):
        limpiar(self.capa)
        panel = self.panel
        estados = panel.instalador.estado_mapas()
        pendientes = [e for e in estados if e.estado in ("no_instalado", "desactualizado")]
        intro = QHBoxLayout()
        intro.addWidget(etiqueta(t("mapas_intro"), 10, QFont.Weight.Normal, SECUNDARIO, envolver=True), 1)
        todos = boton(t("instalar_todos", n=len(pendientes)), self.instalar_todos, "primario")
        todos.setVisible(bool(pendientes))
        todos.setEnabled(bool(panel.guias))
        if not panel.guias:
            todos.setToolTip(t("mapa_sin_guia"))
        intro.addWidget(todos, 0, Qt.AlignmentFlag.AlignTop)
        self.capa.addLayout(intro)
        self.capa.addLayout(barra_catalogo(panel))
        if not estados:
            self.capa.addWidget(etiqueta(t("mapas_sin_catalogo"), 10, QFont.Weight.DemiBold, ATENCION, envolver=True))
        elif not panel.guias:
            self.capa.addWidget(etiqueta(t("mapa_sin_guia"), 9.5, QFont.Weight.DemiBold, ATENCION, envolver=True))
        self.capa.addLayout(rejilla_de([TarjetaMapa(panel, em) for em in estados], 3))
        if estados:
            self.capa.addWidget(etiqueta(t("mapas_nota"), 9, QFont.Weight.Medium, APAGADO, envolver=True))
        self.capa.addStretch(1)

    def instalar_todos(self):
        panel = self.panel
        errores = [e for em in panel.instalador.estado_mapas() if em.estado in ("no_instalado", "desactualizado")
                   if (e := panel.instalador.instalar_mapa(em.mapa, panel.guia_activa()))]
        panel.avisar(t("mapa_error", error=errores[0]) if errores else t("mapas_todos_ok"), MAL if errores else BIEN)
        panel.aplicar_pendientes()
        self.refrescar()


class TarjetaMod(Tarjeta):
    ESTADOS = {"instalado": BIEN, "desactualizado": ATENCION, "no_instalado": APAGADO, "necesita_app": MAL}
    ACTIVACION = {"activo": BIEN, "pendiente": ATENCION, "desactivado": ATENCION, "sin_registrar": APAGADO}

    def __init__(self, panel: Panel, em: I.EstadoMod):
        super().__init__(margen=20)
        e = em.elemento
        idioma = textos.idioma()
        cab = QHBoxLayout()
        cab.setSpacing(14)
        cab.addWidget(Emblema(monograma(e.id, e.texto("nombre", idioma), ICONO_MOD), 52), 0, Qt.AlignmentFlag.AlignTop)
        tx = QVBoxLayout()
        tx.setSpacing(3)
        tx.addWidget(nombre_tarjeta(e.texto("nombre", idioma)))
        tx.addWidget(etiqueta(e.texto("descripcion", idioma), 9.5, QFont.Weight.Normal, SECUNDARIO, envolver=True))
        cab.addLayout(tx, 1)
        self.capa.addLayout(cab)
        chips = [pastilla(("● " if em.estado == "instalado" else "") + t(f"mod_{em.estado}"), self.ESTADOS[em.estado])]
        if em.estado in ("instalado", "desactualizado"):
            chips.append(pastilla(t(f"activacion_{em.activacion}"), self.ACTIVACION[em.activacion]))
        chips.append(pastilla(f"v{em.version or e.version}", APAGADO))
        self.capa.addLayout(fila(*chips, espacio=6))
        acciones = []
        if em.estado in ("no_instalado", "necesita_app"):
            acciones.append(boton_descarga(panel, e, t("instalar")))
        elif em.estado == "desactualizado":
            acciones.append(boton_descarga(panel, e, t("actualizar_a", version=e.version)))
        if em.estado in ("instalado", "desactualizado"):
            if em.activacion in ("desactivado", "sin_registrar"):
                acciones.append(boton(t("activar"), lambda: panel.activar_mod(e), "primario"))
            acciones.append(boton(t("quitar"), lambda: panel.quitar_mod(e)))
        self.capa.addSpacing(4)
        self.capa.addLayout(fila(*acciones))


class PaginaMods(Pagina):
    def refrescar(self):
        limpiar(self.capa)
        panel = self.panel
        self.capa.addWidget(etiqueta(t("mods_intro"), 10, QFont.Weight.Normal, SECUNDARIO, envolver=True))
        self.capa.addLayout(barra_catalogo(panel))
        estados = panel.instalador.estado_mods()
        if not estados:
            self.capa.addWidget(etiqueta(t("mods_sin_catalogo"), 10, QFont.Weight.DemiBold, ATENCION, envolver=True))
        elif panel.instalador.perfil is None:
            self.capa.addWidget(etiqueta(t("mods_sin_perfil"), 10, QFont.Weight.DemiBold, ATENCION, envolver=True))
        self.capa.addLayout(rejilla_de([TarjetaMod(panel, em) for em in estados], 2))
        if estados:
            self.capa.addWidget(etiqueta(t("mods_nota"), 9, QFont.Weight.Medium, APAGADO, envolver=True))
        self.capa.addStretch(1)


class PaginaAjustes(Pagina):
    def refrescar(self):
        limpiar(self.capa)
        panel, cfg = self.panel, self.panel.config

        # General.
        general = self._seccion(t("ajustes_general"))
        idioma = QComboBox()
        for codigo, nombre in textos.IDIOMAS.items():
            idioma.addItem(nombre, codigo)
        idioma.setCurrentIndex(max(0, idioma.findData(cfg.get("idioma", "es"))))
        idioma.currentIndexChanged.connect(lambda _i: panel.cambiar_idioma(idioma.currentData()))
        self._opcion(general, t("op_idioma"), t("op_idioma_desc"), idioma)
        self._opcion(general, t("op_abrir_panel"), t("op_abrir_panel_desc"),
                     Interruptor(cfg.get("abrir_panel_al_iniciar", True), lambda v: self._poner("abrir_panel_al_iniciar", v)))
        self._opcion(general, t("op_inicio_windows"), t("op_inicio_windows_desc"),
                     Interruptor(I.inicio_con_windows(), self._inicio_windows))

        # La guía en la partida.
        guia = self._seccion(t("ajustes_overlay"))
        lado = QComboBox()
        lado.addItem(t("lado_derecha"), "derecha")
        lado.addItem(t("lado_izquierda"), "izquierda")
        lado.setCurrentIndex(max(0, lado.findData(cfg.get("posicion", "derecha"))))
        lado.currentIndexChanged.connect(lambda _i: self._poner("posicion", lado.currentData()))
        self._opcion(guia, t("op_posicion"), t("op_posicion_desc"), lado)
        opacidad = QSlider(Qt.Orientation.Horizontal)
        opacidad.setRange(60, 100)
        opacidad.setValue(round(100 * float(cfg.get("opacidad", 1.0))))
        opacidad.setFixedWidth(180)
        valor = etiqueta(f"{opacidad.value()}%", 9.5, QFont.Weight.DemiBold, SECUNDARIO)
        valor.setFixedWidth(40)

        def cambiar_opacidad(v):
            valor.setText(f"{v}%")
            self._poner("opacidad", v / 100)
        opacidad.valueChanged.connect(cambiar_opacidad)
        caja_op = QWidget()
        co = QHBoxLayout(caja_op)
        co.setContentsMargins(0, 0, 0, 0)
        co.addWidget(opacidad)
        co.addWidget(valor)
        self._opcion(guia, t("op_opacidad"), t("op_opacidad_desc"), caja_op)
        siguientes = QComboBox()
        siguientes.addItem(t("segun_guia"), None)
        for n in range(0, 6):
            siguientes.addItem(str(n), n)
        siguientes.setCurrentIndex(max(0, siguientes.findData(cfg.get("pasos_siguientes"))))
        siguientes.currentIndexChanged.connect(lambda _i: self._poner("pasos_siguientes", siguientes.currentData()))
        self._opcion(guia, t("op_siguientes"), t("op_siguientes_desc"), siguientes)
        self._opcion(guia, t("op_casas"), t("op_casas_desc"),
                     Interruptor(cfg.get("aviso_casas", True), lambda v: self._poner("aviso_casas", v)))
        self._opcion(guia, t("op_historial_fin"), t("op_historial_fin_desc"),
                     Interruptor(cfg.get("abrir_historial_al_terminar", True),
                                 lambda v: self._poner("abrir_historial_al_terminar", v)))
        self._opcion(guia, t("op_pestana"), t("op_pestana_desc"),
                     Interruptor(cfg.get("pestana_historial", True), lambda v: self._poner("pestana_historial", v)))

        # Carpetas (las encuentra rutas.py; aquí se pueden cambiar).
        carpetas = self._seccion(t("ajustes_carpetas"))
        inst = panel.instalador
        juego = QWidget()
        cj = QHBoxLayout(juego)
        cj.setContentsMargins(0, 0, 0, 0)
        cj.addWidget(self._abrir(inst.juego))
        cj.addWidget(boton(t("elegir"), self._elegir_juego))
        self._opcion(carpetas, t("carpeta_juego"), str(inst.juego) if inst.juego else t("no_encontrada"), juego)
        if len(panel.perfiles) > 1:
            perfil = QComboBox()
            perfil.setFixedWidth(320)
            for p in panel.perfiles:
                perfil.addItem(nombre_perfil(p), str(p.carpeta))
            perfil.setCurrentIndex(max(0, perfil.findData(str(inst.perfil))))
            perfil.currentIndexChanged.connect(lambda _i: panel.cambiar_perfil(Path(perfil.currentData())))
            caja = QWidget()
            cp = QHBoxLayout(caja)
            cp.setContentsMargins(0, 0, 0, 0)
            cp.addWidget(perfil)
            cp.addWidget(self._abrir(inst.perfil))
            control = caja
        else:
            control = self._abrir(inst.perfil)
        self._opcion(carpetas, t("carpeta_perfil"), str(inst.perfil) if inst.perfil else t("no_encontrada"), control)
        self._opcion(carpetas, t("carpeta_mod"), str(inst.mod_instalado) if inst.mod_instalado else t("no_encontrada"),
                     self._abrir(inst.mod_instalado))

        # Ayuda y soporte: Discord, datos para un reporte y el log.
        ayuda = self._seccion(t("ajustes_soporte"))
        discord = boton(t("abrir_discord"), lambda: I.abrir_enlace(soporte.DISCORD))
        discord.setEnabled(bool(soporte.DISCORD))
        self._opcion(ayuda, t("op_discord"), t("op_discord_desc") if soporte.DISCORD else t("op_discord_pronto"),
                     discord)
        self._opcion(ayuda, t("op_soporte"), t("op_soporte_desc"), boton(t("copiar"), self.copiar_soporte))
        self._opcion(ayuda, t("op_log"), t("op_log_desc"), self._abrir(rutas.LOGS))
        estado = panel.estado_actualizacion[0]
        if estado in ("disponible", "descargando"):
            control = boton(t("act_actualizar"), panel.actualizar_app, "primario")
            control.setEnabled(estado == "disponible")
        else:
            control = boton(t("act_buscar"), panel.buscar_actualizacion)
            control.setEnabled(estado not in ("desde_codigo", "buscando"))
        self._opcion(ayuda, t("op_version"), panel.texto_actualizacion(), control)

        self.capa.addWidget(etiqueta(t("acerca", version=VERSION), 8.5, QFont.Weight.Medium, APAGADO, envolver=True))
        self.capa.addStretch(1)

    def copiar_soporte(self):
        panel = self.panel
        texto = soporte.datos(panel.config, panel.instalador, panel.juego)
        QGuiApplication.clipboard().setText(texto)
        panel.avisar(t("soporte_copiado"))

    def _seccion(self, titulo: str) -> QVBoxLayout:
        self.capa.addWidget(titulo_seccion(titulo))
        tarjeta = Tarjeta(margen=6)
        tarjeta.capa.setSpacing(0)
        tarjeta.capa.setContentsMargins(20, 6, 20, 6)
        self.capa.addWidget(tarjeta)
        return tarjeta.capa

    def _opcion(self, capa: QVBoxLayout, nombre: str, descripcion: str, control: QWidget):
        if capa.count():
            linea = QFrame()
            linea.setFixedHeight(1)
            linea.setStyleSheet(f"background: {rgba(BORDE, 30)};")
            capa.addWidget(linea)
        f = QHBoxLayout()
        f.setContentsMargins(0, 12, 0, 12)
        f.setSpacing(20)
        tx = QVBoxLayout()
        tx.setSpacing(2)
        tx.addWidget(etiqueta(nombre, 10, QFont.Weight.DemiBold))
        tx.addWidget(etiqueta(descripcion, 8.5, QFont.Weight.Normal, APAGADO, envolver=True))
        f.addLayout(tx, 1)
        f.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
        capa.addLayout(f)

    def _abrir(self, ruta: Path | None) -> QPushButton:
        b = boton(t("abrir"), lambda _=False, r=ruta: I.abrir_carpeta(r))
        b.setEnabled(bool(ruta) and Path(ruta).exists())
        return b

    def _elegir_juego(self):
        inicio = str(self.panel.instalador.juego or rutas.carpeta_steam() or Path.home())
        carpeta = QFileDialog.getExistingDirectory(self, t("elegir_juego"), inicio)
        if carpeta:
            self.panel.cambiar_juego(Path(carpeta))

    def _poner(self, clave: str, valor):
        self.panel.config[clave] = valor
        self.panel.guardar_config()

    def _inicio_windows(self, activo: bool):
        error = I.poner_inicio_con_windows(activo)
        if error:
            self.panel.avisar(t("error_inicio", error=error), MAL)
