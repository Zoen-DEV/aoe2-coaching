"""Partidas clasificatorias (ranked) del historial, sacadas de las repeticiones.

El historial de prácticas (historial.py) se escribe mientras se juega con una guía. Las
clasificatorias no usan guía: se leen de las repeticiones multijugador de savegame, cuya
cabecera (cabecera.py) dice si la partida es clasificatoria, el mapa y quién juega con
qué civilización.

Leer una cabecera cuesta unos 60 ms, así que lo leído se guarda en
clasificatorias.json (también las repeticiones que no son clasificatorias, como None)
y solo se leen las nuevas. Las de un jugador ("SP Replay...") ni se abren. Una
repetición que aún se está escribiendo (partida en curso) se deja para más tarde.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

import cabecera as CB
import repeticiones
import rutas

ARCHIVO = rutas.DATOS / "clasificatorias.json"
EN_CURSO = 45.0  # segundos sin escribirse para dar la repetición por terminada (como vigilante.py)
MODOS_CORTOS = {"rm": "RM", "ew": "EW", "dm": "DM"}


def _fecha(ruta: Path, st: os.stat_result) -> str:
    inicio = repeticiones.inicio_por_nombre(ruta.name) or st.st_ctime
    return datetime.fromtimestamp(inicio).isoformat(timespec="seconds")


def registro(ruta: Path, cab: CB.Cabecera, st: os.stat_result) -> dict:
    """Lo que el historial guarda de una partida clasificatoria."""
    return {
        "id": ruta.name,
        "tipo": "ranked",
        "fecha": _fecha(ruta, st),
        "mapa": cab.mapa,
        "modo": cab.modo,
        "jugadores": [{"nombre": j.nombre, "perfil": j.perfil, "equipo": j.equipo, "color": j.color, "civ": j.civ,
                       "numero": j.numero} for j in cab.jugadores],
    }


def _cargar(archivo: Path | None) -> dict:
    if not archivo:
        return {}
    try:
        datos = json.loads(archivo.read_text(encoding="utf-8"))
        vistas = datos.get("repeticiones", {})
        return vistas if isinstance(vistas, dict) else {}
    except (OSError, ValueError, AttributeError):
        return {}


def _guardar(archivo: Path | None, vistas: dict):
    if not archivo:
        return
    tmp = archivo.with_suffix(".tmp")
    try:
        archivo.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps({"version": 1, "repeticiones": vistas}, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, archivo)
    except OSError:
        pass


def leer(savegame: Path | None = None, archivo: Path | None = ARCHIVO, ahora=time.time) -> list[dict]:
    """Las partidas clasificatorias de la carpeta, de la más antigua a la más reciente."""
    savegame = savegame or repeticiones.carpeta()
    if savegame is None:
        return []
    try:
        entradas = [e for e in os.scandir(savegame) if e.name.lower().endswith(".aoe2record")]
    except OSError:
        return []
    vistas = _cargar(archivo)
    cambios = False
    out = []
    for e in entradas:
        if e.name in vistas:
            if vistas[e.name]:
                out.append(vistas[e.name])
            continue
        if e.name.startswith("SP Replay"):
            continue  # de un jugador: nunca es clasificatoria
        try:
            st = e.stat()
        except OSError:
            continue
        if ahora() - st.st_mtime < EN_CURSO:
            continue  # partida en curso: su cabecera puede no estar entera
        try:
            cab = CB.leer_archivo(Path(e.path))
        except CB.CabeceraError:
            vistas[e.name] = None
            cambios = True
            continue
        reg = registro(Path(e.path), cab, st) if cab.multijugador and cab.clasificatoria else None
        vistas[e.name] = reg
        cambios = True
        if reg:
            out.append(reg)
    presentes = {e.name for e in entradas}
    if any(n not in presentes for n in vistas):
        vistas = {n: v for n, v in vistas.items() if n in presentes}  # repeticiones borradas
        cambios = True
    if cambios:
        _guardar(archivo, vistas)
    out.sort(key=lambda r: r["fecha"])
    return out


# --- Lo que muestra el historial ----------------------------------------------


def perfil_comun(registros: list[dict]) -> int | None:
    """El perfil que está en todas las partidas (el del jugador), si son al menos dos."""
    if len(registros) < 2:
        return None
    comunes = None
    for r in registros:
        perfiles = {j["perfil"] for j in r["jugadores"] if j["perfil"] > 0}
        comunes = perfiles if comunes is None else comunes & perfiles
    return next(iter(comunes)) if comunes and len(comunes) == 1 else None


def equipos(registro: dict, yo: int | None) -> list[list[dict]]:
    """Jugadores por equipo, el propio primero. Sin equipo ("-"), cada uno va solo."""
    grupos: dict[int, list[dict]] = {}
    for j in registro["jugadores"]:
        clave = 100 + j["numero"] if j["equipo"] == CB.SIN_EQUIPO else j["equipo"]
        grupos.setdefault(clave, []).append(j)
    lista = [grupos[k] for k in sorted(grupos)]
    return sorted(lista, key=lambda e: not any(j["perfil"] == yo for j in e))


def titulo(registro: dict) -> str:
    """«RM 1v1», «RM 2v2»..."""
    formato = "v".join(str(len(e)) for e in equipos(registro, None))
    corto = MODOS_CORTOS.get(registro.get("modo") or "")
    return f"{corto} {formato}" if corto else formato


def yo_en(registro: dict, yo: int | None) -> dict | None:
    return next((j for j in registro["jugadores"] if j["perfil"] == yo), None) if yo else None


def rivales(registro: dict, yo: int | None) -> list[dict]:
    """Los jugadores de los otros equipos (o todos menos el primero, si no se sabe quién es uno)."""
    grupos = equipos(registro, yo)
    if yo_en(registro, yo) is None:
        return [j for e in grupos[1:] for j in e]
    return [j for e in grupos if not any(x["perfil"] == yo for x in e) for j in e]


def nombre_repeticion(registro: dict) -> str | None:
    """Nombre de la repetición sin «.aoe2record», tal como lo lista el juego."""
    nombre = registro.get("repeticion") or (registro["id"] if registro.get("tipo") == "ranked" else None)
    return nombre.removesuffix(".aoe2record") if nombre else None


def perfil_de_config(config: dict) -> int | None:
    """El ID de perfil propio: el elegido en Ajustes o, si no, el deducido."""
    for clave in ("match_perfil", "match_perfil_detectado"):
        v = config.get(clave)
        if isinstance(v, int) and not isinstance(v, bool) and v > 0:
            return v
    return None
