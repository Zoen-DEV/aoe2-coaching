"""Pruebas de la guía de ritmo en las clasificatorias, sin juego, red ni ventanas.

    py pruebas/test_ritmo.py

- El reloj en vivo (reloj_vivo.py): la repetición se lee a trozos mientras «se escribe»,
  con operaciones cortadas por la mitad, extrapolación, pausas y fin de partida. Juego
  limpio: solo los clics de edad del propio jugador. Con las repeticiones reales del
  perfil del juego, si las hay: leídas a trozos dan lo mismo que el análisis completo.
- Los objetivos (objetivos.py): sin prácticas, con saltados, la mediana de las últimas
  10, el factor de las ranked y las variantes por civilización.
- La guía de ritmo (ritmo.py) con una clasificatoria simulada (vigilante.simular), y la
  tarjeta que dibuja el overlay.
"""

import json
import os
import random
import struct
import sys
import tempfile
from pathlib import Path

OVERLAY = Path(__file__).resolve().parent.parent  # apps/desktop
sys.path.insert(0, str(OVERLAY))

import analisis as A  # noqa: E402
import cabecera as CB  # noqa: E402
import objetivos as O  # noqa: E402
import reloj_vivo as RV  # noqa: E402
import ritmo as R  # noqa: E402
import textos  # noqa: E402
from historial import historial_de_ejemplo, nuevo_registro, paso_del_hito  # noqa: E402
from lector import adaptar_a_civ, cargar_guias  # noqa: E402

textos.idioma_de_windows = lambda: "es"
GUIAS = cargar_guias()
YO, RIVAL = 1, 2
JUGADORES = [CB.JugadorCabecera(YO, "yo", 5000, 2, 0, 8), CB.JugadorCabecera(RIVAL, "rival", 6000, 3, 1, 1)]


def comprobar(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("  ok ·", msg)


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


# --- Reloj en vivo -------------------------------------------------------------


def test_reloj_a_trozos(tmp: Path):
    print("reloj en vivo: lectura a trozos")
    completa = A.escribir_prueba(tmp / "completa.aoe2record", JUGADORES,
                                 A.sync_prueba(1000) + A.construir_prueba(RIVAL, 12) + A.sync_prueba(2000)
                                 + A.investigar_prueba(RIVAL, 101)  # el rival hace clic en Feudal: no se mira
                                 + A.sync_prueba(500) + A.investigar_prueba(YO, 101) + A.sync_prueba(1500)
                                 + A.cola_prueba(YO, 83, 1) + A.sync_prueba(1000))
    datos = completa.read_bytes()
    total = list(A.leer_operaciones(datos))[-1][1]
    comprobar(total == 6000, "la repetición completa dura 6 s de juego")
    # Se escribe byte a byte: cada corte posible, también en mitad de una operación.
    vivo = tmp / "vivo.aoe2record"
    vivo.write_bytes(b"")
    reloj = Reloj()
    r = RV.RelojVivo(vivo, jugador=YO, ahora=reloj)
    vistos = []
    for i in range(len(datos)):
        with open(vivo, "ab") as f:
            f.write(datos[i:i + 1])
        r.actualizar()
        vistos.append(r.ms)
    comprobar(vistos == sorted(vistos), "el reloj leído nunca vuelve atrás")
    comprobar(r.ms == 6000 and r.terminada, "leída byte a byte, da el mismo tiempo que entera y ve el fin")
    comprobar(r.edades == {2: 3.5}, "solo el clic en Feudal propio (el del rival ni se mira)")
    # Sin saber quién es uno, ningún comando.
    r2 = RV.RelojVivo(completa, jugador=None, ahora=reloj)
    r2.actualizar()
    comprobar(r2.ms == 6000 and r2.edades == {}, "sin jugador propio: solo el reloj")
    # Sincronización corta al final: sin la operación siguiente no se sabe si es corta.
    corta = tmp / "corta.aoe2record"
    e = RV.EscritorPrueba(corta, JUGADORES)
    e.escribir(A.sync_prueba(700))
    r3 = RV.RelojVivo(corta, ahora=reloj)
    r3.actualizar()
    comprobar(r3.ms == 0, "una sincronización sin lo que va detrás espera")
    e.escribir(A.sync_prueba(300))
    r3.actualizar()
    comprobar(r3.ms == 700, "al llegar la siguiente operación, cuenta")


def test_reloj_extrapolado(tmp: Path):
    print("reloj en vivo: entre escrituras y en pausa")
    reloj = Reloj()
    e = RV.EscritorPrueba(tmp / "extra.aoe2record", JUGADORES)
    r = RV.RelojVivo(e.ruta, jugador=YO, velocidad=1.7, ahora=reloj)
    comprobar(r.segundos_sin_datos() is None and r.tiempo() == 0, "sin ninguna sincronización, en 0:00")
    e.avanzar(60)
    comprobar(r.actualizar() and r.leido == 60, "lee lo escrito: 60 s de juego")
    reloj.t += 2
    comprobar(abs(r.tiempo() - 63.4) < 1e-6, "entre escrituras avanza solo a la velocidad de la partida (2 s × 1,7)")
    reloj.t += 30
    tope = 60 + RV.EXTRAPOLAR * 1.7
    comprobar(abs(r.tiempo() - tope) < 1e-6, "sin datos (pausa), se para tras EXTRAPOLAR segundos")
    e.avanzar(5)
    r.actualizar()
    comprobar(r.leido == 65 and abs(r.tiempo() - tope) < 1e-6, "al volver los datos, no salta atrás")
    reloj.t += 10
    e.avanzar(20)
    r.actualizar()
    comprobar(r.tiempo() == 85 and r.retrasos == [32.0, 10.0], "luego sigue lo leído; se apuntan los retrasos")
    e.terminar()
    r.actualizar()
    reloj.t += 5
    comprobar(r.terminada and r.tiempo() == 85, "acabada la partida, el reloj se queda quieto")
    sin_vel = RV.RelojVivo(e.ruta, velocidad=0.0)
    comprobar(sin_vel.velocidad == RV.VELOCIDAD, "sin velocidad en la cabecera, la de las clasificatorias")
    comprobar(CB.leer_archivo(e.ruta).velocidad == 1.7, "la cabecera trae la velocidad de la partida")


def test_reloj_repeticiones_reales():
    print("reloj en vivo: repeticiones reales")
    base = Path(os.environ.get("USERPROFILE", "")) / "Games" / "Age of Empires 2 DE"
    reales = sorted(base.glob("*/savegame/MP Replay*.aoe2record"), key=lambda p: p.stat().st_mtime)[-3:] \
        if base.is_dir() else []
    if not reales:
        print("  (no hay repeticiones reales en este equipo: se salta)")
        return
    rnd = random.Random(3)
    with tempfile.TemporaryDirectory() as d:
        for ruta in reales:
            datos = ruta.read_bytes()
            try:
                cab = CB.leer(datos)
                completo = A.analizar_bytes(datos)
            except (CB.CabeceraError, A.AnalisisError):
                continue
            yo = cab.jugadores[0].numero
            vivo = Path(d) / "vivo.aoe2record"
            vivo.write_bytes(b"")
            r = RV.RelojVivo(vivo, jugador=yo, velocidad=cab.velocidad)
            pos = 0
            while pos < len(datos):
                n = rnd.randint(1, 80_000)
                with open(vivo, "ab") as f:
                    f.write(datos[pos:pos + n])
                pos += n
                r.actualizar()
            edades = {int(k): v[0] for k, v in completo["jugadores"].get(yo, {}).get("edades", {}).items()}
            comprobar(round(r.leido) == completo["duracion"] and r.edades == edades and r.terminada,
                      f"{ruta.name[-30:]}: a trozos, mismo reloj ({completo['duracion']} s) y clics de edad")


# --- Objetivos -----------------------------------------------------------------


def practica(guia: dict, horas: list, clic_feudal=None, fecha_n: int = 0, civ: int = 0) -> dict:
    """Un registro del historial con estas horas por paso (None = sin hacer, "saltado")."""
    from datetime import datetime, timedelta
    g = adaptar_a_civ(guia, civ) if civ else guia
    r = nuevo_registro(g, "[AoE2C] Arena", datetime(2026, 11, 1) + timedelta(hours=fecha_n))
    for p, h in zip(r["pasos"], horas):
        if h == "saltado":
            p["saltado"] = True
        else:
            p["hora"] = h
    r["hitos"]["clic_feudal"] = clic_feudal
    return r


def test_objetivos_sin_practicas():
    print("objetivos: sin prácticas")
    guia = GUIAS["fast_castle"]
    obj = O.calcular(guia, [], elo=1250)
    ref = [p["referencia"] for p in guia["pasos"]]
    comprobar(all(o.origen == O.ELO for o in obj), "todos los pasos salen del elo")
    comprobar([o.segundos for o in obj] == [round(x * 1.12) for x in ref], "referencia × factor del tramo (1200-1400: 1,12)")
    comprobar(O.factor_elo(None) == O.TRAMOS_ELO[0][1] and O.factor_elo(500) == 1.35 and O.factor_elo(2400) == 1.0,
              "elo desconocido, bajo y alto")
    otra = [practica(GUIAS["scouts"], [100] * len(GUIAS["scouts"]["pasos"]), fecha_n=i) for i in range(5)]
    comprobar(all(o.origen == O.ELO for o in O.calcular(guia, otra)), "las prácticas de otra guía no cuentan")


def test_objetivos_con_practicas():
    print("objetivos: con prácticas y saltados")
    guia = GUIAS["fast_castle"]
    n = len(guia["pasos"])
    ref0 = guia["pasos"][0]["referencia"]  # 35
    regs = [practica(guia, [ref0 + 20] + [None] * (n - 1), fecha_n=i) for i in range(2)]
    obj = O.calcular(guia, regs, elo=1250)
    comprobar(obj[0].origen == O.ELO and obj[0].practicas == 2, "con 2 prácticas aún sale del elo")
    # Diez prácticas viejas lentas y diez recientes: solo cuentan las últimas 10.
    regs = [practica(guia, [ref0 + 100] + [None] * (n - 1), fecha_n=i) for i in range(10)]
    regs += [practica(guia, [ref0 + d] + ["saltado"] + [None] * (n - 2), fecha_n=20 + i)
             for i, d in enumerate([10, 20, 30, 40, 50, 20, 20, 40, 40, 20])]
    obj = O.calcular(guia, regs)
    base = 35 + 25  # mediana de 10, 20, 30, 40, 50, 20, 20, 40, 40, 20 = 25
    comprobar(obj[0].origen == O.PRACTICA and obj[0].practicas == 10, "las últimas 10 prácticas")
    comprobar(obj[0].segundos == round(base - 0.25 * (base - ref0)), "base - 25 % de (base - referencia)")
    comprobar(obj[1].origen == O.ELO, "un paso siempre saltado no tiene prácticas: sale del elo")
    rapidas = [practica(guia, [ref0 - 5] + [None] * (n - 1), fecha_n=i) for i in range(5)]
    comprobar(O.calcular(guia, rapidas)[0].segundos == ref0, "nunca por debajo de la referencia")
    seguidos = [o.segundos for o in O.calcular(guia, regs)]
    comprobar(seguidos == sorted(seguidos), "ningún objetivo va antes que el del paso anterior")


def test_factor_ranked():
    print("objetivos: ajuste a las ranked")
    guia = GUIAS["fast_castle"]
    n = len(guia["pasos"])
    refs = [p["referencia"] for p in guia["pasos"]]
    i_feudal = paso_del_hito(guia, "feudal", 1)
    regs = [practica(guia, [r + 40 for r in refs], clic_feudal=refs[i_feudal] + 40, fecha_n=k) for k in range(5)]
    sin = O.calcular(guia, regs)
    clic_p = refs[i_feudal] + 40
    clics_ranked = [clic_p * 1.2] * 3
    con = O.calcular(guia, regs, clics_ranked=clics_ranked)
    comprobar(abs(O.factor_ranked(clics_ranked, [clic_p] * 5) - 1.2) < 1e-9, "factor = mediana ranked / mediana prácticas")
    comprobar(all(c.segundos == max(c.referencia, round(s.segundos * 1.2)) for s, c in zip(sin, con)),
              "se aplica a todos los pasos")
    comprobar(O.calcular(guia, regs, clics_ranked=[]) == sin, "sin ranked analizadas, sin ajuste")
    sin_clic = [practica(guia, [r + 40 for r in refs], fecha_n=k) for k in range(5)]
    comprobar(O.calcular(guia, sin_clic, clics_ranked=clics_ranked) == O.calcular(guia, sin_clic),
              "sin clics en Feudal en las prácticas, sin ajuste")
    pocas = [practica(guia, [refs[0] + 40] + [None] * (n - 1), clic_feudal=clic_p, fecha_n=k) for k in range(5)]
    otro = O.calcular(guia, pocas, elo=1250, clics_ranked=clics_ranked)[1]
    comprobar(otro.origen == O.ELO and otro.segundos == round(refs[1] * 1.12),
              "un paso sin prácticas suficientes sigue saliendo del elo")


def test_variante_civ():
    print("objetivos: variantes por civilización")
    guia = GUIAS["hombres_armas"]  # los persas (8) tienen otras referencias
    persa = adaptar_a_civ(guia, 8)
    n = len(guia["pasos"])
    comprobar(persa["pasos"][0]["referencia"] != guia["pasos"][0]["referencia"], "la guía tiene variante persa")
    obj = O.calcular(guia, [], civ=8, elo=2100)
    comprobar([o.referencia for o in obj] == [p["referencia"] for p in persa["pasos"]],
              "sin prácticas: las referencias de su variante")
    base_persa = persa["pasos"][0]["referencia"] + 20
    base_otra = guia["pasos"][0]["referencia"] + 60
    regs = [practica(guia, [base_persa] + [None] * (n - 1), fecha_n=k, civ=8) for k in range(3)]
    regs += [practica(guia, [base_otra] + [None] * (n - 1), fecha_n=10 + k) for k in range(5)]
    persas = O.calcular(guia, regs, civ=8)[0]
    francos = O.calcular(guia, regs, civ=2)[0]  # los francos no cambian ese paso
    comprobar(persas.practicas == 3 and persas.origen == O.PRACTICA, "persas: solo sus prácticas con la variante persa")
    comprobar(francos.practicas == 5, "otra civilización: las prácticas de la variante general")
    ref = persa["pasos"][0]["referencia"]
    comprobar(persas.segundos == round(base_persa - 0.25 * (base_persa - ref)), "el objetivo, sobre su referencia")


def test_paso_actual():
    print("objetivos: el paso que toca")
    obj = [O.Objetivo(i, s, s, O.ELO, 0) for i, s in enumerate([30, 60, 90])]
    comprobar([O.paso_actual(obj, t) for t in (0, 30, 31, 89, 91)] == [0, 0, 1, 2, 3], "el primero cuyo objetivo no pasó")


# --- Guía de ritmo y tarjeta ---------------------------------------------------------


def test_guia_ritmo(tmp: Path):
    print("guía de ritmo con una clasificatoria simulada")
    import vigilante as V
    from estadisticas import Estadisticas
    carpeta = tmp / "savegame"
    ruta, proveedor, yo = V.simular(carpeta, "1v1")
    proveedor.retraso = 0
    vig = V.Vigilante(lambda: carpeta, Estadisticas(proveedor), lambda: yo, en_segundo_plano=lambda f: f())
    vig.actualizar()
    comprobar(vig.partida is not None and vig.ruta == ruta and vig.cabecera is not None, "el vigilante la ve")
    guia = GUIAS["fast_castle"]
    config = {"ritmo": True, "ritmo_guia": None, "guia_activa": "fast_castle"}
    reloj = Reloj()
    hist = historial_de_ejemplo(guia)
    g = R.GuiaRitmo(hist, GUIAS, config, clics_ranked=lambda _yo: [], en_segundo_plano=lambda f: f(), ahora=reloj)
    g.seguir(vig.ruta, vig.cabecera, yo)
    comprobar(g.activa and g.estado() is None, "sin sincronizaciones aún, nada que dibujar")
    escritor = open(ruta, "ab")
    try:
        _jugar_partida(g, vig, yo, guia, escritor)
    finally:
        escritor.close()
    # Sin perfil propio: solo el reloj, ningún comando.
    g2 = R.GuiaRitmo(hist, GUIAS, config, en_segundo_plano=lambda f: f(), ahora=reloj)
    g2.seguir(vig.ruta, vig.cabecera, None)
    comprobar(g2.reloj.leido > 0 and g2.reloj.jugador is None and g2.reloj.edades == {},
              "sin saber quién es uno, solo el reloj (su clic en Feudal ni se mira)")


def _jugar_partida(g: R.GuiaRitmo, vig, yo: int, guia: dict, escritor):
    config = g.config

    def jugar(segundos, extra=b""):
        ms = int(segundos * 1000)
        escritor.write(b"".join(A.sync_prueba(500) for _ in range(ms // 500)) + extra
                       + struct.pack("<I", A.OP_VISTA) + bytes(12))
        escritor.flush()
        g.seguir(vig.ruta, vig.cabecera, yo)

    jugar(100)
    e = g.estado(1220)
    comprobar(e is not None and e.tiempo == 100 and e.paso == O.paso_actual(e.objetivos, 100), "a los 1:40, el paso que toca")
    comprobar(e.objetivos[0].origen == O.PRACTICA, "con prácticas de la guía, objetivos de práctica")
    comprobar(e.diferencia is None, "antes del objetivo del clic en Feudal no hay comparación")
    i_feudal = paso_del_hito(guia, "feudal", 1)
    objetivo_feudal = e.objetivos[i_feudal].segundos
    jugar(objetivo_feudal + 10 - 100)
    e = g.estado(1220)
    comprobar(e.diferencia == 10, "pasado el objetivo sin clic: lleva 10 s de retraso")
    jugar(5, A.investigar_prueba(2, 101))  # el rival: no cuenta
    comprobar(g.estado(1220).diferencia == 15, "el clic del rival no cuenta")
    jugar(5, A.investigar_prueba(1, 101))
    comprobar(g.estado(1220).diferencia == 20 and g.estado(1220).clics == {2: objetivo_feudal + 20},
              "el clic propio (5 s después) fija la diferencia: +20 s")
    jugar(30)
    comprobar(g.estado(1220).diferencia == 20, "y ya no cambia con el reloj")
    config["ritmo_guia"] = "no_existe"
    comprobar(g.estado() is None, "sin la guía elegida, nada")
    config["ritmo_guia"] = None
    jugar(e.objetivos[-1].segundos + R.FIN_GUIA + 5 - g.reloj.leido)
    comprobar(g.estado() is None, "pasado el último objetivo, la guía se quita")
    g.seguir(None, None, yo)
    comprobar(not g.activa, "al acabar la partida, se para")


def test_tarjeta():
    print("tarjeta de la guía de ritmo")
    from overlay import Pintor, ANCHO, vista_ritmo
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(["-platform", "offscreen"])  # noqa: F841
    guia = GUIAS["fast_castle"]
    obj = O.calcular(guia, [], elo=1250)
    e = R.EstadoRitmo(guia, obj, 200.0, O.paso_actual(obj, 200.0), diferencia=40)
    v = vista_ritmo(e)
    comprobar(v.paso == e.paso and v.referencia == obj[e.paso].segundos and v.condiciones == [],
              "el paso que toca, con su objetivo y sin condiciones (nada se marca)")
    comprobar(v.siguientes[0] == (e.paso + 2, guia["pasos"][e.paso + 1]["titulo"], obj[e.paso + 1].segundos),
              "los siguientes, con sus objetivos")
    comprobar(v.ritmo[0] == "+40 s", "la pastilla: 40 s tarde en el clic de edad")
    fin = vista_ritmo(R.EstadoRitmo(guia, obj, obj[-1].segundos + 5, len(obj)))
    comprobar(fin.paso == len(obj) - 1 and not fin.terminada and fin.ritmo is None, "pasado el último, sigue el último")
    comprobar(Pintor(None, ANCHO).dibujar(v, None, 1.0) > 100, "se dibuja")


def main():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        test_reloj_a_trozos(tmp)
        test_reloj_extrapolado(tmp)
        test_reloj_repeticiones_reales()
        test_objetivos_sin_practicas()
        test_objetivos_con_practicas()
        test_factor_ranked()
        test_variante_civ()
        test_paso_actual()
        test_guia_ritmo(tmp)
        test_tarjeta()
    print("\nTodo bien.")


if __name__ == "__main__":
    main()
