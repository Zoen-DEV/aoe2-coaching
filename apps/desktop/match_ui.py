"""Panel Match Info: los jugadores de la partida clasificatoria en curso y su elo, en una
lista estrecha pegada al borde derecho (o izquierdo) de la pantalla, como los overlays
de los streamers.

- Una fila por jugador: color, bandera, nombre, civilización y elo. Al pasar el ratón,
  el detalle (winrate, elo máximo y puesto, según Ajustes).
- 1v1: debajo de su elo, la diferencia del rival frente al propio (+24: tiene más).
- Por equipos: cada equipo con su elo medio encima (el propio primero).
- Estados: buscando datos (nombres sin elo), cargado, error (un «!» con el motivo) y,
  por jugador, «Sin rating».

Se arrastra en vertical y, al soltarlo, se pega al borde más cercano. Recibe clics sin
quitarle el foco al juego. Solo dibuja: qué partida se muestra y cuándo lo decide el
overlay con el vigilante (vigilante.py).

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
MARGEN = 10             # sombra alrededor de la tarjeta
ANCHO = 236
PAD = 6                 # arriba y abajo
LADO = 12               # a izquierda y derecha
CABECERA = 18           # «RM 1V1 · ARABIA»
FILA = 21
CAB_EQUIPO = 15         # «MEDIA 1302» encima de cada equipo
DIFERENCIA = 14         # la diferencia, debajo del elo del rival (1v1)
ALTURA = 0.13           # posición por defecto: a esta fracción de la pantalla desde arriba
RADIO = 8
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
    """El equipo propio primero (arriba); el resto, en su orden."""
    return sorted(partida.equipos, key=lambda e: not any(j.soy_yo for j in e.jugadores))


def tamano(partida: Partida) -> tuple[int, int]:
    """Ancho y alto de la tarjeta (sin la sombra)."""
    alto = PAD + CABECERA + len(partida.jugadores) * FILA + PAD
    if partida.es_1v1:
        return ANCHO, alto + DIFERENCIA // 2
    return ANCHO, alto + len(partida.equipos) * CAB_EQUIPO


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
    """Dibuja la tarjeta y anota las zonas con consejo (el «!» del error, el detalle de
    cada jugador). derecha: pegada al borde derecho (la franja de color va por fuera)."""

    def __init__(self, p: QPainter, partida: Partida, estado: str, error: str, opciones: Opciones,
                 derecha: bool = True):
        self.p = p
        self.partida = partida
        self.estado = estado
        self.error = error
        self.op = opciones
        self.derecha = derecha
        self.ingles = textos.idioma() == "en"
        self.consejos: list[tuple[QRectF, str]] = []

    def dibujar(self, w: float, h: float):
        p = self.p
        # Esquinas redondeadas solo hacia el centro de la pantalla: el lado del borde, recto.
        caja = QPainterPath()
        caja.addRoundedRect(QRectF(0, 0, w, h), RADIO, RADIO)
        recto = QPainterPath()
        recto.addRect(QRectF(w - RADIO if self.derecha else 0, 0, RADIO, h))
        caja = caja.united(recto)
        p.fillPath(caja, color(FONDO, 236))
        p.setPen(QPen(color(BORDE, 150), 1))
        p.drawPath(caja)
        self._cabecera(w)
        y = PAD + CABECERA
        uno = self.partida.es_1v1
        for i, e in enumerate(equipos_ordenados(self.partida)):
            if uno:
                if i:
                    p.fillRect(QRectF(LADO, y - 0.5, w - 2 * LADO, 1), color(BORDE, 110))
            else:
                self._cabecera_equipo(e, w, y)
                y += CAB_EQUIPO
            for j in e.jugadores:
                self._fila(j, w, y)
                y += FILA

    # Cabecera: «RM 1V1 · ARABIA» y, si toca, el estado.
    def _cabecera(self, w: float):
        pa = self.partida
        titulo = t("mi_en_mapa", modo=pa.titulo, mapa=pa.mapa) if pa.mapa else pa.titulo
        y = PAD
        texto(self.p, QRectF(LADO, y, w - 2 * LADO - 20, CABECERA), titulo.upper(), fuente(7.5, QFont.Weight.Bold, 1.2),
              APAGADO)
        if self.estado == ERROR:
            r = QRectF(w - LADO - 13, y + (CABECERA - 13) / 2, 13, 13)
            self.p.setPen(Qt.PenStyle.NoPen)
            self.p.setBrush(color(ATENCION, 60))
            self.p.drawEllipse(r)
            texto(self.p, r, "!", fuente(7.5, QFont.Weight.Bold), ATENCION, CEN)
            self.consejos.append((r.adjusted(-4, -4, 4, 4), t("mi_error", error=self.error)))

    def _cabecera_equipo(self, e: Equipo, w: float, y: float):
        media = e.promedio if self.estado == CARGADO else None
        cadena = t("mi_media", elo=media if media is not None else "—").upper()
        texto(self.p, QRectF(LADO, y, w - 2 * LADO, CAB_EQUIPO), cadena, fuente(7, QFont.Weight.Bold, 0.8), SECUNDARIO, DER)
        self.p.fillRect(QRectF(LADO, y + CAB_EQUIPO / 2, w - 2 * LADO - ancho(cadena, fuente(7, QFont.Weight.Bold, 0.8))
                               - 8, 1), color(BORDE, 110))

    # Valores de un jugador.
    def _elo(self, j: Jugador) -> tuple[str, QColor, QFont, bool]:
        """(texto, color, letra, es_numero) del hueco del elo."""
        if self.estado == BUSCANDO:
            return "···", APAGADO, fuente(9.5, QFont.Weight.Bold), False
        if self.estado == ERROR:
            return "—", APAGADO, fuente(9.5, QFont.Weight.Bold), False
        if j.rating is None:
            return t("mi_sin_rating"), APAGADO, fuente(7.5, QFont.Weight.DemiBold), False
        return str(j.rating), TEXTO, fuente(9.5, QFont.Weight.Bold), True

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

    def _diferencia(self, j: Jugador) -> tuple[str, QColor] | None:
        """En 1v1, debajo del elo del rival: +24 (tiene más, ámbar) o −24 (menos, verde)."""
        dif = self.partida.diferencia
        if not (self.partida.es_1v1 and not j.soy_yo and self.op.diferencia and self.estado == CARGADO
                and dif is not None):
            return None
        cadena = f"+{dif}" if dif > 0 else (f"−{-dif}" if dif < 0 else "±0")
        return cadena, ATENCION if dif > 0 else (BIEN if dif < 0 else APAGADO)

    def _fila(self, j: Jugador, w: float, y: float):
        p = self.p
        fila = QRectF(1, y, w - 2, FILA)
        if j.soy_yo:
            p.fillRect(fila, color(TEXTO, 9))
        # Franja del color del jugador, en el lado del borde de la pantalla.
        p.fillRect(QRectF(w - 6 if self.derecha else 3, y + 4, 3, FILA - 8), color_jugador(j))
        cx = LADO
        if j.pais:
            banderas.pintar(p, QRectF(cx, y + (FILA - 11) / 2, 15, 11), j.pais)
        cx += 21  # el hueco de la bandera siempre, para que los nombres queden alineados
        elo, c_elo, f_elo, _ = self._elo(j)
        w_elo = max(ancho(elo, f_elo), 28)
        fin = w - LADO - 2
        f_nombre = fuente(8.5, QFont.Weight.DemiBold)
        libre = fin - w_elo - 8 - cx
        w_nombre = texto(p, QRectF(cx, y, libre, FILA), j.nombre, f_nombre, TEXTO)
        resto = libre - w_nombre - 6
        if resto > 26:
            civ = civilizaciones.nombre(j.civ, self.ingles) or "?"
            texto(p, QRectF(cx + w_nombre + 6, y + 0.5, resto, FILA), civ, fuente(7.5), APAGADO)
        texto(p, QRectF(fin - w_elo, y, w_elo, FILA), elo, f_elo, c_elo, DER)
        dif = self._diferencia(j)
        if dif:
            cadena, c = dif
            texto(p, QRectF(fin - 60, y + FILA - 3, 60, DIFERENCIA), cadena, fuente(7.5, QFont.Weight.DemiBold), c, DER)
        # Al pasar el ratón: el detalle completo.
        consejo = "  ·  ".join(x for x in (self._detalle(j), self._rango(j)) if x)
        if dif:
            consejo += "\n" + t("mi_diferencia") + f": {dif[0]}"
        self.consejos.append((fila, f"{j.nombre}\n{consejo}"))


class PanelMatch(QWidget):
    """La ventana del panel. config: el diccionario compartido (lado, altura y opciones)."""

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
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setWindowTitle("Match Info")

    @property
    def derecha(self) -> bool:
        return self.config.get("match_lado", "derecha") != "izquierda"

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

    # Posición: pegado a un borde, a la altura que deje el jugador (siempre en la pantalla).
    def pantalla(self):
        return (self.screen() or QGuiApplication.primaryScreen()).geometry()

    def recolocar(self):
        s = self.pantalla()
        altura = self.config.get("match_altura")
        if not isinstance(altura, (int, float)) or isinstance(altura, bool) or not 0 <= altura <= 1:
            altura = ALTURA
        # La tarjeta toca el borde; la sombra de ese lado queda fuera de la pantalla.
        x = s.x() + s.width() - self.width() + MARGEN if self.derecha else s.x() - MARGEN
        y = s.y() + int(s.height() * altura) - MARGEN
        y = max(s.y() - MARGEN, min(y, s.y() + s.height() - self.height() + MARGEN))
        if self.pos() != QPoint(x, y):
            self.move(x, y)
        if self.isVisible():
            self.update()  # la franja de color cambia de lado

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
            s = self.pantalla()
            centro = self.x() + self.width() / 2
            self.config["match_lado"] = "derecha" if centro >= s.x() + s.width() / 2 else "izquierda"
            altura = (self.y() + MARGEN - s.y()) / max(1, s.height())
            self.config["match_altura"] = round(max(0.0, min(1.0, altura)), 4)
            self.recolocar()  # se pega al borde más cercano
            if self.al_mover:
                self.al_mover()

    def pintar(self, p: QPainter):
        if self.partida is None:
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        w, h = tamano(self.partida)
        tarjeta = QRectF(MARGEN, MARGEN, w, h)
        for i in range(8, 0, -1):  # sombra suave
            path = QPainterPath()
            path.addRoundedRect(tarjeta.adjusted(-i, -i + 2, i, i + 2), RADIO + i, RADIO + i)
            p.fillPath(path, QColor(0, 0, 0, int(5 * (9 - i) / 3)))
        p.translate(MARGEN, MARGEN)
        pintor = PintorMatch(p, self.partida, self.estado, self.error, Opciones.de(self.config), self.derecha)
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
    """--demo [1v1|equipos|sin_rating] [--izquierda]: el panel con una partida inventada.
    Pasa por los estados (buscando, cargado y error) cada 4 s; se arrastra y se cierra con
    Esc o clic derecho."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from partida_en_curso import partida_de_ejemplo
    args = sys.argv[1:]
    tipo = next((a for a in args if a in ("1v1", "equipos", "sin_rating")), "1v1")
    app = QApplication(sys.argv)
    config = {"match_winrate": True, "match_elo_max": "--max" in args, "match_diferencia": True,
              "match_lado": "izquierda" if "--izquierda" in args else "derecha"}
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
