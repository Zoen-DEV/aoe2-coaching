"""Panel Match Info: los jugadores de la partida clasificatoria en curso y su elo, arriba
en el centro de la pantalla, encima del juego (como los overlays de los streamers).

- 1v1: el jugador a la izquierda y el rival a la derecha; en el centro, la diferencia de
  elo del rival frente al propio (+24: el rival tiene más).
- Por equipos: una columna por equipo (el propio primero), una fila por jugador y el elo
  medio del equipo arriba.
- Estados: buscando datos (nombres sin elo), cargado, error (un «!» con el motivo) y,
  por jugador, «Sin rating».

Recibe clics (para arrastrarlo) sin quitarle el foco al juego. Solo dibuja: qué partida
se muestra y cuándo lo decide el overlay con el vigilante (vigilante.py).

    py match_ui.py --demo [1v1|equipos|sin_rating]   el panel con una partida inventada
"""

import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QGuiApplication, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QToolTip, QWidget

sys.path.insert(0, str(Path(__file__).resolve().parent))
import banderas  # noqa: E402
import civilizaciones  # noqa: E402
import textos  # noqa: E402
from estilo import (APAGADO, ATENCION, BANDERAS_CLIC, BIEN, BORDE, FONDO, SECUNDARIO, TEXTO, color,  # noqa: E402
                    fuente)
from partida_en_curso import Equipo, Jugador, Partida  # noqa: E402
from textos import t  # noqa: E402
from vigilante import BUSCANDO, CARGADO, ERROR  # noqa: E402

# Colores de jugador del juego (0 a 7), un poco aclarados para leerse sobre el fondo oscuro.
COLORES_JUGADOR = [QColor(64, 120, 255), QColor(236, 56, 56), QColor(40, 190, 70), QColor(250, 214, 30),
                   QColor(40, 214, 220), QColor(196, 84, 255), QColor(170, 170, 176), QColor(255, 146, 30)]
MARGEN = 14             # sombra alrededor de la tarjeta
PAD = 14
CABECERA = 26           # «RM 1v1 en Arabia»
ANCHO_1V1 = 640
CENTRO_1V1 = 76         # columna del centro (vs y diferencia)
ALTO_1V1 = 48
ANCHO_COLUMNA = 300
SEPARACION = 18
FILA = 27
CAB_COLUMNA = 22
RANGO = 58              # ancho reservado al «#12345»
IZQ = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
DER = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
CEN = Qt.AlignmentFlag.AlignCenter


@dataclass(frozen=True)
class Opciones:
    """Datos opcionales del panel (Ajustes)."""
    elo_max: bool = False
    winrate: bool = True
    diferencia: bool = True

    @staticmethod
    def de(config: dict) -> "Opciones":
        return Opciones(bool(config.get("match_elo_max", False)), bool(config.get("match_winrate", True)),
                        bool(config.get("match_diferencia", True)))


def color_jugador(j: Jugador) -> QColor:
    return COLORES_JUGADOR[j.color] if 0 <= j.color < len(COLORES_JUGADOR) else APAGADO


def equipos_ordenados(partida: Partida) -> list[Equipo]:
    """El equipo propio primero (a la izquierda); el resto, en su orden."""
    return sorted(partida.equipos, key=lambda e: not any(j.soy_yo for j in e.jugadores))


def tamano(partida: Partida) -> tuple[int, int]:
    """Ancho y alto de la tarjeta (sin la sombra)."""
    if partida.es_1v1:
        return ANCHO_1V1, PAD + CABECERA + ALTO_1V1 + PAD
    n = len(partida.equipos)
    filas = max(len(e.jugadores) for e in partida.equipos)
    return 2 * PAD + n * ANCHO_COLUMNA + (n - 1) * SEPARACION, PAD + CABECERA + CAB_COLUMNA + filas * FILA + PAD - 4


def texto(p: QPainter, r: QRectF, cadena: str, f: QFont, c: QColor, alinear=IZQ) -> float:
    """Dibuja una línea (recortada con «…» si no cabe) y devuelve su ancho."""
    fm = QFontMetricsF(f)
    if fm.horizontalAdvance(cadena) > r.width():
        cadena = fm.elidedText(cadena, Qt.TextElideMode.ElideRight, r.width())
    p.setFont(f)
    p.setPen(c)
    p.drawText(r.adjusted(0, 0, 2, 0) if alinear & Qt.AlignmentFlag.AlignLeft else r.adjusted(-2, 0, 0, 0),
               int(alinear.value), cadena)
    return fm.horizontalAdvance(cadena)


def ancho(cadena: str, f: QFont) -> float:
    return QFontMetricsF(f).horizontalAdvance(cadena)


class PintorMatch:
    """Dibuja la tarjeta y anota las zonas con consejo (el «!» del error, la diferencia)."""

    def __init__(self, p: QPainter, partida: Partida, estado: str, error: str, opciones: Opciones):
        self.p = p
        self.partida = partida
        self.estado = estado
        self.error = error
        self.op = opciones
        self.ingles = textos.idioma() == "en"
        self.consejos: list[tuple[QRectF, str]] = []

    def dibujar(self, w: float, h: float):
        p = self.p
        tarjeta = QRectF(0, 0, w, h)
        caja = QPainterPath()
        caja.addRoundedRect(tarjeta, 14, 14)
        p.fillPath(caja, FONDO)
        p.setPen(QPen(BORDE, 1))
        p.drawPath(caja)
        self._cabecera(w)
        if self.partida.es_1v1:
            self._uno_contra_uno(w)
        else:
            self._equipos()

    # Cabecera: «RM 1V1 EN ARABIA» y, si toca, el estado.
    def _cabecera(self, w: float):
        pa = self.partida
        titulo = t("mi_en_mapa", modo=pa.titulo, mapa=pa.mapa) if pa.mapa else pa.titulo
        f = fuente(8.5, QFont.Weight.Bold, 1.4)
        extra = f"  ·  {t('mi_buscando')}" if self.estado == BUSCANDO else ""
        total = ancho(titulo.upper() + extra, f) + (22 if self.estado == ERROR else 0)
        x = (w - total) / 2
        y = PAD - 3
        x += texto(self.p, QRectF(x, y, w - x, 18), titulo.upper(), f, APAGADO)
        if extra:
            texto(self.p, QRectF(x, y, w - x, 18), extra, fuente(8.5, QFont.Weight.DemiBold), color(APAGADO, 190))
        if self.estado == ERROR:
            r = QRectF(x + 8, y + 2, 14, 14)
            self.p.setPen(Qt.PenStyle.NoPen)
            self.p.setBrush(color(ATENCION, 60))
            self.p.drawEllipse(r)
            texto(self.p, r, "!", fuente(8, QFont.Weight.Bold), ATENCION, CEN)
            self.consejos.append((r.adjusted(-4, -4, 4, 4), t("mi_error", error=self.error)))

    # Valores de un jugador.
    def _elo(self, j: Jugador) -> tuple[str, QColor, QFont, bool]:
        """(texto, color, letra, es_numero) del hueco del elo."""
        if self.estado == BUSCANDO:
            return "···", APAGADO, fuente(13, QFont.Weight.Bold), False
        if self.estado == ERROR:
            return "—", APAGADO, fuente(13, QFont.Weight.Bold), False
        if j.rating is None:
            return t("mi_sin_rating"), APAGADO, fuente(9, QFont.Weight.DemiBold), False
        return str(j.rating), TEXTO, fuente(14, QFont.Weight.Bold), True

    def _detalle(self, j: Jugador) -> str:
        """Civilización y, según Ajustes, winrate y elo máximo."""
        partes = [civilizaciones.nombre(j.civ, self.ingles) or "?"]
        if self.estado == CARGADO and self.op.winrate and j.winrate is not None:
            partes.append(f"{round(j.winrate * 100)}%")
        if self.estado == CARGADO and self.op.elo_max and j.maximo is not None:
            partes.append(t("mi_max", elo=j.maximo))
        return "  ·  ".join(partes)

    def _rango(self, j: Jugador) -> str:
        return f"#{j.rango}" if self.estado == CARGADO and j.rating is not None and j.rango else ""

    # 1v1: un bloque a cada lado, en espejo.
    def _uno_contra_uno(self, w: float):
        izq, der = (e.jugadores[0] for e in equipos_ordenados(self.partida))
        y = PAD + CABECERA
        bloque = (w - 2 * PAD - CENTRO_1V1) / 2
        self._bloque(izq, QRectF(PAD, y, bloque, ALTO_1V1), espejo=False)
        self._bloque(der, QRectF(w - PAD - bloque, y, bloque, ALTO_1V1), espejo=True)
        cx = w / 2
        texto(self.p, QRectF(cx - 30, y, 60, 22), "vs", fuente(9, QFont.Weight.DemiBold), APAGADO, CEN)
        dif = self.partida.diferencia
        if self.op.diferencia and self.estado == CARGADO and dif is not None:
            cadena = f"+{dif}" if dif > 0 else (f"−{-dif}" if dif < 0 else "±0")
            c = ATENCION if dif > 0 else (BIEN if dif < 0 else APAGADO)
            f = fuente(9, QFont.Weight.DemiBold)
            pw = ancho(cadena, f) + 16
            r = QRectF(cx - pw / 2, y + 25, pw, 20)
            caja = QPainterPath()
            caja.addRoundedRect(r, 10, 10)
            self.p.fillPath(caja, color(c, 36))
            self.p.setPen(QPen(color(c, 90), 1))
            self.p.drawPath(caja)
            texto(self.p, r, cadena, f, c, CEN)
            self.consejos.append((r, t("mi_diferencia")))

    def _bloque(self, j: Jugador, r: QRectF, espejo: bool):
        """Nombre y civilización por fuera, elo y puesto hacia el centro. espejo: el de la derecha."""
        p = self.p
        exterior, interior = (r.right(), r.left()) if espejo else (r.left(), r.right())
        sentido = -1 if espejo else 1
        # Franja del color del jugador en el borde exterior.
        franja = QRectF(exterior - (4 if espejo else 0), r.y() + 2, 4, r.height() - 4)
        p.fillRect(franja, color_jugador(j))
        elo, c_elo, f_elo, _ = self._elo(j)
        w_elo = max(ancho(elo, f_elo), 40)
        # Línea 1: bandera y nombre | elo.
        x = exterior + sentido * 14
        bandera = QRectF(x if not espejo else x - 20, r.y() + 4, 20, 15) if j.pais else None
        if bandera:
            banderas.pintar(p, bandera, j.pais)
            x += sentido * 28
        libre = abs(interior - x) - w_elo - 12
        f_nombre = fuente(11.5, QFont.Weight.Bold)
        nombre_r = QRectF(x if not espejo else x - libre, r.y(), libre, 22)
        texto(p, nombre_r, j.nombre, f_nombre, TEXTO, DER if espejo else IZQ)
        elo_r = QRectF(interior - w_elo if not espejo else interior, r.y() - 1, w_elo, 24)
        texto(p, elo_r, elo, f_elo, c_elo, IZQ if espejo else DER)
        # Línea 2: civilización (y extras) | puesto.
        x2 = exterior + sentido * 14
        rango = self._rango(j)
        f_rango = fuente(8.5, QFont.Weight.DemiBold)
        w_rango = ancho(rango, f_rango) if rango else 0
        libre2 = abs(interior - x2) - w_rango - 12
        detalle_r = QRectF(x2 if not espejo else x2 - libre2, r.y() + 25, libre2, 18)
        texto(p, detalle_r, self._detalle(j), fuente(9, QFont.Weight.Medium), SECUNDARIO, DER if espejo else IZQ)
        if rango:
            rango_r = QRectF(interior - w_rango if not espejo else interior, r.y() + 25, w_rango, 18)
            texto(p, rango_r, rango, f_rango, APAGADO, IZQ if espejo else DER)

    # Por equipos: columnas.
    def _equipos(self):
        y0 = PAD + CABECERA
        for i, e in enumerate(equipos_ordenados(self.partida)):
            x = PAD + i * (ANCHO_COLUMNA + SEPARACION)
            self._columna(e, x, y0)

    def _columna(self, e: Equipo, x: float, y: float):
        p = self.p
        media = e.promedio if self.estado == CARGADO else None
        cadena = t("mi_media", elo=media if media is not None else "—")
        f = fuente(8.5, QFont.Weight.Bold, 0.6)
        texto(p, QRectF(x, y, ANCHO_COLUMNA - RANGO - 6, 18), cadena.upper(), f, SECUNDARIO, DER)
        p.fillRect(QRectF(x, y + CAB_COLUMNA - 4, ANCHO_COLUMNA, 1), BORDE)
        y += CAB_COLUMNA
        for j in e.jugadores:
            self._fila(j, x, y)
            y += FILA

    def _fila(self, j: Jugador, x: float, y: float):
        p = self.p
        p.fillRect(QRectF(x, y + 5, 3, FILA - 10), color_jugador(j))
        cx = x + 10
        if j.pais:
            banderas.pintar(p, QRectF(cx, y + (FILA - 12) / 2, 16, 12), j.pais)
        cx += 22
        elo, c_elo, f_elo, numero = self._elo(j)
        if numero:
            f_elo = fuente(11, QFont.Weight.Bold)
        w_elo = max(ancho(elo, f_elo), 34)
        fin_elo = x + ANCHO_COLUMNA - RANGO - 6
        libre = fin_elo - w_elo - 10 - cx
        f_nombre = fuente(10, QFont.Weight.DemiBold)
        w_nombre = texto(p, QRectF(cx, y, libre, FILA), j.nombre, f_nombre, TEXTO)
        resto = libre - w_nombre - 8
        if resto > 30:
            texto(p, QRectF(cx + w_nombre + 8, y + 1, resto, FILA), self._detalle(j), fuente(8.5), APAGADO)
        texto(p, QRectF(fin_elo - w_elo, y, w_elo, FILA), elo, f_elo, c_elo, DER)
        rango = self._rango(j)
        if rango:
            texto(p, QRectF(fin_elo + 6, y + 1, RANGO, FILA), rango, fuente(8.5, QFont.Weight.DemiBold), APAGADO)


class PanelMatch(QWidget):
    """La ventana del panel. config: el diccionario compartido (posición y opciones)."""

    def __init__(self, config: dict, al_mover=None):
        super().__init__()
        self.config = config
        self.al_mover = al_mover  # se llama al soltar tras arrastrar (para guardar la posición)
        self.partida: Partida | None = None
        self.estado = CARGADO
        self.error = ""
        self.consejos: list[tuple[QRectF, str]] = []
        self._arrastre: QPoint | None = None
        self._opciones: Opciones | None = None
        self.setWindowFlags(BANDERAS_CLIC)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setWindowTitle("Match Info")

    def poner(self, partida: Partida | None, estado: str = CARGADO, error: str = ""):
        opciones = Opciones.de(self.config)  # Ajustes puede cambiarlas con el panel a la vista
        cambio = (partida, estado, error, opciones) != (self.partida, self.estado, self.error, self._opciones)
        self.partida, self.estado, self.error, self._opciones = partida, estado, error, opciones
        if partida is None:
            return
        w, h = tamano(partida)
        if (self.width(), self.height()) != (w + 2 * MARGEN, h + 2 * MARGEN):
            self.resize(w + 2 * MARGEN, h + 2 * MARGEN)
            self.recolocar()
        if cambio:
            self.update()

    # Posición: arriba en el centro, o donde la deje el jugador (siempre dentro de la pantalla).
    def pantalla(self):
        return (self.screen() or QGuiApplication.primaryScreen()).geometry()

    def recolocar(self):
        s = self.pantalla()
        guardada = self.config.get("match_posicion")
        if isinstance(guardada, list) and len(guardada) == 2 and all(isinstance(v, int) for v in guardada):
            x, y = guardada
        else:
            x, y = s.x() + (s.width() - self.width()) // 2, s.y() + int(s.height() * 0.055)
        x = max(s.x() - MARGEN, min(x, s.x() + s.width() - self.width() + MARGEN))
        y = max(s.y() - MARGEN, min(y, s.y() + s.height() - self.height() + MARGEN))
        if self.pos() != QPoint(x, y):
            self.move(x, y)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._arrastre = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self._arrastre is not None:
            self.move(e.globalPosition().toPoint() - self._arrastre)
            return
        pos = QPointF(e.position()) - QPointF(MARGEN, MARGEN)
        consejo = next((c for r, c in self.consejos if r.contains(pos)), "")
        if consejo:
            QToolTip.showText(e.globalPosition().toPoint() + QPoint(10, 14), consejo, self)
        else:
            QToolTip.hideText()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._arrastre is not None:
            self._arrastre = None
            self.config["match_posicion"] = [self.x(), self.y()]
            self.recolocar()  # si quedó fuera de la pantalla, vuelve
            self.config["match_posicion"] = [self.x(), self.y()]
            if self.al_mover:
                self.al_mover()

    def pintar(self, p: QPainter):
        if self.partida is None:
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        w, h = tamano(self.partida)
        tarjeta = QRectF(MARGEN, MARGEN, w, h)
        for i in range(10, 0, -1):  # sombra suave, como la tarjeta de la guía
            path = QPainterPath()
            path.addRoundedRect(tarjeta.adjusted(-i, -i + 3, i, i + 3), 14 + i, 14 + i)
            p.fillPath(path, QColor(0, 0, 0, int(5 * (11 - i) / 3)))
        p.translate(MARGEN, MARGEN)
        pintor = PintorMatch(p, self.partida, self.estado, self.error, Opciones.de(self.config))
        pintor.dibujar(w, h)
        self.consejos = pintor.consejos

    def paintEvent(self, _):
        p = QPainter(self)
        self.pintar(p)
        p.end()

    def imagen(self) -> QImage:
        """La tarjeta en una imagen (capturas y pruebas), sin abrir ninguna ventana."""
        w, h = tamano(self.partida) if self.partida else (10, 10)
        img = QImage(w + 2 * MARGEN, h + 2 * MARGEN, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        self.pintar(p)
        p.end()
        return img


def main():
    """--demo [1v1|equipos|sin_rating]: el panel con una partida inventada. Pasa por los
    estados (buscando, cargado y error) cada 4 s; se arrastra y se cierra con Esc o clic derecho."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from partida_en_curso import partida_de_ejemplo
    args = sys.argv[1:]
    tipo = next((a for a in args if a in ("1v1", "equipos", "sin_rating")), "1v1")
    app = QApplication(sys.argv)
    config = {"match_winrate": True, "match_elo_max": "--max" in args, "match_diferencia": True}
    panel = PanelMatch(config)
    pasos = [(partida_de_ejemplo(tipo, cargada=False), BUSCANDO, ""), (partida_de_ejemplo(tipo), CARGADO, ""),
             (partida_de_ejemplo(tipo, cargada=False), ERROR, "la API respondió 503")]
    i = [0]

    def siguiente():
        panel.poner(*pasos[i[0] % len(pasos)])
        i[0] += 1

    siguiente()
    panel.show()
    QTimer(panel, interval=4000, timeout=siguiente).start()
    panel.keyPressEvent = lambda e: app.quit() if e.key() == Qt.Key.Key_Escape else None
    panel.contextMenuEvent = lambda e: app.quit()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
