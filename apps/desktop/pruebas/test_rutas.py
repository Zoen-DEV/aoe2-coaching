"""Pruebas de rutas.py: buscar el juego en Steam, elegir la carpeta del perfil y pasar
los datos a %APPDATA% (todo con carpetas inventadas; no toca el juego ni el registro).

    py apps/desktop/pruebas/test_rutas.py
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # nada aparece en pantalla
OVERLAY = Path(__file__).resolve().parent.parent  # apps/desktop
sys.path.insert(0, str(OVERLAY))

import apoyo  # noqa: E402
import instalador as I  # noqa: E402
import lector as L  # noqa: E402
import rutas as R  # noqa: E402


def comprobar(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("  ok ·", msg)


def archivo(p: Path, texto: str = "x", fecha: float | None = None) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(texto, encoding="utf-8")
    if fecha:
        os.utime(p, (fecha, fecha))
    return p


def test_vdf():
    print("Formato de texto de Valve")
    datos = R.leer_vdf('''
"libraryfolders"
{
\t"0"\t{ "path"\t\t"C:\\\\Program Files (x86)\\\\Steam" "apps" { "813780" "1" } }
\t// comentario
\t"1"\t{ "path" "D:\\\\Juegos\\\\SteamLibrary" "label" "" }
}''')
    libs = datos["libraryfolders"]
    comprobar(libs["0"]["path"] == r"C:\Program Files (x86)\Steam", "rutas con barras escapadas")
    comprobar(libs["0"]["apps"] == {"813780": "1"} and libs["1"]["label"] == "", "bloques anidados y valores vacíos")


def test_juego(tmp: Path):
    print("Buscar AoE2 DE en las bibliotecas de Steam")
    steam, otra = tmp / "Steam", tmp / "D" / "SteamLibrary"
    (steam / "steamapps").mkdir(parents=True)
    vdf = '"libraryfolders" { "0" { "path" "%s" } "1" { "path" "%s" } }' % (
        str(steam).replace("\\", "\\\\"), str(otra).replace("\\", "\\\\"))
    archivo(steam / "steamapps" / "libraryfolders.vdf", vdf)
    comprobar(R.bibliotecas_steam(steam) == [steam, otra], "la biblioteca principal y la del disco D")
    comprobar(R.buscar_juego(steam) is None, "sin el juego instalado: None")
    archivo(otra / "steamapps" / f"appmanifest_{R.ID_STEAM_JUEGO}.acf", '"AppState" { "installdir" "AoE2DE" }')
    archivo(otra / "steamapps" / "common" / "AoE2DE" / R.EXE_JUEGO)
    comprobar(R.buscar_juego(steam) == otra / "steamapps" / "common" / "AoE2DE", "lo encuentra en el disco D")
    comprobar(R.buscar_juego(None) is None or R.es_carpeta_juego(R.buscar_juego(None)), "sin Steam no falla")
    archivo(steam / "config" / "loginusers.vdf", '"users" { "76561190000000001" { "PersonaName" "Zoen" } }')
    comprobar(R.nombres_steam(steam) == {"76561190000000001": "Zoen"}, "nombre visible de la cuenta de Steam")


def test_perfiles(tmp: Path):
    print("Elegir la carpeta del perfil")
    base = tmp / "Games" / "Age of Empires 2 DE"
    comprobar(R.buscar_perfiles(base, {}) == [] and R.elegir_perfil([]) == (None, False),
              "sin carpetas (el juego no se abrió nunca): ningún perfil")
    archivo(base / "0" / "profile" / "AdditionalOptions.aop")  # el juego lo crea siempre
    archivo(base / "76561190000000001" / "profile" / "AdditionalOptions.aop")
    archivo(base / "logs" / "x.txt")  # no es un perfil
    perfiles = R.buscar_perfiles(base, {"76561190000000001": "Zoen"})
    comprobar(sorted(p.id for p in perfiles) == ["0", "76561190000000001"], "solo las carpetas con número")
    p, preguntar = R.elegir_perfil(perfiles)
    comprobar(p.nombre == "Zoen" and not preguntar, "jugador nuevo: la cuenta de Steam, sin preguntar")
    hoy = time.time()
    for n in range(3):
        archivo(base / "76561190000000001" / "savegame" / f"partida{n}.aoe2record", fecha=hoy - n * 100)
    perfiles = R.buscar_perfiles(base, {})
    p, preguntar = R.elegir_perfil(perfiles)
    comprobar(p.id == "76561190000000001" and p.repeticiones == 3 and not preguntar,
              "el «0» con solo las opciones no cuenta: se elige solo el que tiene partidas")
    archivo(base / "0" / "savegame" / "offline.aoe2record", fecha=hoy + 50)
    perfiles = R.buscar_perfiles(base, {})
    p, preguntar = R.elegir_perfil(perfiles)
    comprobar(preguntar and p.id == "0", "dos perfiles con partidas: propone el más reciente y pregunta")
    p, preguntar = R.elegir_perfil(perfiles, str(base / "76561190000000001"))
    comprobar(p.id == "76561190000000001" and not preguntar, "el elegido en el panel se respeta")
    p, preguntar = R.elegir_perfil(perfiles, str(base / "borrado"))
    comprobar(preguntar, "si el elegido ya no existe, se vuelve a preguntar")


def test_datos(tmp: Path):
    print("Datos de AoE2C en %APPDATA%")
    viejos, datos = tmp / "codigo", tmp / "AppData" / "AoE2Coaching"
    archivo(viejos / "config.json", '{"idioma": "en"}')
    archivo(viejos / "historial.json", '{"version": 1, "partidas": []}')
    comprobar(R.preparar_datos(datos, viejos) == ["config.json", "historial.json"], "copia los dos archivos")
    comprobar((viejos / "historial.json").is_file(), "los originales no se borran")
    archivo(datos / "config.json", '{"idioma": "es"}')
    comprobar(R.preparar_datos(datos, viejos) == [] and json.loads((datos / "config.json").read_text())["idioma"] == "es",
              "la segunda vez no pisa lo que ya hay en %APPDATA%")
    import config as C
    C.guardar({**C.DEFECTO, "perfil": "X"}, tmp / "nueva" / "carpeta" / "config.json")
    comprobar(C.cargar(tmp / "nueva" / "carpeta" / "config.json")["perfil"] == "X",
              "config.json crea su carpeta y guarda el perfil elegido")
    comprobar(R.CONFIG.parent.name == "AoE2Coaching" and R.HISTORIAL.parent == R.CONFIG.parent,
              f"config e historial en {R.CONFIG.parent}")


def test_sin_perfil(tmp: Path):
    print("Sin carpeta del perfil (juego sin abrir nunca)")
    cat = apoyo.instalador_de_prueba(tmp, "sin_perfil", guias=False).catalogo
    inst = I.Instalador(perfil=None, juego=None, contenido=tmp / "contenido_sin_perfil", catalogo=cat)
    comprobar(inst.mod_instalado is None and inst.xs_perfil is None and not inst.juego_instalado(), "nada que leer")
    comprobar(inst.guia_instalada({}) is None, "ninguna guía instalada")
    comprobar(inst.activar_guia({"archivo_xs": "guia_scouts.xs"}) == I.SIN_PERFIL, "activar una guía explica el motivo")
    estados = inst.estado_mapas()
    comprobar(estados and all(e.estado == "sin_juego" for e in estados),
              "los mapas salen sin instalar (sin juego no se pueden armar)")
    comprobar(inst.instalar_mod(cat.de("mod")[0], tmp / "no.zip") == I.SIN_PERFIL and inst.pendientes() == []
              and all(m.estado == "no_instalado" for m in inst.estado_mods() if m.elemento.compatible()),
              "los mods tampoco se instalan sin perfil")
    comprobar(inst.instalar_mapa(estados[0].mapa) == I.SIN_PERFIL and inst.quitar_mapa(estados[0].mapa) == I.SIN_PERFIL,
              "instalar o quitar un mapa explica el motivo")
    comprobar(list(L.Lector(None)._candidatos()) == [], "el lector no busca nada")
    perfil = tmp / "perfil"
    archivo(perfil / "profile" / "[AoE2C] Arena.xsdat")
    comprobar([p.name for p in L.Lector(perfil)._candidatos()] == ["[AoE2C] Arena.xsdat"],
              "con perfil, busca el .xsdat en su carpeta profile")


def test_inicio():
    print("Inicio con Windows")
    orden = I.comando_inicio()
    comprobar("aoe2c.py" in orden and orden.endswith("--inicio"), f"apunta al programa único con --inicio: {orden}")


def test_panel_perfiles(tmp: Path):
    print("Panel: elegir y cambiar de perfil")
    from PySide6.QtWidgets import QApplication, QComboBox
    import dashboard as D
    import historial as H
    import textos
    app = QApplication.instance() or QApplication([])
    a, b = tmp / "perfiles" / "111", tmp / "perfiles" / "0"
    perfiles = [R.Perfil(a, "Zoen", 63, time.time()), R.Perfil(b, "", 2, time.time() - 1e5)]
    cambios, guardados = [], []
    config = {**__import__("config").DEFECTO}
    panel = D.Panel(config, H.Historial(None), L.cargar_guias(), I.Instalador(perfil=a, contenido=tmp / "contenido_rutas"),
                    comprobar_juego=False,
                    guardar_config=lambda: guardados.append(dict(config)), perfiles=perfiles,
                    al_cambiar_perfil=cambios.append, preguntar_perfil=True)
    textos.poner_idioma("es")
    comprobar(D.nombre_perfil(perfiles[1]).startswith("Sin conexión · 2 partidas"), "el perfil «0» se llama Sin conexión")
    elegido = []
    D.QDialog.exec = lambda self: (elegido.append(self), self.findChildren(D.QRadioButton)[1].setChecked(True), 1)[2]
    panel.mostrar()
    t0 = time.monotonic()
    while not elegido and time.monotonic() - t0 < 3:
        app.processEvents()
    comprobar(elegido, "al mostrarse por primera vez pregunta qué perfil usar")
    comprobar(panel.instalador.perfil == b and config["perfil"] == str(b) and cambios == [b],
              "el elegido pasa al instalador, a config.json y al lector")
    panel.mostrar()
    app.processEvents()
    comprobar(len(elegido) == 1, "no vuelve a preguntar")
    panel.ir("ajustes")
    combo = next(c for c in panel.findChildren(QComboBox) if c.count() == 2 and c.itemData(0) == str(a))
    combo.setCurrentIndex(0)
    comprobar(panel.instalador.perfil == a and cambios[-1] == a, "en Ajustes se cambia de perfil con la lista")
    comprobar(not panel.cambiar_juego(tmp / "no_es_el_juego") and config["juego"] is None,
              "una carpeta sin AoE2DE_s.exe no se acepta")
    juego = tmp / "AoE2DE"
    archivo(juego / R.EXE_JUEGO)
    comprobar(panel.cambiar_juego(juego) and panel.instalador.juego_instalado() and config["juego"] == str(juego),
              "la carpeta del juego elegida a mano se guarda")
    e = R.resolver({"juego": str(juego), "perfil": None})
    comprobar(e.juego == juego, "y la próxima vez se usa esa")
    panel.close()


def main():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        test_vdf()
        test_juego(tmp)
        test_perfiles(tmp)
        test_datos(tmp)
        test_sin_perfil(tmp)
        test_inicio()
        test_panel_perfiles(tmp)
    print("\nTodo bien.")


if __name__ == "__main__":
    main()
