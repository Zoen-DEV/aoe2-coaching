"""Pruebas de lo que necesita la app instalada: actualizaciones, desinstalación y las
órdenes del instalador (sin abrir ventanas ni conectarse a GitHub).

    py pruebas/test_empaquetado.py

Usa un perfil inventado en una carpeta temporal: no toca el juego, el registro de
Windows ni %APPDATA%.
"""

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # nada aparece en pantalla
os.environ["AOE2C_INSTANCIA"] = f"AoE2Coaching-prueba-{os.getpid()}"  # nunca la copia abierta de verdad
OVERLAY = Path(__file__).resolve().parent.parent  # apps/desktop
sys.path.insert(0, str(OVERLAY))

import actualizacion as A  # noqa: E402
import apoyo  # noqa: E402
import catalogo as K  # noqa: E402
import config as C  # noqa: E402
import desinstalar as D  # noqa: E402
import historial as H  # noqa: E402
import instalador as I  # noqa: E402
import textos  # noqa: E402


def comprobar(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("  ok ·", msg)


def publicacion(etiqueta: str, archivo: str | None = None, tamano: int = 1000, digest: str | None = None,
                **extra) -> dict:
    p = {"tag_name": etiqueta, "draft": False, "prerelease": False, "html_url": f"https://github.com/x/{etiqueta}",
         "assets": []}
    if archivo:
        a = {"name": archivo, "size": tamano, "browser_download_url": f"https://github.com/x/{archivo}"}
        if digest:
            a["digest"] = digest
        p["assets"].append(a)
    p.update(extra)
    return p


def test_elegir():
    print("Actualizaciones: elegir la versión")
    pubs = [
        publicacion("contenido-2026-11-07", "catalogo.json"),
        publicacion("desktop-v1.2.0", "AoE2Coaching-Setup-1.2.0.exe", digest="sha256:" + "a" * 64),
        publicacion("desktop-v1.3.0", "AoE2Coaching-Setup-1.3.0.exe", prerelease=True),
        publicacion("desktop-v1.4.0", "AoE2Coaching-Setup-1.4.0.exe", draft=True),
        publicacion("desktop-v1.1.0", "AoE2Coaching-Setup-1.1.0.exe"),
        publicacion("desktop-v2.0.0"),  # sin instalador todavía
        publicacion("desktop-v1.5.0", "AoE2Coaching-Setup-1.4.9.exe"),  # el nombre no coincide
        publicacion("desktop-vx", "AoE2Coaching-Setup-x.exe"),
    ]
    a = A.elegir(pubs, "1.0.0")
    comprobar(a is not None and a.version == "1.2.0", "la más nueva publicada con su instalador (ni borradores ni previas)")
    comprobar(a.sha256 == "a" * 64 and a.tamano == 1000, "con el tamaño y el SHA-256 que da GitHub")
    comprobar(A.elegir(pubs, "1.2.0") is None, "si ya es la última, no hay nada")
    comprobar(A.elegir(pubs, "1.10.0") is None, "las versiones se comparan como números")
    comprobar(A.elegir({"message": "rate limit"}, "1.0.0") is None, "una respuesta rara no rompe nada")
    sin_hash = A.elegir([publicacion("desktop-v1.1.0", "AoE2Coaching-Setup-1.1.0.exe", digest="md5:x")], "1.0.0")
    comprobar(sin_hash is not None and sin_hash.sha256 is None, "sin SHA-256 válido, solo se comprueba el tamaño")


def test_descargar(tmp: Path):
    print("Actualizaciones: descargar el instalador")
    origen = tmp / "origen.exe"
    origen.write_bytes(b"MZ" + bytes(5000))
    sha = hashlib.sha256(origen.read_bytes()).hexdigest()
    vistos = []
    a = A.Actualizacion("1.2.0", str(origen), origen.stat().st_size, sha, "")
    ruta = A.descargar(a, tmp / "descargas", progreso=lambda b, t: vistos.append((b, t)))
    comprobar(ruta.name == "AoE2Coaching-Setup-1.2.0.exe" and ruta.read_bytes() == origen.read_bytes(),
              "queda como AoE2Coaching-Setup-<versión>.exe")
    comprobar(vistos and vistos[-1] == (a.tamano, a.tamano), "avisa del progreso")
    for malo, motivo in ((A.Actualizacion("1.2.1", str(origen), a.tamano, "0" * 64, ""), "otro hash"),
                         (A.Actualizacion("1.2.2", str(origen), a.tamano - 1, None, ""), "otro tamaño")):
        try:
            A.descargar(malo, tmp / "descargas")
            comprobar(False, f"con {motivo} falla")
        except A.ActualizacionError:
            comprobar(not list((tmp / "descargas").glob(f"*{malo.version}*")), f"con {motivo} falla y no deja nada")


def test_panel(tmp: Path):
    print("Actualizaciones: el panel")
    from PySide6.QtWidgets import QApplication, QPushButton
    app = QApplication.instance() or QApplication([])
    import dashboard as DB
    inst = apoyo.instalador_de_prueba(tmp, "panel_act")
    salir = []
    p = DB.Panel(C.cargar(tmp / "nada.json"), H.Historial(None), inst.guias(), inst, segundo_plano=False,
                 guardar_config=lambda: None, comprobar_juego=False, al_salir=lambda: salir.append(True))
    comprobar(p.estado_actualizacion[0] == "desde_codigo", "desde el código (o en las pruebas) no busca")
    p.ir("ajustes")
    app.processEvents()
    botones = {b.text(): b for b in p.p_ajustes.findChildren(QPushButton)}
    comprobar(not botones[textos.t("act_buscar")].isEnabled(), "y el botón «Buscar» está desactivado")

    origen = tmp / "nuevo.exe"
    origen.write_bytes(b"MZ" + bytes(100))
    nueva = A.Actualizacion("9.0.0", str(origen), origen.stat().st_size, None, "")
    lanzados = []
    buscar, descargar, lanzar = A.buscar, A.descargar, A.lanzar
    try:
        A.buscar = lambda: nueva
        A.descargar = lambda a, progreso=None: descargar(a, tmp / "act", progreso)
        A.lanzar = lambda ruta: lanzados.append(ruta)
        p.estado_actualizacion = ("sin_buscar", "")
        p.buscar_actualizacion()
        app.processEvents()
        comprobar(p.estado_actualizacion[0] == "disponible" and not p.boton_actualizar.isHidden(),
                  "si hay una versión nueva, aparece «Actualizar a v9.0.0»")
        comprobar("9.0.0" in p.boton_actualizar.text(), "con su número")
        botones = {b.text(): b for b in p.p_ajustes.findChildren(QPushButton)}
        comprobar(textos.t("act_actualizar") in botones, "y en Ajustes el botón «Actualizar»")

        class EnPartida:
            en_partida = True
        p.overlay = EnPartida()
        p.actualizar_app()
        comprobar(not lanzados and p.mensaje.text() == textos.t("act_en_partida"), "en plena partida no actualiza")
        p.overlay = None
        p.actualizar_app()
        comprobar(len(lanzados) == 1 and lanzados[0].name == "AoE2Coaching-Setup-9.0.0.exe",
                  "descarga el instalador y lo abre")
        comprobar(salir == [True], "y cierra AoE2C para que el instalador lo reemplace")

        A.buscar = lambda: None
        p.estado_actualizacion = ("sin_buscar", "")
        p.buscar_actualizacion()
        comprobar(p.estado_actualizacion[0] == "al_dia" and p.boton_actualizar.isHidden(), "al día: sin botón")

        def sin_red():
            raise A.ActualizacionError("sin conexión")
        A.buscar = sin_red
        p.buscar_actualizacion()
        comprobar(p.estado_actualizacion == ("error", "sin conexión"), "sin conexión lo dice en Ajustes")
    finally:
        A.buscar, A.descargar, A.lanzar = buscar, descargar, lanzar


def preparar_juego(tmp: Path) -> tuple[I.Instalador, Path]:
    """Un perfil con todo lo de AoE2C instalado y un mod de otro autor."""
    inst = apoyo.instalador_de_prueba(tmp, "desinstalar")
    ruta = Path(inst.catalogo.origen)
    K.guardar_copia(ruta.read_bytes(), str(ruta), inst.contenido)
    guias = inst.guias()
    comprobar(inst.activar_guia(guias["fast_castle"]) is None, "(preparación) guía activada")
    comprobar(inst.instalar_mapa(inst.mapas()[0], guias["fast_castle"]) is None, "(preparación) mapa instalado")
    mod = inst.catalogo.buscar("mod", apoyo.MOD_PRUEBA)
    comprobar(inst.instalar_mod(mod, K.descargar_paquete(inst.catalogo, mod, inst.descargas)) is None,
              "(preparación) mod instalado")
    inst.aplicar_pendientes(False)
    otro = inst.mods_locales / "mod-de-otro"
    otro.mkdir(parents=True)
    (otro / "info.json").write_text("{}", encoding="utf-8")
    I.cambiar_mod_status(inst.mod_status, [{"accion": "activar", "carpeta": "mod-de-otro", "titulo": "Otro"}])
    (inst.xs_perfil / "script_de_otro.xs").write_text("// otro", encoding="utf-8")
    datos = tmp / "datos_app"
    (datos / "logs").mkdir(parents=True)
    (datos / "historial.json").write_text("[]", encoding="utf-8")
    return inst, datos


def rutas_mod_status(inst: I.Instalador) -> list[str]:
    return [m["Path"] for m in json.loads(inst.mod_status.read_text(encoding="utf-8"))["Mods"]]


def test_desinstalar(tmp: Path):
    print("Desinstalar")
    inst, datos = preparar_juego(tmp)
    antes = rutas_mod_status(inst)
    comprobar({"local//guia-apertura-castillos", f"local//{apoyo.MOD_PRUEBA}", "local//mod-de-otro"} <= set(antes),
              "(preparación) mod-status.json con los mods de AoE2C y el de otro")
    inicio = []
    args = dict(perfiles=[inst.perfil], contenido=inst.contenido, datos=datos, inicio=lambda a: inicio.append(a))

    codigo = D.main(["--desinstalar", "--juego", "--datos"], juego_abierto=lambda: True, **args)
    comprobar(codigo == D.JUEGO_ABIERTO, "con el juego abierto devuelve 2")
    comprobar((inst.xs_perfil / I.XS_COMUN).is_file() and inst.mod_instalado.is_dir() and datos.is_dir()
              and not inicio, "y no toca nada (ni el juego, ni los datos, ni el inicio con Windows)")

    codigo = D.main(["--desinstalar", "--juego"], juego_abierto=lambda: False, **args)
    comprobar(codigo == D.BIEN, "con el juego cerrado, todo bien")
    xs = sorted(p.name for p in inst.xs_perfil.iterdir())
    comprobar(xs == ["script_de_otro.xs"], "quita aoe2c_guia.xs y los guia_*.xs, no los scripts de otros")
    comprobar(not inst.mod_instalado.exists() and not (inst.mods_locales / apoyo.MOD_PRUEBA).exists(),
              "quita el mod de los mapas y los mods instalados desde el panel")
    comprobar((inst.mods_locales / "mod-de-otro").is_dir(), "deja los mods de otros")
    comprobar(rutas_mod_status(inst) == [r for r in antes if r == "local//mod-de-otro"],
              "en mod-status.json solo quita las líneas de AoE2C")
    comprobar(inicio == [False], "quita AoE2C del inicio con Windows")
    comprobar(datos.is_dir(), "sin --datos, el historial y la configuración se quedan")

    comprobar(D.main(["--desinstalar", "--datos"], juego_abierto=lambda: True, **args) == D.BIEN and not datos.exists(),
              "--datos borra la carpeta de datos (sin --juego no importa si el juego está abierto)")
    comprobar(D.main(["--desinstalar", "--juego"], juego_abierto=lambda: False, **args) == D.BIEN,
              "otra vez, sin nada que quitar, no falla")


def test_ordenes():
    print("Órdenes del instalador")
    import aoe2c
    comprobar(aoe2c.orden_instalador([]) is None and aoe2c.orden_instalador(["--inicio"]) is None,
              "sin órdenes del instalador, abre la app")
    comprobar(aoe2c.orden_instalador(["--salir"]) == 0, "--salir sin ninguna copia abierta termina bien")


def main():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        test_elegir()
        test_descargar(tmp)
        test_panel(tmp)
        test_desinstalar(tmp)
        test_ordenes()
    print("\nTodo bien.")


if __name__ == "__main__":
    main()
