"""Pruebas de las repeticiones del historial y del soporte (sin abrir ventanas).

    py pruebas/test_soporte.py

Usa una carpeta savegame inventada (repeticiones vacías con la fecha puesta a mano) y
un log inventado: no toca el perfil real ni el log de la app.
"""

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # nada aparece en pantalla
OVERLAY = Path(__file__).resolve().parent.parent  # apps/desktop
sys.path.insert(0, str(OVERLAY))

import apoyo  # noqa: E402
import config as C  # noqa: E402
import historial as H  # noqa: E402
import lector as L  # noqa: E402
import repeticiones as R  # noqa: E402
import soporte as S  # noqa: E402
import textos  # noqa: E402

FC = L.cargar_guias()["fast_castle"]


def comprobar(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("  ok ·", msg)


def ts(texto: str) -> float:
    return datetime.fromisoformat(texto).timestamp()


def repeticion(savegame: Path, inicio: str, fin: str) -> Path:
    """Una repetición vacía que empezó en `inicio` y se escribió por última vez en `fin`."""
    d = datetime.fromisoformat(inicio)
    ruta = savegame / f"SP Replay v101.103.57257.0 @{d:%Y.%m.%d %H%M%S}.aoe2record"
    ruta.write_bytes(b"")
    os.utime(ruta, (ts(fin), ts(fin)))
    return ruta


def registro(id_: str, fecha: str, ultimo_dato: str | None) -> dict:
    r = H.nuevo_registro(FC, "[AoE2C] Arena", datetime.fromisoformat(fecha))
    r["id"] = id_
    r["escritura"] = ts(ultimo_dato) if ultimo_dato else 0
    r["pasos"][0]["hora"] = 5
    return r


def preparar_savegame(tmp: Path) -> tuple[Path, dict]:
    savegame = tmp / "perfil" / "savegame"
    savegame.mkdir(parents=True)
    rep = {
        "reiniciada": repeticion(savegame, "2026-11-06T12:32:21", "2026-11-06T12:32:31"),
        "larga": repeticion(savegame, "2026-11-06T12:32:35", "2026-11-06T13:03:53"),
        "corta": repeticion(savegame, "2026-11-06T18:00:17", "2026-11-06T18:02:38"),
        "siguiente": repeticion(savegame, "2026-11-06T18:02:43", "2026-11-06T18:03:53"),
    }
    (savegame / "otra cosa.txt").write_text("x")
    return savegame, rep


def test_buscar(tmp: Path):
    print("Repeticiones: cada partida con la suya")
    savegame, rep = preparar_savegame(tmp)
    casos = [
        ("descarta la repetición de una partida reiniciada a los 10 s",
         registro("a", "2026-11-06T12:32:36", "2026-11-06T13:00:05"), rep["larga"]),
        ("no confunde una partida corta con la siguiente",
         registro("b", "2026-11-06T18:00:22", "2026-11-06T18:02:37"), rep["corta"]),
        ("la siguiente partida, con la suya",
         registro("c", "2026-11-06T18:02:45", "2026-11-06T18:03:49"), rep["siguiente"]),
        ("partida importada al arrancar (fecha = último dato)",
         registro("d", "2026-11-06T13:00:05", "2026-11-06T13:00:05"), rep["larga"]),
        ("sin repetición: partida de otro día",
         registro("e", "2026-11-08T10:00:00", "2026-11-08T10:20:00"), None),
    ]
    for msg, r, esperada in casos:
        comprobar(R.buscar(r, savegame) == esperada, msg)
    comprobar(R.buscar(casos[0][1], tmp / "no existe") is None, "sin carpeta savegame no falla")


def test_vincular(tmp: Path):
    print("Repeticiones: vínculo guardado en la partida")
    savegame, rep = preparar_savegame(tmp / "vincular")
    R.poner_perfil(savegame.parent)
    r = registro("a", "2026-11-06T12:32:36", "2026-11-06T13:00:05")
    comprobar(R.de_registro(r) == rep["larga"] and r["repeticion"] == rep["larga"].name,
              "la encuentra y guarda su nombre en la partida")
    rep["larga"].rename(savegame / "renombrada.aoe2record")
    comprobar(R.de_registro(r) is None and "repeticion" not in r, "si la borran, se quita el vínculo")
    R.poner_perfil(None)
    comprobar(R.de_registro(r) is None, "sin perfil, no hay repetición")


def test_historial_ui(tmp: Path):
    print("Historial: «Ver repetición» y «Mostrar en carpeta»")
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from historial_ui import ContenidoHistorial
    savegame, rep = preparar_savegame(tmp / "ui")
    R.poner_perfil(savegame.parent)
    hist = H.Historial(tmp / "ui" / "historial.json")
    con = registro("con", "2026-11-06T12:32:36", "2026-11-06T13:00:05")
    sin = registro("sin", "2026-11-08T10:00:00", "2026-11-08T10:20:00")
    hist.poner(con)
    hist.poner(sin)
    hist.guardar()
    c = ContenidoHistorial(hist)
    abiertos, carpetas, juego = [], [], {"abierto": False}
    c.juego_abierto = lambda: juego["abierto"]
    c.abrir_juego = lambda: abiertos.append(1)
    c.mostrar_en_carpeta = carpetas.append
    c.abrir("con")
    app.processEvents()
    comprobar(c.ver_repeticion.isEnabled() and c.en_carpeta.isEnabled(), "con repetición, los dos botones activos")
    comprobar(H.Historial(hist.archivo).buscar("con").get("repeticion") == rep["larga"].name,
              "el vínculo queda guardado en historial.json")
    c.ver_repeticion.click()
    comprobar(abiertos == [1], "con el juego cerrado, lo abre")
    comprobar(rep["larga"].stem in c.nota_repeticion.text() and c.nota_repeticion.isVisibleTo(c),
              "y dice qué repetición elegir")
    comprobar(QGuiApplication.clipboard().text() == rep["larga"].stem, "con el nombre copiado")
    juego["abierto"] = True
    c.ver_repeticion.click()
    comprobar(abiertos == [1] and c.nota_repeticion.text().startswith(textos.t("hi_como_ver", nombre="")[:10]),
              "con el juego abierto, no lo vuelve a abrir")
    c.en_carpeta.click()
    comprobar(carpetas == [rep["larga"]], "«Mostrar en carpeta» señala el archivo")
    c.elegir("sin")
    comprobar(not c.ver_repeticion.isEnabled() and not c.en_carpeta.isEnabled(),
              "sin repetición, los botones quedan desactivados")
    comprobar(not c.nota_repeticion.isVisibleTo(c), "y la nota de la otra partida desaparece")
    R.poner_perfil(None)


def test_errores_log(tmp: Path):
    print("Soporte: últimos errores del log")
    log = tmp / "logs" / "aoe2c.log"
    log.parent.mkdir()
    log.with_name("aoe2c.log.1").write_text(
        "2026-11-07 10:00:00,000 WARNING aoe2c: catálogo: sin conexión\n", encoding="utf-8")
    log.write_text(
        "2026-11-07 11:00:00,000 INFO aoe2c: juego: C:\\Steam | perfil: C:\\x\\76561199524040890\n"
        "2026-11-07 11:00:01,000 ERROR aoe2c: error no capturado\n"
        "Traceback (most recent call last):\n"
        "ValueError: algo\n"
        "2026-11-07 11:00:02,000 INFO aoe2c: todo bien\n", encoding="utf-8")
    errores = S.ultimos_errores(log)
    comprobar(errores[0].endswith("sin conexión"), "empieza por los avisos del log anterior")
    comprobar(errores[-1] == "ValueError: algo" and len(errores) == 4, "incluye la traza y no las líneas INFO")
    comprobar(S.ultimos_errores(log, 2) == errores[-2:], "solo las últimas n")
    comprobar(S.ultimos_errores(tmp / "no.log") == [], "sin log, lista vacía")


def test_datos(tmp: Path):
    print("Soporte: datos para copiar")
    os.environ["USERPROFILE"] = r"C:\Users\Jugador"
    comprobar(S.anonimizar(r"c:\users\jugador\Games\Age of Empires 2 DE\76561199524040890\savegame")
              == r"%USERPROFILE%\Games\Age of Empires 2 DE\<steamid>\savegame",
              "quita la carpeta del usuario y el SteamID")
    log = tmp / "datos" / "aoe2c.log"
    log.parent.mkdir()
    log.write_text("2026-11-07 11:00:01,000 ERROR aoe2c: no se pudo leer "
                   "C:\\Users\\Jugador\\Games\\Age of Empires 2 DE\\76561199524040890\\profile\n", encoding="utf-8")
    inst = apoyo.instalador_de_prueba(tmp, "soporte")
    texto = S.datos(C.cargar(tmp / "nada.json"), inst, False, log)
    for parte in (f"v{S.VERSION}", "Windows", "Juego: encontrado (cerrado)", "Guías: fast_castle", "Mapas:", "Mods:",
                  "Últimos avisos y errores (1):"):
        comprobar(parte in texto, f"incluye «{parte}»")
    comprobar("Jugador" not in texto and "76561199524040890" not in texto, "sin el usuario ni el SteamID")


def test_panel(tmp: Path):
    print("Panel: Ayuda y soporte en Ajustes")
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication, QPushButton
    app = QApplication.instance() or QApplication(sys.argv)
    import dashboard as D
    config = C.cargar(tmp / "nada.json")
    inst = apoyo.instalador_de_prueba(tmp, "panel_soporte")
    p = D.Panel(config, H.Historial(None), inst.guias(), inst, segundo_plano=False, guardar_config=lambda: None,
                comprobar_juego=False)
    p.ir("ajustes")
    app.processEvents()
    botones = {b.text(): b for b in p.p_ajustes.findChildren(QPushButton)}
    comprobar(textos.t("abrir_discord") in botones and not botones[textos.t("abrir_discord")].isEnabled(),
              "«Abrir Discord» desactivado hasta tener la invitación")
    botones[textos.t("copiar")].click()
    app.processEvents()
    comprobar(QGuiApplication.clipboard().text().startswith("AoE2 Coaching v"), "«Copiar» deja los datos en el portapapeles")
    comprobar(p.mensaje.text() == textos.t("soporte_copiado"), "y lo avisa")


def main():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        test_buscar(tmp)
        test_vincular(tmp)
        test_historial_ui(tmp)
        test_errores_log(tmp)
        test_datos(tmp)
        test_panel(tmp)
    print("\nTodo bien.")


if __name__ == "__main__":
    main()
