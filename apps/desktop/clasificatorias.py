"""Partidas clasificatorias (ranked) del historial, sacadas de las repeticiones.

El historial de prácticas (historial.py) se escribe mientras se juega con una guía. Las
clasificatorias no usan guía: se leen de las repeticiones multijugador de savegame, cuya
cabecera (cabecera.py) dice si la partida es clasificatoria, el mapa y quién juega con
qué civilización.

Leer una cabecera cuesta unos 60 ms, así que lo leído se guarda en
clasificatorias.json (también las repeticiones que no son clasificatorias, como None)
y solo se leen las nuevas. Las de un jugador ("SP Replay...") ni se abren. Una
repetición que aún se está escribiendo (partida en curso) se deja para más tarde.

Las de Partida rápida no son clasificatorias (la cabecera lo dice) y no entran. El
resultado y el elo no están en la repetición: salen de la API oficial (completar()).
"""

import json
import os
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

import cabecera as CB
import estadisticas as E
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


# --- Resultado y elo, de la API oficial -----------------------------------------
#
# getRecentMatchHistory da las últimas partidas de un jugador con, por jugador, si ganó
# (outcome 1) o perdió (0) y su elo antes y después. Cada partida se empareja con su
# repetición por los jugadores y la hora de inicio (la repetición empieza unos segundos
# después). Lo encontrado se guarda en clasificatorias.json: "resultado" (victoria o
# derrota del jugador) y "elo" ({perfil: [antes, después]}). La API solo guarda las
# últimas partidas, así que pasados DIAS_API ya no se pregunta por una partida.

URL_HISTORIAL = "https://aoe-api.worldsedgelink.com/community/leaderboard/getRecentMatchHistory"
DIAS_API = 14
MARGEN_INICIO = 300  # segundos entre el inicio según la API y la hora en el nombre de la repetición
ESPERA_API = 300.0  # segundos entre preguntas por partidas que aún no salen
_ultima_peticion = -ESPERA_API


def url_historial(perfil: int) -> str:
    return f"{URL_HISTORIAL}?{urllib.parse.urlencode({'title': 'age2', 'profile_ids': f'[{int(perfil)}]'})}"


def leer_historial(respuesta: object) -> list[dict]:
    """Las partidas de una respuesta de getRecentMatchHistory: {"inicio", "jugadores":
    {perfil: (outcome, antes, después)}}. Las entradas raras se saltan."""
    if not isinstance(respuesta, dict):
        raise E.EstadisticasError("respuesta inesperada: no es un objeto")
    resultado = respuesta.get("result")
    if not isinstance(resultado, dict) or resultado.get("code") != 0:
        mensaje = resultado.get("message") if isinstance(resultado, dict) else None
        raise E.EstadisticasError(f"la API respondió con un error: {mensaje or resultado!r}")
    partidas = respuesta.get("matchHistoryStats")
    if not isinstance(partidas, list):
        raise E.EstadisticasError("respuesta inesperada: matchHistoryStats no es una lista")
    out = []
    for m in partidas:
        try:
            jugadores = {}
            for x in m["matchhistorymember"]:
                jugadores[int(x["profile_id"])] = (int(x["outcome"]), int(x["oldrating"]), int(x["newrating"]))
            out.append({"inicio": int(m["startgametime"]), "jugadores": jugadores})
        except (KeyError, TypeError, ValueError):
            continue
    return out


def emparejar(registro: dict, partidas: list[dict]) -> dict | None:
    """La partida de la API con los mismos jugadores y la hora de inicio más cercana."""
    try:
        inicio = datetime.fromisoformat(registro["fecha"]).timestamp()
    except (KeyError, ValueError):
        return None
    perfiles = {j["perfil"] for j in registro["jugadores"] if j["perfil"] > 0}
    candidatas = [m for m in partidas if set(m["jugadores"]) == perfiles and abs(m["inicio"] - inicio) <= MARGEN_INICIO]
    return min(candidatas, key=lambda m: abs(m["inicio"] - inicio), default=None)


def poner_resultado(registro: dict, partida: dict, yo: int) -> bool:
    """Anota el elo de todos y el resultado del jugador. False si no está en la partida."""
    if yo not in partida["jugadores"]:
        return False
    registro["elo"] = {str(p): [antes, despues] for p, (_, antes, despues) in partida["jugadores"].items()}
    outcome = partida["jugadores"][yo][0]
    registro["resultado"] = "victoria" if outcome == 1 else "derrota" if outcome == 0 else None
    return True


def pendientes(registros: list[dict], ahora: float) -> list[dict]:
    """Ranked sin resultado aún y lo bastante recientes para que la API las tenga."""
    out = []
    for r in registros:
        if "resultado" in r:
            continue
        try:
            if ahora - datetime.fromisoformat(r["fecha"]).timestamp() <= DIAS_API * 86400:
                out.append(r)
        except (KeyError, ValueError):
            continue
    return out


def completar(registros: list[dict], yo: int | None, archivo: Path | None = ARCHIVO,
              pedir=E._pedir_url, ahora=time.time, forzar: bool = False) -> bool:
    """Pide a la API el resultado y el elo de las ranked que no los tienen y los guarda.
    Devuelve True si anotó alguno. Sin conexión o con un error de la API, no hace nada
    (se vuelve a probar pasados ESPERA_API segundos)."""
    global _ultima_peticion
    if not yo:
        return False
    faltan = pendientes(registros, ahora())
    if not faltan or (not forzar and time.monotonic() - _ultima_peticion < ESPERA_API):
        return False
    _ultima_peticion = time.monotonic()
    try:
        partidas = leer_historial(json.loads(pedir(url_historial(yo))))
    except (E.EstadisticasError, ValueError):
        return False
    hechas = [r for r in faltan if (m := emparejar(r, partidas)) is not None and poner_resultado(r, m, yo)]
    if not hechas:
        return False
    vistas = _cargar(archivo)
    for r in hechas:
        if vistas.get(r["id"]):
            vistas[r["id"]].update(resultado=r["resultado"], elo=r["elo"])
    _guardar(archivo, vistas)
    return True


def elo_de(registro: dict, perfil: int | None) -> tuple[int, int] | None:
    """(antes, después) del jugador, si se sabe."""
    par = (registro.get("elo") or {}).get(str(perfil))
    return (par[0], par[1]) if isinstance(par, list) and len(par) == 2 else None


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
