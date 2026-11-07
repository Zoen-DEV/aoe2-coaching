"""Pruebas del catálogo de contenido: formato, descargas con hash, guías, mapas, mods y
mod-status.json, y las páginas Guías, Mapas y MODs del panel.

    py apps/desktop/pruebas/test_catalogo.py

Usa un juego falso y carpetas temporales (apoyo.py): no toca el juego, el perfil real
ni %APPDATA%. Necesita las guías armadas (py content/guias/build.py).
"""

import copy
import json
import os
import sys
import tempfile
import time
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # nada aparece en pantalla
sys.path.insert(0, str(Path(__file__).resolve().parent))

import apoyo  # noqa: E402
import catalogo as K  # noqa: E402
import config as C  # noqa: E402
import historial as H  # noqa: E402
import instalador as I  # noqa: E402
import textos  # noqa: E402


def comprobar(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("  ok ·", msg)


def falla(funcion, *args) -> str:
    try:
        funcion(*args)
    except K.CatalogoError as e:
        return str(e)
    return ""


# --- Formato -------------------------------------------------------------------------


def test_formato(tmp: Path):
    print("Formato del catálogo y versiones")
    ruta = apoyo.catalogo_de_prueba(tmp / "formato")
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    cat = K.leer(datos, str(ruta), estricto=True)
    comprobar([e.tipo for e in cat.elementos].count("mapa") == 5 and len(cat.de("guia")) == 2 and len(cat.de("mod")) == 2,
              "2 guías, 5 mapas y 2 mods")
    fc = cat.buscar("guia", "fast_castle")
    comprobar(fc.paquete and len(fc.paquete.sha256) == 64 and fc.texto("descripcion", "en").startswith("Straight"),
              "cada guía lleva paquete con SHA-256 y textos en los dos idiomas")
    comprobar(all(e.paquete is None for e in cat.de("mapa")), "los mapas no traen paquete (se arman en la PC)")
    comprobar(K.mas_nueva("1.10.0", "1.9.9") and not K.mas_nueva("1.0", "1.0.0") and K.mas_nueva("2", "1.99.99"),
              "las versiones se comparan por números, no como texto")
    comprobar(not cat.buscar("mod", "mod-futuro").compatible() and fc.compatible(),
              "lo que pide una app más nueva no es compatible")
    comprobar(cat.url_paquete(fc) == str(ruta.parent / fc.paquete.archivo), "paquetes junto al catalogo.json local")
    remoto = K.leer(datos, "https://github.com/x/y/releases/download/contenido-1/catalogo.json")
    comprobar(remoto.url_paquete(fc) == f"https://github.com/x/y/releases/download/contenido-1/guia-fast_castle-{fc.version}.zip",
              "y junto al catalogo.json publicado")

    raro = copy.deepcopy(datos)
    raro["elementos"].append({"tipo": "civilizacion", "id": "aztecas"})
    raro["elementos"][0]["paquete"]["sha256"] = "x"
    leido = K.leer(raro)
    comprobar(len(leido.elementos) == len(cat.elementos) - 1 and len(leido.descartados) == 2,
              "un tipo desconocido o un elemento roto se descartan sin romper el resto")
    comprobar("sha256" in falla(K.leer, raro, "", True), "en modo estricto (generador) son un error")
    del raro["elementos"][0]
    comprobar("tipo desconocido" in falla(K.leer, raro, "", True), "también el tipo desconocido")
    comprobar("actualiza la app" in falla(K.leer, {**datos, "formato": 2}), "un formato más nuevo pide actualizar la app")
    comprobar("JSON" in falla(K.leer, b"{roto"), "un catálogo roto da un error legible")
    repetido = copy.deepcopy(datos)
    repetido["elementos"].append(copy.deepcopy(datos["elementos"][0]))
    comprobar("repetido" in falla(K.leer, repetido, "", True), "un id repetido es un error")
    malo = copy.deepcopy(datos)
    next(e for e in malo["elementos"] if e["tipo"] == "mod")["datos"]["carpeta"] = "../windows"
    comprobar("carpeta" in falla(K.leer, malo, "", True), "una carpeta de mod con ../ no se acepta")
    sin_en = copy.deepcopy(datos)
    sin_en["elementos"][0]["nombre"] = {"es": "Solo español"}
    comprobar("inglés" in falla(K.leer, sin_en, "", True), "cada texto tiene que estar en español e inglés")


def test_descargas(tmp: Path):
    print("Descargas: hash, tamaño, paquetes peligrosos y copia sin conexión")
    ruta = apoyo.catalogo_de_prueba(tmp / "descargas")
    cat, datos = K.descargar(str(ruta))
    comprobar(len(cat.elementos) == 9 and datos == ruta.read_bytes(), "descargar el catálogo (ruta local)")
    fc = cat.buscar("guia", "fast_castle")
    zip_ = K.descargar_paquete(cat, fc, tmp / "bajadas")
    comprobar(zip_.is_file() and K.sha256_de(zip_) == fc.paquete.sha256, "el paquete llega y su hash coincide")
    original = ruta.parent / fc.paquete.archivo
    bueno = original.read_bytes()
    original.write_bytes(bueno[:-1] + bytes([bueno[-1] ^ 1]))
    comprobar("hash" in falla(K.descargar_paquete, cat, fc, tmp / "bajadas2")
              and not any((tmp / "bajadas2").glob("*")), "un paquete alterado se rechaza y no queda en disco")
    original.write_bytes(bueno + b"extra")
    comprobar("hash" in falla(K.descargar_paquete, cat, fc, tmp / "bajadas2"), "uno con bytes de más, también")
    original.write_bytes(bueno)
    comprobar("no se pudo leer" in falla(K.descargar, str(tmp / "no_existe.json")), "sin catálogo, error legible")

    peligroso = tmp / "peligroso.zip"
    with zipfile.ZipFile(peligroso, "w") as z:
        z.writestr("../../fuera.txt", "x")
    comprobar("no permitida" in falla(K.extraer, peligroso, tmp / "extraido") and not (tmp / "fuera.txt").exists(),
              "un paquete con ../ no puede escribir fuera de su carpeta")
    with zipfile.ZipFile(peligroso, "w") as z:
        z.writestr("C:/Windows/x.txt", "x")
    comprobar("no permitida" in falla(K.extraer, peligroso, tmp / "extraido"), "ni con una ruta absoluta")

    copia = tmp / "copia"
    comprobar(K.cargar_copia(copia) is None, "sin copia guardada no hay catálogo")
    K.guardar_copia(datos, cat.origen, copia)
    guardado = K.cargar_copia(copia)
    comprobar(guardado and len(guardado.elementos) == 9 and guardado.origen == str(ruta),
              "la copia guardada sirve sin conexión (con su origen, para los paquetes)")
    os.environ["AOE2C_CATALOGO"] = "https://ejemplo/catalogo.json"
    comprobar(K.fuente_por_defecto() == "https://ejemplo/catalogo.json", "AOE2C_CATALOGO elige otro catálogo")
    del os.environ["AOE2C_CATALOGO"]


# --- Guías ------------------------------------------------------------------------------


def test_guias(tmp: Path):
    print("Guías del catálogo")
    inst = apoyo.instalador_de_prueba(tmp, "guias", guias=False)
    cat = inst.catalogo
    comprobar(inst.guias() == {}, "al principio no hay guías instaladas")
    sc = cat.buscar("guia", "scouts")
    comprobar(inst.instalar_guia(sc, K.descargar_paquete(cat, sc, inst.descargas)) is None, "instalar Scouts")
    comprobar(list(inst.guias()) == ["scouts"] and inst.version_guia("scouts") == sc.version,
              "queda en contenido/guias con su versión")
    comprobar(inst.activar_guia(inst.guias()["scouts"]) is None and inst.guia_instalada(inst.guias()) == "scouts",
              "y se puede activar para los mapas")
    fc = cat.buscar("guia", "fast_castle")
    error = inst.instalar_guia(sc, K.descargar_paquete(cat, fc, inst.descargas))
    comprobar(error and "scouts" in error and list(inst.guias()) == ["scouts"],
              "el paquete de otra guía no se instala con el nombre equivocado")
    comprobar(inst.quitar_guia(inst.guias()["scouts"]) is None and inst.guias() == {} and inst.version_guia("scouts") is None,
              "quitar la guía")


# --- mod-status.json ------------------------------------------------------------------------


MOD_STATUS = {"Mods": [
    {"CheckSum": "1342791553", "Enabled": True, "LastUpdate": "1755095488084", "Path": "subscribed//409484_Legacy ES Maps",
     "Priority": 1, "PublishID": 0, "Title": "Legacy ES Maps", "WorkshopID": 409484},
    {"CheckSum": "1520413741", "Enabled": False, "LastUpdate": "0", "Path": "local//icono-prueba", "Priority": 2,
     "PublishID": 0, "Title": "Icono de prueba", "WorkshopID": 0},
    {"CheckSum": "4260840331", "Enabled": False, "LastUpdate": "1576867363937", "Path": "subscribed//2416_No Intro",
     "Priority": 7, "PublishID": 0, "Title": "No Intro", "WorkshopID": 2416},
], "Unsub": []}


def test_mod_status(tmp: Path):
    print("mod-status.json: solo nuestras líneas, copia antes y orden intacto")
    archivo = tmp / "ms" / "mod-status.json"
    archivo.parent.mkdir()
    archivo.write_text(json.dumps(MOD_STATUS, separators=(",", ":")), encoding="utf-8")
    comprobar(I.cambiar_mod_status(archivo, [{"accion": "activar", "carpeta": "icono-prueba", "titulo": "x"}]) is None,
              "activar un mod que el jugador desactivó")
    d = json.loads(archivo.read_text(encoding="utf-8"))
    comprobar(d["Mods"][1]["Enabled"] is True and d["Mods"][1]["CheckSum"] == "1520413741" and d["Mods"][1]["Priority"] == 2,
              "solo cambia Enabled (su prioridad y su CheckSum siguen igual)")
    comprobar(d["Mods"][0] == MOD_STATUS["Mods"][0] and d["Mods"][2] == MOD_STATUS["Mods"][2],
              "los demás mods quedan exactamente igual (también los desactivados)")
    comprobar(json.loads((archivo.parent / I.COPIA_MOD_STATUS).read_text(encoding="utf-8")) == MOD_STATUS,
              "antes guarda una copia del archivo original")
    antes = archivo.read_bytes()
    comprobar(I.cambiar_mod_status(archivo, [{"accion": "activar", "carpeta": "icono-prueba", "titulo": "x"}]) is None
              and archivo.read_bytes() == antes, "si ya está activo, no reescribe nada")
    I.cambiar_mod_status(archivo, [{"accion": "activar", "carpeta": "guia-apertura-castillos", "titulo": "AoE2 Coaching"}])
    d = json.loads(archivo.read_text(encoding="utf-8"))
    nuevo = d["Mods"][-1]
    comprobar(nuevo["Path"] == "local//guia-apertura-castillos" and nuevo["Enabled"] and nuevo["Priority"] == 8
              and nuevo["WorkshopID"] == 0, "un mod nuevo va al final, con la prioridad siguiente")
    comprobar([m["Path"] for m in d["Mods"][:3]] == [m["Path"] for m in MOD_STATUS["Mods"]], "el orden de los otros no cambia")
    I.cambiar_mod_status(archivo, [{"accion": "quitar", "carpeta": "icono-prueba", "titulo": "x"}])
    d = json.loads(archivo.read_text(encoding="utf-8"))
    comprobar([m["Path"] for m in d["Mods"]] == ["subscribed//409484_Legacy ES Maps", "subscribed//2416_No Intro",
                                                  "local//guia-apertura-castillos"], "quitar borra solo su línea")
    archivo.write_text("{roto", encoding="utf-8")
    error = I.cambiar_mod_status(archivo, [{"accion": "activar", "carpeta": "icono-prueba", "titulo": "x"}])
    comprobar(error and archivo.read_text(encoding="utf-8") == "{roto", "un archivo que no se entiende no se toca")
    nuevo = tmp / "ms2" / "mod-status.json"
    I.cambiar_mod_status(nuevo, [{"accion": "activar", "carpeta": "icono-prueba", "titulo": "Icono de prueba"}])
    d = json.loads(nuevo.read_text(encoding="utf-8"))
    comprobar(d["Unsub"] == [] and d["Mods"][0]["Priority"] == 1, "si el juego aún no lo creó, se crea con el formato del juego")


# --- Mods ---------------------------------------------------------------------------------


def test_mods(tmp: Path):
    print("Mods: instalar, activar con el juego cerrado, actualizar y quitar")
    inst = apoyo.instalador_de_prueba(tmp, "mods", guias=False)
    cat = inst.catalogo
    mod = cat.buscar("mod", apoyo.MOD_PRUEBA)
    estados = {m.elemento.id: m for m in inst.estado_mods()}
    comprobar(estados[apoyo.MOD_PRUEBA].estado == "no_instalado" and estados["mod-futuro"].estado == "necesita_app",
              "al principio: uno sin instalar y otro que pide una app más nueva")
    paquete = K.descargar_paquete(cat, mod, inst.descargas)
    comprobar(inst.instalar_mod(mod, paquete, juego_abierto=True) is None, "instalar con el juego abierto (mod nuevo)")
    carpeta = inst.mods_locales / apoyo.MOD_PRUEBA
    comprobar((carpeta / "info.json").is_file() and (carpeta / "resources").is_dir(), "los archivos van a mods/local")
    comprobar(not inst.mod_status.exists() and inst.activacion(apoyo.MOD_PRUEBA) == "pendiente",
              "con el juego abierto, mod-status.json no se toca: la activación queda pendiente")
    comprobar(inst.aplicar_pendientes(juego_abierto=True) == ([], None), "mientras el juego siga abierto, sigue pendiente")
    aplicados, error = inst.aplicar_pendientes(juego_abierto=False)
    comprobar(error is None and [p["carpeta"] for p in aplicados] == [apoyo.MOD_PRUEBA]
              and inst.activacion(apoyo.MOD_PRUEBA) == "activo", "al cerrarse el juego, se activa")
    estado = {m.elemento.id: m for m in inst.estado_mods()}[apoyo.MOD_PRUEBA]
    comprobar(estado.estado == "instalado" and estado.version == "1.0.0", "queda instalado con su versión")

    otro = I.Instalador(perfil=inst.perfil, juego=inst.juego, contenido=inst.contenido, catalogo=inst.catalogo)
    comprobar(otro.pendientes() == [] and otro.activacion(apoyo.MOD_PRUEBA) == "activo",
              "el estado sobrevive a reiniciar la app")
    datos = json.loads(inst.mod_status.read_text(encoding="utf-8"))
    datos["Mods"][0]["Enabled"] = False  # el jugador lo desactiva en el juego
    inst.mod_status.write_text(json.dumps(datos), encoding="utf-8")
    comprobar(inst.activacion(apoyo.MOD_PRUEBA) == "desactivado", "se ve si el jugador lo desactivó en el juego")
    inst.activar_mod(apoyo.MOD_PRUEBA, "Icono de prueba", juego_abierto=False)
    comprobar(inst.activacion(apoyo.MOD_PRUEBA) == "activo", "y se puede volver a activar")

    nueva = K.Elemento(**{**mod.__dict__, "version": "1.1.0"})
    inst.catalogo = K.Catalogo([nueva if e is mod else e for e in cat.elementos], cat.origen)
    comprobar({m.elemento.id: m for m in inst.estado_mods()}[apoyo.MOD_PRUEBA].estado == "desactualizado",
              "con una versión nueva en el catálogo, sale desactualizado")
    paquete = K.descargar_paquete(cat, mod, inst.descargas)
    comprobar(inst.instalar_mod(nueva, paquete, juego_abierto=True) == I.JUEGO_ABIERTO,
              "actualizarlo con el juego abierto pide cerrarlo (tiene sus archivos cargados)")
    comprobar(inst.instalar_mod(nueva, paquete, juego_abierto=False) is None
              and {m.elemento.id: m for m in inst.estado_mods()}[apoyo.MOD_PRUEBA].version == "1.1.0",
              "con el juego cerrado se actualiza")
    comprobar(not any(p.name.startswith(".aoe2c-") for p in inst.mods_locales.iterdir()), "sin carpetas temporales")
    comprobar(inst.quitar_mod(nueva, juego_abierto=True) == I.JUEGO_ABIERTO and carpeta.exists(),
              "quitarlo con el juego abierto pide cerrarlo")
    comprobar(inst.quitar_mod(nueva) is None and not carpeta.exists()
              and I.buscar_en_mod_status(inst.mod_status, apoyo.MOD_PRUEBA) is None,
              "quitarlo borra la carpeta y su línea de mod-status.json")
    malo = tmp / "no_es_mod.zip"
    with zipfile.ZipFile(malo, "w") as z:
        z.writestr("hola.txt", "x")
    comprobar("info.json" in (inst.instalar_mod(mod, malo) or "") and not carpeta.exists(),
              "un paquete sin info.json no se instala")


def test_mapas_mod(tmp: Path):
    print("Mapas: el mod de los mapas también se activa")
    inst = apoyo.instalador_de_prueba(tmp, "mapas_mod")
    inst.instalar_mapa(inst.mapas()[0], inst.guias()["fast_castle"])
    comprobar(inst.activacion(I.NOMBRE_MOD) == "pendiente", "al instalar el primer mapa, su mod queda por activar")
    inst.aplicar_pendientes(False)
    comprobar(inst.activacion(I.NOMBRE_MOD) == "activo", "y se activa con el juego cerrado")
    inst.instalar_mapa(inst.mapas()[1])
    comprobar(inst.pendientes() == [], "los siguientes mapas no vuelven a tocar mod-status.json")


# --- Panel ---------------------------------------------------------------------------------


def test_panel(tmp: Path):
    print("Panel: catálogo, Guías, Mapas y MODs")
    from PySide6.QtWidgets import QApplication, QPushButton
    app = QApplication.instance() or QApplication(sys.argv)
    import dashboard as D
    textos.poner_idioma("es")
    inst = apoyo.instalador_de_prueba(tmp, "panel", guias=False)
    fuente = inst.catalogo.origen
    inst.catalogo = None  # el panel lo descarga
    config = C.cargar(tmp / "nada.json")
    cambios = []
    p = D.Panel(config, H.Historial(None), {}, inst, comprobar_juego=False, guardar_config=lambda: None,
                fuente_catalogo=fuente, segundo_plano=False, al_cambiar_guias=cambios.append)
    comprobar(p.estado_catalogo[0] == "nunca", "sin copia guardada, no hay catálogo todavía")
    p.ir("inicio")
    comprobar(p.p_inicio.nombre_guia.text() == textos.t("sin_guia"), "inicio sin guías: lo dice y no falla")
    p.ir("guias")
    p.actualizar_catalogo()
    comprobar(p.estado_catalogo[0] == "al_dia" and inst.catalogo and K.cargar_copia(inst.contenido),
              "«Buscar novedades» descarga el catálogo y guarda una copia")
    instalar = [b for b in p.p_guias.findChildren(QPushButton) if b.text() == textos.t("instalar")]
    comprobar(len(instalar) == 2, "Guías ofrece instalar las dos guías del catálogo")
    instalar[1].click()
    app.processEvents()
    comprobar(list(p.guias) == ["scouts"] and cambios and list(cambios[-1]) == ["scouts"],
              "instalar Scouts: el panel y el lector la reciben")
    comprobar(config["guia_activa"] == "scouts" and inst.guia_instalada(p.guias) == "scouts",
              "la primera guía instalada queda activa en los mapas")
    p.ir("mapas")
    tarjetas = p.p_mapas.findChildren(D.TarjetaMapa)
    comprobar(len(tarjetas) == 5 and all(t.em.estado == "no_instalado" for t in tarjetas), "Mapas: los 5 del catálogo")
    tarjetas[0].instalar()
    app.processEvents()
    comprobar(inst.activacion(I.NOMBRE_MOD) == "activo", "instalar un mapa activa su mod en el acto (juego cerrado)")
    p.ir("mods")
    comprobar(len(p.p_mods.findChildren(D.TarjetaMod)) == 2, "MODs: los dos mods del catálogo")
    p.juego = True  # el juego está abierto
    boton = next(b for b in p.p_mods.findChildren(QPushButton) if b.text() == textos.t("instalar") and b.isEnabled())
    boton.click()
    app.processEvents()
    comprobar(inst.activacion(apoyo.MOD_PRUEBA) == "pendiente" and p.mensaje.text() == textos.t("mod_instalado_ok",
              nombre="Icono de prueba"), "con el juego abierto: se instala y la activación espera")
    p.juego = False
    p.comprobar_juego = True
    real = I.juego_abierto
    I.juego_abierto = lambda: False  # se cerró el juego
    try:
        p.actualizar_estado(forzar=True)
    finally:
        I.juego_abierto = real
        p.comprobar_juego = False
    comprobar(inst.activacion(apoyo.MOD_PRUEBA) == "activo" and "Icono de prueba" in p.mensaje.text(),
              f"al cerrarse el juego, el panel lo activa y avisa: «{p.mensaje.text()}»")
    futuro = [b for b in p.p_mods.findChildren(QPushButton) if b.text() == textos.t("necesita_app")]
    comprobar(len(futuro) == 1 and not futuro[0].isEnabled(), "el mod que pide otra app: «Necesita actualizar AoE2C»")
    for idioma in ("en", "es"):
        p.cambiar_idioma(idioma)
        for nombre in ("guias", "mapas", "mods"):
            p.ir(nombre)
            app.processEvents()
    comprobar(True, "las páginas se dibujan en los dos idiomas")
    p.fuente_catalogo = str(tmp / "no_existe.json")
    p.actualizar_catalogo()
    comprobar(p.estado_catalogo[0] == "sin_conexion" and inst.catalogo is not None,
              "sin conexión se sigue usando el último catálogo")

    # De verdad en segundo plano: la descarga vuelve a la ventana por una señal.
    inst2 = apoyo.instalador_de_prueba(tmp, "panel2", guias=False)
    fuente2, inst2.catalogo = inst2.catalogo.origen, None
    p2 = D.Panel(C.cargar(tmp / "nada2.json"), H.Historial(None), {}, inst2, comprobar_juego=False,
                 guardar_config=lambda: None, fuente_catalogo=fuente2)
    p2.ir("guias")
    p2.actualizar_catalogo()
    t0 = time.monotonic()
    while p2.estado_catalogo[0] == "buscando" and time.monotonic() - t0 < 10:
        app.processEvents()
    p2.instalar_elemento(inst2.catalogo.buscar("guia", "fast_castle"))
    comprobar(("guia", "fast_castle") in p2.descargando, "mientras descarga, la guía sale «Descargando…»")
    while p2.descargando and time.monotonic() - t0 < 10:
        app.processEvents()
    comprobar(p2.estado_catalogo[0] == "al_dia" and list(p2.guias) == ["fast_castle"],
              "en segundo plano: catálogo y guía llegan sin bloquear el panel")


def main():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        test_formato(tmp)
        test_descargas(tmp)
        test_guias(tmp)
        test_mod_status(tmp)
        test_mods(tmp)
        test_mapas_mod(tmp)
        test_panel(tmp)
    print("\nTodo bien.")


if __name__ == "__main__":
    main()
