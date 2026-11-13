"""Historial de partidas: el contenido (lo usan la página Historial del panel y la
ventana flotante) y la ventana flotante, que solo se ve en el menú principal del juego.

- Arriba, un filtro por guía. Por defecto se ven todas las partidas.
- A la izquierda, «Resumen» y la lista de partidas.
- A la derecha, sin partida elegida, el resumen: con una guía, la media de cada hito
  frente a las partidas anteriores, la evolución y los pasos donde más tiempo se pierde;
  con varias guías, una fila por guía.
- Con una partida elegida: sus hitos frente a la media de su guía, su lugar en la
  evolución, el paso a paso y la carpeta de su repetición (ver repeticiones.py).

Los textos que explican algo van en puntos de información (InfoPunto), no a la vista.
"""

from datetime import datetime

import repeticiones

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QToolTip,
                               QVBoxLayout, QWidget)

# Mismos colores que el panel (estilo.py, «Panel e historial»), no los del overlay.
from estilo import ATENCION, BANDERAS_CLIC, BIEN, ORO_CLARO, PISTA, SERIE_CASTILLOS, SERIE_FEUDAL
from estilo import ORO as ACENTO
from estilo import P_APAGADO as APAGADO
from estilo import P_BORDE as BORDE
from estilo import P_FONDO as FONDO
from estilo import P_SECUNDARIO as SECUNDARIO
from estilo import P_TARJETA as TARJETA
from estilo import P_TEXTO as TEXTO
from estilo import cargar_fuentes, color, fuente, titulo
from historial import (VENTANA_MEDIA, Historial, comparacion_final, duracion, nombre_hito, pasos_hechos, principal,
                       puntos_debiles, reloj, resumen_hito, tramos, valor_principal, vista)
from textos import t as tx

MARGEN = 14  # sombra alrededor de la tarjeta
RADIO = 5
PARTIDAS_GRAFICO = 20
IZQ = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
DER = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
CEN = Qt.AlignmentFlag.AlignCenter


def fecha_corta(iso: str) -> str:
    try:
        d = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{d.day:02d} {tx('hi_meses').split()[d.month - 1]} {d.hour:02d}:{d.minute:02d}"


def mapa_corto(mapa: str) -> str:
    """«[AoE2C] Arena» -> «Arena»: en el historial todos los mapas son de AoE2C."""
    return mapa.split(" Guia")[0].removeprefix("[AoE2C] ")


def desfase(seg: int | float | None) -> tuple[str, object]:
    """Texto y color de una diferencia de tiempo (negativo = más rápido)."""
    if seg is None:
        return "", APAGADO
    seg = round(seg)
    if seg == 0:
        return "±0 s", APAGADO
    return (f"+{duracion(seg)}", ATENCION) if seg > 0 else (f"−{duracion(-seg)}", BIEN)


def texto(p: QPainter, r: QRectF, t: str, f: QFont, c, alinear=IZQ):
    p.setFont(f)
    p.setPen(c)
    t = QFontMetricsF(f).elidedText(t, Qt.TextElideMode.ElideRight, r.width())
    p.drawText(r, int(alinear.value), t)


def caja(p: QPainter, r: QRectF, radio: float, relleno, borde=None):
    path = QPainterPath()
    path.addRoundedRect(r, radio, radio)
    p.fillPath(path, relleno)
    if borde is not None:
        p.setPen(QPen(borde, 1))
        p.drawPath(path)


def seleccion(p: QPainter, r: QRectF):
    """Fila elegida en la barra lateral: fondo dorado tenue y una franja a la izquierda."""
    caja(p, r, 3, color(ACENTO, 30))
    p.fillRect(QRectF(r.x(), r.y() + 6, 2, r.height() - 12), ACENTO)


def pintor(w: QWidget) -> QPainter:
    p = QPainter(w)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    return p


class InfoPunto(QWidget):
    """Punto de información: un «!» en un círculo que muestra su texto al pasar el ratón.
    Para lo que conviene saber pero no hace falta tener siempre a la vista."""

    def __init__(self, texto: str = "", padre: QWidget | None = None):
        super().__init__(padre)
        self.texto = texto
        self.encima = False
        self.setFixedSize(16, 16)
        self.setCursor(Qt.CursorShape.WhatsThisCursor)

    def poner(self, texto: str):
        self.texto = texto
        self.setVisible(bool(texto))

    def enterEvent(self, _):
        self.encima = True
        self.update()
        QToolTip.showText(self.mapToGlobal(QPoint(-6, self.height() + 6)), f"<qt>{self.texto}</qt>", self)

    def leaveEvent(self, _):
        self.encima = False
        self.update()
        QToolTip.hideText()

    def paintEvent(self, _):
        p = pintor(self)
        c = ORO_CLARO if self.encima else APAGADO
        p.setPen(QPen(color(c, 255 if self.encima else 170), 1))
        p.setBrush(color(ACENTO, 30) if self.encima else Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(1, 1, 14, 14))
        p.setFont(fuente(7.5, QFont.Weight.Bold))
        p.setPen(c)
        p.drawText(QRectF(0, 0, 16, 15.5), int(CEN.value), "!")
        p.end()


def junto_a(info: InfoPunto, x: float, texto_titulo: str, f: QFont, y: int = 12):
    """Coloca el punto de información a la derecha de un título pintado en (x, y)."""
    info.move(int(x + QFontMetricsF(f).horizontalAdvance(texto_titulo) + 8), y)


# --- Fichas de los hitos -----------------------------------------------------


class Ficha(QWidget):
    def __init__(self, nombre: str):
        super().__init__()
        self.nombre = nombre
        self.valor = None
        self.comparado = None
        self.sufijo = ""
        self.pie = ""
        self.setFixedHeight(92)

    def poner(self, valor, comparado, sufijo: str, pie: str):
        """valor grande, chip con la diferencia frente a `comparado` y una línea de pie."""
        self.valor, self.comparado, self.sufijo, self.pie = valor, comparado, sufijo, pie
        self.update()

    def paintEvent(self, _):
        p = pintor(self)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        caja(p, r, RADIO, TARJETA, BORDE)
        x, w = 14, r.width() - 28
        texto(p, QRectF(x, 10, w, 16), self.nombre.upper(), fuente(7.5, QFont.Weight.Bold, 1.2), APAGADO)
        grande = reloj(self.valor) if self.valor is not None else "—"
        f_grande = titulo(17)
        texto(p, QRectF(x, 26, w, 32), grande, f_grande, TEXTO)
        ancho_pie = w
        if self.valor is not None and self.comparado is not None:
            t, c = desfase(self.valor - self.comparado)
            t = f"{t} {self.sufijo}".strip()
            f = fuente(8.5, QFont.Weight.DemiBold)
            ancho = QFontMetricsF(f).horizontalAdvance(t) + 16
            chip = QRectF(x + w - ancho, 32, ancho, 20)
            if x + QFontMetricsF(f_grande).horizontalAdvance(grande) + 10 > chip.left():
                # Ficha estrecha: la diferencia baja a la línea de abajo para no pisar el tiempo.
                chip.moveTop(61)
                ancho_pie = w - ancho - 8
            caja(p, chip, 2, color(c, 24), color(c, 80))
            texto(p, chip, t, f, c, CEN)
        f_pie = fuente(8.5, QFont.Weight.Medium)
        pie = self.pie
        if QFontMetricsF(f_pie).horizontalAdvance(pie) > ancho_pie:
            pie = pie.split(" · ")[-1]  # si no cabe entero, la última parte
        texto(p, QRectF(x, 62, ancho_pie, 18), pie, f_pie, SECUNDARIO)
        p.end()


# --- Gráfico de evolución ----------------------------------------------------


COLORES_SERIE = (SERIE_FEUDAL, SERIE_CASTILLOS)


def series_de(registro: dict | None) -> list[tuple[str, str, QColor]]:
    """Líneas del gráfico de evolución de la guía de la partida: (clave, nombre, color)."""
    if registro is None:
        return []
    return [(clave, nombre_hito(registro, clave), c) for clave, c in zip(vista(registro)["series"], COLORES_SERIE)]


class Grafico(QWidget):
    """Llegada a cada edad (o a la meta de la guía) en las últimas partidas (más abajo = más rápido)."""

    def __init__(self, al_elegir):
        super().__init__()
        self.al_elegir = al_elegir
        self.SERIES: list[tuple[str, str, QColor]] = []
        self.registros: list[dict] = []
        self.seleccion = None
        self.encima: int | None = None
        self.setMouseTracking(True)
        self.setMinimumHeight(200)
        self.info = InfoPunto(tx("hi_evolucion_nota"), self)
        junto_a(self.info, 16, tx("hi_evolucion"), fuente(10.5, QFont.Weight.Bold))

    def poner(self, registros: list[dict], seleccion: str | None):
        self.registros, self.seleccion = registros, seleccion
        self.SERIES = series_de(registros[-1] if registros else None)
        self.update()

    def _zona(self) -> QRectF:
        return QRectF(48, 46, self.width() - 48 - 54, self.height() - 46 - 30)

    def _x(self, i: int, z: QRectF) -> float:
        n = len(self.registros)
        return z.center().x() if n == 1 else z.left() + z.width() * i / (n - 1)

    def _rango(self) -> tuple[float, float]:
        valores = [r["hitos"].get(k) for r in self.registros for k, *_ in self.SERIES]
        valores += [r["referencias"].get(k) for r in self.registros[-1:] for k, *_ in self.SERIES]
        valores = [v for v in valores if v is not None]
        if not valores:
            return 0, 900
        lo, hi = min(valores), max(valores)
        lo = (lo - 30) // 60 * 60
        hi = -(-(hi + 30) // 60) * 60
        return lo, max(hi, lo + 120)

    def paintEvent(self, _):
        p = pintor(self)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        caja(p, r, RADIO, TARJETA, BORDE)
        texto(p, QRectF(16, 10, 200, 20), tx("hi_evolucion"), fuente(10.5, QFont.Weight.Bold), TEXTO)
        # Leyenda (con nombre, así el color no es lo único que identifica la serie).
        lx = r.right() - 16
        for _, nombre, c in reversed(self.SERIES):
            f = fuente(8.5, QFont.Weight.DemiBold)
            tw = QFontMetricsF(f).horizontalAdvance(nombre)
            texto(p, QRectF(lx - tw, 12, tw, 18), nombre, f, SECUNDARIO, DER)
            p.setPen(QPen(c, 2))
            p.drawLine(QPointF(lx - tw - 24, 21), QPointF(lx - tw - 8, 21))
            lx -= tw + 40
        z = self._zona()
        if not self.registros:
            p.end()
            return
        lo, hi = self._rango()
        y = lambda v: z.bottom() - (v - lo) / (hi - lo) * z.height()  # noqa: E731
        # Rejilla discreta, en minutos.
        paso = 60 if hi - lo <= 360 else 120
        v = lo
        while v <= hi:
            p.setPen(QPen(color(TEXTO, 16), 1))
            p.drawLine(QPointF(z.left(), y(v)), QPointF(z.right(), y(v)))
            texto(p, QRectF(0, y(v) - 8, z.left() - 8, 16), reloj(v), fuente(7.5, QFont.Weight.Medium), APAGADO, DER)
            v += paso
        # Referencias de la guía: línea discontinua de cada serie.
        ultimo = self.registros[-1]
        for clave, _, c in self.SERIES:
            ref = ultimo["referencias"].get(clave)
            if ref is None or not lo <= ref <= hi:
                continue
            p.setPen(QPen(color(c, 110), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(z.left(), y(ref)), QPointF(z.right(), y(ref)))
        # Partida elegida: banda vertical.
        for i, reg in enumerate(self.registros):
            if reg["id"] == self.seleccion:
                caja(p, QRectF(self._x(i, z) - 9, z.top() - 4, 18, z.height() + 8), 3, color(TEXTO, 12))
        # Series.
        for clave, _, c in self.SERIES:
            puntos = [(i, reg["hitos"].get(clave)) for i, reg in enumerate(self.registros)]
            p.setPen(QPen(c, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            previo = None
            for i, v in puntos:
                if v is None:
                    previo = None
                    continue
                punto = QPointF(self._x(i, z), y(v))
                if previo is not None:
                    p.drawLine(previo, punto)
                previo = punto
            for i, v in puntos:
                if v is None:
                    continue
                p.setPen(QPen(FONDO, 2))
                p.setBrush(c)
                radio = 5 if self.registros[i]["id"] == self.seleccion or i == self.encima else 4
                p.drawEllipse(QPointF(self._x(i, z), y(v)), radio, radio)
            # Etiqueta directa en el último punto.
            ultimos = [(i, v) for i, v in puntos if v is not None]
            if ultimos:
                i, v = ultimos[-1]
                texto(p, QRectF(self._x(i, z) + 8, y(v) - 8, 50, 16), reloj(v), fuente(8, QFont.Weight.Bold), TEXTO)
        # Eje x: primera y última fecha.
        f = fuente(7.5, QFont.Weight.Medium)
        texto(p, QRectF(z.left() - 20, z.bottom() + 8, 120, 16), fecha_corta(self.registros[0]["fecha"])[:6], f,
              APAGADO)
        if len(self.registros) > 1:
            texto(p, QRectF(z.right() - 100, z.bottom() + 8, 120, 16), fecha_corta(self.registros[-1]["fecha"])[:6],
                  f, APAGADO, DER)
        # Al pasar el ratón: línea vertical y los valores de esa partida.
        if self.encima is not None and self.encima < len(self.registros):
            reg = self.registros[self.encima]
            x = self._x(self.encima, z)
            p.setPen(QPen(color(TEXTO, 60), 1))
            p.drawLine(QPointF(x, z.top()), QPointF(x, z.bottom()))
            lineas = [fecha_corta(reg["fecha"]) + " · " + mapa_corto(reg["mapa"])]
            for clave, nombre, _ in self.SERIES:
                lineas.append(f"{nombre}  {reloj(reg['hitos'].get(clave))}")
            ancho, alto = 168, 16 + 17 * len(lineas)
            bx = x + 12 if x + 12 + ancho < r.right() else x - 12 - ancho
            caja(p, QRectF(bx, z.top(), ancho, alto), 4, color(FONDO, 250), color(ACENTO, 90))
            for k, linea in enumerate(lineas):
                peso = QFont.Weight.DemiBold if k == 0 else QFont.Weight.Medium
                texto(p, QRectF(bx + 10, z.top() + 8 + 17 * k, ancho - 20, 17), linea, fuente(8.5, peso),
                      TEXTO if k == 0 else SECUNDARIO)
                if k:
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(self.SERIES[k - 1][2])
                    p.drawEllipse(QPointF(bx + ancho - 14, z.top() + 8 + 17 * k + 8.5), 3.5, 3.5)
        p.end()

    def _indice(self, x: float) -> int | None:
        if not self.registros:
            return None
        z = self._zona()
        mejor = min(range(len(self.registros)), key=lambda i: abs(self._x(i, z) - x))
        return mejor if abs(self._x(mejor, z) - x) < 24 else None

    def mouseMoveEvent(self, e):
        i = self._indice(e.position().x())
        if i != self.encima:
            self.encima = i
            self.update()

    def leaveEvent(self, _):
        self.encima = None
        self.update()

    def mousePressEvent(self, e):
        i = self._indice(e.position().x())
        if i is not None and e.button() == Qt.MouseButton.LeftButton:
            self.al_elegir(self.registros[i]["id"])


# --- Puntos débiles ----------------------------------------------------------


class PuntosDebiles(QWidget):
    FILAS = 5

    def __init__(self):
        super().__init__()
        self.tramos: list[dict] = []
        self.partidas = 0
        self.setMinimumHeight(196)
        self.info = InfoPunto("", self)
        junto_a(self.info, 16, tx("hi_donde_pierdes"), fuente(10.5, QFont.Weight.Bold))

    def poner(self, tramos_: list[dict], partidas: int):
        self.tramos, self.partidas = tramos_, partidas
        n = min(partidas, VENTANA_MEDIA)
        self.info.poner(tx("hi_media_una") if n == 1 else tx("hi_media_n", n=n))
        self.update()

    def paintEvent(self, _):
        p = pintor(self)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        caja(p, r, RADIO, TARJETA, BORDE)
        texto(p, QRectF(16, 10, r.width() - 32, 20), tx("hi_donde_pierdes"), fuente(10.5, QFont.Weight.Bold), TEXTO)
        lentos = [t for t in self.tramos if t["media"] >= 1][: self.FILAS]
        y = 42
        if not lentos:
            texto(p, QRectF(16, y, r.width() - 32, 40), tx("hi_sin_tramos"),
                  fuente(9.5, QFont.Weight.Medium), BIEN)
            p.end()
            return
        maximo = max(t["media"] for t in lentos)
        alto = (r.height() - y - 12) / self.FILAS
        for t in lentos:
            w = r.width() - 32
            valor, c = desfase(t["media"])
            texto(p, QRectF(16, y, w - 60, 18), f"{t['n']}. {t['titulo']}", fuente(9, QFont.Weight.Medium), SECUNDARIO)
            texto(p, QRectF(16, y, w, 18), valor, fuente(9, QFont.Weight.Bold), TEXTO, DER)
            caja(p, QRectF(16, y + 21, w, 5), 2.5, PISTA)
            caja(p, QRectF(16, y + 21, max(5, w * t["media"] / maximo), 5), 2.5, c)
            y += alto
        p.end()


# --- Barra lateral: resumen y lista de partidas -------------------------------


class FilaResumen(QWidget):
    """Entrada fija arriba de la barra lateral: vuelve al resumen."""

    def __init__(self, al_pulsar):
        super().__init__()
        self.al_pulsar = al_pulsar
        self.elegida = True
        self.partidas = 0
        self.encima = False
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def poner(self, elegida: bool, partidas: int):
        self.elegida, self.partidas = elegida, partidas
        self.update()

    def paintEvent(self, _):
        p = pintor(self)
        r = QRectF(self.rect()).adjusted(2, 1, -2, -1)
        if self.elegida:
            seleccion(p, r)
        elif self.encima:
            caja(p, r, 3, color(TEXTO, 10))
        zona = QRectF(12, 0, self.width() - 24, self.height())
        texto(p, zona, tx("hi_resumen"), fuente(9.5, QFont.Weight.Bold), TEXTO)
        texto(p, zona, str(self.partidas), fuente(9, QFont.Weight.DemiBold), SECUNDARIO if self.elegida else APAGADO,
              DER)
        p.end()

    def enterEvent(self, _):
        self.encima = True
        self.update()

    def leaveEvent(self, _):
        self.encima = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.al_pulsar()


class ListaPartidas(QWidget):
    """Partidas de la más reciente a la más antigua: fecha y tiempo del hito principal
    arriba; debajo, el mapa (y la guía, si se ven todas) y la diferencia con la media."""

    FILA = 52

    def __init__(self, al_elegir):
        super().__init__()
        self.al_elegir = al_elegir
        self.registros: list[dict] = []
        self.seleccion = None
        self.marcas: dict[str, tuple] = {}
        self.con_guia = False
        self.encima: int | None = None
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def poner(self, registros: list[dict], seleccion: str | None, marcas: dict[str, tuple], con_guia: bool):
        """marcas: por guía, (media, mejor) de su hito principal. con_guia: escribe la
        guía en cada fila (cuando se ven partidas de varias)."""
        self.registros, self.seleccion = registros, seleccion
        self.marcas, self.con_guia = marcas, con_guia
        self.setFixedHeight(self.FILA * len(registros) + 4)
        self.update()

    def paintEvent(self, _):
        p = pintor(self)
        w = self.width()
        y = 0
        for k, reg in enumerate(self.registros):
            fila = QRectF(2, y + 1, w - 4, self.FILA - 2)
            elegida = reg["id"] == self.seleccion
            if elegida:
                seleccion(p, fila)
            elif k == self.encima:
                caja(p, fila, 3, color(TEXTO, 10))
            ancho = w - 24
            valor = valor_principal(reg)
            media_guia, mejor = self.marcas.get(reg["guia"], (None, None))
            texto(p, QRectF(12, y + 8, ancho - 60, 18), fecha_corta(reg["fecha"]), fuente(9.5, QFont.Weight.Bold),
                  TEXTO)
            texto(p, QRectF(12, y + 8, ancho, 18), reloj(valor), fuente(10, QFont.Weight.Bold),
                  TEXTO if valor is not None else APAGADO, DER)
            if valor is None:
                t, c = f"{pasos_hechos(reg)}/{len(reg['pasos'])}", APAGADO
            elif valor == mejor:
                t, c = "★", BIEN
            else:
                t, c = desfase(valor - media_guia) if media_guia is not None else ("", APAGADO)
            f_dif = fuente(8.5, QFont.Weight.DemiBold)
            texto(p, QRectF(12, y + 27, ancho, 16), t, f_dif, c, DER)
            sub = f"{reg['guia']} · {mapa_corto(reg['mapa'])}" if self.con_guia else mapa_corto(reg["mapa"])
            texto(p, QRectF(12, y + 27, ancho - QFontMetricsF(f_dif).horizontalAdvance(t) - 10, 16), sub,
                  fuente(8.5, QFont.Weight.Medium), SECUNDARIO if elegida else APAGADO)
            y += self.FILA
        p.end()

    def _fila(self, y: float) -> int | None:
        k = int(y // self.FILA)
        return k if y >= 0 and 0 <= k < len(self.registros) else None

    def mouseMoveEvent(self, e):
        k = self._fila(e.position().y())
        if k != self.encima:
            self.encima = k
            self.update()

    def leaveEvent(self, _):
        self.encima = None
        self.update()

    def mousePressEvent(self, e):
        k = self._fila(e.position().y())
        if k is not None and e.button() == Qt.MouseButton.LeftButton:
            self.al_elegir(self.registros[k]["id"])


# --- Resumen de todas las guías ----------------------------------------------


class TablaGuias(QWidget):
    """Una fila por guía: partidas, mejor marca y media de su hito principal, y la
    diferencia de la media con las partidas anteriores. Un clic filtra por esa guía."""

    CABECERA, FILA = 34, 56
    COLUMNAS = (("hi_col_partidas", 300), ("hi_col_mejor", 210), ("hi_col_media", 120))  # clave, borde derecho

    def __init__(self, al_elegir):
        super().__init__()
        self.al_elegir = al_elegir
        self.filas: list[dict] = []
        self.encima: int | None = None
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def poner(self, historial: Historial):
        self.filas = []
        for nombre, n in historial.guias():
            regs = historial.de_guia(nombre)
            self.filas.append({"guia": nombre, "partidas": n, "hito": nombre_hito(regs[-1], principal(regs[-1])),
                               **resumen_hito(regs, principal(regs[-1]))})
        self.setFixedHeight(self.CABECERA + self.FILA * len(self.filas) + 8)
        self.update()

    def paintEvent(self, _):
        p = pintor(self)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        caja(p, r, RADIO, TARJETA, BORDE)
        w = r.width()
        f_cab = fuente(7.5, QFont.Weight.Bold, 1.1)
        texto(p, QRectF(18, 6, 200, self.CABECERA - 6), tx("hi_col_guia"), f_cab, APAGADO)
        for clave, borde in self.COLUMNAS:
            texto(p, QRectF(w - borde - 90, 6, 90, self.CABECERA - 6), tx(clave), f_cab, APAGADO, DER)
        y = self.CABECERA
        for k, f in enumerate(self.filas):
            p.setPen(QPen(color(BORDE, 30), 1))
            p.drawLine(QPointF(18, y + 0.5), QPointF(w - 18, y + 0.5))
            if k == self.encima:
                caja(p, QRectF(4, y + 3, w - 8, self.FILA - 5), 3, color(ACENTO, 16))
            texto(p, QRectF(18, y + 9, w - 440, 20), f["guia"], titulo(10.5, 0.3), TEXTO)
            texto(p, QRectF(18, y + 30, w - 440, 16), f["hito"], fuente(8.5, QFont.Weight.Medium), APAGADO)
            fila = QRectF(0, y, 0, self.FILA)
            for valor, borde, c in ((str(f["partidas"]), 300, SECUNDARIO), (reloj(f["mejor"]), 210, TEXTO),
                                    (reloj(f["media"]), 120, TEXTO)):
                fila.setLeft(w - borde - 90)
                fila.setWidth(90)
                texto(p, fila, valor, fuente(10.5, QFont.Weight.DemiBold), c if valor != "—" else APAGADO, DER)
            if f["media"] is not None and f["media_anterior"] is not None:
                t, c = desfase(f["media"] - f["media_anterior"])
                chip = QRectF(w - 18 - 76, y + (self.FILA - 20) / 2, 76, 20)
                caja(p, chip, 2, color(c, 24), color(c, 80))
                texto(p, chip, t, fuente(8.5, QFont.Weight.DemiBold), c, CEN)
            y += self.FILA
        p.end()

    def _fila(self, y: float) -> int | None:
        k = int((y - self.CABECERA) // self.FILA)
        return k if y >= self.CABECERA and 0 <= k < len(self.filas) else None

    def mouseMoveEvent(self, e):
        k = self._fila(e.position().y())
        if k != self.encima:
            self.encima = k
            self.update()

    def leaveEvent(self, _):
        self.encima = None
        self.update()

    def mousePressEvent(self, e):
        k = self._fila(e.position().y())
        if k is not None and e.button() == Qt.MouseButton.LeftButton:
            self.al_elegir(self.filas[k]["guia"])


# --- Detalle paso a paso -----------------------------------------------------


class TablaPasos(QWidget):
    FILA = 30

    def __init__(self):
        super().__init__()
        self.filas: list[dict] = []

    def poner(self, registro: dict | None):
        self.filas = tramos(registro) if registro else []
        self.setFixedHeight(22 + self.FILA * len(self.filas) + 4)
        self.update()

    def paintEvent(self, _):
        p = pintor(self)
        w = self.width()
        f_cab = fuente(7.5, QFont.Weight.Bold, 1.1)
        texto(p, QRectF(8, 0, 200, 22), tx("hi_col_paso"), f_cab, APAGADO)
        texto(p, QRectF(w - 182, 0, 54, 22), tx("hi_col_hora"), f_cab, APAGADO, DER)
        texto(p, QRectF(w - 124, 0, 54, 22), tx("hi_col_ref"), f_cab, APAGADO, DER)
        texto(p, QRectF(w - 66, 0, 58, 22), tx("hi_col_tramo"), f_cab, APAGADO, DER)
        peor = max((f["tramo"] for f in self.filas if f["tramo"] is not None), default=None)
        y = 22
        for f in self.filas:
            if peor is not None and peor >= 10 and f["tramo"] == peor:
                caja(p, QRectF(2, y + 1, w - 4, self.FILA - 2), 3, color(ATENCION, 22), color(ATENCION, 70))
            hecho = f["hora"] is not None
            texto(p, QRectF(8, y, w - 196, self.FILA), f"{f['n']}. {f['titulo']}", fuente(9, QFont.Weight.Medium),
                  SECUNDARIO if hecho else APAGADO)
            if hecho:
                texto(p, QRectF(w - 182, y, 54, self.FILA), reloj(f["hora"]), fuente(9, QFont.Weight.DemiBold), TEXTO,
                      DER)
                t, c = desfase(f["desfase"])
                texto(p, QRectF(w - 124, y, 54, self.FILA), t, fuente(8.5, QFont.Weight.Medium), c, DER)
                t, c = desfase(f["tramo"])
                texto(p, QRectF(w - 66, y, 58, self.FILA), t, fuente(8.5, QFont.Weight.Bold), c, DER)
            else:
                texto(p, QRectF(w - 182, y, 174, self.FILA), tx("hi_sin_hacer") if f["saltado"] else tx("hi_no_llego"),
                      fuente(8.5, QFont.Weight.Medium), APAGADO, DER)
            y += self.FILA
        p.end()


# --- Contenido ---------------------------------------------------------------


def _rgba(c: QColor, a: int) -> str:
    return f"rgba({c.red()},{c.green()},{c.blue()},{a})"


ESTILO = f"""
QLabel {{ color: {TEXTO.name()}; background: transparent; }}
QToolTip {{ color: {TEXTO.name()}; background: #25211b; border: 1px solid {_rgba(BORDE, 90)};
           padding: 6px 9px; font-family: 'Segoe UI'; font-size: 9pt; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {_rgba(TEXTO, 36)}; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {_rgba(TEXTO, 70)}; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ height: 0; background: none; }}
QPushButton {{ color: {SECUNDARIO.name()}; background: transparent; border: 1px solid {_rgba(BORDE, 60)};
              border-radius: 3px; padding: 5px 12px; font-family: 'Segoe UI'; font-size: 9pt; font-weight: 600; }}
QPushButton:hover {{ color: {ORO_CLARO.name()}; background: {_rgba(ACENTO, 22)}; border-color: {_rgba(ACENTO, 140)}; }}
QPushButton:disabled {{ color: {_rgba(APAGADO, 140)}; background: transparent; border-color: {_rgba(BORDE, 24)}; }}
QPushButton#filtro {{ padding: 5px 13px; }}
QPushButton#filtro:checked {{ color: {ORO_CLARO.name()}; background: {_rgba(ACENTO, 28)}; border-color: {ACENTO.name()}; }}
QPushButton#cerrar {{ padding: 0; min-width: 26px; max-width: 26px; min-height: 26px; max-height: 26px;
                     font-size: 10pt; }}
QPushButton#borrar[confirmar="true"] {{ color: #ffc4c4; border-color: rgba(255,96,96,140);
                                       background: rgba(255,96,96,40); }}
"""


def etiqueta(t: str, tam: float, peso=QFont.Weight.Normal, c=TEXTO, espacio=0.0) -> QLabel:
    lab = QLabel(t)
    lab.setFont(fuente(tam, peso, espacio))
    lab.setStyleSheet(f"color: {c.name()};")
    return lab


def desplazable(contenido: QWidget) -> QScrollArea:
    s = QScrollArea()
    s.setWidget(contenido)
    s.setWidgetResizable(True)
    s.setFrameShape(QFrame.Shape.NoFrame)
    s.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    return s


def con_info(lab: QLabel, info: InfoPunto) -> QHBoxLayout:
    """Un rótulo con su punto de información al lado."""
    f = QHBoxLayout()
    f.setContentsMargins(0, 0, 0, 0)
    f.setSpacing(7)
    f.addWidget(lab)
    f.addWidget(info)
    f.addStretch(1)
    return f


class Panel(QWidget):
    """Caja con borde para la barra lateral y el detalle."""

    def paintEvent(self, _):
        p = pintor(self)
        caja(p, QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), RADIO, TARJETA, BORDE)
        p.end()


class FilaFichas(QWidget):
    """Una ficha por hito de la guía (cuatro en Fast Castle, tres en Scouts)."""

    def __init__(self):
        super().__init__()
        self.fila = QHBoxLayout(self)
        self.fila.setContentsMargins(0, 0, 0, 0)
        self.fila.setSpacing(10)
        self.fichas: dict[str, Ficha] = {}
        self.setFixedHeight(92)

    def preparar(self, claves: list[str], nombres: list[str]):
        if list(self.fichas) == claves and [f.nombre for f in self.fichas.values()] == nombres:
            return
        for f in self.fichas.values():
            f.setParent(None)
            f.deleteLater()
        self.fichas = {}
        for clave, nombre in zip(claves, nombres):
            self.fichas[clave] = Ficha(nombre)
            self.fila.addWidget(self.fichas[clave])

    def items(self):
        return self.fichas.items()


class ContenidoHistorial(QWidget):
    """El filtro por guía, la barra lateral con las partidas y el panel con los datos. Lo
    usan la página Historial del panel y la ventana flotante del juego.

    `filtro` es el nombre de una guía o None (todas las partidas, lo normal)."""

    LATERAL = 268

    def __init__(self, historial: Historial):
        super().__init__()
        cargar_fuentes()
        self.historial = historial
        self.seleccion: str | None = None  # None = resumen
        self.filtro: str | None = None  # None = todas las guías
        self.fin_de_partida = False
        self.repeticion = None  # Path de la repetición de la partida elegida
        self.mostrar_en_carpeta = repeticiones.mostrar_en_carpeta
        self.setStyleSheet(ESTILO)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(12)

        # Sin partidas.
        self.vacio = etiqueta(tx("hi_vacio"), 11, QFont.Weight.Medium, APAGADO)
        self.vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        raiz.addWidget(self.vacio, 1)

        # Filtro por guía (solo si hay partidas de más de una).
        self.barra_filtros = QWidget()
        self.filtros = QHBoxLayout(self.barra_filtros)
        self.filtros.setContentsMargins(0, 0, 0, 0)
        self.filtros.setSpacing(8)
        self.grupo = QButtonGroup(self)
        self._firma_filtros = None
        raiz.addWidget(self.barra_filtros)

        # Contenido: barra lateral a la izquierda, panel a la derecha.
        self.contenido = QWidget()
        cuerpo = QHBoxLayout(self.contenido)
        cuerpo.setContentsMargins(0, 0, 0, 0)
        cuerpo.setSpacing(14)

        lateral = Panel()
        lateral.setFixedWidth(self.LATERAL)
        ll = QVBoxLayout(lateral)
        ll.setContentsMargins(8, 8, 4, 8)
        ll.setSpacing(6)
        self.resumen = FilaResumen(lambda: self.elegir(None))
        ll.addWidget(self.resumen)
        separador = QFrame()
        separador.setFixedHeight(1)
        separador.setStyleSheet(f"background: {_rgba(BORDE, 30)};")
        ll.addWidget(separador)
        self.lista = ListaPartidas(self.elegir)
        ll.addWidget(desplazable(self.lista), 1)
        cuerpo.addWidget(lateral)

        # Resumen de todas las guías (sin filtro y con partidas de varias).
        self.vista_guias = QWidget()
        vt = QVBoxLayout(self.vista_guias)
        vt.setContentsMargins(0, 0, 0, 0)
        self.tabla_guias = TablaGuias(self.filtrar)
        vt.addWidget(self.tabla_guias)
        vt.addStretch(1)
        cuerpo.addWidget(self.vista_guias, 1)

        # Resumen de una guía: medias, evolución y dónde se pierde tiempo.
        self.vista_general = QWidget()
        vg = QVBoxLayout(self.vista_general)
        vg.setContentsMargins(0, 0, 0, 0)
        vg.setSpacing(12)
        self.rotulo_medias = etiqueta("", 7.5, QFont.Weight.Bold, APAGADO, 1.4)
        vg.addLayout(con_info(self.rotulo_medias, InfoPunto(tx("hi_medias_nota"))))
        self.fichas_general = FilaFichas()
        vg.addWidget(self.fichas_general)
        self.grafico_general = Grafico(self.elegir)
        vg.addWidget(self.grafico_general, 1)
        self.debiles = PuntosDebiles()
        vg.addWidget(self.debiles)
        cuerpo.addWidget(self.vista_general, 1)

        # Una partida: hitos frente a la media de su guía, su lugar en la evolución y el paso a paso.
        self.vista_partida = QWidget()
        vp = QVBoxLayout(self.vista_partida)
        vp.setContentsMargins(0, 0, 0, 0)
        vp.setSpacing(12)
        fila = QHBoxLayout()
        fila.setSpacing(8)
        self.titulo_detalle = QLabel("")
        self.titulo_detalle.setFont(titulo(13, 0.3))
        fila.addWidget(self.titulo_detalle)
        self.guia_detalle = etiqueta("", 9.5, QFont.Weight.Medium, APAGADO)
        fila.addWidget(self.guia_detalle, 1, Qt.AlignmentFlag.AlignBottom)
        self.en_carpeta = QPushButton(tx("hi_en_carpeta"))
        self.borrar = QPushButton(tx("hi_borrar"))
        self.borrar.setObjectName("borrar")
        for b, al_pulsar in ((self.en_carpeta, self.pulsar_en_carpeta), (self.borrar, self.pulsar_borrar)):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(al_pulsar)
            fila.addWidget(b)
        vp.addLayout(fila)
        # La partida que acaba de terminar, en una línea.
        self.aviso = etiqueta("", 10, QFont.Weight.DemiBold, BIEN)
        self.aviso.setWordWrap(True)
        self.aviso.setStyleSheet(f"color: {BIEN.name()}; background: {_rgba(BIEN, 26)}; "
                                 f"border-left: 2px solid {BIEN.name()}; padding: 8px 12px;")
        vp.addWidget(self.aviso)
        self.fichas = FilaFichas()
        vp.addWidget(self.fichas)
        self.grafico = Grafico(self.elegir)
        self.grafico.setFixedHeight(190)
        vp.addWidget(self.grafico)
        detalle = Panel()
        ld = QVBoxLayout(detalle)
        ld.setContentsMargins(12, 10, 6, 8)
        ld.addLayout(con_info(etiqueta(tx("hi_paso_a_paso"), 10.5, QFont.Weight.Bold), InfoPunto(tx("hi_pasos_nota"))))
        self.pasos = TablaPasos()
        ld.addWidget(desplazable(self.pasos), 1)
        vp.addWidget(detalle, 1)
        cuerpo.addWidget(self.vista_partida, 1)

        raiz.addWidget(self.contenido, 1)

    # Datos.
    def abrir(self, seleccion: str | None = None, fin_de_partida: bool = False):
        self.historial.cargar()
        self.fin_de_partida = fin_de_partida
        self.elegir(seleccion)

    def filtrar(self, guia: str | None):
        """Solo las partidas de una guía (None = todas)."""
        self.filtro = guia
        self.refrescar()

    def elegir(self, id_: str | None):
        self.seleccion = id_
        reg = self.historial.buscar(id_)
        if reg and self.filtro and reg["guia"] != self.filtro:
            self.filtro = None  # la partida pedida no es de la guía filtrada
        self.refrescar()

    def pulsar_borrar(self):
        if self.seleccion is None:
            return
        if self.borrar.property("confirmar"):
            self.historial.quitar(self.seleccion)
            self.historial.guardar()
            self.seleccion = None
            self.refrescar()
        else:
            self.borrar.setText(tx("hi_borrar_confirmar"))
            self.borrar.setProperty("confirmar", True)
            self.borrar.style().polish(self.borrar)

    def pulsar_en_carpeta(self):
        if self.repeticion is not None:
            self.mostrar_en_carpeta(self.repeticion)

    def _poner_repeticion(self, sel: dict):
        antes = sel.get("repeticion")
        self.repeticion = repeticiones.de_registro(sel)
        if sel.get("repeticion") != antes:
            self.historial.guardar()
        hay = self.repeticion is not None
        self.en_carpeta.setEnabled(hay)
        self.en_carpeta.setToolTip("" if hay else tx("hi_sin_repeticion"))

    def _reiniciar_borrar(self):
        self.borrar.setText(tx("hi_borrar"))
        self.borrar.setProperty("confirmar", False)
        self.borrar.style().polish(self.borrar)

    def _pintar_filtros(self, guias: list[tuple[str, int]]):
        firma = (tuple(guias), self.filtro)
        self.barra_filtros.setVisible(len(guias) > 1)
        if firma == self._firma_filtros:
            return
        self._firma_filtros = firma
        for b in self.grupo.buttons():
            self.grupo.removeButton(b)
            b.setParent(None)
            b.deleteLater()
        while self.filtros.count():
            self.filtros.takeAt(0)
        total = sum(n for _, n in guias)
        for nombre, n in [(None, total)] + guias:
            b = QPushButton(f"{nombre or tx('hi_todas')}   {n}")
            b.setObjectName("filtro")
            b.setCheckable(True)
            b.setChecked(nombre == self.filtro)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, x=nombre: self.filtrar(x))
            self.grupo.addButton(b)
            self.filtros.addWidget(b)
        self.filtros.addStretch(1)

    def refrescar(self):
        self._reiniciar_borrar()
        guias = self.historial.guias()
        if self.filtro not in dict(guias):
            self.filtro = None
        sel = self.historial.buscar(self.seleccion)
        if sel and self.filtro and sel["guia"] != self.filtro:
            sel = None
        self.seleccion = sel["id"] if sel else None
        visibles = self.historial.de_guia(self.filtro)
        hay = bool(visibles)
        self.vacio.setVisible(not hay)
        self.contenido.setVisible(hay)
        self._pintar_filtros(guias)
        if not hay:
            return
        # La guía del panel de la derecha: la de la partida elegida, la filtrada o la única que hay.
        guia = sel["guia"] if sel else (self.filtro or (guias[0][0] if len(guias) == 1 else None))
        marcas = {}
        for nombre, _ in guias:
            de_la_guia = self.historial.de_guia(nombre)
            res = resumen_hito(de_la_guia, principal(de_la_guia[-1]))
            marcas[nombre] = (res["media"], res["mejor"])
        self.resumen.poner(sel is None, len(visibles))
        self.lista.poner(list(reversed(visibles)), self.seleccion, marcas, self.filtro is None and len(guias) > 1)
        self.vista_guias.setVisible(guia is None)
        self.vista_general.setVisible(sel is None and guia is not None)
        self.vista_partida.setVisible(sel is not None)
        if guia is None:
            self.tabla_guias.poner(self.historial)
            return
        regs = self.historial.de_guia(guia)
        claves = vista(regs[-1])["hitos"]
        nombres = [nombre_hito(regs[-1], k) for k in claves]
        if sel is None:
            self.fichas_general.preparar(claves, nombres)
            self._pintar_general(regs)
        else:
            self.fichas.preparar(claves, nombres)
            self._pintar_partida(regs, sel, len(guias) > 1)

    def _pintar_general(self, regs: list[dict]):
        n = min(len(regs), VENTANA_MEDIA)
        self.rotulo_medias.setText(tx("hi_medias", n=n) if n > 1 else tx("hi_medias_una"))
        for clave, ficha in self.fichas_general.items():
            res = resumen_hito(regs, clave)
            ficha.poner(res["media"], res["media_anterior"], "",
                        tx("hi_mejor", hora=reloj(res["mejor"])) if res["mejor"] is not None else "")
        self.grafico_general.poner(regs[-PARTIDAS_GRAFICO:], None)
        self.debiles.poner(puntos_debiles(regs), len(regs))

    def _pintar_partida(self, regs: list[dict], sel: dict, con_guia: bool):
        # La partida que acaba de terminar: su tiempo y cómo queda frente a las anteriores.
        if self.fin_de_partida and sel is regs[-1]:
            valor = valor_principal(sel)
            if valor is not None:
                partes = [tx("hi_hito_a_las", hito=nombre_hito(sel, principal(sel)), hora=reloj(valor)),
                          comparacion_final(self.historial, sel).rstrip(".")]
            else:
                partes = [tx("hi_hasta_paso", n=pasos_hechos(sel), total=len(sel["pasos"]))]
            self.aviso.setText(" · ".join(x for x in partes if x))
            self.aviso.show()
        else:
            self.aviso.hide()

        self.titulo_detalle.setText(f"{fecha_corta(sel['fecha'])} · {mapa_corto(sel['mapa'])}")
        self.guia_detalle.setText(sel["guia"] if con_guia else "")
        self._poner_repeticion(sel)
        for clave, ficha in self.fichas.items():
            res = resumen_hito(regs, clave, excluir=sel["id"])
            pie = []  # si no cabe entero, la ficha deja la última parte (la media)
            if sel["referencias"].get(clave) is not None:
                pie.append(tx("hi_ref", hora=reloj(sel["referencias"][clave])))
            if res["media"] is not None:
                pie.append(tx("hi_media_de", hora=reloj(res["media"])))
            ficha.poner(sel["hitos"].get(clave), res["media"], "", " · ".join(pie))
        # El gráfico muestra la ventana de partidas que incluye la elegida.
        i = next(k for k, r in enumerate(regs) if r["id"] == sel["id"])
        inicio = min(max(0, len(regs) - PARTIDAS_GRAFICO), i)
        self.grafico.poner(regs[inicio:inicio + PARTIDAS_GRAFICO], sel["id"])
        self.pasos.poner(sel)


# --- Ventana flotante ----------------------------------------------------------


class VentanaHistorial(QWidget):
    """El historial encima del juego, sin quitarle el foco: solo en el menú principal del
    juego (nunca durante una partida); se abre solo al volver de una partida de guía.
    Fuera del juego no se ve: ahí el historial está en el panel."""

    ANCHO, ALTO = 1140, 800

    def __init__(self, historial: Historial, al_cerrar):
        super().__init__()
        self.historial = historial
        self.setWindowFlags(BANDERAS_CLIC)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet(ESTILO)
        self.setWindowTitle(tx("hi_titulo"))

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(MARGEN + 24, MARGEN + 18, MARGEN + 24, MARGEN + 22)
        raiz.setSpacing(14)

        cab = QHBoxLayout()
        nombre = QLabel(tx("hi_titulo"))
        nombre.setFont(titulo(15, 0.5))
        cab.addWidget(nombre, 1)
        cerrar = QPushButton("✕")
        cerrar.setObjectName("cerrar")
        cerrar.setCursor(Qt.CursorShape.PointingHandCursor)
        cerrar.clicked.connect(al_cerrar)
        cab.addWidget(cerrar)
        raiz.addLayout(cab)

        self.cuerpo = ContenidoHistorial(historial)
        raiz.addWidget(self.cuerpo, 1)

    # La lista, las vistas, elegir(), pulsar_borrar()... son del contenido.
    seleccion = property(lambda self: self.cuerpo.seleccion)
    vacio = property(lambda self: self.cuerpo.vacio)
    aviso = property(lambda self: self.cuerpo.aviso)
    lista = property(lambda self: self.cuerpo.lista)
    resumen = property(lambda self: self.cuerpo.resumen)
    vista_general = property(lambda self: self.cuerpo.vista_general)
    vista_partida = property(lambda self: self.cuerpo.vista_partida)

    def elegir(self, id_: str | None):
        self.cuerpo.elegir(id_)

    def pulsar_borrar(self):
        self.cuerpo.pulsar_borrar()

    def abrir(self, seleccion: str | None = None, fin_de_partida: bool = False):
        self.cuerpo.abrir(seleccion, fin_de_partida)
        self.recolocar()

    # Ventana.
    def recolocar(self):
        pantalla = (self.screen() or QGuiApplication.primaryScreen()).geometry()
        ancho = min(self.ANCHO, int(pantalla.width() * 0.92)) + 2 * MARGEN
        alto = min(self.ALTO, int(pantalla.height() * 0.9)) + 2 * MARGEN
        self.setGeometry(pantalla.x() + (pantalla.width() - ancho) // 2,
                         pantalla.y() + (pantalla.height() - alto) // 2, ancho, alto)

    def paintEvent(self, _):
        p = pintor(self)
        tarjeta = QRectF(MARGEN, MARGEN, self.width() - 2 * MARGEN, self.height() - 2 * MARGEN)
        for i in range(10, 0, -1):
            path = QPainterPath()
            path.addRoundedRect(tarjeta.adjusted(-i, -i + 3, i, i + 3), 18 + i, 18 + i)
            p.fillPath(path, QColor(0, 0, 0, int(5 * (11 - i) / 3)))
        caja(p, tarjeta, 8, FONDO, BORDE)
        p.end()
