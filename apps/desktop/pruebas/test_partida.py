"""Pruebas de la partida en curso (panel Match Info), sin red ni ventanas.

    py pruebas/test_partida.py

- La cabecera de las repeticiones (cabecera.py), con repeticiones de prueba y, si hay un
  perfil del juego en este equipo, con sus repeticiones reales.
- Las estadísticas (estadisticas.py) con las respuestas reales de la API guardadas en
  pruebas/datos/worldsedgelink (sacadas el 2026-11-12): caché, esperas y validación.
- El modelo (partida_en_curso.py): 1v1, partida por equipos y jugadores sin rating.
- El vigilante (vigilante.py): empieza y acaba partidas mirando una carpeta savegame.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

OVERLAY = Path(__file__).resolve().parent.parent  # apps/desktop
sys.path.insert(0, str(OVERLAY))

import cabecera as CB  # noqa: E402
import estadisticas as E  # noqa: E402
import partida_en_curso as P  # noqa: E402
import vigilante as V  # noqa: E402

DATOS = Path(__file__).resolve().parent / "datos" / "worldsedgelink"
HERA, KVOTHE = 199325, 1943128  # la RM 1v1 en Arabia de historial_reciente.json
SIN_RM_1V1 = 10191122           # no tiene entrada en RM 1v1 (sí en equipos)


def comprobar(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("  ok ·", msg)


def leer_json(nombre: str) -> object:
    return json.loads((DATOS / nombre).read_text(encoding="utf-8"))


def fichas_9() -> dict[int, E.Ficha]:
    return E.leer_fichas(leer_json("estadisticas_9_jugadores.json"))


def jugadores_de(n_partida: int) -> list[CB.JugadorCabecera]:
    """Los jugadores de una partida real de historial_reciente.json, como los daría su cabecera."""
    m = leer_json("historial_reciente.json")["matchHistoryStats"][n_partida]
    nombres = {p["profile_id"]: p["alias"] for p in leer_json("historial_reciente.json")["profiles"]}
    return [CB.JugadorCabecera(i + 1, nombres.get(r["profile_id"], "?"), r["profile_id"], r["teamid"] + 2, i,
                               r["civilization_id"]) for i, r in enumerate(m["matchhistoryreportresults"])]


class ProveedorFalso:
    """Lee los fixtures; cuenta las peticiones y puede fallar a propósito."""

    def __init__(self):
        self.pedidos: list[list[int]] = []
        self.fallo: E.EstadisticasError | None = None
        self.todas = fichas_9()

    def fichas(self, perfiles):
        self.pedidos.append(list(perfiles))
        if self.fallo:
            raise self.fallo
        return {p: self.todas[p] for p in perfiles if p in self.todas}


class Reloj:
    def __init__(self, t: float = 1_800_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


# --- Cabecera ----------------------------------------------------------------------


def test_cabecera(tmp: Path):
    print("cabecera de la repetición")
    js = jugadores_de(0)
    ruta = CB.escribir_prueba(tmp / "cab" / "MP Replay 1v1.aoe2record", js, mapa="Arabia")
    c = CB.leer_archivo(ruta)
    comprobar(c.clasificatoria and c.multijugador and c.modo == "rm" and c.mapa == "Arabia" and c.mapa_id == 9,
              "1v1 clasificatoria en Arabia")
    comprobar([(j.perfil, j.equipo, j.civ) for j in c.jugadores] == [(j.perfil, j.equipo, j.civ) for j in js],
              "perfiles, equipos y civilizaciones de los dos jugadores")
    c = CB.leer_archivo(CB.escribir_prueba(tmp / "cab" / "4v4.aoe2record", jugadores_de(1), clasificatoria=False,
                                           mapa="Selva negra", mapa_id=12))
    comprobar(len(c.jugadores) == 8 and not c.clasificatoria and c.mapa == "Selva negra", "4v4 no clasificatoria")
    datos = ruta.read_bytes()
    for nombre, trozo, esperado in (("a medio escribir", datos[:40], "aún no"), ("vacía", b"", "corto"),
                                    ("dañada", datos[:8] + b"\x00" * (len(datos) - 8), "dañada")):
        try:
            CB.leer(trozo)
            comprobar(False, f"repetición {nombre}")
        except CB.CabeceraError as e:
            comprobar(esperado in str(e), f"repetición {nombre}: {e}")
    otro = CB.escribir_prueba(tmp / "cab" / "ew.aoe2record", js, tipo=13)
    comprobar(CB.leer_archivo(otro).modo == "ew", "guerras imperiales")


def test_repeticiones_reales():
    """Las repeticiones del perfil de este equipo, si hay (en GitHub Actions no)."""
    import rutas
    reales = V.repeticiones(rutas.para_scripts()[1] / "savegame")  # ruta inexistente si no hay perfil
    if not reales:
        print("repeticiones reales: no hay perfil del juego en este equipo, se salta")
        return
    print(f"repeticiones reales ({len(reales)})")
    errores = []
    for r in reales:
        try:
            CB.leer_archivo(r)
        except CB.CabeceraError as e:
            errores.append(f"{r.name}: {e}")
    comprobar(not errores, f"se leen todas las cabeceras {errores[:3]}")


# --- Estadísticas ------------------------------------------------------------------


def test_fichas():
    print("respuesta de la API oficial")
    f = fichas_9()
    comprobar(len(f) == 9, "nueve jugadores en una sola respuesta")
    hera = f[HERA].ratings[E.LEADERBOARDS["rm_1v1"]]
    comprobar((hera.rating, hera.rango, hera.maximo, hera.victorias, hera.derrotas) == (2923, 9, 3108, 5596, 1790),
              "elo, puesto, máximo y victorias de Hera en RM 1v1")
    comprobar(f[HERA].pais == "ca" and f[HERA].alias == "VIT | Hera", "país y nombre")
    comprobar(E.LEADERBOARDS["rm_1v1"] not in f[SIN_RM_1V1].ratings, "un jugador sin RM 1v1")
    sin_puesto = f[1104952].ratings[E.LEADERBOARDS["rm_1v1"]]
    comprobar(sin_puesto.rango is None and sin_puesto.maximo is None, "puesto -1 y máximo 0 -> sin dato")
    malas = [
        ("no es un objeto", []),
        ("error de la API", {"result": {"code": 7, "message": "UNREGISTERED"}}),
        ("rating como texto", {"result": {"code": 0}, "statGroups": [{"id": 1, "members": [
            {"profile_id": 1, "alias": "a", "country": "es"}]}], "leaderboardStats": [
            {"statgroup_id": 1, "leaderboard_id": 3, "rating": "1200", "rank": 1, "highestrating": 1, "wins": 1,
             "losses": 1}]}),
        ("sin statGroups", {"result": {"code": 0}}),
    ]
    for nombre, r in malas:
        try:
            E.leer_fichas(r)
            comprobar(False, nombre)
        except E.EstadisticasError as e:
            comprobar(True, f"{nombre}: {e}")
    url = E.ApiOficial.url([HERA, KVOTHE])
    comprobar(url == E.URL_ESTADISTICAS + "?title=age2&profile_ids=%5B199325%2C1943128%5D", "URL de la petición")
    api = E.ApiOficial(lambda u: (DATOS / "estadisticas_9_jugadores.json").read_bytes())
    comprobar(api.fichas([HERA])[HERA].alias == "VIT | Hera", "ApiOficial lee la respuesta")
    try:
        E.ApiOficial(lambda u: b"<html>").fichas([HERA])
        comprobar(False, "HTML en vez de JSON")
    except E.EstadisticasError as e:
        comprobar(not e.reintentable, f"HTML en vez de JSON: {e}")


def test_cache_y_esperas():
    print("caché y esperas")
    prov, reloj = ProveedorFalso(), Reloj(0)
    est = E.Estadisticas(prov, reloj)
    est.fichas([HERA, KVOTHE])
    est.fichas([HERA, KVOTHE])
    comprobar(len(prov.pedidos) == 1, "la segunda vez sale de la caché")
    est.fichas([HERA, SIN_RM_1V1, 999])
    comprobar(prov.pedidos[-1] == [SIN_RM_1V1, 999], "solo se piden los que faltan")
    est.fichas([999])
    comprobar(len(prov.pedidos) == 2, "un perfil que la API no conoce también se guarda")
    reloj.t = E.CADUCIDAD + 1
    est.fichas([HERA])
    comprobar(prov.pedidos[-1] == [HERA], "a los 10 minutos se vuelve a pedir")

    prov.fallo = E.EstadisticasError("la API respondió 429", reintentable=True)
    n = len(prov.pedidos)
    for intento, espera in enumerate((30, 60, 120)):
        try:
            est.fichas([5755296])
        except E.EstadisticasError:
            pass
        comprobar(len(prov.pedidos) == n + intento + 1 and est.no_antes_de == reloj.t + espera,
                  f"429: espera {espera} s")
        try:
            est.fichas([5755296])
        except E.EstadisticasError:
            pass
        comprobar(len(prov.pedidos) == n + intento + 1, "durante la espera no se pide nada")
        reloj.t += espera
    prov.fallo = None
    comprobar(5755296 in est.fichas([5755296]), "pasada la espera, vuelve a funcionar")


# --- Modelo ------------------------------------------------------------------------


def test_modelo():
    print("modelo de la partida")
    cab = CB.Cabecera(68.9, 0, 9, "Arabia", True, True, jugadores_de(0))
    p = P.armar(cab, "uno", HERA, fichas_9())
    comprobar(p.leaderboard == "rm_1v1" and p.es_1v1 and p.titulo == "RM 1v1", "RM 1v1 usa el leaderboard de 1v1")
    comprobar(p.yo.rating == 2923 and p.rival.rating == 2014 and p.diferencia == 2014 - 2923,
              "diferencia de elo del rival: −909")
    comprobar(p.rival.pais == "ar" and p.rival.rango == 702 and round(p.rival.winrate, 3) == 0.504,
              "país, puesto y winrate del rival")
    sin_datos = P.armar(cab, "uno", HERA)
    comprobar(all(j.rating is None for j in sin_datos.jugadores) and sin_datos.diferencia is None,
              "sin fichas (buscando datos), nadie tiene rating")

    js = jugadores_de(0)
    js[1] = CB.JugadorCabecera(2, "No conozco el honor", SIN_RM_1V1, 3, 1, 4)
    p = P.armar(CB.Cabecera(68.9, 0, 9, "Arabia", True, True, js), "uno", HERA, fichas_9())
    comprobar(p.rival.rating is None and p.diferencia is None, "rival sin RM 1v1: sin rating y sin diferencia")
    comprobar(P.armar(cab, "uno", None, fichas_9()).diferencia is None, "sin perfil propio no hay diferencia")

    cab = CB.Cabecera(68.9, 0, 12, "Selva negra", True, True, jugadores_de(1))
    p = P.armar(cab, "eq", HERA, fichas_9())
    comprobar(p.leaderboard == "rm_team" and p.titulo == "RM 4v4" and len(p.equipos) == 2, "4v4: leaderboard de equipos")
    comprobar(p.yo.rating == 1640, "el elo del jugador es el de equipos, no el de 1v1")
    equipo = next(e for e in p.equipos if any(j.perfil == HERA for j in e.jugadores))
    ratings = [j.rating for j in equipo.jugadores]
    comprobar(equipo.promedio == round(sum(ratings) / 4), f"elo medio del equipo: {equipo.promedio}")
    js = jugadores_de(1)
    js[0] = CB.JugadorCabecera(1, "Nuevo", 42, js[0].equipo, 0, 1)  # la API no lo conoce
    p = P.armar(CB.Cabecera(68.9, 0, 12, "", True, True, js), "eq", HERA, fichas_9())
    e = next(e for e in p.equipos if any(j.perfil == 42 for j in e.jugadores))
    con = [j.rating for j in e.jugadores if j.rating is not None]
    comprobar(len(con) == 3 and e.promedio == round(sum(con) / 3), "el medio no cuenta al que no tiene rating")
    libres = [CB.JugadorCabecera(n, f"j{n}", n, CB.SIN_EQUIPO, n - 1, 1) for n in (1, 2, 3)]
    p = P.armar(CB.Cabecera(68.9, 0, 9, "", True, True, libres), "ffa", None)
    comprobar(len(p.equipos) == 3 and p.leaderboard == "rm_team" and p.formato == "1v1v1", "todos contra todos")
    comprobar(P.armar(CB.Cabecera(68.9, 9, 9, "", True, True, jugadores_de(0)), "x", HERA, fichas_9())
              .jugadores[0].rating is None, "un tipo de partida sin leaderboard: sin rating")


# --- Vigilante -----------------------------------------------------------------------


def test_vigilante(tmp: Path):
    print("vigilante de partidas")
    carpeta = tmp / "savegame"
    carpeta.mkdir()
    reloj, prov = Reloj(), ProveedorFalso()
    est = E.Estadisticas(prov, reloj)
    v = V.Vigilante(lambda: carpeta, est, lambda: HERA, ahora=reloj, en_segundo_plano=lambda f: f())
    avisos = []
    v.al_empezar = lambda p: avisos.append(("empieza", p.id))
    v.al_terminar = lambda: avisos.append(("acaba",))

    def repeticion(nombre: str, edad: float = 0, **kw) -> Path:
        r = CB.escribir_prueba(carpeta / nombre, kw.pop("jugadores", jugadores_de(0)), **kw)
        os.utime(r, (reloj.t - edad, reloj.t - edad))
        return r

    v.actualizar()
    comprobar(v.estado == V.OCULTO and not avisos, "sin repeticiones no hay partida")
    repeticion("SP vieja.aoe2record", edad=3600)
    v.actualizar()
    comprobar(v.estado == V.OCULTO, "una repetición vieja no es una partida en curso")
    repeticion("MP sala.aoe2record", clasificatoria=False)
    v.actualizar()
    comprobar(v.estado == V.OCULTO and not avisos, "una partida no clasificatoria no se muestra")
    reloj.t += 5
    r = repeticion("MP ranked.aoe2record")
    v.actualizar()
    comprobar(avisos == [("empieza", r.name)] and v.estado == V.CARGADO, "empieza la clasificatoria y carga el elo")
    comprobar(v.partida.yo.rating == 2923 and v.partida.diferencia == -909, "con el elo de cada uno")
    pedidos = len(prov.pedidos)
    for _ in range(5):
        reloj.t += 10
        os.utime(r, (reloj.t, reloj.t))  # el juego sigue escribiendo
        v.actualizar()
    comprobar(len(prov.pedidos) == pedidos and len(avisos) == 1, "mientras se juega no se pide nada más")
    reloj.t += V.SIN_ESCRITURA + 1
    v.actualizar()
    comprobar(avisos[-1] == ("acaba",) and v.estado == V.OCULTO and v.partida is None,
              "la repetición deja de crecer: la partida acabó")
    os.utime(r, (reloj.t - 10, reloj.t - 10))
    v.actualizar()
    comprobar(len(avisos) == 2, "la misma repetición no vuelve a empezar")

    # Una nueva sin que la anterior se haya parado: acaba una y empieza la otra.
    reloj.t += 5
    a = repeticion("MP a.aoe2record")
    v.actualizar()
    reloj.t += 5
    b = repeticion("MP b.aoe2record", jugadores=jugadores_de(1), mapa="Selva negra")
    v.actualizar()
    v.actualizar()
    comprobar(avisos[-3:] == [("empieza", a.name), ("acaba",), ("empieza", b.name)], "una partida sigue a otra")
    comprobar(v.partida.leaderboard == "rm_team", "la nueva es por equipos")

    # La API falla: se ve la partida con un error y se reintenta tras la espera.
    reloj.t += V.SIN_ESCRITURA + 1
    v.actualizar()
    prov.fallo = E.EstadisticasError("la API respondió 503", reintentable=True)
    est._cache.clear()
    reloj.t += 5
    c = repeticion("MP c.aoe2record")
    v.actualizar()
    comprobar(v.estado == V.ERROR and v.partida is not None and "503" in v.error,
              "la API falla: la partida se ve igual, con el error")
    prov.fallo = None
    for _ in range(2):
        reloj.t += 10
        os.utime(c, (reloj.t, reloj.t))
        v.actualizar()
    comprobar(v.estado == V.ERROR, "no se reintenta antes de la espera (30 s)")
    reloj.t += 15
    os.utime(c, (reloj.t, reloj.t))
    v.actualizar()
    comprobar(v.estado == V.CARGADO and v.partida.yo.rating == 2923, "pasada la espera, carga el elo")

    # Un resultado que llega tarde (de una partida que ya acabó) no se aplica.
    lento = []
    v2 = V.Vigilante(lambda: carpeta, E.Estadisticas(ProveedorFalso(), reloj), lambda: HERA, ahora=reloj,
                     en_segundo_plano=lento.append)
    v2.actualizar()
    comprobar(v2.estado == V.BUSCANDO and v2.partida.yo.rating is None, "buscando datos: nombres sin elo")
    reloj.t += V.SIN_ESCRITURA + 1
    v2.actualizar()
    lento[0]()
    v2.actualizar()
    comprobar(v2.estado == V.OCULTO and v2.partida is None, "el elo que llega tarde no resucita la partida")


def test_perfil_propio(tmp: Path):
    print("perfil propio")
    carpeta = tmp / "perfil"
    yo = 25000000
    comprobar(V.perfil_propio(carpeta) is None, "sin repeticiones no se sabe")
    for i, rival in enumerate((111, 222, 333)):
        js = [CB.JugadorCabecera(1, "yo", yo, 2, 0, 1), CB.JugadorCabecera(2, "rival", rival, 3, 1, 2)]
        CB.escribir_prueba(carpeta / f"MP {i}.aoe2record", js, clasificatoria=i % 2 == 0)
        if i == 0:
            comprobar(V.perfil_propio(carpeta) is None, "con una sola repetición no se sabe cuál es")
    CB.escribir_prueba(carpeta / "SP.aoe2record", [CB.JugadorCabecera(1, "otro", 999, 2, 0, 1)],
                       multijugador=False)
    comprobar(V.perfil_propio(carpeta) == yo, "el que está en todas las multijugador (las de un jugador no cuentan)")


def main():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        test_cabecera(tmp)
        test_repeticiones_reales()
        test_fichas()
        test_cache_y_esperas()
        test_modelo()
        test_vigilante(tmp)
        test_perfil_propio(tmp)
    print("\nTodo bien.")


if __name__ == "__main__":
    main()
