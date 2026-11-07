"""Dónde están el juego, el perfil del jugador y los datos de AoE2C.

- **Juego.** Se busca en las bibliotecas de Steam (libraryfolders.vdf) la que tiene
  AoE2 DE (id 813780). Por ahora solo Steam.
- **Perfil.** Las carpetas de %USERPROFILE%\\Games\\Age of Empires 2 DE\\<id>. El id no es
  fijo (con Steam es el SteamID64; "0" es el perfil sin conexión). Si solo una tiene uso
  (repeticiones, mods o datos de la guía), se elige sola; si hay varias, se pregunta.
- **Datos de AoE2C.** config.json, historial.json, los logs y el contenido descargado
  (contenido\\) van en %APPDATA%\\AoE2Coaching\\.
  La primera vez se copian los que había junto al código (versión anterior).
"""

import logging
import logging.handlers
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
ID_STEAM_JUEGO = "813780"
EXE_JUEGO = "AoE2DE_s.exe"

# --- Datos de AoE2C -------------------------------------------------------------

DATOS = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "AoE2Coaching"
CONFIG = DATOS / "config.json"
HISTORIAL = DATOS / "historial.json"
LOGS = DATOS / "logs"
LOG = LOGS / "aoe2c.log"
CONTENIDO = DATOS / "contenido"  # guías descargadas, copia del catálogo y estado de lo instalado
ANTIGUOS = HERE  # donde la versión anterior guardaba config.json e historial.json


def preparar_datos(datos: Path = DATOS, antiguos: Path = ANTIGUOS) -> list[str]:
    """Crea la carpeta de datos y copia los archivos de la versión anterior que aún no
    estén allí (no se borran los originales). Devuelve los nombres copiados."""
    copiados = []
    try:
        datos.mkdir(parents=True, exist_ok=True)
        for nombre in ("config.json", "historial.json"):
            viejo, nuevo = antiguos / nombre, datos / nombre
            if viejo.is_file() and not nuevo.exists():
                shutil.copy2(viejo, nuevo)
                copiados.append(nombre)
    except OSError as e:
        logging.getLogger("aoe2c").warning("no se pudieron preparar los datos en %s: %s", datos, e)
    return copiados


def configurar_log(archivo: Path = LOG) -> None:
    """Log en %APPDATA%\\AoE2Coaching\\logs (3 archivos de 512 KB como máximo) y los errores
    no capturados, también los de los hilos en segundo plano, van allí. El botón
    "Copiar datos para soporte" del panel copia los últimos (ver soporte.py)."""
    raiz = logging.getLogger("aoe2c")
    if raiz.handlers:
        return
    raiz.setLevel(logging.INFO)
    try:
        archivo.parent.mkdir(parents=True, exist_ok=True)
        h = logging.handlers.RotatingFileHandler(archivo, maxBytes=512 * 1024, backupCount=2, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        raiz.addHandler(h)
    except OSError:
        raiz.addHandler(logging.NullHandler())

    anterior = sys.excepthook

    def no_capturado(tipo, valor, traza):
        raiz.error("error no capturado", exc_info=(tipo, valor, traza))
        anterior(tipo, valor, traza)

    sys.excepthook = no_capturado

    import threading
    anterior_hilo = threading.excepthook

    def no_capturado_hilo(a):
        raiz.error("error no capturado en el hilo %s", a.thread.name if a.thread else "?",
                   exc_info=(a.exc_type, a.exc_value, a.exc_traceback))
        anterior_hilo(a)

    threading.excepthook = no_capturado_hilo


# --- Steam y el juego -----------------------------------------------------------


def leer_vdf(texto: str) -> dict:
    """Lee el formato de texto de Valve (libraryfolders.vdf, loginusers.vdf, .acf)."""
    fichas, i, n = [], 0, len(texto)
    while i < n:
        c = texto[i]
        if c == '"':
            j, parte = i + 1, []
            while j < n and texto[j] != '"':
                if texto[j] == "\\" and j + 1 < n:
                    j += 1
                parte.append(texto[j])
                j += 1
            fichas.append("".join(parte))
            i = j + 1
        elif c in "{}":
            fichas.append(c)
            i += 1
        elif texto.startswith("//", i):
            while i < n and texto[i] != "\n":
                i += 1
        else:
            i += 1

    def bloque(k: int) -> tuple[dict, int]:
        out = {}
        while k < len(fichas) and fichas[k] != "}":
            clave = fichas[k]
            if k + 1 >= len(fichas):
                break
            if fichas[k + 1] == "{":
                out[clave], k = bloque(k + 2)
                k += 1  # la "}"
            else:
                out[clave] = fichas[k + 1]
                k += 2
        return out, k

    return bloque(0)[0]


def carpeta_steam() -> Path | None:
    """La instalación de Steam (registro de Windows, o la ruta por defecto)."""
    candidatos = []
    try:
        import winreg
        for raiz, clave, valor in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                                   (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
                                   (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath")):
            try:
                with winreg.OpenKey(raiz, clave) as k:
                    candidatos.append(Path(winreg.QueryValueEx(k, valor)[0]))
            except OSError:
                pass
    except ImportError:
        pass
    pf86 = os.environ.get("ProgramFiles(x86)") or r"C:\Program Files (x86)"
    candidatos.append(Path(pf86) / "Steam")
    steam = next((c for c in candidatos if (c / "steamapps").is_dir()), None)
    return steam.resolve() if steam else None  # el registro la guarda en minúsculas


def bibliotecas_steam(steam: Path | None) -> list[Path]:
    if steam is None:
        return []
    libs = [steam]
    try:
        datos = leer_vdf((steam / "steamapps" / "libraryfolders.vdf").read_text(encoding="utf-8", errors="replace"))
        for lib in datos.get("libraryfolders", {}).values():
            if isinstance(lib, dict) and lib.get("path"):
                libs.append(Path(lib["path"]))
    except OSError:
        pass
    vistas, out = set(), []
    for lib in libs:
        clave = os.path.normcase(str(lib))
        if clave not in vistas:
            vistas.add(clave)
            out.append(lib)
    return out


def es_carpeta_juego(carpeta: Path | None) -> bool:
    return carpeta is not None and (Path(carpeta) / EXE_JUEGO).is_file()


def buscar_juego(steam: Path | None = None) -> Path | None:
    """La carpeta de AoE2 DE en alguna biblioteca de Steam, o None."""
    for lib in bibliotecas_steam(steam if steam is not None else carpeta_steam()):
        apps = lib / "steamapps"
        nombre = "AoE2DE"
        try:
            acf = leer_vdf((apps / f"appmanifest_{ID_STEAM_JUEGO}.acf").read_text(encoding="utf-8", errors="replace"))
            nombre = acf.get("AppState", {}).get("installdir") or nombre
        except OSError:
            pass
        carpeta = apps / "common" / nombre
        if es_carpeta_juego(carpeta):
            return carpeta
    return None


def nombres_steam(steam: Path | None = None) -> dict[str, str]:
    """SteamID64 -> nombre visible de las cuentas que iniciaron sesión en esta PC."""
    steam = steam if steam is not None else carpeta_steam()
    if steam is None:
        return {}
    try:
        datos = leer_vdf((steam / "config" / "loginusers.vdf").read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return {}
    return {sid: u.get("PersonaName") or "" for sid, u in datos.get("users", {}).items() if isinstance(u, dict)}


# --- Perfil del jugador ---------------------------------------------------------


def carpeta_perfiles() -> Path:
    return Path(os.environ.get("USERPROFILE") or Path.home()) / "Games" / "Age of Empires 2 DE"


@dataclass
class Perfil:
    carpeta: Path
    nombre: str          # nombre de la cuenta de Steam, si se conoce
    repeticiones: int    # .aoe2record en savegame
    ultimo_uso: float    # fecha del archivo más reciente (0 si no hay)

    @property
    def id(self) -> str:
        return self.carpeta.name

    @property
    def usado(self) -> bool:
        return self.ultimo_uso > 0


def _uso(carpeta: Path) -> tuple[int, float]:
    """(repeticiones, fecha más reciente) mirando solo carpetas concretas, sin recorrer
    todo el perfil. Las opciones (profile/*.aop) no cuentan: el juego las crea siempre."""
    repeticiones, ultimo = 0, 0.0
    for sub, es_uso in (("savegame", lambda n: n.endswith(".aoe2record")),
                        ("profile", lambda n: n.endswith(".xsdat")),
                        ("mods/local", lambda n: True), ("mods/subscribed", lambda n: True)):
        try:
            for e in os.scandir(carpeta / sub):
                nombre = e.name.lower()
                if es_uso(nombre):
                    if nombre.endswith(".aoe2record"):
                        repeticiones += 1
                    ultimo = max(ultimo, e.stat().st_mtime)
        except OSError:
            continue
    return repeticiones, ultimo


def buscar_perfiles(base: Path | None = None, nombres: dict[str, str] | None = None) -> list[Perfil]:
    """Las carpetas de perfil, la usada más recientemente primero."""
    base = base if base is not None else carpeta_perfiles()
    nombres = nombres if nombres is not None else nombres_steam()
    out = []
    try:
        entradas = list(os.scandir(base))
    except OSError:
        return []
    for e in entradas:
        if e.is_dir() and e.name.isdigit():
            carpeta = Path(e.path)
            if any((carpeta / s).is_dir() for s in ("profile", "savegame", "mods")):
                rep, ultimo = _uso(carpeta)
                out.append(Perfil(carpeta, nombres.get(e.name, ""), rep, ultimo))
    return sorted(out, key=lambda p: (p.ultimo_uso, p.repeticiones), reverse=True)


def elegir_perfil(perfiles: list[Perfil], guardado: str | None = None) -> tuple[Perfil | None, bool]:
    """(perfil, hay_que_preguntar). Usa el guardado si sigue existiendo; si no, el único
    con uso. Si hay varios con uso, propone el más reciente y pide preguntar."""
    if guardado:
        for p in perfiles:
            if os.path.normcase(str(p.carpeta)) == os.path.normcase(str(guardado)):
                return p, False
    if not perfiles:
        return None, False
    usados = [p for p in perfiles if p.usado]
    if len(usados) > 1:
        return usados[0], True
    if usados:
        return usados[0], False
    # Ninguno con uso (jugador nuevo): la cuenta de Steam conocida, o el que no es "0".
    return next((p for p in perfiles if p.nombre), None) or next((p for p in perfiles if p.id != "0"), perfiles[0]), False


# --- Todo junto -------------------------------------------------------------------


@dataclass
class Entorno:
    juego: Path | None
    perfil: Perfil | None
    perfiles: list[Perfil]
    preguntar: bool  # hay varios perfiles con uso y ninguno elegido


def resolver(config: dict) -> Entorno:
    """Carpetas del juego y del perfil: las elegidas en el panel (config) si siguen
    valiendo; si no, las que se encuentran solas."""
    steam = carpeta_steam()
    juego = Path(config["juego"]) if es_carpeta_juego(config.get("juego") and Path(config["juego"])) else None
    juego = juego or buscar_juego(steam)
    perfiles = buscar_perfiles(nombres=nombres_steam(steam))
    perfil, preguntar = elegir_perfil(perfiles, config.get("perfil"))
    return Entorno(juego, perfil, perfiles, preguntar)


def para_scripts() -> tuple[Path, Path]:
    """(juego, perfil) para los scripts de desarrollo (build.py, tools/), con las mismas
    reglas que la app y el perfil elegido en el panel. Si algo falta, devuelve una ruta
    que no existe, con un nombre que lo explica, para que el error lo diga."""
    import json
    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        config = {}
    e = resolver(config if isinstance(config, dict) else {})
    juego = e.juego or Path("<no se encontró AoE2 DE en las bibliotecas de Steam>")
    perfil = e.perfil.carpeta if e.perfil else carpeta_perfiles() / "<no se encontró la carpeta del perfil>"
    return juego, perfil
