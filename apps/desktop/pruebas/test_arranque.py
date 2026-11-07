"""Prueba del arranque completo (main) sin mostrar nada en pantalla.

    py pruebas/test_arranque.py

Ejecuta overlay.main() con la plataforma "offscreen" de Qt y un historial en memoria,
y comprueba que tras la animación de inicio se abre el panel, que una segunda copia
del programa no arranca (le pide a la primera que muestre el panel) y que
«Cerrar AoE2C» termina el programa. No escribe en config.json ni en historial.json.
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
OVERLAY = Path(__file__).resolve().parent.parent  # apps/desktop
sys.path.insert(0, str(OVERLAY))

import dashboard as D  # noqa: E402
import historial as H  # noqa: E402
import overlay as O  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

registro = {"mostrado": 0, "segunda": None, "salida": None}


def comprobar(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("  ok ·", msg)


class App(QApplication):
    def exec(self):
        def comprobar_y_salir():
            panel = next(w for w in QApplication.topLevelWidgets() if isinstance(w, D.Panel))
            registro["visible"] = panel.isVisible()
            # Una segunda copia: no debe arrancar y la primera debe mostrar el panel.
            panel.hide()
            registro["segunda"] = O.instancia_unica(lambda: None)
            QTimer.singleShot(400, lambda: (registro.__setitem__("reabierto", panel.isVisible()),
                                            next(b for b in panel.findChildren(D.QPushButton)
                                                 if "Cerrar AoE2C" in b.text()).click()))
        QTimer.singleShot(1500, comprobar_y_salir)
        QTimer.singleShot(8000, self.quit)  # por si algo se cuelga
        registro["salida"] = super().exec()
        return registro["salida"]


def main():
    print("Arranque completo (sin pantalla)")
    with tempfile.TemporaryDirectory() as d:
        O.CONFIG = Path(d) / "config.json"  # preferencias por defecto, en una carpeta temporal
        O.QApplication = App
        O.Historial = lambda: H.Historial(None)  # historial en memoria
        # Sin tocar el sistema: ni %APPDATA%, ni el registro, ni las carpetas reales del juego.
        O.preparar = lambda config: O.rutas.Entorno(None, None, [], False)
        O.Bienvenida.FIJA = 0.2  # animación corta
        mostrar = D.Panel.mostrar

        def contar(self):
            registro["mostrado"] += 1
            mostrar(self)
        D.Panel.mostrar = contar
        sys.argv = ["overlay.py"]
        try:
            O.main()
        except SystemExit:
            pass
    comprobar(registro.get("visible"), "tras la animación de inicio se abre el panel")
    comprobar(registro["segunda"] is None, "una segunda copia no arranca")
    comprobar(registro.get("reabierto"), "y la primera vuelve a mostrar su panel")
    comprobar(registro["mostrado"] == 2, "panel mostrado 2 veces (inicio y segunda copia)")
    comprobar(registro["salida"] == 0, "«Cerrar AoE2C» termina el programa")
    print("\nTodo bien.")


if __name__ == "__main__":
    main()
