"""Instala en el juego lo que se elige en el panel: la guía activa y los mapas.

- **Guía activa.** Todos los mapas [AoE2C] cargan el mismo script, aoe2c_guia.xs, de la
  carpeta xs del perfil. Elegir una guía es copiar su script (guia_scouts.xs...) encima
  de ese archivo. Vale para la siguiente partida; no hace falta reiniciar el juego.
- **Mapas.** Cada mapa es un .rms (con su imagen .png) dentro del mod local
  "guia-apertura-castillos". Se pueden instalar, quitar o guardar una copia en otra
  carpeta. Un mapa nuevo sale en la lista del juego al reiniciarlo.

Los archivos de origen son los que genera content/guias/build.py en build/mods/ (raíz del monorepo).
"""

import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAIZ = HERE.parent.parent  # raíz del monorepo
MOD_ORIGEN = RAIZ / "build" / "mods" / "guia-apertura-castillos"
CATALOGO = RAIZ / "content" / "mapas" / "mapas.json"
PERFIL = Path(r"C:\Users\User\Games\Age of Empires 2 DE\76561199524040890")
JUEGO = Path(r"C:\Program Files (x86)\Steam\steamapps\common\AoE2DE")
NOMBRE_MOD = "guia-apertura-castillos"
XS_COMUN = "aoe2c_guia.xs"
RMS = Path("resources") / "_common" / "random-map-scripts"
XS = Path("resources") / "_common" / "xs"
ID_STEAM_JUEGO = 813780
CLAVE_INICIO = r"Software\Microsoft\Windows\CurrentVersion\Run"
NOMBRE_INICIO = "AoE2Coaching"


@dataclass
class EstadoMapa:
    mapa: dict
    estado: str  # "instalado", "desactualizado", "no_instalado" o "sin_construir"
    imagen: Path | None


def mismos_bytes(a: Path, b: Path) -> bool:
    try:
        return a.stat().st_size == b.stat().st_size and a.read_bytes() == b.read_bytes()
    except OSError:
        return False


class Instalador:
    def __init__(self, perfil: Path = PERFIL, origen: Path = MOD_ORIGEN, catalogo: Path = CATALOGO):
        self.perfil = Path(perfil)
        self.origen = Path(origen)
        self.catalogo = Path(catalogo)

    # Rutas.
    @property
    def xs_perfil(self) -> Path:
        return self.perfil / XS

    @property
    def mod_instalado(self) -> Path:
        return self.perfil / "mods" / "local" / NOMBRE_MOD

    def mapas(self) -> list[dict]:
        try:
            return json.loads(self.catalogo.read_text(encoding="utf-8"))["mapas"]
        except (OSError, ValueError, KeyError):
            return []

    # Guía activa.
    def guia_instalada(self, guias: dict[str, dict]) -> str | None:
        """Id de la guía que cargan ahora los mapas (según el aoe2c_guia.xs del perfil)."""
        actual = self.xs_perfil / XS_COMUN
        for id_, guia in guias.items():
            if mismos_bytes(actual, self.origen / XS / guia["archivo_xs"]):
                return id_
        return None

    def activar_guia(self, guia: dict) -> str | None:
        """Copia el script de la guía como aoe2c_guia.xs. Devuelve un error o None."""
        origen = self.origen / XS / guia["archivo_xs"]
        if not origen.is_file():
            return f"falta {origen.name}: ejecuta build.py"
        try:
            for destino in (self.xs_perfil, self.mod_instalado / XS):
                destino.mkdir(parents=True, exist_ok=True)
                shutil.copy2(origen, destino / guia["archivo_xs"])
                tmp = destino / (XS_COMUN + ".tmp")
                shutil.copy2(origen, tmp)
                os.replace(tmp, destino / XS_COMUN)
        except OSError as e:
            return str(e)
        return None

    # Mapas.
    def estado_mapas(self) -> list[EstadoMapa]:
        out = []
        for m in self.mapas():
            fuente = self.origen / RMS / m["archivo"]
            instalado = self.mod_instalado / RMS / m["archivo"]
            imagen = fuente.with_suffix(".png")
            if not fuente.is_file():
                estado = "sin_construir"
            elif not instalado.is_file():
                estado = "no_instalado"
            elif mismos_bytes(fuente, instalado):
                estado = "instalado"
            else:
                estado = "desactualizado"
            out.append(EstadoMapa(m, estado, imagen if imagen.is_file() else None))
        return out

    def _archivos(self, mapa: dict) -> list[Path]:
        fuente = self.origen / RMS / mapa["archivo"]
        return [p for p in (fuente, fuente.with_suffix(".png")) if p.is_file()]

    def instalar_mapa(self, mapa: dict, guia: dict | None = None) -> str | None:
        """Copia el mapa (y su imagen) al mod local. Si el perfil aún no tiene el script
        común, instala también el de la guía `guia`."""
        archivos = self._archivos(mapa)
        if not archivos:
            return f"falta {mapa['archivo']}: ejecuta build.py"
        try:
            destino = self.mod_instalado / RMS
            destino.mkdir(parents=True, exist_ok=True)
            info = self.origen / "info.json"
            if info.is_file() and not (self.mod_instalado / "info.json").is_file():
                shutil.copy2(info, self.mod_instalado / "info.json")
            for a in archivos:
                shutil.copy2(a, destino / a.name)
        except OSError as e:
            return str(e)
        if guia and not (self.xs_perfil / XS_COMUN).is_file():
            return self.activar_guia(guia)
        return None

    def quitar_mapa(self, mapa: dict) -> str | None:
        instalado = self.mod_instalado / RMS / mapa["archivo"]
        try:
            for p in (instalado, instalado.with_suffix(".png")):
                if p.is_file():
                    p.unlink()
        except OSError as e:
            return str(e)
        return None

    def exportar_mapa(self, mapa: dict, carpeta: Path) -> str | None:
        """Guarda una copia del .rms (y su imagen) en otra carpeta."""
        archivos = self._archivos(mapa)
        if not archivos:
            return f"falta {mapa['archivo']}: ejecuta build.py"
        try:
            for a in archivos:
                shutil.copy2(a, Path(carpeta) / a.name)
        except OSError as e:
            return str(e)
        return None


# --- Juego y Windows ----------------------------------------------------------


def juego_instalado() -> bool:
    return (JUEGO / "AoE2DE_s.exe").is_file()


def juego_abierto() -> bool:
    """True si AoE2DE_s.exe se está ejecutando (lista de procesos de Windows)."""
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                        ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                        ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        foto = kernel32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
        if not foto or foto == wintypes.HANDLE(-1).value:
            return False
        try:
            e = PROCESSENTRY32W()
            e.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            ok = kernel32.Process32FirstW(foto, ctypes.byref(e))
            while ok:
                if e.szExeFile.lower() == "aoe2de_s.exe":
                    return True
                ok = kernel32.Process32NextW(foto, ctypes.byref(e))
        finally:
            kernel32.CloseHandle(foto)
    except (OSError, AttributeError):
        pass
    return False


def abrir_juego() -> None:
    """Abre AoE2 DE con Steam."""
    os.startfile(f"steam://rungameid/{ID_STEAM_JUEGO}")


def abrir_carpeta(carpeta: Path) -> None:
    if Path(carpeta).exists():
        os.startfile(str(carpeta))


def comando_inicio() -> str:
    """Orden que abre AoE2C sin consola (pythonw + overlay.py)."""
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    return f'"{pyw if pyw.is_file() else exe}" "{HERE / "overlay.py"}"'


def inicio_con_windows() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLAVE_INICIO) as k:
            winreg.QueryValueEx(k, NOMBRE_INICIO)
        return True
    except OSError:
        return False


def poner_inicio_con_windows(activo: bool) -> str | None:
    """Añade o quita AoE2C de los programas que se abren al iniciar sesión (solo este usuario)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLAVE_INICIO, 0, winreg.KEY_SET_VALUE) as k:
            if activo:
                winreg.SetValueEx(k, NOMBRE_INICIO, 0, winreg.REG_SZ, comando_inicio())
            else:
                try:
                    winreg.DeleteValue(k, NOMBRE_INICIO)
                except FileNotFoundError:
                    pass
    except OSError as e:
        return str(e)
    return None
