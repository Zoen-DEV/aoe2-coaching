"""Pruebas del historial de partidas (sin abrir ninguna ventana).

    py pruebas/test_historial.py

Simula partidas segundo a segundo con el mismo formato .xsdat que escribe el juego
y comprueba lo que se guarda en el historial y lo que hace el overlay.
"""

import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # nada aparece en pantalla
OVERLAY = Path(__file__).resolve().parent.parent  # apps/desktop
sys.path.insert(0, str(OVERLAY))

import historial as H  # noqa: E402
import lector as L  # noqa: E402

GUIA = L.cargar_guias()["fast_castle"]
N = len(GUIA["pasos"])
I_FEUDAL = GUIA["techs"].index("edad_feudal")
I_CAST = GUIA["techs"].index("edad_castillos")


def partida(retraso: int = 30, clic_f: int = 640, clic_c: int = 830, hasta: int = 1100, saltar: int | None = None):
    """Genera (tiempo, Estado) cada segundo, como el script XS."""
    feudal, castillos = clic_f + 130, clic_c + 160
    for t in range(0, hasta):
        horas = []
        for i, p in enumerate(GUIA["pasos"]):
            hora = p["referencia"] + retraso
            if i == H.paso_del_hito(GUIA, "feudal", 1):
                hora = clic_f
            if i == H.paso_del_hito(GUIA, "castillos", 1):
                hora = clic_c
            if i == N - 1:
                hora = castillos
            horas.append(hora if t >= hora and i != saltar else -1)
        paso = 0
        while paso < N and horas[paso] >= 0:
            paso += 1
        if horas[-1] >= 0:
            horas = [h if h >= 0 else -2 for h in horas]
            paso = N
        techs = [0] * GUIA["num_techs"]
        techs[I_FEUDAL] = 2 if t >= feudal else (1 if t >= clic_f else 0)
        techs[I_CAST] = 2 if t >= castillos else (1 if t >= clic_c else 0)
        edad = 2 if t >= castillos else (1 if t >= feudal else 0)
        yield L.Estado(t, 1, paso, horas, [0] * GUIA["num_datos"], techs, edad, 20, 5, 0)


def jugar(seg: H.Seguimiento, estados, mapa="[AoE2C] Arena", desde=0.0):
    escritura = desde
    for e in estados:
        escritura += 1
        seg.observar(GUIA, e, 0.5, mapa, escritura)
    return e, escritura


def comprobar(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("  ok ·", msg)


def test_partida_completa(tmp: Path):
    print("Partida completa y fin de partida")
    h = H.Historial(tmp / "h1.json")
    s = H.Seguimiento(h)
    ultimo, escritura = jugar(s, partida(retraso=30))
    comprobar(s.terminada is None, "durante la partida no se abre el historial")
    s.observar(GUIA, ultimo, 10.0, "[AoE2C] Arena", escritura)  # dejan de llegar datos
    comprobar(s.terminada is not None, "al parar la partida se avisa para abrir el historial")
    h2 = H.Historial(tmp / "h1.json")
    comprobar(len(h2.registros) == 1, "se guarda una partida en el archivo")
    r = h2.registros[0]
    comprobar(r["hitos"] == {"clic_feudal": 640, "feudal": 770, "clic_castillos": 830, "castillos": 990, "meta": 990},
              f"hitos correctos: {r['hitos']}")
    comprobar(r["completada"] and H.pasos_hechos(r) == N, "todos los pasos hechos")
    comprobar(r["referencias"]["feudal"] == r["referencias"]["clic_feudal"] + 130, "referencia de Feudal = clic + 130 s")
    t = H.tramos(r)
    comprobar(t[0]["tramo"] == 30 and t[1]["tramo"] == 0, "el tramo mide el tiempo perdido en cada paso")


def test_pausa_y_nueva(tmp: Path):
    print("Pausa, reanudar y partida nueva")
    h = H.Historial(tmp / "h2.json")
    s = H.Seguimiento(h)
    estados = list(partida(retraso=10))
    ultimo, esc = jugar(s, estados[:400])
    s.observar(GUIA, ultimo, 8.0, "[AoE2C] Arena", esc)  # pausa
    comprobar(s.terminada is not None, "en la pausa también se avisa")
    s.terminada = None
    ultimo, esc = jugar(s, estados[400:], desde=esc)  # se reanuda
    comprobar(len(h.registros) == 1, "al reanudar sigue la misma partida")
    jugar(s, partida(retraso=50, clic_f=660, clic_c=850, hasta=900), desde=esc)  # otra partida
    comprobar(len(h.registros) == 2, "el reloj vuelve a 0: partida nueva")
    comprobar(h.registros[1]["hitos"]["clic_feudal"] == 660, "la segunda partida tiene sus propios hitos")
    comprobar(h.registros[1]["hitos"]["castillos"] is None and not h.registros[1]["completada"],
              "partida sin llegar a Castillos: el hito queda vacío")


def test_overlay_reiniciado(tmp: Path):
    print("Overlay cerrado y abierto a mitad de partida")
    archivo = tmp / "h3.json"
    estados = list(partida(retraso=10))
    s = H.Seguimiento(H.Historial(archivo))
    _, esc = jugar(s, estados[:700])
    s2 = H.Seguimiento(H.Historial(archivo))  # overlay nuevo
    jugar(s2, estados[720:], desde=esc + 20)
    h = H.Historial(archivo)
    comprobar(len(h.registros) == 1, "continúa el registro en vez de duplicarlo")
    r = h.registros[0]
    comprobar(r["hitos"]["feudal"] == 770 and r["hitos"]["castillos"] == 990, f"hitos vistos tras reabrir: {r['hitos']}")


def test_overlay_tarde(tmp: Path):
    print("Overlay abierto cuando ya se había hecho el clic en Feudal")
    h = H.Historial(tmp / "h4.json")
    s = H.Seguimiento(h)
    estados = list(partida(retraso=10))
    jugar(s, estados[700:])  # empieza a mirar después de llegar a Feudal (770 no, 700 > clic 640)
    r = h.registros[0]
    comprobar(r["hitos"]["clic_feudal"] == 640, "el clic se toma de la hora del paso de la guía")
    comprobar(r["hitos"]["feudal"] == 770, "la llegada a Feudal sí se vio (a las 770)")
    h5 = H.Historial(tmp / "h5.json")
    s5 = H.Seguimiento(h5)
    jugar(s5, list(partida(retraso=10))[800:])
    comprobar(h5.registros[0]["hitos"]["feudal"] is None, "si no se vio la llegada a Feudal, queda vacía (no inventada)")


def test_importar(tmp: Path):
    print("Partida jugada con el overlay cerrado")
    archivo = tmp / "h6.json"
    ultimo = list(partida(retraso=10))[-1]
    s = H.Seguimiento(H.Historial(archivo))
    s.observar(GUIA, ultimo, 3600.0, "[AoE2C] Arabia", 1_700_000_000.0)
    h = H.Historial(archivo)
    comprobar(len(h.registros) == 1 and h.registros[0]["mapa"] == "[AoE2C] Arabia",
              "se importa el último archivo al arrancar")
    comprobar(h.registros[0]["hitos"]["castillos"] == 990, "con la llegada a Castillos del paso final")
    comprobar(s.terminada is None, "importar no abre el historial")
    s2 = H.Seguimiento(H.Historial(archivo))
    s2.observar(GUIA, ultimo, 3600.0, "[AoE2C] Arabia", 1_700_000_000.0)
    comprobar(len(H.Historial(archivo).registros) == 1, "y no se duplica al volver a abrir el overlay")
    vacia = next(partida(hasta=1))
    s3 = H.Seguimiento(H.Historial(tmp / "h7.json"))
    s3.observar(GUIA, vacia, 3600.0, "[AoE2C] Arena", 5.0)
    comprobar(not (tmp / "h7.json").exists(), "una partida sin pasos hechos no se guarda")


def test_estadisticas():
    print("Estadísticas")
    h = H.historial_de_ejemplo(GUIA, 14)
    regs = h.registros
    res = H.resumen_hito(regs, "castillos")
    vals = [r["hitos"]["castillos"] for r in regs]
    comprobar(res["mejor"] == min(vals) and res["cuenta"] == 14, "mejor marca y cuenta")
    comprobar(abs(res["media"] - sum(vals[-10:]) / 10) < 1e-9, "media de las últimas 10")
    debiles = H.puntos_debiles(regs)
    comprobar(debiles[0]["n"] in (5, 6, 11), f"el tramo más lento es uno de los inventados: {debiles[0]['n']}")
    linea = H.comparacion_final(h, regs[-1])
    comprobar("media" in linea, f"línea de comparación: {linea}")
    comprobar(H.comparacion_final(H.Historial(None), regs[-1]).startswith("Primera"), "primera partida")


def test_archivo_roto(tmp: Path):
    print("Archivo del historial dañado")
    a = tmp / "roto.json"
    a.write_text("{no es json", encoding="utf-8")
    comprobar(H.Historial(a).registros == [], "se ignora sin fallar")


def test_overlay(tmp: Path):
    print("Overlay: el historial se abre al acabar y se cierra al volver a la partida")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    import overlay as O
    O.CONFIG = tmp / "config.json"
    h = H.Historial(tmp / "h8.json")
    s = H.Seguimiento(h)
    estados = list(partida(retraso=10))
    estado = {"e": estados[0], "f": 0.0, "i": 0}

    def fuente():
        s.observar(GUIA, estado["e"], estado["f"], "[AoE2C] Arena", 1000.0 + estado["i"])
        return GUIA, estado["e"], estado["f"]

    w = O.Overlay(fuente, solo_con_juego=False, historial=h, seguimiento=s)
    w.temporizador.stop()
    w.juego_delante = True

    def ticks(n=40):
        for _ in range(n):
            w.tick()
            app.processEvents()

    for i in range(0, 1100, 7):
        estado["e"], estado["i"] = estados[i], i
        w.tick()
    comprobar(not w.historial_abierto and not w.pestana_historial.isVisible(), "en partida: ni ventana ni pestaña")
    comprobar("Primera" in (w.vista.comparacion or ""), f"tarjeta final: «{w.vista.comparacion}»")
    estado["f"] = 10.0
    ticks()
    comprobar(w.historial_abierto and w.ventana_historial.isVisible(), "al parar la partida se abre el historial")
    comprobar(w.ventana_historial.aviso.isVisible() and "Castillos a las 16:30" in w.ventana_historial.aviso.text(),
              f"aviso: «{w.ventana_historial.aviso.text()}»")
    estado["f"] = 0.0
    ticks()
    comprobar(not w.historial_abierto and not w.ventana_historial.isVisible(), "al reanudar se cierra")
    estado["f"] = 10.0
    ticks()
    w.cerrar_historial()
    ticks()
    comprobar(w.pestana_historial.isVisible() is False, "la pestaña solo sale con el juego real delante (no en pruebas)")
    w.solo_con_juego = True
    w.ultima_comprobacion = time.monotonic() + 1e6  # no mirar la ventana activa de verdad
    ticks()
    comprobar(w.pestana_historial.isVisible(), "fuera de partida, con el juego delante, sale la pestaña")
    w.pestana_historial.al_pulsar(w.pestana_historial)
    ticks()
    comprobar(w.ventana_historial.isVisible() and not w.pestana_historial.isVisible(), "la pestaña abre el historial")
    w.cambiar_pestana_historial(False)
    w.cerrar_historial()
    ticks()
    comprobar(not w.pestana_historial.isVisible(), "la pestaña se puede desactivar desde el menú")
    # Fuera del juego la ventana flotante no se ve: el historial está en el panel.
    w.abrir_historial()
    w.juego_delante = False
    ticks()
    comprobar(w.historial_abierto and not w.ventana_historial.isVisible(), "fuera del juego, la ventana flotante no se ve")
    pedidos = []
    w.al_abrir_historial = lambda: pedidos.append(1)
    w.cerrar_historial()
    w.ver_historial()
    comprobar(pedidos == [1] and not w.historial_abierto, "«Ver historial» fuera del juego abre el del panel")
    w.juego_delante = True
    w.ver_historial()
    ticks()
    comprobar(pedidos == [1] and w.ventana_historial.isVisible(), "y dentro del juego, la ventana flotante")
    # Con otra partida en curso (clasificatoria o cualquiera), ni ventana ni pestaña: solo en el menú.
    w.cambiar_pestana_historial(True)
    w.vigilante = type("V", (), {"partida": None, "en_curso": True})()
    ticks()
    comprobar(w.historial_abierto and not w.ventana_historial.isVisible() and not w.pestana_historial.isVisible(),
              "durante cualquier partida el historial no se ve")
    w.vigilante.en_curso = False
    ticks()
    comprobar(w.ventana_historial.isVisible(), "al volver al menú principal se ve")
    w.vigilante = None
    w.cambiar_pestana_historial(False)
    w.cerrar_historial()
    ticks()
    # Elegir y borrar desde la ventana.
    v = w.ventana_historial
    v.abrir()
    comprobar(v.seleccion is None and v.vista_general.isVisibleTo(v) and not v.vista_partida.isVisibleTo(v),
              "sin partida elegida se ve el resumen general")
    v.lista.al_elegir(h.registros[0]["id"])
    comprobar(v.seleccion == h.registros[0]["id"] and v.vista_partida.isVisibleTo(v)
              and not v.vista_general.isVisibleTo(v), "al elegir una partida en la barra lateral se ve su detalle")
    v.resumen.al_pulsar()
    comprobar(v.vista_general.isVisibleTo(v), "«Resumen general» vuelve a la vista general")
    v.pulsar_borrar()
    comprobar(len(h.registros) == 1, "en el resumen general Borrar no hace nada")
    v.elegir(h.registros[0]["id"])
    v.pulsar_borrar()
    comprobar(len(h.registros) == 1, "el primer clic en Borrar solo pide confirmación")
    v.pulsar_borrar()
    comprobar(len(H.Historial(tmp / "h8.json").registros) == 0 and v.vacio.isVisibleTo(v), "el segundo clic la borra")


def test_lector_y_seguimiento(tmp: Path):
    print("De extremo a extremo: archivo .xsdat -> lector -> historial")
    xsdat = tmp / "[AoE2C] Arena.xsdat"
    lec = L.Lector()
    lec._candidatos = lambda: iter([xsdat])
    s = H.Seguimiento(H.Historial(tmp / "h9.json"))
    for e in list(partida(retraso=5))[::3]:
        L.escribir_prueba(xsdat, GUIA, e)
        os.utime(xsdat, (e.tiempo + 1e6, e.tiempo + 1e6))
        lec.actualizar()
        s.observar(lec.guia, lec.estado, 0.5, lec.archivo.stem, lec.mtime)
    r = s.historial.registros[0]
    comprobar(r["mapa"] == "[AoE2C] Arena" and r["hitos"]["castillos"] == 990, "lee el archivo del juego")
    comprobar(abs(r["hitos"]["feudal"] - 770) <= 3, f"llegada a Feudal con lecturas cada 3 s: {r['hitos']['feudal']}")


def test_ranked(tmp: Path):
    print("Ranked: se leen de las repeticiones y se filtran en el historial")
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    import cabecera as CB
    import clasificatorias as R
    import historial_ui as HU
    import repeticiones
    sg = tmp / "perfil_ranked" / "savegame"
    yo, rival = 111, 222
    J = CB.JugadorCabecera
    uno = [J(1, "Yo", yo, 2, 0, 8), J(2, "Rook", rival, 3, 1, 1)]
    ranked = "MP Replay v101.103.57257.0 @2026.11.12 121309 (2).aoe2record"
    CB.escribir_prueba(sg / ranked, uno, mapa="Arabia")
    CB.escribir_prueba(sg / "MP Replay v101.103.57257.0 @2026.11.12 131309 (1).aoe2record",
                       [J(1, "Yo", yo, 2, 0, 8), J(2, "Otro", 333, 3, 1, 4)], mapa="Arena")
    CB.escribir_prueba(sg / "MP Replay v101.103.57257.0 @2026.11.11 101010 (1).aoe2record", uno,
                       clasificatoria=False)
    CB.escribir_prueba(sg / "SP Replay v101.103.57257.0 @2026.11.11 090000.aoe2record", uno)
    en_curso = sg / "MP Replay v101.103.57257.0 @2026.11.13 090000 (1).aoe2record"
    CB.escribir_prueba(en_curso, uno)
    for f in sg.iterdir():
        if f != en_curso:
            os.utime(f, (time.time() - 3600, time.time() - 3600))
    cache = tmp / "clasificatorias.json"
    regs = R.leer(sg, cache)
    comprobar([r["mapa"] for r in regs] == ["Arabia", "Arena"],
              "solo las ranked terminadas (ni la no clasificatoria, ni la de un jugador, ni la que sigue en curso)")
    comprobar(regs[0]["fecha"] == "2026-11-12T12:13:09" and R.titulo(regs[0]) == "RM 1v1", "fecha y modo")
    comprobar(R.perfil_comun(regs) == yo and R.rivales(regs[0], yo)[0]["nombre"] == "Rook",
              "el jugador es el que está en todas; el rival, el otro")
    llamadas = []
    original = CB.leer_archivo
    CB.leer_archivo = lambda ruta: llamadas.append(ruta) or original(ruta)
    try:
        comprobar(len(R.leer(sg, cache)) == 2 and not llamadas, "la segunda vez no se vuelve a abrir ninguna")
    finally:
        CB.leer_archivo = original
    comprobar(R.nombre_repeticion(regs[0]) == ranked.removesuffix(".aoe2record"), "nombre sin extensión")

    # Resultado y elo, de la API (con una respuesta inventada).
    import json
    from datetime import datetime
    inicio = int(datetime(2026, 11, 12, 12, 13, 5).timestamp())  # la API: unos segundos antes que la repetición
    respuesta = {"result": {"code": 0, "message": "SUCCESS"}, "matchHistoryStats": [
        {"startgametime": inicio, "matchhistorymember": [
            {"profile_id": yo, "outcome": 1, "oldrating": 949, "newrating": 993},
            {"profile_id": rival, "outcome": 0, "oldrating": 1010, "newrating": 966}]},
        {"startgametime": inicio + 7200, "matchhistorymember": [  # otra partida, con otro rival
            {"profile_id": yo, "outcome": 0, "oldrating": 993, "newrating": 950},
            {"profile_id": 999, "outcome": 1, "oldrating": 980, "newrating": 1020}]},
        {"startgametime": "roto"}]}
    pedidas = []
    pedir = lambda url: pedidas.append(url) or json.dumps(respuesta).encode()  # noqa: E731
    ahora = lambda: datetime(2026, 11, 13).timestamp()  # noqa: E731
    comprobar(R.completar(regs, yo, cache, pedir, ahora, forzar=True), "la API trae el resultado")
    comprobar(pedidas == [R.URL_HISTORIAL + "?title=age2&profile_ids=%5B111%5D"], "una sola petición, con el perfil")
    comprobar(regs[0]["resultado"] == "victoria" and R.elo_de(regs[0], yo) == (949, 993)
              and R.elo_de(regs[0], rival) == (1010, 966), "victoria y elo antes y después de cada jugador")
    comprobar("resultado" not in regs[1], "una partida sin su pareja en la API se queda sin resultado")
    comprobar(R.leer(sg, cache)[0]["resultado"] == "victoria", "el resultado queda guardado")
    comprobar(not R.completar(regs, yo, cache, pedir, ahora) and len(pedidas) == 1,
              "no se vuelve a preguntar enseguida")
    comprobar(R.pendientes(regs, datetime(2026, 12, 30).timestamp()) == [], "pasados unos días ya no se pregunta")
    import estadisticas as E

    def falla(url):
        raise E.EstadisticasError("sin conexión", reintentable=True)
    comprobar(not R.completar(regs, yo, cache, falla, ahora, forzar=True), "sin conexión, no pasa nada")

    h = H.historial_de_ejemplo(GUIA, 3)
    repeticiones.poner_perfil(sg.parent)
    try:
        c = HU.ContenidoHistorial(h, lambda: yo)
        c._ranked_leidas_en = time.monotonic()  # sin hilo: se ponen a mano
        c._poner_ranked(regs)
        c.abrir()
        comprobar(len(c.lista.registros) == 5 and c.barra_filtros.isVisibleTo(c), "Todas: ranked y prácticas juntas")
        c.filtrar_tipo(HU.RANKED)
        comprobar(len(c.lista.registros) == 2 and c.vista_ranked.isVisibleTo(c), "Ranked: solo ranked, con su resumen")
        comprobar(c.conteo_rivales.filas == [("Rook", 1), ("Otro", 1)], "resumen: rivales")
        c.filtrar_tipo(HU.PRACTICA)
        comprobar(len(c.lista.registros) == 3 and all(not HU.es_ranked(r) for r in c.lista.registros),
                  "Práctica: solo prácticas")
        c.elegir(ranked)
        comprobar(c.tipo is None and c.vista_partida.isVisibleTo(c) and c.cuerpo_ranked.isVisibleTo(c)
                  and not c.cuerpo_practica.isVisibleTo(c) and not c.borrar.isVisibleTo(c),
                  "elegir una ranked desde Práctica vuelve a Todas y muestra sus jugadores (sin Borrar)")
        c.pulsar_copiar()
        comprobar(QGuiApplication.clipboard().text() == ranked.removesuffix(".aoe2record")
                  and c.copiar.text() == "Copiado", "Copiar nombre deja el nombre de la repetición en el portapapeles")
        c.pulsar_borrar()
        c.pulsar_borrar()
        comprobar(c.buscar(ranked) is not None, "una ranked no se borra")
        comprobar(c.resultado_detalle.isVisibleTo(c) and c.resultado_detalle.text() == "Victoria",
                  "el detalle dice si ganaste")
        comprobar(HU.cambio_elo(c.buscar(ranked), yo)[0] == "+44", "y cuánto elo")
        c.filtrar_tipo(HU.RANKED)
        comprobar("1 V · 0 D" in c.rotulo_ranked.text() and "ELO 993" in c.rotulo_ranked.text(),
                  f"resumen: balance y elo actual («{c.rotulo_ranked.text()}»)")
        c.elegir(h.registros[0]["id"])
        comprobar(c.cuerpo_practica.isVisibleTo(c) and c.borrar.isVisibleTo(c) and not c.copiar.isEnabled(),
                  "una práctica sin repetición: Copiar desactivado")
    finally:
        repeticiones.poner_perfil(None)
    app.processEvents()


def main():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        test_partida_completa(tmp)
        test_pausa_y_nueva(tmp)
        test_overlay_reiniciado(tmp)
        test_overlay_tarde(tmp)
        test_importar(tmp)
        test_estadisticas()
        test_archivo_roto(tmp)
        test_lector_y_seguimiento(tmp)
        test_overlay(tmp)
        test_ranked(tmp)
    print("\nTodo bien.")


if __name__ == "__main__":
    main()
