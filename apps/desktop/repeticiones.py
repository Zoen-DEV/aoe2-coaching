"""Repeticiones (.aoe2record) de las partidas del historial.

El juego deja una repetición por partida en savegame del perfil, con la hora de inicio
en el nombre: "SP Replay v101.103.57257.0 @2026.11.06 123235.aoe2record". Una partida
del historial va con la repetición que empezó antes que ella (o a la vez) y que se
siguió escribiendo al menos hasta su último dato. Así se descartan las partidas
reiniciadas a los pocos segundos, que también dejan repetición.

El nombre encontrado se guarda en el registro ("repeticion") para no buscar cada vez.

AoE2 DE no carga una repetición desde fuera. Probado el 2026-11-12 con el juego real
(v101.103.57257.0): lanzado con Steam y la ruta del .aoe2record como argumento, y con
la opción GAM de su tabla de arranque ("GAM=ruta", "GAM=nombre" y "GAM ruta"), recibe
el argumento pero se queda en el menú principal sin abrir el archivo. Por eso el
historial no tiene un botón "Ver repetición": solo "Carpeta", que abre el Explorador
con la repetición seleccionada.
"""

import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

MARGEN = 15  # segundos de tolerancia entre los relojes del juego, del .xsdat y de la repetición
MAX_ANTES = 12 * 3600  # una repetición que empezó más de 12 h antes no es de esa partida
HORA_EN_NOMBRE = re.compile(r"@(\d{4})\.(\d{2})\.(\d{2}) (\d{2})(\d{2})(\d{2})")

_perfil: Path | None = None


def poner_perfil(carpeta: Path | None) -> None:
    """Carpeta del perfil en uso (la que elige rutas.py o el panel)."""
    global _perfil
    _perfil = Path(carpeta) if carpeta else None


def carpeta() -> Path | None:
    return _perfil / "savegame" if _perfil else None


def inicio_por_nombre(nombre: str) -> float | None:
    m = HORA_EN_NOMBRE.search(nombre)
    if not m:
        return None
    try:
        return datetime(*map(int, m.groups())).timestamp()
    except ValueError:
        return None


def _ventana(registro: dict) -> tuple[float, float] | None:
    """(inicio, último dato) de la partida, en segundos desde 1970."""
    try:
        inicio = datetime.fromisoformat(registro["fecha"]).timestamp()
    except (KeyError, ValueError):
        return None
    fin = registro.get("escritura") or inicio
    return min(inicio, fin), fin


def buscar(registro: dict, savegame: Path | None = None) -> Path | None:
    """La repetición de la partida, o None si no está."""
    savegame = savegame or carpeta()
    ventana = _ventana(registro)
    if savegame is None or ventana is None:
        return None
    inicio, fin = ventana
    mejor, mejor_inicio = None, None
    try:
        entradas = list(os.scandir(savegame))
    except OSError:
        return None
    for e in entradas:
        if not e.name.lower().endswith(".aoe2record"):
            continue
        empieza = inicio_por_nombre(e.name)
        try:
            st = e.stat()
        except OSError:
            continue
        if empieza is None:
            empieza = st.st_ctime
        if not (inicio - MAX_ANTES <= empieza <= inicio + MARGEN):
            continue
        if st.st_mtime < fin - MARGEN:
            continue  # terminó antes del último dato: otra partida (o una reiniciada)
        if mejor_inicio is None or empieza > mejor_inicio:
            mejor, mejor_inicio = Path(e.path), empieza
    return mejor


def de_registro(registro: dict, savegame: Path | None = None) -> Path | None:
    """La repetición vinculada a la partida. La busca si aún no la tiene y guarda el
    nombre en el registro (el que llama guarda el historial si cambió)."""
    savegame = savegame or carpeta()
    if savegame is None:
        return None
    nombre = registro.get("repeticion")
    if nombre:
        ruta = savegame / nombre
        if ruta.is_file():
            return ruta
    ruta = buscar(registro, savegame)
    if ruta is not None:
        registro["repeticion"] = ruta.name
    elif nombre:
        registro.pop("repeticion", None)  # la borraron o es de otro perfil
    return ruta


def mostrar_en_carpeta(ruta: Path) -> None:
    """Abre el Explorador con la repetición seleccionada."""
    try:
        subprocess.Popen(["explorer", "/select,", str(ruta)])
    except OSError:
        os.startfile(str(ruta.parent))
