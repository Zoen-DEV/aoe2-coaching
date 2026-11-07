"""Ventana del historial de aperturas.

Mismo estilo que la tarjeta de la guía. Recibe clics y la rueda del ratón sin
quitarle el foco al juego.

- A la izquierda, una barra lateral con «Resumen general» y la lista de partidas.
- A la derecha, sin partida elegida, el resumen general: la media de cada hito
  (clic en Feudal, Feudal, clic en Castillos, Castillos) frente a las partidas
  anteriores, la evolución de Feudal y Castillos y los tramos donde más tiempo pierdes.
- Con una partida elegida: sus hitos frente a tu media, su lugar en la evolución
  y el detalle paso a paso.
"""

from datetime import datetime

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout,
                               QWidget)

from estilo import (ACENTO, APAGADO, ATENCION, BANDERAS_CLIC, BIEN, BORDE, FONDO, PISTA, SECUNDARIO,
                    SERIE_CASTILLOS, SERIE_FEUDAL, TARJETA, TEXTO, color, fuente)
from historial import (VENTANA_MEDIA, Historial, comparacion_final, duracion, nombre_hito, pasos_hechos, principal,
                       puntos_debiles, reloj, resumen_hito, tramos, valor_principal, vista)

MARGEN = 14  # sombra alrededor de la tarjeta
PARTIDAS_GRAFICO = 20
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
IZQ = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
DER = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
CEN = Qt.AlignmentFlag.AlignCenter


def fecha_corta(iso: str) -> str:
    try:
        d = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{d.day:02d} {MESES[d.month - 1]} {d.hour:02d}:{d.minute:02d}"


def mapa_corto(mapa: str) -> str:
    return mapa.split(" Guia")[0]


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


def pintor(w: QWidget) -> QPainter:
    p = QPainter(w)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    return p


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
        caja(p, r, 12, TARJETA, BORDE)
        x, w = 14, r.width() - 28
        texto(p, QRectF(x, 10, w, 16), self.nombre.upper(), fuente(7.5, QFont.Weight.Bold, 1.2), APAGADO)
        grande = reloj(self.valor) if self.valor is not None else "—"
        f_grande = fuente(18, QFont.Weight.Bold)
        texto(p, QRectF(x, 26, w, 32), grande, f_grande, TEXTO)
        ancho_pie = w
        if self.valor is not None and self.comparado is not None:
            t, c = desfase(self.valor - self.comparado)
            t = f"{t} {self.sufijo}"
            f = fuente(8.5, QFont.Weight.DemiBold)
            ancho = QFontMetricsF(f).horizontalAdvance(t) + 16
            chip = QRectF(x + w - ancho, 32, ancho, 20)
            if x + QFontMetricsF(f_grande).horizontalAdvance(grande) + 10 > chip.left():
                # Ficha estrecha: la diferencia baja a la línea de abajo para no pisar el tiempo.
                chip.moveTop(61)
                ancho_pie = w - ancho - 8
            caja(p, chip, 10, color(c, 34), color(c, 80))
            texto(p, chip, t, f, c, CEN)
        f_pie = fuente(8.5, QFont.Weight.Medium)
        pie = self.pie
        if QFontMetricsF(f_pie).horizontalAdvance(pie) > ancho_pie:
            pie = pie.split(" · ")[-1]  # si no cabe entero, la última parte (la mejor marca)
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
        self.setMinimumHeight(210)

    def poner(self, registros: list[dict], seleccion: str | None):
        self.registros, self.seleccion = registros, seleccion
        self.SERIES = series_de(registros[-1] if registros else None)
        self.update()

    def _zona(self) -> QRectF:
        return QRectF(48, 56, self.width() - 48 - 54, self.height() - 56 - 30)

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
        caja(p, r, 12, TARJETA, BORDE)
        texto(p, QRectF(16, 10, 200, 20), "Evolución", fuente(10.5, QFont.Weight.Bold), TEXTO)
        texto(p, QRectF(16, 26, r.width() - 32, 16), "Más abajo = más rápido · discontinua = referencia",
              fuente(8, QFont.Weight.Medium), APAGADO)
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
                caja(p, QRectF(self._x(i, z) - 9, z.top() - 4, 18, z.height() + 8), 9, color(TEXTO, 14))
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
            caja(p, QRectF(bx, z.top(), ancho, alto), 8, color(FONDO, 250), color(TEXTO, 40))
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
        self.setMinimumHeight(210)

    def poner(self, tramos_: list[dict], partidas: int):
        self.tramos, self.partidas = tramos_, partidas
        self.update()

    def paintEvent(self, _):
        p = pintor(self)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        caja(p, r, 12, TARJETA, BORDE)
        texto(p, QRectF(16, 10, r.width() - 32, 20), "Dónde pierdes tiempo", fuente(10.5, QFont.Weight.Bold), TEXTO)
        n = min(self.partidas, VENTANA_MEDIA)
        texto(p, QRectF(16, 26, r.width() - 32, 16),
              f"Media de {'la última partida' if n == 1 else f'las últimas {n} partidas'} · por tramo",
              fuente(8, QFont.Weight.Medium), APAGADO)
        lentos = [t for t in self.tramos if t["media"] >= 1][: self.FILAS]
        y = 52
        if not lentos:
            texto(p, QRectF(16, y, r.width() - 32, 40), "Ningún tramo te hace perder tiempo. ¡Bien!",
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


# --- Barra lateral: resumen general y lista de partidas ----------------------


class FilaResumen(QWidget):
    """Entrada fija arriba de la barra lateral: vuelve a la vista general."""

    def __init__(self, al_pulsar):
        super().__init__()
        self.al_pulsar = al_pulsar
        self.elegida = True
        self.partidas = 0
        self.encima = False
        self.setFixedHeight(50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def poner(self, elegida: bool, partidas: int):
        self.elegida, self.partidas = elegida, partidas
        self.update()

    def paintEvent(self, _):
        p = pintor(self)
        r = QRectF(self.rect()).adjusted(2, 1, -2, -1)
        if self.elegida:
            caja(p, r, 8, color(ACENTO, 40), color(ACENTO, 90))
        elif self.encima:
            caja(p, r, 8, color(TEXTO, 14))
        texto(p, QRectF(12, 8, r.width() - 20, 18), "Resumen general", fuente(9.5, QFont.Weight.Bold), TEXTO)
        n = self.partidas
        texto(p, QRectF(12, 26, r.width() - 20, 16),
              f"Comparativa de {n} {'partida' if n == 1 else 'partidas'}", fuente(8.5, QFont.Weight.Medium),
              SECUNDARIO if self.elegida else APAGADO)
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
    """Partidas de la más reciente a la más antigua: fecha, mapa, Castillos y diferencia con la media."""

    FILA = 52

    def __init__(self, al_elegir):
        super().__init__()
        self.al_elegir = al_elegir
        self.registros: list[dict] = []
        self.seleccion = None
        self.media = None
        self.mejor = None
        self.encima: int | None = None
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def poner(self, registros: list[dict], seleccion: str | None, media, mejor):
        """media y mejor: del hito principal de la guía (Castillos, o la meta en Scouts)."""
        self.registros, self.seleccion = registros, seleccion
        self.media, self.mejor = media, mejor
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
                caja(p, fila, 8, color(ACENTO, 40), color(ACENTO, 90))
            elif k == self.encima:
                caja(p, fila, 8, color(TEXTO, 14))
            ancho = w - 24
            castillos = valor_principal(reg)
            texto(p, QRectF(12, y + 8, ancho - 60, 18), fecha_corta(reg["fecha"]), fuente(9.5, QFont.Weight.Bold),
                  TEXTO)
            texto(p, QRectF(12, y + 8, ancho, 18), reloj(castillos), fuente(10, QFont.Weight.Bold),
                  TEXTO if castillos is not None else APAGADO, DER)
            texto(p, QRectF(12, y + 27, ancho - 70, 16),
                  f"{mapa_corto(reg['mapa'])} · {pasos_hechos(reg)}/{len(reg['pasos'])} pasos",
                  fuente(8.5, QFont.Weight.Medium), SECUNDARIO if elegida else APAGADO)
            if castillos is None:
                t, c = f"sin {nombre_hito(reg, principal(reg))}", APAGADO
            elif castillos == self.mejor:
                t, c = "★ mejor", BIEN
            else:
                t, c = desfase(castillos - self.media) if self.media is not None else ("", APAGADO)
            texto(p, QRectF(12, y + 27, ancho, 16), t, fuente(8.5, QFont.Weight.DemiBold), c, DER)
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
        texto(p, QRectF(8, 0, 200, 22), "PASO", f_cab, APAGADO)
        texto(p, QRectF(w - 182, 0, 54, 22), "HORA", f_cab, APAGADO, DER)
        texto(p, QRectF(w - 124, 0, 54, 22), "VS REF.", f_cab, APAGADO, DER)
        texto(p, QRectF(w - 66, 0, 58, 22), "TRAMO", f_cab, APAGADO, DER)
        peor = max((f["tramo"] for f in self.filas if f["tramo"] is not None), default=None)
        y = 22
        for f in self.filas:
            if peor is not None and peor >= 10 and f["tramo"] == peor:
                caja(p, QRectF(2, y + 1, w - 4, self.FILA - 2), 8, color(ATENCION, 26), color(ATENCION, 70))
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
                texto(p, QRectF(w - 182, y, 174, self.FILA), "sin hacer" if f["saltado"] else "no llegó",
                      fuente(8.5, QFont.Weight.Medium), APAGADO, DER)
            y += self.FILA
        p.end()


# --- Ventana -----------------------------------------------------------------


ESTILO = """
QLabel { color: #f0f3f7; background: transparent; }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,40); border-radius: 3px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: rgba(255,255,255,70); }
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page { height: 0; background: none; }
QPushButton { color: #bac2ce; background: rgba(255,255,255,14); border: 1px solid rgba(255,255,255,34);
              border-radius: 13px; padding: 4px 12px; font-family: 'Segoe UI'; font-size: 9pt; font-weight: 600; }
QPushButton:hover { color: #f0f3f7; background: rgba(255,255,255,34); border-color: rgba(255,255,255,70); }
QPushButton#cerrar { padding: 0; min-width: 26px; max-width: 26px; min-height: 26px; max-height: 26px;
                     font-size: 10pt; }
QPushButton#borrar[confirmar="true"] { color: #ffc4c4; border-color: rgba(255,96,96,140);
                                       background: rgba(255,96,96,40); }
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


class Panel(QWidget):
    """Caja con borde para la barra lateral y el detalle."""

    def paintEvent(self, _):
        p = pintor(self)
        caja(p, QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 12, TARJETA, BORDE)
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
    """Barra lateral con las partidas y el panel con los datos. Lo usan la ventana del
    historial (al acabar una partida) y la página de estadísticas del panel de AoE2C.

    `guia_fija` limita el contenido a una guía; si es None, se ve la de la partida
    elegida o la última jugada."""

    LATERAL = 268

    def __init__(self, historial: Historial, al_titular=None):
        super().__init__()
        self.historial = historial
        self.al_titular = al_titular or (lambda _t: None)  # recibe el subtítulo ("Guía · N partidas")
        self.seleccion: str | None = None  # None = resumen general
        self.fin_de_partida = False
        self.guia_fija: str | None = None
        self.setStyleSheet(ESTILO)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)

        # Sin partidas.
        self.vacio = etiqueta("Aún no hay partidas guardadas.\n\nJuega en un mapa [AoE2C] con AoE2C abierto: "
                              "cada partida se guarda sola, con la hora de cada paso.", 11, QFont.Weight.Medium,
                              SECUNDARIO)
        self.vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vacio.setWordWrap(True)
        raiz.addWidget(self.vacio, 1)

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
        separador.setStyleSheet("background: rgba(255,255,255,26);")
        ll.addWidget(separador)
        ll.addWidget(etiqueta("  PARTIDAS", 7.5, QFont.Weight.Bold, APAGADO, 1.2))
        self.lista = ListaPartidas(self.elegir)
        ll.addWidget(desplazable(self.lista), 1)
        cuerpo.addWidget(lateral)

        # Vista general: medias, evolución y puntos débiles de todas las partidas.
        self.vista_general = QWidget()
        vg = QVBoxLayout(self.vista_general)
        vg.setContentsMargins(0, 0, 0, 0)
        vg.setSpacing(12)
        self.fichas_general = FilaFichas()
        vg.addWidget(self.fichas_general)
        self.grafico_general = Grafico(self.elegir)
        vg.addWidget(self.grafico_general, 1)
        self.debiles = PuntosDebiles()
        vg.addWidget(self.debiles)
        cuerpo.addWidget(self.vista_general, 1)

        # Vista de una partida: hitos frente a tu media, su lugar en la evolución y el paso a paso.
        self.vista_partida = QWidget()
        vp = QVBoxLayout(self.vista_partida)
        vp.setContentsMargins(0, 0, 0, 0)
        vp.setSpacing(12)
        fila = QHBoxLayout()
        self.titulo_detalle = etiqueta("", 13, QFont.Weight.Bold)
        fila.addWidget(self.titulo_detalle, 1)
        self.borrar = QPushButton("Borrar")
        self.borrar.setObjectName("borrar")
        self.borrar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.borrar.setToolTip("Quitar esta partida del historial")
        self.borrar.clicked.connect(self.pulsar_borrar)
        fila.addWidget(self.borrar)
        vp.addLayout(fila)
        self.aviso = etiqueta("", 10, QFont.Weight.DemiBold, BIEN)
        self.aviso.setWordWrap(True)
        self.aviso.setStyleSheet("color: #38cc80; background: rgba(56,204,128,30); border: 1px solid "
                                 "rgba(56,204,128,80); border-radius: 10px; padding: 8px 12px;")
        vp.addWidget(self.aviso)
        self.fichas = FilaFichas()
        vp.addWidget(self.fichas)
        self.grafico = Grafico(self.elegir)
        self.grafico.setFixedHeight(200)
        vp.addWidget(self.grafico)
        detalle = Panel()
        ld = QVBoxLayout(detalle)
        ld.setContentsMargins(12, 10, 6, 8)
        ld.addWidget(etiqueta("Paso a paso", 10.5, QFont.Weight.Bold))
        self.pasos = TablaPasos()
        ld.addWidget(desplazable(self.pasos), 1)
        vp.addWidget(detalle, 1)
        cuerpo.addWidget(self.vista_partida, 1)

        raiz.addWidget(self.contenido, 1)

    # Datos.
    def abrir(self, seleccion: str | None = None, fin_de_partida: bool = False):
        self.historial.cargar()
        self.seleccion = seleccion
        self.fin_de_partida = fin_de_partida
        self.refrescar()

    def mostrar_guia(self, nombre: str | None):
        """Limita el contenido a una guía (None = la de la última partida)."""
        self.guia_fija = nombre
        self.refrescar()

    def elegir(self, id_: str | None):
        self.seleccion = id_
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
            self.borrar.setText("¿Borrar? Pulsa otra vez")
            self.borrar.setProperty("confirmar", True)
            self.borrar.style().polish(self.borrar)

    def _reiniciar_borrar(self):
        self.borrar.setText("Borrar")
        self.borrar.setProperty("confirmar", False)
        self.borrar.style().polish(self.borrar)

    def refrescar(self):
        self._reiniciar_borrar()
        sel = self.historial.buscar(self.seleccion)
        if sel and self.guia_fija and sel["guia"] != self.guia_fija:
            sel = None
        guia = self.guia_fija or (sel["guia"] if sel else self.historial.ultima_guia())
        regs = self.historial.de_guia(guia)
        hay = bool(regs)
        self.vacio.setVisible(not hay)
        self.contenido.setVisible(hay)
        if not hay:
            self.seleccion = None
            self.al_titular("Sin partidas")
            return
        self.seleccion = sel["id"] if sel else None
        self.al_titular(f"{guia} · {len(regs)} {'partida' if len(regs) == 1 else 'partidas'}")

        ultimo = regs[-1]
        claves = vista(ultimo)["hitos"]
        res = resumen_hito(regs, principal(ultimo))
        self.resumen.poner(sel is None, len(regs))
        self.lista.poner(list(reversed(regs)), self.seleccion, res["media"], res["mejor"])
        self.vista_general.setVisible(sel is None)
        self.vista_partida.setVisible(sel is not None)
        if sel is None:
            self.fichas_general.preparar(claves, [f"{nombre_hito(ultimo, k)} · media" for k in claves])
            self._pintar_general(regs)
        else:
            self.fichas.preparar(claves, [nombre_hito(ultimo, k) for k in claves])
            self._pintar_partida(regs, sel)

    def _pintar_general(self, regs: list[dict]):
        n = min(len(regs), VENTANA_MEDIA)
        for clave, ficha in self.fichas_general.items():
            res = resumen_hito(regs, clave)
            pie = [f"Últimas {n}" if n > 1 else "Última", f"mejor {reloj(res['mejor'])}" if res["mejor"] is not None else ""]
            ficha.poner(res["media"], res["media_anterior"], "vs antes", " · ".join(x for x in pie if x))
        self.grafico_general.poner(regs[-PARTIDAS_GRAFICO:], None)
        self.debiles.poner(puntos_debiles(regs), len(regs))

    def _pintar_partida(self, regs: list[dict], sel: dict):
        # Aviso de la partida que acaba de terminar.
        if self.fin_de_partida and sel is regs[-1]:
            partes = ["Partida terminada"]
            valor = valor_principal(sel)
            if valor is not None:
                partes.append(f"{nombre_hito(sel, principal(sel))} a las {reloj(valor)}")
                comp = comparacion_final(self.historial, sel)
                if comp:
                    partes.append(comp.rstrip("."))
            else:
                partes.append(f"guía hasta el paso {pasos_hechos(sel)} de {len(sel['pasos'])}")
            debil = max((f for f in tramos(sel) if f["tramo"] is not None), key=lambda f: f["tramo"], default=None)
            if debil and debil["tramo"] >= 10:
                partes.append(f"donde más perdiste: {debil['n']}. {debil['titulo']} ({desfase(debil['tramo'])[0]})")
            self.aviso.setText(" · ".join(partes))
            self.aviso.show()
        else:
            self.aviso.hide()

        self.titulo_detalle.setText(f"{fecha_corta(sel['fecha'])} · {mapa_corto(sel['mapa'])}")
        for clave, ficha in self.fichas.items():
            res = resumen_hito(regs, clave, excluir=sel["id"])
            pie = []
            if res["mejor"] is not None:
                pie.append(f"Mejor {reloj(res['mejor'])}")
            if sel["referencias"].get(clave) is not None:
                pie.append(f"Ref. {reloj(sel['referencias'][clave])}")
            ficha.poner(sel["hitos"].get(clave), res["media"], "vs media", " · ".join(pie))
        # El gráfico muestra la ventana de partidas que incluye la elegida.
        i = next(k for k, r in enumerate(regs) if r["id"] == sel["id"])
        inicio = min(max(0, len(regs) - PARTIDAS_GRAFICO), i)
        self.grafico.poner(regs[inicio:inicio + PARTIDAS_GRAFICO], sel["id"])
        self.pasos.poner(sel)


class VentanaHistorial(QWidget):
    """Ventana flotante del historial: se abre sola al acabar una partida, encima del
    juego y sin quitarle el foco."""

    ANCHO, ALTO = 1140, 800

    def __init__(self, historial: Historial, al_cerrar):
        super().__init__()
        self.historial = historial
        self.setWindowFlags(BANDERAS_CLIC)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet(ESTILO)
        self.setWindowTitle("AoE2 Coaching · Historial de aperturas")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(MARGEN + 22, MARGEN + 18, MARGEN + 22, MARGEN + 20)
        raiz.setSpacing(12)

        # Cabecera.
        cab = QHBoxLayout()
        textos = QVBoxLayout()
        textos.setSpacing(0)
        textos.addWidget(etiqueta("AOE2 COACHING · HISTORIAL DE APERTURAS", 8.5, QFont.Weight.Bold, APAGADO, 1.4))
        self.subtitulo = etiqueta("", 15, QFont.Weight.Bold)
        textos.addWidget(self.subtitulo)
        cab.addLayout(textos, 1)
        cerrar = QPushButton("✕")
        cerrar.setObjectName("cerrar")
        cerrar.setToolTip("Cerrar el historial")
        cerrar.setCursor(Qt.CursorShape.PointingHandCursor)
        cerrar.clicked.connect(al_cerrar)
        cab.addWidget(cerrar, 0, Qt.AlignmentFlag.AlignTop)
        raiz.addLayout(cab)

        self.cuerpo = ContenidoHistorial(historial, self.subtitulo.setText)
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
        caja(p, tarjeta, 18, FONDO, BORDE)
        p.end()
