"""Arma AoE2C para instalar: la app con PyInstaller y el instalador con Inno Setup.

    py apps/desktop/empaquetado/empaquetar.py            app + instalador
    py apps/desktop/empaquetado/empaquetar.py --sin-instalador   solo la app

1. Exporta el logo (build/marca/aoe2c.ico) para el .exe y el instalador, y las imágenes y
   la letra del instalador (build/marca/instalador, ver marca_instalador.py).
2. PyInstaller en modo carpeta (no un solo .exe: abre más rápido y los antivirus lo
   marcan menos) -> build/desktop/dist/AoE2Coaching/AoE2Coaching.exe
3. Inno Setup (ISCC.exe) con aoe2c.iss -> build/instalador/AoE2Coaching-Setup-<versión>.exe

La versión sale de apps/desktop/version.py. Necesita `py -m pip install -r requirements.txt`
(PyInstaller) e Inno Setup 6.7 o posterior (https://jrsoftware.org/isinfo.php, o
`winget install JRSoftware.InnoSetup`). En GitHub Actions lo corre desktop.yml (plan 7).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
DESKTOP = AQUI.parent
RAIZ = DESKTOP.parent.parent
BUILD = RAIZ / "build"
TRABAJO = BUILD / "desktop"
DIST = TRABAJO / "dist"
APP = DIST / "AoE2Coaching"
INSTALADOR = BUILD / "instalador"
ICONO = BUILD / "marca" / "aoe2c.ico"
NOMBRE = "AoE2Coaching"

sys.path.insert(0, str(DESKTOP))
from version import VERSION  # noqa: E402

# Lo que la app no usa: así la carpeta pesa menos.
EXCLUIR = ["tkinter", "unittest", "pydoc", "numpy", "PIL",
           "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtPdf", "PySide6.QtWebEngineCore",
           "PySide6.QtMultimedia", "PySide6.QtOpenGL", "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtDataVisualization"]


# Lo que PyInstaller copia de Qt y la app no usa (rutas dentro de _internal/PySide6). El
# teclado virtual arrastra QML y Quick; el visor de PDF, Qt6Pdf; opengl32sw es un OpenGL
# por software y la app no dibuja con OpenGL. De las traducciones de Qt quedan es y en.
PODAR = ["opengl32sw.dll", "Qt6Pdf.dll", "Qt6Qml.dll", "Qt6QmlMeta.dll", "Qt6QmlModels.dll",
         "Qt6QmlWorkerScript.dll", "Qt6Quick.dll", "Qt6VirtualKeyboard.dll",
         "plugins/platforminputcontexts", "plugins/imageformats/qpdf.dll", "plugins/generic"]
TRADUCCIONES = ("_es.qm", "_en.qm")


def podar(app: Path) -> None:
    qt = app / "_internal" / "PySide6"
    for nombre in PODAR:
        ruta = qt / nombre
        if ruta.is_dir():
            shutil.rmtree(ruta)
        elif ruta.is_file():
            ruta.unlink()
    for qm in (qt / "translations").glob("*.qm"):
        if not qm.name.endswith(TRADUCCIONES):
            qm.unlink()


def version_windows(version: str) -> tuple[int, int, int, int]:
    partes = [int(x) for x in version.split(".")][:4]
    return tuple(partes + [0] * (4 - len(partes)))


def archivo_version(destino: Path) -> Path:
    """Los datos de "Propiedades > Detalles" del .exe (versión, nombre, autor)."""
    v = version_windows(VERSION)
    texto = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={v}, prodvers={v}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Zoen-DEV'),
      StringStruct('FileDescription', 'AoE2 Coaching'),
      StringStruct('FileVersion', '{VERSION}'),
      StringStruct('InternalName', '{NOMBRE}'),
      StringStruct('LegalCopyright', 'Zoen-DEV'),
      StringStruct('OriginalFilename', '{NOMBRE}.exe'),
      StringStruct('ProductName', 'AoE2 Coaching'),
      StringStruct('ProductVersion', '{VERSION}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")
    return destino


def exportar_logo() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import logo
    logo.exportar(ICONO.parent)
    sys.path.insert(0, str(AQUI))
    import marca_instalador
    marca_instalador.exportar(ICONO.parent)


def armar_app() -> Path:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        sys.exit("Falta PyInstaller: py -m pip install -r requirements.txt")
    shutil.rmtree(APP, ignore_errors=True)
    orden = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
             "--name", NOMBRE, "--icon", str(ICONO), "--version-file", str(archivo_version(TRABAJO / "version.txt")),
             "--distpath", str(DIST), "--workpath", str(TRABAJO / "work"), "--specpath", str(TRABAJO),
             "--paths", str(DESKTOP)]
    for m in EXCLUIR:
        orden += ["--exclude-module", m]
    orden.append(str(DESKTOP / "aoe2c.py"))
    subprocess.run(orden, check=True)
    podar(APP)
    exe = APP / f"{NOMBRE}.exe"
    if not exe.is_file():
        sys.exit(f"PyInstaller no generó {exe}")
    return exe


def buscar_iscc() -> Path | None:
    propio = os.environ.get("ISCC")
    candidatos = [Path(propio)] if propio else []
    en_path = shutil.which("iscc")
    if en_path:
        candidatos.append(Path(en_path))
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
                 os.environ.get("LOCALAPPDATA") and str(Path(os.environ["LOCALAPPDATA"]) / "Programs")):
        if base:
            candidatos.append(Path(base) / "Inno Setup 6" / "ISCC.exe")
    return next((c for c in candidatos if c.is_file()), None)


def armar_instalador() -> Path:
    iscc = buscar_iscc()
    if iscc is None:
        sys.exit("Falta Inno Setup 6 (ISCC.exe): winget install JRSoftware.InnoSetup, o la variable ISCC")
    INSTALADOR.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(iscc), "/Qp", f"/DVersion={VERSION}", f"/DFuente={APP}", f"/DSalida={INSTALADOR}",
                    f"/DIcono={ICONO}", f"/DMarca={ICONO.parent / 'instalador'}", str(AQUI / "aoe2c.iss")],
                   check=True)
    salida = INSTALADOR / f"{NOMBRE}-Setup-{VERSION}.exe"
    if not salida.is_file():
        sys.exit(f"Inno Setup no generó {salida}")
    return salida


def main(args: list[str]) -> None:
    exportar_logo()
    exe = armar_app()
    print(f"app: {exe}")
    if "--sin-instalador" not in args:
        print(f"instalador: {armar_instalador()}")


if __name__ == "__main__":
    main(sys.argv[1:])
