"""Pruebas del panel Match Info (match_ui.py), sin abrir ninguna ventana.

    py pruebas/test_match_ui.py

Dibuja el panel en memoria con las partidas de ejemplo (1v1, por equipos y sin rating)
en cada estado y comprueba lo que se calcula: tamaño, orden de los equipos, textos de
cada jugador, consejos, opciones de Ajustes y arrastre.
"""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # nada aparece en pantalla
OVERLAY = Path(__file__).resolve().parent.parent  # apps/desktop
RAIZ = OVERLAY.parent.parent
sys.path.insert(0, str(OVERLAY))

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import civilizaciones  # noqa: E402
import match_ui as M  # noqa: E402
import textos  # noqa: E402
from partida_en_curso import Equipo, Partida, partida_de_ejemplo  # noqa: E402
from vigilante import BUSCANDO, CARGADO, ERROR  # noqa: E402

app = QApplication.instance() or QApplication([])
textos.poner_idioma("es")


def comprobar(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("  ok ·", msg)


def pintor(partida, estado=CARGADO, error="", **opciones) -> M.PintorMatch:
    """Dibuja la partida en una imagen y devuelve el pintor (con sus consejos)."""
    panel = M.PanelMatch({})
    panel.poner(partida, estado, error)
    img = panel.imagen()
    p = QPainter(img)
    pm = M.PintorMatch(p, partida, estado, error, M.Opciones(**opciones))
    pm.dibujar(*M.tamano(partida))
    p.end()
    return pm


def test_civilizaciones():
    print("nombres de las civilizaciones")
    datos = json.loads((RAIZ / "content" / "guias" / "tecnologias.json").read_text(encoding="utf-8"))["civilizaciones"]
    iguales = {int(i): (c["nombre"], c["nombre_en"]) for i, c in datos.items()} == civilizaciones.NOMBRES
    comprobar(iguales, "civilizaciones.py coincide con tecnologias.json (si no: py content/guias/tecnologias.py --solo-app)")
    comprobar(civilizaciones.nombre(1) == "Britanos" and civilizaciones.nombre(1, True) == "Britons"
              and civilizaciones.nombre(999) == "", "nombre por ID, en los dos idiomas")


def test_banderas():
    print("banderas")
    import banderas
    import banderas_datos
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage
    comprobar(len(banderas_datos.SVG) > 240 and all(len(c) == 2 for c in banderas_datos.SVG),
              f"{len(banderas_datos.SVG)} banderas por código de dos letras")
    invalidas = [c for c in banderas_datos.SVG if banderas._renderer(c) is None]
    comprobar(not invalidas, f"Qt entiende todos los SVG {invalidas[:5]}")

    def pintada(codigo, minimo=200):
        img = QImage(20, 15, QImage.Format.Format_ARGB32)
        img.fill(0)
        p = QPainter(img)
        banderas.pintar(p, QRectF(0, 0, 20, 15), codigo)
        p.end()
        return sum(1 for x in range(20) for y in range(15) if QColor.fromRgba(img.pixel(x, y)).alpha() > minimo)

    comprobar(pintada("AR") > 250, "la bandera de un país (el código en mayúsculas también vale)")
    comprobar(pintada("zz", 0) > 250 and pintada("zz") < 50, "un país sin bandera: el recuadro tenue con el código")
    comprobar(pintada(None, 0) == 0, "sin país, nada")


def test_tamanos_y_orden():
    print("tamaño y orden")
    uno, eq = partida_de_ejemplo("1v1"), partida_de_ejemplo("equipos")
    comprobar(M.tamano(uno) == (M.ANCHO_1V1, M.PAD * 2 + M.CABECERA + M.ALTO_1V1), "1v1: una franja")
    w, h = M.tamano(eq)
    comprobar(w == 2 * M.PAD + 2 * M.ANCHO_COLUMNA + M.SEPARACION and h > M.tamano(uno)[1], "4v4: dos columnas")
    invertida = Partida(uno.id, uno.modo, uno.leaderboard, uno.mapa, True, tuple(reversed(uno.equipos)))
    comprobar(M.equipos_ordenados(invertida)[0].jugadores[0].soy_yo, "el propio va a la izquierda aunque sea el equipo 2")
    tres = Partida("x", "rm", "rm_team", "Arabia", True, eq.equipos + (Equipo(4, eq.equipos[0].jugadores[:2]),))
    comprobar(M.tamano(tres)[0] == 2 * M.PAD + 3 * M.ANCHO_COLUMNA + 2 * M.SEPARACION, "tres equipos, tres columnas")


def test_textos_de_jugador():
    print("lo que se ve de cada jugador")
    uno = partida_de_ejemplo("1v1")
    yo = uno.yo
    pm = pintor(uno)
    comprobar(pm._elo(yo)[0] == "1220" and pm._rango(yo) == "#12688", "elo y puesto")
    comprobar(pm._detalle(yo) == "Persas  ·  51%", "civilización y winrate (por defecto, sin el máximo)")
    comprobar(pintor(uno, elo_max=True, winrate=False)._detalle(yo) == "Persas  ·  máx 1301", "opciones de Ajustes")
    comprobar(pintor(uno, BUSCANDO)._elo(yo)[0] == "···" and pintor(uno, BUSCANDO)._rango(yo) == "",
              "buscando datos: sin elo ni puesto")
    comprobar(pintor(uno, ERROR, "503")._elo(yo)[0] == "—", "error: un guion")
    sin = partida_de_ejemplo("sin_rating")
    comprobar(pintor(sin)._elo(sin.rival)[0] == "Sin rating" and pintor(sin)._rango(sin.rival) == "",
              "jugador sin rating")
    textos.poner_idioma("en")
    comprobar(pintor(sin)._elo(sin.rival)[0] == "Unrated" and pintor(uno)._detalle(yo).startswith("Persians"),
              "en inglés")
    textos.poner_idioma("es")


def test_consejos():
    print("consejos")
    uno = partida_de_ejemplo("1v1")
    comprobar([c for _, c in pintor(uno).consejos] == ["Elo del rival frente al tuyo"], "la diferencia tiene consejo")
    comprobar(pintor(uno, diferencia=False).consejos == [], "sin diferencia si se quita en Ajustes")
    err = pintor(uno, ERROR, "la API respondió 503").consejos
    comprobar(len(err) == 1 and "503" in err[0][1], "el «!» del error explica el motivo")
    comprobar(pintor(partida_de_ejemplo("sin_rating")).consejos == [], "sin rating del rival: no hay diferencia")
    comprobar(pintor(partida_de_ejemplo("equipos")).consejos == [], "por equipos no hay diferencia")


def test_ventana():
    print("ventana")
    config: dict = {}
    guardado = []
    panel = M.PanelMatch(config, al_mover=lambda: guardado.append(True))
    panel.poner(partida_de_ejemplo("1v1"))
    s = panel.pantalla()
    comprobar(abs(panel.x() + panel.width() / 2 - (s.x() + s.width() / 2)) <= 1 and panel.y() < s.y() + s.height() * 0.1,
              "por defecto, arriba en el centro")
    flags = panel.windowFlags()
    comprobar(bool(flags & Qt.WindowType.WindowDoesNotAcceptFocus) and bool(flags & Qt.WindowType.WindowStaysOnTopHint)
              and not flags & Qt.WindowType.WindowTransparentForInput, "recibe clics sin quitar el foco, siempre encima")

    def raton(tipo, x, y):
        pos = QPointF(x, y)
        return QMouseEvent(tipo, pos, pos, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                           Qt.KeyboardModifier.NoModifier)

    inicio = panel.pos()
    panel.mousePressEvent(raton(QMouseEvent.Type.MouseButtonPress, inicio.x() + 50, inicio.y() + 20))
    panel.mouseMoveEvent(raton(QMouseEvent.Type.MouseMove, inicio.x() + 50 - 40, inicio.y() + 20 + 150))
    panel.mouseReleaseEvent(raton(QMouseEvent.Type.MouseButtonRelease, inicio.x() + 50 - 40, inicio.y() + 20 + 150))
    comprobar(config["match_posicion"] == [inicio.x() - 40, inicio.y() + 150] and guardado,
              "arrastrar lo mueve y guarda la posición")
    otro = M.PanelMatch(config)
    otro.poner(partida_de_ejemplo("equipos"))
    comprobar(otro.pos() == QPoint(inicio.x() - 40, inicio.y() + 150), "la posición guardada se respeta")
    config["match_posicion"] = [s.x() + s.width() + 500, s.y() - 900]
    otro.recolocar()
    comprobar(otro.x() <= s.x() + s.width() - otro.width() + M.MARGEN and otro.y() >= s.y() - M.MARGEN,
              "una posición fuera de la pantalla vuelve a ella")
    config["match_posicion"] = "roto"
    otro.recolocar()
    comprobar(otro.y() < s.y() + s.height() * 0.1, "una posición mal guardada se ignora")
    for tipo in ("1v1", "equipos", "sin_rating"):
        for estado in (BUSCANDO, CARGADO, ERROR):
            panel.poner(partida_de_ejemplo(tipo, cargada=estado == CARGADO), estado, "error")
            img = panel.imagen()
            comprobar(not img.isNull() and img.width() == M.tamano(panel.partida)[0] + 2 * M.MARGEN,
                      f"se dibuja {tipo} · {estado}")


def test_atajo():
    print("atajo de teclado")
    import atajos as A
    comprobar(A.parsear("Ctrl+Alt+M") == (A.MOD_CONTROL | A.MOD_ALT, ord("M")), "Ctrl+Alt+M")
    comprobar(A.parsear("shift + F9") == (A.MOD_SHIFT, 0x78) and A.parsear("F10") == (0, 0x79), "teclas F")
    comprobar(A.parsear("M") is None and A.parsear("Ctrl+Patata") is None and A.parsear("") is None,
              "sin modificador (le quitaría la tecla al juego) o desconocida: no vale")
    if sys.platform != "win32":
        return
    import ctypes
    pulsado = []
    atajo = A.AtajoGlobal(lambda: pulsado.append(True))
    # Sin registrar nada en Windows: se simula el aviso que manda el sistema al pulsarlo.
    app.installNativeEventFilter(atajo)
    atajo.activo = True
    ctypes.windll.user32.PostThreadMessageW(ctypes.windll.kernel32.GetCurrentThreadId(), A.WM_HOTKEY, atajo.id, 0)
    ctypes.windll.user32.PostThreadMessageW(ctypes.windll.kernel32.GetCurrentThreadId(), A.WM_HOTKEY, atajo.id + 7, 0)
    for _ in range(5):
        app.processEvents()
    atajo.activo = False
    app.removeNativeEventFilter(atajo)
    comprobar(pulsado == [True], "el aviso de su combinación lo dispara (y el de otra, no)")


def test_overlay():
    print("en el overlay")
    import tempfile
    import config as C
    import estadisticas as E
    import overlay as O
    import vigilante as V
    with tempfile.TemporaryDirectory() as d:
        carpeta = Path(d)
        ruta, proveedor, yo = V.simular(carpeta, "1v1")
        proveedor.retraso = 0
        v = V.Vigilante(lambda: carpeta, E.Estadisticas(proveedor), lambda: None, en_segundo_plano=lambda f: f())
        config = dict(C.DEFECTO)
        w = O.Overlay(lambda: (None, None, 99.0), solo_con_juego=False, config=config, vigilante=v)
        w.temporizador.stop()
        w.guardar_config = lambda: None
        w.perfil_detectado = yo

        def ticks(n=25):
            for _ in range(n):
                w.ultima_vigilancia = 0.0  # sin esperar el segundo entre vistazos
                w.tick()

        ticks()
        panel = w.panel_match
        comprobar(panel.isVisible() and panel.windowOpacity() == 1.0 and v.estado == V.CARGADO,
                  "empieza la clasificatoria: el panel aparece con el elo")
        comprobar(panel.partida.yo is not None and panel.partida.yo.perfil == yo, "sabe cuál es el jugador")
        comprobar(config["match_perfil_detectado"] == yo, "el perfil deducido se guarda")
        w.alternar_match()
        ticks()
        comprobar(not panel.isVisible(), "el atajo lo oculta")
        w.alternar_match()
        ticks()
        comprobar(panel.isVisible(), "y lo vuelve a mostrar")
        config["match_info"] = False
        ticks()
        comprobar(not panel.isVisible(), "apagado en Ajustes, no se ve")
        config["match_info"] = True
        ticks()
        ruta.unlink()
        ticks()
        comprobar(not panel.isVisible() and v.partida is None, "acaba la partida: se oculta solo")
        w.match_oculto = True
        ruta2, _, _ = V.simular(carpeta, "equipos")
        ticks()
        comprobar(panel.isVisible() and panel.partida.leaderboard == "rm_team",
                  "la partida siguiente se ve aunque la anterior se ocultara con el atajo")
        config["match_perfil"] = 12345
        comprobar(w.perfil_propio() == 12345, "el perfil elegido a mano manda sobre el deducido")
        panel.hide()


def test_guia_en_ranked():
    print("la guía durante una clasificatoria")
    import tempfile
    import config as C
    import estadisticas as E
    import overlay as O
    import vigilante as V
    from lector import cargar_guias
    guia = next(iter(cargar_guias().values()))
    estado = O.estado_simulado(guia, 3, 300)
    with tempfile.TemporaryDirectory() as d:
        carpeta = Path(d)
        v = V.Vigilante(lambda: carpeta, E.Estadisticas(V.ProveedorDeEjemplo(partida_de_ejemplo("1v1"))),
                        lambda: None, en_segundo_plano=lambda f: f())
        w = O.Overlay(lambda: (guia, estado, 0.0), solo_con_juego=False, config=dict(C.DEFECTO), vigilante=v)
        w.temporizador.stop()
        w.guardar_config = lambda: None

        def ticks():
            for _ in range(25):
                w.ultima_vigilancia = 0.0
                w.tick()

        ticks()
        comprobar(w.isVisible() and not w.panel_match.isVisible(), "sin clasificatoria: la guía, como siempre")
        ruta, _, _ = V.simular(carpeta, "1v1")
        ticks()
        comprobar(not w.isVisible() and w.panel_match.isVisible(), "con clasificatoria: Match Info y sin guía")
        ruta.unlink()
        ticks()
        comprobar(w.isVisible() and not w.panel_match.isVisible(), "al acabar, vuelve la guía")
        w.hide()


def test_ajustes():
    print("ajustes")
    import config as C
    import overlay as O
    from dashboard import Panel
    from historial import Historial
    from instalador import Instalador
    from PySide6.QtGui import QKeySequence
    from PySide6.QtWidgets import QKeySequenceEdit, QLineEdit

    class OverlayFalso:
        def __init__(self):
            self.atajos, self.libre = [], True
            self.en_partida = False

        def poner_atajo(self, texto):
            self.atajos.append(texto)
            return self.libre

    config = C.cargar(Path(os.devnull))
    config["match_perfil_detectado"] = 25237933
    falso = OverlayFalso()
    p = Panel(config, Historial(None), {}, Instalador(), overlay=falso, icono=O.icono_app(), guardar_config=lambda: None,
              comprobar_juego=False)
    p.ir("ajustes")
    pagina = p.p_ajustes
    atajo = pagina.findChild(QKeySequenceEdit)
    perfil = next(e for e in pagina.findChildren(QLineEdit) if e.validator() is not None)
    comprobar(atajo.keySequence().toString() == "Ctrl+Alt+M" and perfil.placeholderText() == "25237933",
              "el atajo y el perfil deducido (como pista)")
    atajo.setKeySequence(QKeySequence("Ctrl+Shift+K"))
    pagina._poner_atajo(atajo)
    comprobar(config["match_atajo"] == "Ctrl+Shift+K" and falso.atajos[-1] == "Ctrl+Shift+K", "cambiar el atajo lo registra")
    falso.libre = False
    atajo.setKeySequence(QKeySequence("Ctrl+Alt+J"))
    pagina._poner_atajo(atajo)
    comprobar(config["match_atajo"] == "Ctrl+Shift+K" and atajo.keySequence().toString() == "Ctrl+Shift+K"
              and falso.atajos[-1] == "Ctrl+Shift+K", "si lo usa otra aplicación, vuelve al anterior")
    falso.libre = True
    atajo.setKeySequence(QKeySequence("J"))
    pagina._poner_atajo(atajo)
    comprobar(config["match_atajo"] == "Ctrl+Shift+K", "una tecla sola no vale (se la quitaría al juego)")
    atajo.clear()
    pagina._poner_atajo(atajo)
    comprobar(config["match_atajo"] == "", "borrarlo deja sin atajo")
    perfil.setText("1943128")
    perfil.editingFinished.emit()
    comprobar(config["match_perfil"] == 1943128, "el ID escrito a mano se guarda")
    perfil.setText("")
    perfil.editingFinished.emit()
    comprobar(config["match_perfil"] is None, "vacío: vuelve a usarse el deducido")
    config["match_posicion"] = [10, 10]
    pagina._centrar_match()
    comprobar(config["match_posicion"] is None, "«Volver arriba al centro»")


def main():
    test_civilizaciones()
    test_banderas()
    test_tamanos_y_orden()
    test_textos_de_jugador()
    test_consejos()
    test_ventana()
    test_atajo()
    test_overlay()
    test_guia_en_ranked()
    test_ajustes()
    print("\nTodo bien.")


if __name__ == "__main__":
    main()
