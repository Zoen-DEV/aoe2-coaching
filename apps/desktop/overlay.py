"""Overlay de AoE2 Coaching: la guía de apertura para AoE2 DE.

Ventana translúcida, siempre encima y que deja pasar los clics, que dibuja la
guía a partir del archivo que escribe el script XS del mapa (ver lector.py).
Se controla desde su icono en la bandeja del sistema (posición y salir).

Se abre con aoe2c.py (el programa único; ver allí las opciones). También:
    py overlay.py --demo        partida simulada, para ver el diseño sin jugar
    py overlay.py --captura DIR imágenes de prueba (sobre una captura del juego si existe fondo.png)
"""

import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (QAction, QColor, QFont, QFontMetricsF, QGuiApplication, QIcon, QImage, QPainter,
                           QPainterPath, QPen, QPixmap)
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402
import logo  # noqa: E402
import repeticiones  # noqa: E402
import rutas  # noqa: E402
import textos  # noqa: E402
from estilo import (ACENTO, APAGADO, ATENCION, BANDERAS_CLIC, BIEN, BORDE, EMOJI, FONDO, MAL, PISTA,  # noqa: E402
                    SECUNDARIO, TARJETA, TEXTO, color, fuente)
from historial import Historial, Seguimiento, comparacion_final, historial_de_ejemplo  # noqa: E402
from historial_ui import VentanaHistorial  # noqa: E402
from lector import Estado, Lector, cargar_guias, mapas_de  # noqa: E402
from textos import de, t  # noqa: E402

HERE = Path(__file__).resolve().parent
CONFIG = rutas.CONFIG  # %APPDATA%\AoE2Coaching\config.json
log = logging.getLogger("aoe2c")

# --- Estilo ------------------------------------------------------------------

ANCHO = 368
MARGEN = 14  # espacio alrededor de la tarjeta para la sombra
PAD = 18
BOTON = 26  # botón de menú, arriba a la derecha de la tarjeta
DURACION_PLIEGUE = 0.28  # segundos que tarda en plegarse o desplegarse
SIN_DATOS = 4.0  # segundos sin datos nuevos para dar la partida por terminada
ICONOS = {
    "casa": "🏠", "oveja": "🐑", "campamento_maderero": "🪓", "jabali": "🐗", "molino": "🫐",
    "campamento_minero": "⛏️", "centro_urbano": "🏛️", "granja": "🌾", "mercado": "⚖️",
    "herreria": "🔨", "castillo": "🏰", "aldeano": "👤", "cuartel": "⚔️",
    "establo": "🐴", "explorador": "🐎", "galeria_tiro": "🎯", "arquero": "🏹", "miliciano": "🗡️",
    "hombre_armas": "🛡️", "aguila": "🦅",
}


def reloj(seg: int) -> str:
    seg = max(0, seg)
    return f"{seg // 60}:{seg % 60:02d}"


def duracion(seg: int) -> str:
    return f"{seg} s" if seg < 60 else reloj(seg)


# --- Qué se muestra ------------------------------------------------------------


@dataclass
class Condicion:
    etiqueta: str
    valor: str
    fraccion: float
    hecha: bool


@dataclass
class Vista:
    nombre: str
    tiempo: int
    paso: int
    total: int
    hechos: int
    ritmo: tuple[str, QColor] | None
    terminada: bool
    titulo: str = ""
    texto: str = ""
    icono: str = ""
    referencia: int = 0
    condiciones: list[Condicion] = field(default_factory=list)
    siguientes: list[tuple[int, str, int]] = field(default_factory=list)
    aviso: str = ""
    resumen: str = ""
    final: str = ""
    comparacion: str = ""  # esta partida frente al historial (tarjeta final)
    titulo_final: str = ""
    icono_final: str = "castillo"


def ritmo(diferencia: int, margen: int) -> tuple[str, QColor]:
    if diferencia > margen:
        return f"+{duracion(diferencia)}", ATENCION
    if diferencia < -margen:
        return f"−{duracion(-diferencia)}", ACENTO
    return t("ov_a_tiempo"), BIEN


def construir_vista(guia: dict, e: Estado, siguientes: int | None = None, aviso_casas: bool = True) -> Vista:
    """siguientes: pasos de «A continuación» (None = los de la guía). aviso_casas: False lo quita."""
    pasos = guia["pasos"]
    total = len(pasos)
    hechos = sum(1 for h in e.horas if h >= 0)
    ultimo = max((i for i in range(min(e.paso, total)) if e.horas[i] >= 0), default=None)
    r = ritmo(e.horas[ultimo] - pasos[ultimo]["referencia"], guia["margen_segundos"]) if ultimo is not None else None
    v = Vista(guia["nombre"], e.tiempo, e.paso, total, hechos, r, e.paso >= total)
    v.titulo_final = de(guia, "titulo_final") or t("ov_titulo_final")
    v.icono_final = guia.get("icono_final", v.icono_final)

    if v.terminada:
        ult = total - 1
        if e.horas[ult] >= 0:
            texto, _ = ritmo(e.horas[ult] - pasos[ult]["referencia"], guia["margen_segundos"])
            v.resumen = t("ov_resumen", paso=de(pasos[ult], "titulo"), hora=reloj(e.horas[ult]),
                          ref=reloj(pasos[ult]["referencia"]), ritmo=texto.lower())
        saltados = [de(p, "titulo") for p, h in zip(pasos, e.horas) if h == -2]
        if saltados:
            v.resumen += "\n" + t("ov_sin_hacer", pasos=", ".join(saltados))
        v.final = de(guia, "mensaje_final")
        return v

    p = pasos[e.paso]
    v.titulo, v.texto, v.icono, v.referencia = de(p, "titulo"), de(p, "texto"), p["icono"], p["referencia"]
    for c in p["condiciones"]:
        if c["tipo"] == "contador":
            n = e.datos[c["indice"]]
            v.condiciones.append(Condicion(de(c, "etiqueta"), f"{min(n, c['min'])}/{c['min']}", min(1.0, n / c["min"]), n >= c["min"]))
        else:
            estado = e.techs[c["indice"]]
            hecha = (e.edad >= c["objetivo"]) if c["tipo"] == "edad" else estado >= c["objetivo"]
            texto = t("ov_hecha") if hecha else (t("ov_en_curso") if estado >= 1 else t("ov_pendiente"))
            v.condiciones.append(Condicion(de(c, "etiqueta"), texto, 1.0 if hecha else (0.5 if estado >= 1 else 0.0), hecha))
    n_siguientes = guia["pasos_siguientes_visibles"] if siguientes is None else siguientes
    for i in range(e.paso + 1, min(total, e.paso + 1 + n_siguientes)):
        v.siguientes.append((i + 1, de(pasos[i], "titulo"), pasos[i]["referencia"]))
    if aviso_casas and guia["aviso_casas"] and e.tiempo >= 20 and e.libre <= 2 and e.casas_en_obra == 0:
        v.aviso = t("ov_aviso_casas", pob=e.poblacion, max=e.poblacion + e.libre)
    return v


# --- Dibujo ------------------------------------------------------------------


class Pintor:
    """Dibuja (o solo mide, si painter es None) la tarjeta. Devuelve la altura."""

    def __init__(self, painter: QPainter | None, ancho: float):
        self.p = painter
        self.w = ancho

    def texto(self, x, y, w, t, f, c, alinear=Qt.AlignmentFlag.AlignLeft, envolver=False, h=None) -> float:
        fm = QFontMetricsF(f)
        modo = Qt.TextFlag.TextWordWrap if envolver else Qt.TextFlag.TextSingleLine
        flags = int(alinear.value) | int(modo.value)
        if not envolver:
            t = fm.elidedText(t, Qt.TextElideMode.ElideRight, w)
        rect = fm.boundingRect(QRectF(x, y, w, 10000), flags, t)
        alto = h if h is not None else rect.height()
        if self.p:
            self.p.setFont(f)
            self.p.setPen(c)
            vertical = int(Qt.AlignmentFlag.AlignVCenter.value) if h is not None else int(Qt.AlignmentFlag.AlignTop.value)
            self.p.drawText(QRectF(x, y, w, alto), flags | vertical, t)
        return alto

    def caja(self, r: QRectF, radio: float, relleno: QColor, borde: QColor | None = None):
        if not self.p:
            return
        path = QPainterPath()
        path.addRoundedRect(r, radio, radio)
        self.p.fillPath(path, relleno)
        if borde:
            self.p.setPen(QPen(borde, 1))
            self.p.drawPath(path)

    def barra(self, x, y, w, h, fraccion, c):
        self.caja(QRectF(x, y, w, h), h / 2, PISTA)
        if fraccion > 0:
            self.caja(QRectF(x, y, max(h, w * fraccion), h), h / 2, c)

    def pastilla(self, x_derecha, y, t, c) -> float:
        f = fuente(9.5, QFont.Weight.DemiBold)
        w = QFontMetricsF(f).horizontalAdvance(t) + 18
        r = QRectF(x_derecha - w, y, w, 22)
        self.caja(r, 11, color(c, 38), color(c, 90))
        self.texto(r.x(), r.y(), r.width(), t, f, c, Qt.AlignmentFlag.AlignHCenter, h=22)
        return w

    def dibujar(self, v: Vista, aviso_paso: tuple[str, float] | None, entrada: float) -> float:
        x0, w = PAD, self.w - 2 * PAD
        y = PAD - 2

        # Cabecera: nombre de la guía y reloj de la partida.
        self.texto(x0, y, w - 60, v.nombre.upper(), fuente(8.5, QFont.Weight.Bold, 1.4), APAGADO)
        # El reloj deja sitio a la derecha para el botón de menú (otra ventana encima).
        self.texto(x0, y, w - 2 * BOTON - 16, reloj(v.tiempo), fuente(9.5, QFont.Weight.DemiBold), SECUNDARIO,
                   Qt.AlignmentFlag.AlignRight)
        y += 22

        # Paso y ritmo.
        if v.terminada:
            self.texto(x0, y, w, t("ov_completada"), fuente(14, QFont.Weight.Bold), TEXTO, h=24)
        else:
            f1, f2 = fuente(14, QFont.Weight.Bold), fuente(14, QFont.Weight.Normal)
            t1 = t("ov_paso", n=v.paso + 1)
            self.texto(x0, y, w, t1, f1, TEXTO, h=24)
            self.texto(x0 + QFontMetricsF(f1).horizontalAdvance(t1) + 4, y, w, t("ov_de", total=v.total), f2, APAGADO,
                       h=24)
        if v.ritmo:
            self.pastilla(x0 + w, y + 1, *v.ritmo)
        y += 32
        self.barra(x0, y, w, 4, v.hechos / v.total, BIEN if v.terminada else ACENTO)
        y += 16

        # Aviso breve del paso que se acaba de completar.
        if aviso_paso:
            texto, alpha = aviso_paso
            if self.p:
                self.p.setOpacity(alpha)
            r = QRectF(x0, y, w, 32)
            self.caja(r, 10, color(BIEN, 34), color(BIEN, 80))
            self.texto(r.x() + 12, r.y(), r.width() - 24, "✓  " + texto, fuente(9.5, QFont.Weight.DemiBold), BIEN, h=32)
            if self.p:
                self.p.setOpacity(1.0)
            y += 42

        if v.terminada:
            y = self._final(v, x0, y, w)
        else:
            y = self._actual(v, x0, y, w, entrada)
            if v.siguientes:
                y = self._siguientes(v, x0, y, w)
        if v.aviso:
            r = QRectF(x0, y, w, 34)
            self.caja(r, 10, color(MAL, 40), color(MAL, 110))
            self.texto(r.x() + 12, r.y(), r.width() - 24, "⚠  " + v.aviso, fuente(9.5, QFont.Weight.DemiBold), QColor(255, 196, 196), h=34)
            y += 44
        return y + PAD - 10

    def _actual(self, v: Vista, x0, y, w, entrada) -> float:
        dy = (1 - entrada) * 10
        if self.p:
            self.p.setOpacity(0.25 + 0.75 * entrada)
        y0 = y
        y += dy
        ix, iy = x0 + 14, y + 14
        tx = ix + 40 + 12
        tw = x0 + w - 14 - tx
        alto = self._cuerpo_actual(v, ix, iy, tx, tw, medir=True)
        r = QRectF(x0, y, w, alto + 28)
        self.caja(r, 12, TARJETA, BORDE)
        if self.p:
            self.caja(QRectF(x0, y + 12, 3, r.height() - 24), 1.5, ACENTO)
        self._cuerpo_actual(v, ix, iy, tx, tw, medir=False)
        if self.p:
            self.p.setOpacity(1.0)
        return y0 + r.height() + 14

    def _cuerpo_actual(self, v: Vista, ix, iy, tx, tw, medir: bool) -> float:
        p = self.p
        if medir:
            self.p = None
        # Icono.
        self.caja(QRectF(ix, iy, 40, 40), 11, color(ACENTO, 40), color(ACENTO, 70))
        self.texto(ix, iy, 40, ICONOS.get(v.icono, "•"), fuente(16, familia=EMOJI), TEXTO, Qt.AlignmentFlag.AlignHCenter, h=40)
        # Título y objetivo.
        self.texto(tx, iy - 1, tw, v.titulo, fuente(12, QFont.Weight.Bold), TEXTO, h=22)
        restante = v.referencia - v.tiempo
        if restante >= 0:
            sub, c = t("ov_faltan", ref=reloj(v.referencia), resto=reloj(restante)), APAGADO
        else:
            sub, c = t("ov_tarde", ref=reloj(v.referencia), tarde=duracion(-restante)), ATENCION
        self.texto(tx, iy + 21, tw, sub, fuente(9, QFont.Weight.Medium), c, h=18)
        y = iy + 50
        # Instrucción.
        y += self.texto(ix, y, tx + tw - ix, v.texto, fuente(9.5), SECUNDARIO, envolver=True) + 12
        # Condiciones.
        for cond in v.condiciones:
            fv = fuente(9, QFont.Weight.DemiBold)
            self.texto(ix, y, tx + tw - ix, cond.etiqueta, fuente(9, QFont.Weight.Medium), SECUNDARIO, h=18)
            valor = ("✓ " if cond.hecha else "") + cond.valor
            self.texto(ix, y, tx + tw - ix, valor, fv, BIEN if cond.hecha else TEXTO, Qt.AlignmentFlag.AlignRight, h=18)
            y += 21
            self.barra(ix, y, tx + tw - ix, 4, cond.fraccion, BIEN if cond.hecha else ACENTO)
            y += 12
        self.p = p
        return y - iy - 4

    def _siguientes(self, v: Vista, x0, y, w) -> float:
        self.texto(x0 + 2, y, w, t("ov_a_continuacion"), fuente(8, QFont.Weight.Bold, 1.3), APAGADO, h=16)
        y += 22
        for n, titulo, ref in v.siguientes:
            if self.p:
                self.p.setPen(QPen(color(TEXTO, 60), 1.2))
                self.p.setBrush(Qt.BrushStyle.NoBrush)
                self.p.drawEllipse(QRectF(x0 + 2, y + 3, 22, 22))
            self.texto(x0 + 2, y + 3, 22, str(n), fuente(8, QFont.Weight.Bold), SECUNDARIO, Qt.AlignmentFlag.AlignHCenter, h=22)
            self.texto(x0 + 36, y, w - 36 - 48, titulo, fuente(9.5, QFont.Weight.Medium), SECUNDARIO, h=28)
            self.texto(x0, y, w, reloj(ref), fuente(9, QFont.Weight.Medium), APAGADO, Qt.AlignmentFlag.AlignRight, h=28)
            y += 32
        return y + 6

    def _final(self, v: Vista, x0, y, w) -> float:
        tw = w - 28
        alto = 22 + self._medir_envuelto(v.resumen, tw) + 10 + self._medir_envuelto(v.final, tw)
        if v.comparacion:
            alto += 10 + self._medir_envuelto(v.comparacion, tw)
        r = QRectF(x0, y, w, alto + 28)
        self.caja(r, 12, color(BIEN, 26), color(BIEN, 80))
        yy = y + 14
        self.texto(x0 + 14, yy, tw, f"{ICONOS.get(v.icono_final, '🏁')}  {v.titulo_final}", fuente(11.5, QFont.Weight.Bold),
                   TEXTO, h=22)
        yy += 26
        yy += self.texto(x0 + 14, yy, tw, v.resumen, fuente(9.5), SECUNDARIO, envolver=True) + 10
        if v.comparacion:
            yy += self.texto(x0 + 14, yy, tw, v.comparacion, fuente(9.5, QFont.Weight.DemiBold), TEXTO,
                             envolver=True) + 10
        self.texto(x0 + 14, yy, tw, v.final, fuente(9.5, QFont.Weight.Medium), TEXTO, envolver=True)
        return y + r.height() + 14

    @staticmethod
    def _medir_envuelto(t: str, w: float) -> float:
        fm = QFontMetricsF(fuente(9.5))
        return fm.boundingRect(QRectF(0, 0, w, 10000), int(Qt.TextFlag.TextWordWrap.value), t).height()


# --- Ventana -----------------------------------------------------------------


ESTILO_MENU = """
QMenu { background: rgba(18, 22, 30, 250); color: #e8ecf2; border: 1px solid rgba(255,255,255,30);
        border-radius: 10px; padding: 6px; font-family: 'Segoe UI'; font-size: 10pt; }
QMenu::item { padding: 7px 18px 7px 26px; border-radius: 6px; }
QMenu::item:selected { background: rgba(94, 164, 255, 60); }
QMenu::indicator { width: 12px; height: 12px; left: 8px; }
QMenu::separator { height: 1px; background: rgba(255,255,255,24); margin: 5px 8px; }
"""

def ventana_en_primer_plano_es_aoe() -> bool:
    """True si la ventana activa es la del juego (o una del propio overlay, como su menú)."""
    try:
        import ctypes
        from ctypes import wintypes
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == os.getpid():
            return True
        proceso = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not proceso:
            return False
        try:
            buf = ctypes.create_unicode_buffer(1024)
            n = wintypes.DWORD(1024)
            if not kernel32.QueryFullProcessImageNameW(proceso, 0, buf, ctypes.byref(n)):
                return False
            return buf.value.lower().endswith("aoe2de_s.exe")
        finally:
            kernel32.CloseHandle(proceso)
    except (OSError, AttributeError):
        return True  # fuera de Windows no se filtra


class VentanaClic(QWidget):
    """Ventana pequeña que sí recibe clics (la de la tarjeta los deja pasar al juego),
    sin quitarle el foco al juego."""

    def __init__(self, al_pulsar, consejo: str):
        super().__init__()
        self.al_pulsar = al_pulsar
        self.encima = False
        self.setWindowFlags(BANDERAS_CLIC)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(consejo)

    def enterEvent(self, _):
        self.encima = True
        self.update()

    def leaveEvent(self, _):
        self.encima = False
        self.update()

    def mousePressEvent(self, evento):
        if evento.button() == Qt.MouseButton.LeftButton:
            if os.environ.get("GUIA_DEBUG"):
                print("CLIC", type(self).__name__, flush=True)
            self.al_pulsar(self)


def chevron(p: QPainter, cx: float, cy: float, hacia_derecha: bool, c: QColor, tam: float = 4.0):
    p.setPen(QPen(c, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    d = tam if hacia_derecha else -tam
    p.drawPolyline([QPointF(cx - d / 2, cy - tam), QPointF(cx + d / 2, cy), QPointF(cx - d / 2, cy + tam)])


class BotonRedondo(VentanaClic):
    """Botón redondo de la cabecera: "puntos" (menú) o "plegar"."""

    def __init__(self, icono: str, al_pulsar, consejo: str, lado_derecho):
        super().__init__(al_pulsar, consejo)
        self.icono = icono
        self.lado_derecho = lado_derecho  # función: True si el overlay está a la derecha
        self.setFixedSize(BOTON, BOTON)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(color(TEXTO, 70 if self.encima else 34), 1))
        p.setBrush(color(TEXTO, 34 if self.encima else 14))
        p.drawEllipse(QRectF(0.5, 0.5, BOTON - 1, BOTON - 1))
        tinta = TEXTO if self.encima else SECUNDARIO
        if self.icono == "puntos":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(tinta)
            for dx in (-5.5, 0, 5.5):
                p.drawEllipse(QPointF(BOTON / 2 + dx, BOTON / 2), 1.7, 1.7)
        else:  # plegar: apunta hacia el borde de la pantalla
            chevron(p, BOTON / 2, BOTON / 2, self.lado_derecho(), tinta)
        p.end()


class Pestana(VentanaClic):
    """Pestaña pegada al borde de la pantalla cuando la tarjeta está plegada."""

    ANCHO, ALTO = 34, 82

    def __init__(self, al_pulsar, lado_derecho):
        super().__init__(al_pulsar, t("ov_mostrar_guia"))
        self.lado_derecho = lado_derecho
        self.texto = ""
        self.setFixedSize(self.ANCHO, self.ALTO)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        derecha = self.lado_derecho()
        r = QRectF(0.5, 0.5, self.ANCHO + 14, self.ALTO - 1)
        if not derecha:
            r.moveLeft(-14.5)
        path = QPainterPath()
        path.addRoundedRect(r, 12, 12)
        p.fillPath(path, QColor(22, 28, 38, 252) if self.encima else FONDO)
        p.setPen(QPen(color(ACENTO, 140) if self.encima else BORDE, 1))
        p.drawPath(path)
        p.fillRect(QRectF(self.ANCHO - 3 if derecha else 0, 16, 3, self.ALTO - 32), ACENTO)
        chevron(p, self.ANCHO / 2, 22, not derecha, TEXTO if self.encima else SECUNDARIO, 4.5)
        p.setFont(fuente(10, QFont.Weight.Bold))
        p.setPen(TEXTO)
        p.drawText(QRectF(0, 36, self.ANCHO, 20), int(Qt.AlignmentFlag.AlignCenter.value), self.texto)
        p.setFont(fuente(7.5, QFont.Weight.DemiBold))
        p.setPen(APAGADO)
        p.drawText(QRectF(0, 54, self.ANCHO, 16), int(Qt.AlignmentFlag.AlignCenter.value), t("ov_pestana_paso"))
        p.end()


class PestanaHistorial(VentanaClic):
    """Pestaña en el borde de la pantalla, fuera de partida, que abre el historial."""

    ANCHO, ALTO = 34, 128

    def __init__(self, al_pulsar, lado_derecho):
        super().__init__(al_pulsar, t("ov_ver_historial"))
        self.lado_derecho = lado_derecho
        self.setFixedSize(self.ANCHO, self.ALTO)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        derecha = self.lado_derecho()
        r = QRectF(0.5, 0.5, self.ANCHO + 14, self.ALTO - 1)
        if not derecha:
            r.moveLeft(-14.5)
        path = QPainterPath()
        path.addRoundedRect(r, 12, 12)
        p.fillPath(path, QColor(22, 28, 38, 252) if self.encima else FONDO)
        p.setPen(QPen(color(ACENTO, 140) if self.encima else BORDE, 1))
        p.drawPath(path)
        p.fillRect(QRectF(self.ANCHO - 3 if derecha else 0, 16, 3, self.ALTO - 32), ACENTO)
        # Icono: tres barras que bajan (tiempos que mejoran).
        tinta = TEXTO if self.encima else SECUNDARIO
        for k, h in enumerate((12, 9, 6)):
            p.fillRect(QRectF(self.ANCHO / 2 - 7 + k * 5, 30 - h, 3.4, h), tinta)
        # Texto vertical.
        p.save()
        p.translate(self.ANCHO / 2, 80)
        p.rotate(90 if derecha else -90)
        p.setFont(fuente(7.5, QFont.Weight.Bold, 1.2))
        p.setPen(TEXTO if self.encima else APAGADO)
        p.drawText(QRectF(-44, -9, 88, 18), int(Qt.AlignmentFlag.AlignCenter.value), t("ov_pestana_historial"))
        p.restore()
        p.end()


def cargar_config() -> dict:
    return C.cargar(CONFIG)


class Overlay(QWidget):
    def __init__(self, fuente_estado, solo_con_juego: bool = True, historial: Historial | None = None,
                 seguimiento: Seguimiento | None = None, config: dict | None = None):
        super().__init__()
        self.historial = historial
        self.seguimiento = seguimiento
        self.fuente_estado = fuente_estado  # función que devuelve (guia, estado, frescura en s)
        self.solo_con_juego = solo_con_juego
        self.config = config if config is not None else cargar_config()  # compartido con el panel
        self.al_abrir_panel = None  # función que abre el panel de AoE2C (la pone main)
        self.vista: Vista | None = None
        self.paso_anterior: int | None = None
        self.aviso_paso: tuple[str, float] | None = None  # (texto, hora de inicio)
        self.inicio_entrada = 0.0
        self.fin_desde: float | None = None
        self.opacidad = 0.0
        self.pliegue = 1.0 if self.config["plegado"] else 0.0  # 0 = desplegada, 1 = plegada
        self.anim_desde = self.pliegue
        self.anim_inicio = 0.0
        self.pix: QPixmap | None = None
        self.pix_clave = None
        self.alto_cache: float | None = None
        self.ultima_geometria = None
        self.juego_delante = True
        self.ultima_comprobacion = 0.0
        self.bandeja = None
        self.estado_bandeja = ""
        self.menu_bandeja: QMenu | None = None
        self.menu_abierto: QMenu | None = None
        self.guia: dict | None = None
        self._alto_max: dict[tuple, float] = {}
        self.setWindowFlags(BANDERAS_CLIC | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setWindowOpacity(0.0)
        derecha = lambda: self.config["posicion"] != "izquierda"  # noqa: E731
        self.boton_menu = BotonRedondo("puntos", self.abrir_menu, t("ov_menu"), derecha)
        self.boton_plegar = BotonRedondo("plegar", lambda _: self.plegar(True), t("ov_plegar"), derecha)
        self.pestana = Pestana(lambda _: self.plegar(False), derecha)
        # Historial: la ventana y la pestaña que la abre fuera de partida.
        self.ventana_historial = VentanaHistorial(historial, self.cerrar_historial) if historial else None
        self.idioma = textos.idioma()  # para rehacer los textos fijos si el panel cambia el idioma
        self.pestana_historial = PestanaHistorial(lambda _: self.abrir_historial(), derecha)
        self.historial_abierto = False
        self.historial_forzado = False  # abierto desde el menú: se ve aunque el juego no esté delante
        self.opacidad_historial = 0.0
        self.en_partida = False
        self.ultimo_raise = 0.0
        self.temporizador = QTimer(self, interval=33, timeout=self.tick)
        self.temporizador.setTimerType(Qt.TimerType.PreciseTimer)  # fotogramas regulares en las animaciones
        self.temporizador.start()

    # Menú y acciones.
    def crear_menu(self) -> QMenu:
        menu = QMenu()
        menu.setStyleSheet(ESTILO_MENU)
        menu.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.llenar_menu(menu)
        return menu

    def llenar_menu(self, menu: QMenu):
        """Opciones del menú (⋯ de la tarjeta y clic derecho en la bandeja). Se rellena
        cada vez que se abre, así las marcas siguen lo que se cambie en el panel."""
        menu.clear()
        if self.al_abrir_panel:
            accion = menu.addAction(t("menu_abrir_panel"), self.al_abrir_panel)
            f = accion.font()
            f.setBold(True)
            accion.setFont(f)
            menu.addSeparator()
        menu.addAction(t("menu_mostrar_guia"), lambda: self.plegar(not self.config["plegado"]))
        if self.historial:
            menu.addAction(t("menu_ver_historial"), lambda: self.abrir_historial(forzado=True))
            accion = QAction(t("menu_pestana"), menu, checkable=True, checked=self.config["pestana_historial"])
            accion.triggered.connect(self.cambiar_pestana_historial)
            menu.addAction(accion)
        menu.addSeparator()
        for clave, valor in (("menu_derecha", "derecha"), ("menu_izquierda", "izquierda")):
            accion = QAction(t(clave), menu, checkable=True, checked=self.config["posicion"] == valor)
            accion.triggered.connect(lambda _=False, v=valor: self.cambiar_posicion(v))
            menu.addAction(accion)
        menu.addSeparator()
        menu.addAction(t("menu_cerrar"), QApplication.instance().quit)

    def abrir_historial(self, seleccion: str | None = None, fin_de_partida: bool = False, forzado: bool = False):
        if not self.ventana_historial:
            return
        self.ventana_historial.abrir(seleccion, fin_de_partida)
        self.historial_abierto = True
        self.historial_forzado = forzado

    def cerrar_historial(self):
        self.historial_abierto = False
        self.historial_forzado = False

    def cambiar_pestana_historial(self, valor: bool):
        self.config["pestana_historial"] = bool(valor)
        self.guardar_config()

    def abrir_menu(self, boton: QWidget):
        # popup() no bloquea: el overlay sigue actualizándose con el menú abierto.
        self.menu_abierto = self.crear_menu()
        if os.environ.get("GUIA_DEBUG"):
            self.menu_abierto.aboutToShow.connect(lambda: print("MENU ABIERTO", flush=True))
        esquina = boton.mapToGlobal(QPoint(boton.width(), boton.height()))
        self.menu_abierto.popup(QPoint(esquina.x() - self.menu_abierto.sizeHint().width(), esquina.y() + 6))

    def plegar(self, plegado: bool, guardar: bool = True):
        if plegado != self.config["plegado"]:
            # Animación por tiempo: parte de donde esté ahora, aunque se pulse a mitad.
            self.anim_desde = self.pliegue
            self.anim_inicio = time.monotonic()
            self.temporizador.setInterval(16)  # arranca ya a 60 fps, sin esperar al siguiente ciclo
        self.config["plegado"] = plegado
        if guardar:
            self.guardar_config()

    def reiniciar(self):
        """Estado inicial, para cuando el jugador sale de la partida."""
        self.vista = self.guia = None
        self.paso_anterior = self.aviso_paso = self.fin_desde = None
        self.pix_clave = self.alto_cache = self.ultima_geometria = None
        if self.config["plegado"]:
            self.config["plegado"] = False
            self.guardar_config()
        self.pliegue = self.anim_desde = 0.0

    def pliegue_actual(self, ahora: float) -> float:
        objetivo = 1.0 if self.config["plegado"] else 0.0
        t = (ahora - self.anim_inicio) / DURACION_PLIEGUE
        if t >= 1:
            return objetivo
        t = 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2  # aceleración y frenado suaves
        return self.anim_desde + (objetivo - self.anim_desde) * t

    def cambiar_posicion(self, valor: str):
        self.config["posicion"] = valor
        self.guardar_config()

    def guardar_config(self):
        C.guardar(self.config, CONFIG)

    def aplicar_idioma(self):
        """El panel cambió el idioma: rehace los textos fijos (consejos y ventana del historial)."""
        self.idioma = textos.idioma()
        self.boton_menu.setToolTip(t("ov_menu"))
        self.boton_plegar.setToolTip(t("ov_plegar"))
        self.pestana.setToolTip(t("ov_mostrar_guia"))
        self.pestana_historial.setToolTip(t("ov_ver_historial"))
        self.alto_cache = None
        for w in (self.pestana, self.pestana_historial):
            w.update()
        if self.ventana_historial:
            self.ventana_historial.hide()
            self.ventana_historial.deleteLater()
            self.ventana_historial = VentanaHistorial(self.historial, self.cerrar_historial)
            self.historial_abierto = self.historial_forzado = False
            self.opacidad_historial = 0.0

    # Estado del juego -> vista.
    def tick(self):
        if textos.idioma() != self.idioma:
            self.aplicar_idioma()
        guia, estado, frescura = self.fuente_estado()
        ahora = time.monotonic()
        en_partida = guia is not None and estado is not None and frescura < SIN_DATOS
        if not en_partida and self.vista is not None and self.opacidad == 0:
            self.reiniciar()  # salió de la partida: cuando ya no se ve, vuelve al estado inicial
        if en_partida:
            vista = construir_vista(guia, estado, self.config.get("pasos_siguientes"), self.config.get("aviso_casas", True))
            if self.paso_anterior is not None and vista.paso > self.paso_anterior:
                i = vista.paso - 1
                p = guia["pasos"][i]
                h = estado.horas[i]
                extra = ""
                if h >= 0:
                    texto, _ = ritmo(h - p["referencia"], guia["margen_segundos"])
                    extra = f" · {reloj(h)}" + ("" if texto == t("ov_a_tiempo") else f" ({texto})")
                self.aviso_paso = (f"{de(p, 'titulo')}{extra}", ahora)
                self.inicio_entrada = ahora
            self.paso_anterior = vista.paso
            self.vista = vista
            self.guia = guia
            if vista.terminada and self.fin_desde is None:
                self.fin_desde = ahora
            if not vista.terminada:
                self.fin_desde = None
            if vista.terminada and self.historial and self.seguimiento:
                vista.comparacion = comparacion_final(self.historial, self.seguimiento.actual)
        if self.solo_con_juego and ahora - self.ultima_comprobacion > 0.25:
            self.ultima_comprobacion = ahora
            self.juego_delante = ventana_en_primer_plano_es_aoe()
        visible = en_partida and self.vista is not None and self.juego_delante
        if self.fin_desde is not None and ahora - self.fin_desde > 90:
            visible = False  # el resumen final se queda 90 s
        self.opacidad = self.acercar(self.opacidad, 1.0 if visible else 0.0, 0.3)
        self.pliegue = self.pliegue_actual(ahora)
        self.actualizar_bandeja(guia, estado, frescura)
        self.en_partida = en_partida
        self.tick_historial(en_partida)

        plegada = self.pliegue > 0.98
        o = self.opacidad * min(1.0, max(0.3, float(self.config.get("opacidad", 1.0))))  # preferencia del panel
        self.mostrar(self, o if not plegada else 0)
        self.mostrar(self.boton_menu, o if self.pliegue < 0.02 else 0)
        self.mostrar(self.boton_plegar, o if self.pliegue < 0.02 else 0)
        self.mostrar(self.pestana, o if self.pliegue > 0.6 else 0)
        if self.vista:
            texto = "✓" if self.vista.terminada else str(self.vista.paso + 1)
            if texto != self.pestana.texto:
                self.pestana.texto = texto
                self.pestana.update()
        if self.isVisible() or self.pestana.isVisible():
            self.renderizar(ahora)
            self.recolocar()
            if ahora - self.ultimo_raise > 5:
                for w in (self, self.boton_plegar, self.boton_menu, self.pestana):
                    if w.isVisible():
                        w.raise_()
                self.ultimo_raise = ahora
        # 60 fps solo mientras algo se anima; en reposo basta con 20 comprobaciones por segundo.
        animando = (0 < self.opacidad < 1) or (0 < self.pliegue < 1) or self.aviso_paso is not None \
            or ahora - self.inicio_entrada < 0.5 or 0 < self.opacidad_historial < 1
        intervalo = 16 if animando else 50
        if self.temporizador.interval() != intervalo:
            self.temporizador.setInterval(intervalo)

    def tick_historial(self, en_partida: bool):
        """La ventana del historial se abre sola al acabar (o pausar) la partida y se
        cierra al volver a ella. Fuera de partida, la pestaña del borde la abre."""
        if not self.ventana_historial:
            return
        if self.seguimiento and self.seguimiento.terminada:
            id_ = self.seguimiento.terminada
            self.seguimiento.terminada = None
            if self.config.get("abrir_historial_al_terminar", True):
                self.abrir_historial(id_, fin_de_partida=True)
        if en_partida and self.historial_abierto and not self.historial_forzado:
            self.historial_abierto = False  # se reanudó la partida
        visible = self.historial_abierto and (self.historial_forzado or (self.juego_delante and not en_partida))
        self.opacidad_historial = self.acercar(self.opacidad_historial, 1.0 if visible else 0.0, 0.3)
        self.mostrar(self.ventana_historial, self.opacidad_historial)
        pestana = (self.config["pestana_historial"] and self.solo_con_juego and self.juego_delante
                   and not en_partida and not self.historial_abierto)
        self.mostrar(self.pestana_historial, 1.0 if pestana else 0.0)
        if pestana:
            pantalla = (self.pestana_historial.screen() or QGuiApplication.primaryScreen()).geometry()
            derecha = self.config["posicion"] != "izquierda"
            x = pantalla.x() + pantalla.width() - PestanaHistorial.ANCHO if derecha else pantalla.x()
            y = pantalla.y() + int(pantalla.height() * 0.42)
            if self.pestana_historial.pos() != QPoint(x, y):
                self.pestana_historial.move(x, y)
                self.pestana_historial.update()

    def renderizar(self, ahora: float):
        """Dibuja la tarjeta en una imagen guardada y solo la rehace si cambia lo que se ve.
        Mover la ventana (al plegar) no necesita redibujar nada."""
        aviso = self.aviso_actual(ahora)
        entrada = self.entrada(ahora)
        clave = (repr(self.vista), aviso and (aviso[0], round(aviso[1] * 24)), round(entrada * 30))
        if clave == self.pix_clave:
            return
        self.pix_clave = clave
        alto = Pintor(None, ANCHO).dibujar(self.vista, aviso, 1.0)
        self.alto_cache = alto
        escala = self.devicePixelRatioF() or 1.0
        pix = QPixmap(int((ANCHO + 2 * MARGEN) * escala), int((alto + 2 * MARGEN) * escala))
        pix.setDevicePixelRatio(escala)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        self.pintar(p, ahora)
        p.end()
        self.pix = pix
        self.update()

    @staticmethod
    def acercar(valor: float, objetivo: float, paso: float) -> float:
        valor += (objetivo - valor) * paso
        return objetivo if abs(valor - objetivo) < 0.01 else valor

    @staticmethod
    def mostrar(w: QWidget, opacidad: float):
        if abs(w.windowOpacity() - opacidad) > 0.004:
            w.setWindowOpacity(opacidad)
        if opacidad > 0 and not w.isVisible():
            w.show()
        elif opacidad <= 0 and w.isVisible():
            w.hide()

    def actualizar_bandeja(self, guia, estado, frescura):
        if not self.bandeja:
            return
        if guia and estado:
            texto = t("ov_bandeja_paso", guia=guia["nombre"], n=min(estado.paso + 1, len(guia["pasos"])))
            if frescura >= 45:
                texto += t("ov_sin_partida")
        else:
            texto = t("bandeja_esperando")
        if texto != self.estado_bandeja:
            self.estado_bandeja = texto
            self.bandeja.setToolTip(texto)

    def aviso_actual(self, ahora: float):
        if not self.aviso_paso:
            return None
        texto, t0 = self.aviso_paso
        edad = ahora - t0
        if edad > 4.0:
            self.aviso_paso = None
            return None
        alpha = min(1.0, edad / 0.25) * (1.0 if edad < 3.4 else max(0.0, (4.0 - edad) / 0.6))
        return texto, alpha

    def entrada(self, ahora: float) -> float:
        t = min(1.0, (ahora - self.inicio_entrada) / 0.45)
        return 1 - (1 - t) ** 3

    def alto_tarjeta(self) -> float:
        if not self.vista:
            return 200
        if self.alto_cache is None:
            self.alto_cache = Pintor(None, ANCHO).dibujar(self.vista, self.aviso_actual(time.monotonic()), 1.0)
        return self.alto_cache

    def alto_maximo(self, guia: dict) -> float:
        """La tarjeta más alta posible en esta guía (con aviso de paso y de casas),
        para fijar su borde superior y que los botones no se muevan."""
        clave = (guia["nombre"], self.config.get("pasos_siguientes"), textos.idioma())
        if self._alto_max.get(clave) is None:
            altos = []
            for paso in range(len(guia["pasos"]) + 1):
                v = construir_vista(guia, estado_simulado(guia, paso, 30), self.config.get("pasos_siguientes"))
                v.aviso = v.aviso or t("ov_aviso_casas", pob=14, max=15)
                if v.terminada:
                    v.comparacion = t("hi_nueva_mejor", hora="16:40") + " · " + t("hi_media", hora="17:05", dif="−1:20")
                altos.append(Pintor(None, ANCHO).dibujar(v, ("Paso · 0:00 (+10 s)", 1.0), 1.0))
            self._alto_max[clave] = max(altos)
        return self._alto_max[clave]

    def recolocar(self):
        pantalla = (self.screen() or QGuiApplication.primaryScreen()).geometry()
        alto = int(self.alto_tarjeta()) + 2 * MARGEN
        ancho = ANCHO + 2 * MARGEN
        derecha = self.config["posicion"] != "izquierda"
        if derecha:  # encima del marcador de puntos; el borde de arriba queda fijo
            x = pantalla.x() + pantalla.width() - ancho - 4
            maximo = int(self.alto_maximo(self.guia)) + 2 * MARGEN if self.guia else alto
            y = pantalla.y() + int(pantalla.height() * 0.715) - maximo
        else:
            x, y = pantalla.x() + 6, pantalla.y() + int(pantalla.height() * 0.27)
        # Al plegar, la tarjeta se desliza hacia el borde.
        desplazamiento = int(self.pliegue * (ancho + 10))
        x += desplazamiento if derecha else -desplazamiento
        geometria = (x, y, ancho, alto)
        if geometria == self.ultima_geometria:
            return  # nada que mover
        self.ultima_geometria = geometria
        self.setGeometry(*geometria)
        by = y + MARGEN + PAD - 8
        bx = x + MARGEN + ANCHO - PAD - BOTON + 6
        self.boton_menu.move(bx, by)
        self.boton_plegar.move(bx - BOTON - 6, by)
        px = pantalla.x() + pantalla.width() - Pestana.ANCHO if derecha else pantalla.x()
        self.pestana.move(px, y + MARGEN + 10)

    def paintEvent(self, _):
        if not self.vista or self.pix is None:
            return
        p = QPainter(self)
        p.drawPixmap(0, 0, self.pix)
        p.end()

    def pintar(self, p: QPainter, ahora: float | None = None):
        ahora = time.monotonic() if ahora is None else ahora
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        aviso = self.aviso_actual(ahora)
        alto = Pintor(None, ANCHO).dibujar(self.vista, aviso, 1.0)
        tarjeta = QRectF(MARGEN, MARGEN, ANCHO, alto)
        # Sombra suave.
        for i in range(10, 0, -1):
            path = QPainterPath()
            path.addRoundedRect(tarjeta.adjusted(-i, -i + 3, i, i + 3), 18 + i, 18 + i)
            p.fillPath(path, QColor(0, 0, 0, int(5 * (11 - i) / 3)))
        path = QPainterPath()
        path.addRoundedRect(tarjeta, 18, 18)
        p.fillPath(path, FONDO)
        p.setPen(QPen(BORDE, 1))
        p.drawPath(path)
        p.translate(MARGEN, MARGEN)
        Pintor(p, ANCHO).dibujar(self.vista, aviso, self.entrada(ahora))

    # Bandeja del sistema.
    def crear_bandeja(self, app: QApplication):
        self.bandeja = QSystemTrayIcon(icono_app(), app)
        self.bandeja.setToolTip("AoE2 Coaching")
        self.menu_bandeja = self.crear_menu()
        self.menu_bandeja.aboutToShow.connect(lambda: self.llenar_menu(self.menu_bandeja))
        self.bandeja.setContextMenu(self.menu_bandeja)  # clic derecho: menú con «Cerrar AoE2C»
        self.bandeja.activated.connect(self.pulsar_bandeja)
        self.bandeja.show()

    def pulsar_bandeja(self, motivo):
        """Clic (o doble clic) en el icono de la bandeja: abre el panel."""
        if motivo in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            if self.al_abrir_panel:
                self.al_abrir_panel()


# --- Icono y aviso de inicio ---------------------------------------------------

def icono_app() -> QIcon:
    """El logo de AoE2C (logo.py): ventanas, bandeja y aviso de inicio."""
    return logo.icono()


def suave(t: float) -> float:
    """Curva de salida cúbica (rápida al principio, frena al final)."""
    t = min(1.0, max(0.0, t))
    return 1 - (1 - t) ** 3


class Bienvenida(QWidget):
    """Tarjeta breve en el centro de la pantalla al abrir el programa, para saber que
    se abrió. Entra con un leve zoom, se queda un momento y se desvanece. No recibe
    clics ni quita el foco."""

    W, H, SOMBRA = 320, 196, 16
    ENTRADA, FIJA, SALIDA = 0.45, 1.9, 0.6

    def __init__(self):
        super().__init__()
        self.setWindowFlags(BANDERAS_CLIC | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(self.W + 2 * self.SOMBRA, self.H + 2 * self.SOMBRA)
        self.inicio = 0.0
        self.temporizador = QTimer(self, interval=16, timeout=self.update)
        self.temporizador.setTimerType(Qt.TimerType.PreciseTimer)

    def duracion(self) -> float:
        return self.ENTRADA + self.FIJA + self.SALIDA

    def mostrar(self):
        pantalla = QGuiApplication.primaryScreen().geometry()
        self.move(pantalla.center() - self.rect().center())
        self.inicio = time.monotonic()
        self.show()
        self.temporizador.start()

    def fotograma(self, t: float) -> tuple[float, float, float]:
        """(opacidad, escala, avance de la línea de acento) en el segundo t."""
        if t < self.ENTRADA:
            e = suave(t / self.ENTRADA)
            return e, 0.94 + 0.06 * e, e
        if t < self.ENTRADA + self.FIJA:
            return 1.0, 1.0, 1.0
        s = suave((t - self.ENTRADA - self.FIJA) / self.SALIDA)
        return 1.0 - s, 1.0 + 0.02 * s, 1.0

    def paintEvent(self, _):
        t = time.monotonic() - self.inicio
        if t >= self.duracion():
            self.temporizador.stop()
            self.close()
            self.deleteLater()
            return
        p = QPainter(self)
        self.pintar(p, t)
        p.end()

    def pintar(self, p: QPainter, segundo: float):
        opacidad, escala, linea = self.fotograma(segundo)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setOpacity(opacidad)
        c = QPointF(self.width() / 2, self.height() / 2)
        p.translate(c)
        p.scale(escala, escala)
        p.translate(-c)
        tarjeta = QRectF(self.SOMBRA, self.SOMBRA, self.W, self.H)
        for i in range(12, 0, -1):  # sombra suave
            path = QPainterPath()
            path.addRoundedRect(tarjeta.adjusted(-i, -i + 4, i, i + 4), 20 + i, 20 + i)
            p.fillPath(path, QColor(0, 0, 0, int(4 * (13 - i) / 3)))
        path = QPainterPath()
        path.addRoundedRect(tarjeta, 20, 20)
        p.fillPath(path, FONDO)
        p.setPen(QPen(BORDE, 1))
        p.drawPath(path)

        # Icono con un halo azul que se abre al entrar.
        lado = 68
        ic = QRectF(tarjeta.center().x() - lado / 2, tarjeta.top() + 22, lado, lado)
        halo = 34 + 10 * linea
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color(ACENTO, int(38 * linea)))
        p.drawEllipse(ic.center(), halo, halo)
        p.drawPixmap(ic.toRect(), icono_app().pixmap(256, 256))

        y = ic.bottom() + 12
        p.setFont(fuente(15, QFont.Weight.DemiBold))
        p.setPen(TEXTO)
        p.drawText(QRectF(tarjeta.left(), y, self.W, 28), Qt.AlignmentFlag.AlignCenter, "AoE2 Coaching")
        # Línea de acento que crece desde el centro.
        ancho = 56 * linea
        p.setPen(QPen(ACENTO, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(tarjeta.center().x() - ancho / 2, y + 34), QPointF(tarjeta.center().x() + ancho / 2, y + 34))
        p.setFont(fuente(9.5))
        p.setPen(SECUNDARIO)
        p.drawText(QRectF(tarjeta.left() + 24, y + 44, self.W - 48, 36),
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                   t("ov_bienvenida"))


# --- Datos simulados (demo y capturas) ---------------------------------------


def estado_simulado(guia: dict, paso: int, tiempo: int, avance: float = 0.6) -> Estado:
    pasos = guia["pasos"]
    horas = [p["referencia"] + 12 + 6 * i if i < paso else -1 for i, p in enumerate(pasos)]
    datos = [0] * guia["num_datos"]
    techs = [0] * guia["num_techs"]
    edad = 0
    for i, p in enumerate(pasos):
        if i > paso:
            break
        for c in p["condiciones"]:
            if c["tipo"] == "contador":
                objetivo = c["min"] if i < paso else int(c["min"] * avance)
                datos[c["indice"]] = max(datos[c["indice"]], objetivo)
            else:
                techs[c["indice"]] = 2 if i < paso else 1
                if c["tipo"] == "edad" and i < paso:
                    edad = max(edad, c["objetivo"])
    return Estado(tiempo, 1, paso, horas, datos, techs, edad, 14, 1 if paso == 4 else 6, 0)


def preparar(config: dict) -> rutas.Entorno:
    """Log, datos en %APPDATA%, inicio con Windows y carpetas del juego y del perfil.
    Es lo único que toca el sistema al arrancar (las pruebas lo sustituyen)."""
    rutas.configurar_log()
    from soporte import version_windows
    from version import VERSION
    log.info("AoE2C v%s · %s", VERSION, version_windows())
    from instalador import actualizar_inicio_con_windows
    if actualizar_inicio_con_windows():
        log.info("inicio con Windows corregido para apuntar a esta copia")
    entorno = rutas.resolver(config)
    log.info("juego: %s | perfil: %s%s", entorno.juego, entorno.perfil and entorno.perfil.carpeta,
             " (hay que elegir)" if entorno.preguntar else "")
    return entorno


def main():
    args = sys.argv[1:]
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(icono_app())

    if "--captura" in args:
        destino = Path(args[args.index("--captura") + 1])
        destino.mkdir(parents=True, exist_ok=True)
        if "--idioma" in args and args.index("--idioma") + 1 < len(args):
            textos.poner_idioma(args[args.index("--idioma") + 1])  # la tarjeta y el historial (el panel, abajo)
        guias = cargar_guias()
        guia = guia_elegida(args)
        fondo = Path(args[args.index("--fondo") + 1]) if "--fondo" in args else HERE / "fondo.png"
        ejemplo = historial_de_ejemplo(guia)
        casos = [("inicio", 0, 18), ("paso5", 4, 352), ("feudal", 9, 640), ("final", len(guia["pasos"]), 975)]
        for nombre, paso, seg in casos:
            estado = estado_simulado(guia, paso, seg)
            w = Overlay(lambda: (guia, estado, 0), solo_con_juego=False)
            w.temporizador.stop()  # solo se dibuja en memoria: no se abre ninguna ventana
            w.vista, w.guia = construir_vista(guia, estado), guia
            if nombre == "final":
                w.vista.comparacion = comparacion_final(ejemplo, ejemplo.registros[-1])
            if nombre == "paso5":
                w.aviso_paso = (f"{de(guia['pasos'][3], 'titulo')} · 3:52 (+22 s)", time.monotonic())
            alto = int(w.alto_tarjeta()) + 2 * MARGEN
            img = QImage(ANCHO + 2 * MARGEN, alto, QImage.Format.Format_ARGB32_Premultiplied)
            img.fill(Qt.GlobalColor.transparent)
            q = QPainter(img)
            w.pintar(q, ahora=time.monotonic() + 1.0)
            q.end()
            if fondo.exists():
                base = QImage(str(fondo))
                q = QPainter(base)
                x = base.width() - img.width() - 4
                y = int(base.height() * 0.715) - img.height()
                q.drawImage(x, y, img)
                q.end()
                base.save(str(destino / f"{nombre}.png"))
            else:
                img.save(str(destino / f"{nombre}.png"))
            print(destino / f"{nombre}.png")
        # El aviso de inicio, ya entrado del todo.
        b = Bienvenida()
        img = QImage(b.size(), QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        q = QPainter(img)
        b.pintar(q, b.ENTRADA + 0.5)
        q.end()
        img.save(str(destino / "bienvenida.png"))
        print(destino / "bienvenida.png")
        # La ventana del historial, con datos inventados: resumen general, al acabar una partida y sin partidas.
        for nombre, hist, sel, fin in (("historial", ejemplo, None, False),
                                       ("historial_partida", ejemplo, ejemplo.registros[-1]["id"], True),
                                       ("historial_vacio", Historial(None), None, False)):
            v = VentanaHistorial(hist, lambda: None)
            v.abrir(sel, fin_de_partida=fin)
            v.resize(v.ANCHO + 2 * MARGEN, v.ALTO + 2 * MARGEN)  # tamaño real, sea cual sea la pantalla
            v.grab().save(str(destino / f"{nombre}.png"))
            print(destino / f"{nombre}.png")
        # El panel: cada página, con datos inventados y sin tocar config.json.
        capturar_panel(destino, guias, ejemplo, args)
        return

    # Datos de la versión anterior (junto al código) -> %APPDATA%\AoE2Coaching\, antes de leerlos.
    copiados = rutas.preparar_datos() if CONFIG == rutas.CONFIG else []
    config = cargar_config()
    entorno = preparar(config)
    if copiados:
        log.info("datos copiados de la versión anterior: %s", ", ".join(copiados))
    perfil = entorno.perfil.carpeta if entorno.perfil else None
    repeticiones.poner_perfil(perfil)  # para vincular cada partida del historial con su repetición
    from instalador import Instalador
    instalador = Instalador(perfil=perfil, juego=entorno.juego)  # guías instaladas desde el catálogo

    if "--demo" in args:
        # Partida simulada con un historial inventado (no se guarda nada en disco). Al
        # acabar la guía, la "partida" deja de enviar datos y se abre el historial.
        guia = guia_elegida(args)
        historial = historial_de_ejemplo(guia)
        seguimiento = Seguimiento(historial)
        inicio = time.monotonic()
        fin_guia = 5 * len(guia["pasos"]) + 8

        def demo():
            s = time.monotonic() - inicio
            paso = min(len(guia["pasos"]), int(s // 5))
            if s > fin_guia + 25:
                app.quit()  # el demo se cierra solo
            estado = estado_simulado(guia, paso, int(min(s, fin_guia) * 12), avance=(s % 5) / 5)
            frescura = 0 if s < fin_guia else s - fin_guia
            seguimiento.observar(guia, estado, frescura, "[AoE2C] Arena", time.time())
            return guia, estado, frescura

        fuente_estado = demo
    else:
        lector = Lector(perfil, instalador.guias())
        historial = Historial()
        seguimiento = Seguimiento(historial)

        def real():
            lector.actualizar()
            frescura = lector.segundos_sin_datos()
            mapa = lector.archivo.stem if lector.archivo else None
            seguimiento.observar(lector.guia, lector.estado, frescura, mapa, lector.mtime)
            return lector.guia, lector.estado, frescura

        fuente_estado = real

    # Una sola copia del programa: si ya hay una abierta, se le pide que muestre su panel.
    servidor = instancia_unica(lambda: panel.mostrar(), app.quit)
    if servidor is None:
        return

    textos.poner_idioma(config.get("idioma", "es"))
    w = Overlay(fuente_estado, solo_con_juego="--demo" not in args, historial=historial, seguimiento=seguimiento,
                config=config)
    w.crear_bandeja(app)

    def ocultado():
        # La primera vez que la ✕ esconde el panel, un aviso de Windows dice dónde sigue.
        if w.bandeja:
            w.bandeja.showMessage(t("bandeja_titulo"), t("bandeja_texto"), icono_app(), 6000)

    def perfil_cambiado(carpeta: Path | None):
        repeticiones.poner_perfil(carpeta)
        if "--demo" not in args:
            lector.perfil, lector.archivo, lector.mtime = carpeta, None, 0.0

    def guias_cambiadas(guias: dict):
        # Se instaló, actualizó o quitó una guía: el lector reconoce sus partidas desde ya.
        if "--demo" not in args:
            lector.guias, lector.mapas = guias, mapas_de(guias)
            lector.archivo, lector.mtime = None, 0.0

    from catalogo import fuente_por_defecto
    from dashboard import Panel
    panel = Panel(config, historial, instalador.guias(), instalador, overlay=w,
                  icono=icono_app(), al_salir=app.quit, al_ocultar=ocultado, guardar_config=w.guardar_config,
                  perfiles=entorno.perfiles, al_cambiar_perfil=perfil_cambiado,
                  preguntar_perfil=entorno.preguntar, fuente_catalogo=fuente_por_defecto(),
                  al_cambiar_guias=guias_cambiadas)
    w.al_abrir_panel = panel.mostrar

    if "--inicio" in args:
        # Abierto por el inicio con Windows: espera en la bandeja, sin animación ni panel.
        sys.exit(app.exec())

    bienvenida = Bienvenida()  # para saber que el programa se abrió
    bienvenida.mostrar()

    def tras_bienvenida():
        # El panel se abre al acabar la animación, salvo que haya una partida en curso
        # (para no taparla ni quitarle el foco al juego). Si hay que elegir perfil, siempre.
        if (config.get("abrir_panel_al_iniciar", True) or entorno.preguntar) and not w.en_partida:
            panel.mostrar()

    QTimer.singleShot(int(bienvenida.duracion() * 1000), tras_bienvenida)
    sys.exit(app.exec())


def nombre_instancia() -> str:
    # AOE2C_INSTANCIA: otro nombre, para que las pruebas no hablen con la copia abierta.
    return os.environ.get("AOE2C_INSTANCIA") or "AoE2Coaching-" + (os.environ.get("USERNAME") or "usuario")


def instancia_unica(al_pedir_panel, al_pedir_salir=None):
    """Devuelve el servidor local de esta copia, o None si ya había otra abierta (a la
    que se le pide que muestre el panel). Si otra copia manda "salir" (el instalador,
    antes de poner una versión nueva o de desinstalar), se llama a al_pedir_salir."""
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    nombre = nombre_instancia()
    otro = QLocalSocket()
    otro.connectToServer(nombre)
    if otro.waitForConnected(300):
        otro.write(b"mostrar")
        otro.waitForBytesWritten(500)
        otro.disconnectFromServer()
        return None
    servidor = QLocalServer()
    if not servidor.listen(nombre):
        QLocalServer.removeServer(nombre)  # quedó de un cierre brusco
        servidor.listen(nombre)

    def conexion():
        s = servidor.nextPendingConnection()
        if s:
            s.waitForReadyRead(300)
            pedido = bytes(s.readAll().data())
            s.disconnectFromServer()
            if pedido == b"salir" and al_pedir_salir:
                al_pedir_salir()
            else:
                al_pedir_panel()

    servidor.newConnection.connect(conexion)
    return servidor


def pedir_salir(espera: float = 8.0) -> bool:
    """Pide a la copia abierta que se cierre y espera a que lo haga. True si ya no queda
    ninguna abierta (o no había). Lo usa `AoE2Coaching.exe --salir` (el instalador)."""
    from PySide6.QtNetwork import QLocalSocket
    otro = QLocalSocket()
    otro.connectToServer(nombre_instancia())
    if not otro.waitForConnected(500):
        return True
    otro.write(b"salir")
    otro.waitForBytesWritten(500)
    otro.disconnectFromServer()
    fin = time.monotonic() + espera
    while time.monotonic() < fin:
        time.sleep(0.2)
        prueba = QLocalSocket()
        prueba.connectToServer(nombre_instancia())
        if not prueba.waitForConnected(200):
            time.sleep(0.5)  # que termine de soltar sus archivos
            return True
        prueba.disconnectFromServer()
    return False


def guia_elegida(args: list[str]) -> dict:
    """La guía de --guia ID (para --demo y --captura) o la primera."""
    guias = cargar_guias()
    if "--guia" in args and args.index("--guia") + 1 < len(args):
        return guias.get(args[args.index("--guia") + 1]) or next(iter(guias.values()))
    return next(iter(guias.values()))


def capturar_panel(destino: Path, guias: dict, ejemplo: Historial, args: list[str]):
    """panel_<página>.png de cada página del panel, en memoria y sin mostrar ventanas."""
    from dashboard import PAGINAS, Panel
    from instalador import Instalador
    config = C.cargar(Path(os.devnull))  # preferencias por defecto
    if "--idioma" in args and args.index("--idioma") + 1 < len(args):
        config["idioma"] = args[args.index("--idioma") + 1]
    panel = Panel(config, ejemplo, guias, Instalador(), icono=icono_app(), guardar_config=lambda: None,
                  comprobar_juego=False)
    panel.resize(1240, 800)
    for nombre in PAGINAS:
        panel.ir(nombre)
        panel.grab().save(str(destino / f"panel_{nombre}.png"))
        print(destino / f"panel_{nombre}.png")


if __name__ == "__main__":
    main()
