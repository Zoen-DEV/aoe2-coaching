"""Soporte: los datos que se pegan al pedir ayuda y el acceso al Discord.

Sin servidor, la única forma de enterarse de un error es que el jugador lo cuente. El
botón "Copiar datos para soporte" del panel junta lo que hace falta para entenderlo:
versión de la app y de Windows, si encontró el juego y el perfil, el contenido
instalado y los últimos avisos y errores del log.

Antes de copiarlo se quitan los datos personales: la carpeta del usuario de Windows
queda como %USERPROFILE% y los SteamID como <steamid>.
"""

import os
import platform
import re
import sys
from pathlib import Path

import rutas
from version import VERSION

# Invitación al Discord de AoE2 Coaching (canal de errores). Vacía hasta crear el servidor
# (paso 9 del plan): entonces el botón del panel queda desactivado.
DISCORD = ""

LINEAS_LOG = 30  # avisos y errores (con sus trazas) que se copian
STEAMID = re.compile(r"\b7656\d{13}\b")
INICIO_LINEA = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} (\w+) ")


def anonimizar(texto: str) -> str:
    usuario = os.environ.get("USERPROFILE")
    if usuario:
        texto = re.sub(re.escape(usuario), "%USERPROFILE%", texto, flags=re.IGNORECASE)
        texto = re.sub(re.escape(usuario.replace("\\", "/")), "%USERPROFILE%", texto, flags=re.IGNORECASE)
    return STEAMID.sub("<steamid>", texto)


def ultimos_errores(log: Path = rutas.LOG, n: int = LINEAS_LOG) -> list[str]:
    """Las últimas n líneas de avisos y errores del log (con las líneas de sus trazas)."""
    archivos = [log.with_name(f"{log.name}.{i}") for i in (2, 1)] + [log]  # del más viejo al actual
    out: list[str] = []
    for archivo in archivos:
        try:
            lineas = archivo.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        dentro = False
        for linea in lineas:
            m = INICIO_LINEA.match(linea)
            if m:
                dentro = m.group(1) in ("WARNING", "ERROR", "CRITICAL")
            if dentro:
                out.append(linea)
    return out[-n:]


def version_windows() -> str:
    v = sys.getwindowsversion() if hasattr(sys, "getwindowsversion") else None
    if v is None:
        return platform.platform()
    nombre = "11" if v.major == 10 and v.build >= 22000 else str(v.major)
    return f"Windows {nombre} (build {v.build}, {platform.machine()})"


def _contenido(instalador) -> list[str]:
    out = []
    try:
        guias = instalador.guias()
        out.append("Guías: " + (", ".join(f"{i} {instalador.version_guia(i) or '?'}" for i in sorted(guias))
                                or "ninguna"))
    except Exception as e:  # el informe sale aunque algo falle
        out.append(f"Guías: error ({e})")
    try:
        mapas = instalador.estado_mapas()
        out.append("Mapas: " + (", ".join(f"{m.mapa.get('id', '?')} {m.estado}" for m in mapas) or "ninguno"))
    except Exception as e:
        out.append(f"Mapas: error ({e})")
    try:
        mods = instalador.estado_mods()
        out.append("Mods: " + (", ".join(f"{m.elemento.id} {m.version or '-'} {m.estado}/{m.activacion}"
                                         for m in mods) or "ninguno"))
    except Exception as e:
        out.append(f"Mods: error ({e})")
    catalogo = getattr(instalador, "catalogo", None)
    out.append(f"Catálogo: {'cargado' if catalogo is not None else 'sin cargar'}")
    return out


def datos(config: dict, instalador=None, juego_abierto: bool | None = None, log: Path = rutas.LOG) -> str:
    """El texto que copia el botón "Copiar datos para soporte"."""
    empaquetada = getattr(sys, "frozen", False)
    lineas = [
        f"AoE2 Coaching v{VERSION} ({'instalada' if empaquetada else 'desde el código'})",
        version_windows(),
        f"Python {platform.python_version()}",
        f"Idioma: {config.get('idioma')}",
    ]
    if instalador is not None:
        lineas.append(f"Juego: {'encontrado' if instalador.juego else 'no encontrado'}"
                      + ("" if juego_abierto is None else f" ({'abierto' if juego_abierto else 'cerrado'})"))
        perfil = instalador.perfil
        lineas.append("Perfil: " + ("no encontrado" if perfil is None
                                    else "sin conexión (0)" if perfil.name == "0" else "Steam"))
        lineas += _contenido(instalador)
    errores = ultimos_errores(log)
    lineas.append("")
    lineas.append(f"Últimos avisos y errores ({len(errores)}):" if errores else "Sin avisos ni errores en el log.")
    lineas += errores
    return anonimizar("\n".join(lineas))
