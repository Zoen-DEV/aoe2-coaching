"""Lo que hizo cada jugador en una partida, sacado de los comandos de su repetición.

Detrás de la cabecera (cabecera.py), la repetición guarda la partida como una lista de
operaciones: comandos de los jugadores (construir, investigar, poner unidades en cola...)
y sincronizaciones que hacen avanzar el reloj del juego. Con ellas sale:

- el build order real: edificios, investigaciones y unidades, con el momento del clic;
- la subida de edad: el clic en Feudal, Castillos o Imperial y la llegada estimada
  (clic + lo que tarda la investigación sin bonificaciones de civilización);
- las acciones por minuto (los comandos que llegan a la repetición, eAPM);
- los aldeanos puestos en cola a lo largo de la partida;
- los ratos con el centro urbano parado (estimados, ver paradas_cu).

Los tiempos son de juego (los del reloj del juego), en segundos. El formato sigue al de
mgz (github.com/happyleavesaoc/aoc-mgz, licencia MIT, mgz/fast), comprobado con
repeticiones de la versión 101.103. Si algo no cuadra se para ahí: lo leído hasta
entonces vale.
"""

import struct
from pathlib import Path

import cabecera as CB

# Operaciones del cuerpo.
OP_ACCION, OP_SYNC, OP_VISTA, OP_CHAT, OP_POSTGAME = 1, 2, 3, 4, 6
# Comandos.
A_ORDEN_IA = 10  # los da el juego (exploración automática): no cuentan como acciones
A_INVESTIGAR, A_CONSTRUIR, A_COLA = 101, 102, 129
A_DIMITIR = 11

ALDEANO = 83
EDADES = {101: 2, 102: 3, 103: 4}  # tecnología -> edad a la que lleva
DURACION_EDAD = {101: 130, 102: 160, 103: 190}  # segundos de juego, sin bonificaciones
LARGO_SYNC_DE = 4 * 8 * 11  # valores por jugador de las sincronizaciones de DE

# Tipos de evento del build order.
EDIFICIO, TECNOLOGIA, UNIDAD, EDAD = "edificio", "tecnologia", "unidad", "edad"

# --- Centro urbano -------------------------------------------------------------
CENTRO_URBANO = 109
CU_UNIDAD = 25  # segundos que tarda un aldeano (y lo demás que sale del centro urbano)
# Tecnologías del centro urbano -> segundos: telar, carretilla, carro de mano, vigilancia,
# patrulla y las tres edades.
CU_TECNOLOGIAS = {22: 25, 213: 75, 249: 55, 8: 25, 280: 40, **DURACION_EDAD}
PERSAS = 8
RAPIDEZ_PERSAS = {1: 1.05, 2: 1.10, 3: 1.15, 4: 1.20}  # el centro urbano trabaja más rápido
HUNOS, CHINOS, MAYAS = 17, 6, 16
# Edificios que dan población: (población, segundos de construcción con un aldeano).
CASA, CASTILLO = 70, 82
DA_POBLACION = {CASA: (5, 25), CENTRO_URBANO: (5, 150), CASTILLO: (20, 200)}
POBLACION_MAX = 200
# Las casas solo se miran hasta el clic en Castillos (y como mucho 20 minutos): sin las
# bajas, que no salen en la repetición, la población estimada se aleja de la real.
CASAS_HASTA = 1200
COLA, CASAS = "cola", "casas"  # por qué estuvo parado


class AnalisisError(Exception):
    pass


def _inicio_cuerpo(d: bytes) -> int:
    """Posición de la primera operación (tras la cabecera y el bloque de metadatos)."""
    if len(d) < 8:
        raise AnalisisError("archivo demasiado corto")
    tam = struct.unpack_from("<I", d)[0]
    i = tam + 4  # versión del registro
    try:
        primero = struct.unpack_from("<I", d, i)[0]
        i += 4
        if primero != 500:
            i += 4
        i += 20
        a, b, _ = struct.unpack_from("<III", d, i)
    except struct.error:
        raise AnalisisError("la repetición no tiene partida") from None
    i += 12
    if a != 0:
        i -= 12
    if b == 2:  # DE
        i -= 8
    return i


FIN = "fin"            # operación de fin de partida (postgame) o desconocida: no se sigue
MAX_ACCION = 1 << 20   # un comando más largo es que el formato no cuadra


def operacion(d: bytes, i: int, fin: int | None = None):
    """La operación que empieza en i: (tipo, posición de la siguiente, valor).

    - OP_SYNC: valor = milisegundos que avanza el reloj del juego;
    - OP_ACCION: valor = (jugador, comando, datos), o None si no es del formato de DE;
    - OP_VISTA, OP_CHAT: valor = None;
    - FIN: fin de la partida o algo que no se entiende (valor = None).

    None si los bytes aún no llegan al final de la operación (la repetición de una
    partida en curso se corta en cualquier sitio): se vuelve a intentar con más."""
    fin = len(d) if fin is None else fin
    if i + 4 > fin:
        return None
    op = struct.unpack_from("<I", d, i)[0]
    i += 4
    if op == OP_ACCION:
        if i + 4 > fin:
            return None
        n = struct.unpack_from("<I", d, i)[0]
        if not 1 <= n <= MAX_ACCION:
            return FIN, i, None
        siguiente = i + 4 + n + 4  # largo, comando y datos, número de secuencia
        if siguiente > fin:
            return None
        comando = d[i + 4]
        datos = d[i + 5:i + 4 + n]
        valor = None
        if len(datos) >= 3:
            jugador, largo = struct.unpack_from("<bh", datos)
            if largo == len(datos) - 3:  # formato de DE 71094 en adelante
                valor = (jugador, comando, datos[3:])
        return OP_ACCION, siguiente, valor
    if op == OP_SYNC:
        if i + 8 > fin:
            return None  # sin la marca no se sabe si la sincronización es corta
        inc, marca = struct.unpack_from("<II", d, i)
        if marca:
            return OP_SYNC, i + 4, inc  # corta: la marca es ya la operación siguiente
        if i + 8 + 16 > fin:
            return None
        _, es_de = struct.unpack_from("<4xI4xI", d, i + 8)
        siguiente = i + 8 + (LARGO_SYNC_DE + 4 if es_de else 24)
        return (OP_SYNC, siguiente, inc) if siguiente <= fin else None
    if op == OP_VISTA:
        return (OP_VISTA, i + 12, None) if i + 12 <= fin else None
    if op == OP_CHAT:
        if i + 8 > fin:
            return None
        _, n = struct.unpack_from("<II", d, i)
        return (OP_CHAT, i + 8 + n, None) if i + 8 + n <= fin else None
    return FIN, i, None


def leer_operaciones(d: bytes):
    """Recorre el cuerpo: (tiempo en ms, jugador, comando, datos) por cada comando y, al
    final, ("fin", tiempo) con la duración. Para en la primera operación que no entiende."""
    i = _inicio_cuerpo(d)
    t = 0
    while True:
        r = operacion(d, i)
        if r is None or r[0] == FIN:
            break
        tipo, i, valor = r
        if tipo == OP_SYNC:
            t += valor
        elif tipo == OP_ACCION and valor is not None:
            yield t, *valor
    yield "fin", t


def analizar_bytes(d: bytes) -> dict:
    """{"duracion": s, "jugadores": {numero: {"eventos": [[t, tipo, id, cantidad]],
    "acciones": [por minuto], "aldeanos": [[t, total]], "edades": {edad: [clic, llegada]}}}}"""
    jugadores: dict[int, dict] = {}
    duracion = 0
    # Lo que hace falta para el centro urbano, por jugador: [trabajos, edificios, militares].
    cu: dict[int, list] = {}

    def de(n: int) -> dict:
        cu.setdefault(n, [[], [], []])
        return jugadores.setdefault(n, {"eventos": [], "acciones": [], "aldeanos": [], "edades": {}})

    for paso in leer_operaciones(d):
        if paso[0] == "fin":
            duracion = paso[1] / 1000
            break
        t_ms, jugador, comando, datos = paso
        if not 1 <= jugador <= 8:
            continue
        t = round(t_ms / 1000, 1)
        j = de(jugador)
        if comando != A_ORDEN_IA:
            minuto = int(t // 60)
            while len(j["acciones"]) <= minuto:
                j["acciones"].append(0)
            j["acciones"][minuto] += 1
        try:
            if comando == A_CONSTRUIR:
                _, _, _, edificio = struct.unpack_from("<h2xffI", datos)
                j["eventos"].append([t, EDIFICIO, edificio, 1])
                if edificio in DA_POBLACION:
                    cu[jugador][1].append((t, edificio))
            elif comando == A_INVESTIGAR:
                objeto, _, tech = struct.unpack_from("<Ihh", datos)
                if tech in CU_TECNOLOGIAS:
                    cu[jugador][0].append((t, (objeto,), tech, 1))
                if tech in EDADES:
                    edad = EDADES[tech]
                    if str(edad) not in j["edades"]:
                        j["edades"][str(edad)] = [t, round(t + DURACION_EDAD[tech], 1)]
                        j["eventos"].append([t, EDAD, tech, 1])
                else:
                    j["eventos"].append([t, TECNOLOGIA, tech, 1])
            elif comando == A_COLA:
                n, tipo, unidad, cantidad = struct.unpack_from("<h4xhhh", datos)
                if cantidad <= 0:
                    continue
                if tipo == CENTRO_URBANO and n > 0:
                    cu[jugador][0].append((t, struct.unpack_from(f"<{n}I", datos, 16), None, cantidad))
                elif unidad != ALDEANO:
                    cu[jugador][2].extend([t] * cantidad)
                if unidad == ALDEANO:
                    total = (j["aldeanos"][-1][1] if j["aldeanos"] else 0) + cantidad
                    j["aldeanos"].append([t, total])
                else:
                    j["eventos"].append([t, UNIDAD, unidad, cantidad])
        except struct.error:
            continue
    if not jugadores and duracion <= 0:
        raise AnalisisError("la repetición no tiene comandos")
    try:
        civs = {j.numero: j.civ for j in CB.leer(d).jugadores}
    except CB.CabeceraError:
        civs = {}
    for numero, j in jugadores.items():
        trabajos, edificios, militares = cu[numero]
        j["cu_paradas"] = paradas_cu(trabajos, edificios, militares, j["edades"], civs.get(numero, 0), duracion)
    return {"duracion": round(duracion), "jugadores": jugadores}


def _edad_en(edades: dict, t: float) -> int:
    """La edad en el segundo t, según la llegada estimada a cada una."""
    return 1 + sum(1 for e in ("2", "3", "4") if e in edades and edades[e][1] <= t)


def paradas_cu(trabajos: list, edificios: list, militares: list, edades: dict, civ: int,
               duracion: float) -> list[list]:
    """Los ratos con algún centro urbano parado: [[inicio, fin, motivo]], motivo COLA (no
    tenía nada en cola) o CASAS (tenía un aldeano esperando por falta de población).

    Es una estimación: la repetición solo guarda los clics. Se simula la cola de cada
    centro urbano (cada orden trae el suyo) con lo que tarda cada aldeano o tecnología,
    sin las bonificaciones de civilización salvo la de los persas. La población se cuenta
    con lo puesto en cola (las bajas no se saben) y los edificios que la dan, terminados
    a lo que tarda un aldeano en construirlos; por eso solo se mira hasta el clic en
    Castillos. Del primer centro urbano cuenta desde el inicio hasta el final; de los
    demás, solo entre un trabajo y el siguiente (no se sabe cuándo se terminan ni si los
    destruyen)."""
    colas: dict[int, list] = {}        # centro urbano -> [(clic, duración, es unidad)]
    previsto: dict[int, float] = {}    # centro urbano -> cuándo acabaría lo que tiene (para repartir)
    vistas: set[int] = set()
    for t, objetos, tech, n in sorted(trabajos, key=lambda x: x[0]):
        if tech in vistas:  # una tecnología se investiga una sola vez
            continue
        if tech is not None:
            vistas.add(tech)
        dur = CU_UNIDAD if tech is None else CU_TECNOLOGIAS[tech]
        for _ in range(n):
            # Con varios centros urbanos elegidos, al que antes queda libre.
            o = min(objetos, key=lambda o: (max(previsto.get(o, 0.0), t), o))
            colas.setdefault(o, []).append((t, dur, tech is None))
            previsto[o] = max(previsto.get(o, 0.0), t) + dur
    if not colas:
        return []
    primero = min(colas, key=lambda o: colas[o][0][0])
    # Población: lo que da cada edificio al terminarse, y la de partida.
    huecos = sorted((t + DA_POBLACION[e][1], 15 if e == CENTRO_URBANO and civ == CHINOS else DA_POBLACION[e][0])
                    for t, e in edificios)
    capacidad_inicial = 15 if civ == CHINOS else 5
    poblacion = {CHINOS: 7, MAYAS: 5}.get(civ, 4)
    clic_castillos = edades.get("3", [CASAS_HASTA])[0]
    casas_hasta = -1.0 if civ == HUNOS else min(CASAS_HASTA, clic_castillos)
    militares = sorted(militares)
    m = 0

    def capacidad(t: float) -> int:
        return min(POBLACION_MAX, capacidad_inicial + sum(p for fin, p in huecos if fin <= t))

    paradas: list[list] = []
    libre = {o: (0.0 if o == primero else colas[o][0][0]) for o in colas}
    while True:
        pendientes = [o for o in colas if colas[o]]
        if not pendientes:
            break
        o = min(pendientes, key=lambda o: (max(libre[o], colas[o][0][0]), o))
        clic, dur, es_unidad = colas[o].pop(0)
        if clic > libre[o]:
            paradas.append([libre[o], clic, COLA])
        inicio = max(libre[o], clic)
        while m < len(militares) and militares[m] <= inicio:
            m += 1
            poblacion += 1
        if es_unidad and inicio < casas_hasta and poblacion >= capacidad(inicio):
            # Espera a la primera casa que deje sitio (si no llega, hasta dejar de mirar).
            espera = next((fin for fin, _ in huecos if fin > inicio and capacidad(fin) > poblacion), None)
            fin_espera = casas_hasta if espera is None else min(espera, casas_hasta)
            if fin_espera > inicio:
                paradas.append([inicio, fin_espera, CASAS])
                inicio = fin_espera
        if es_unidad:
            poblacion += 1
        libre[o] = inicio + dur / RAPIDEZ_PERSAS[_edad_en(edades, inicio)] if civ == PERSAS else inicio + dur
    if libre[primero] < duracion:
        paradas.append([libre[primero], duracion, COLA])
    return [[round(a, 1), round(b, 1), motivo] for a, b, motivo in sorted(paradas) if b - a >= 0.05]


def cu_parado(datos: dict, t: float) -> dict:
    """El tiempo con el centro urbano parado hasta el segundo t: {"total": s, "casas": s
    (la parte por falta de población), "edades": {edad: s}} (ver paradas_cu)."""
    total = casas = 0.0
    por_edad: dict[int, float] = {}
    cortes = [0.0] + [datos["edades"][e][1] for e in ("2", "3", "4") if e in datos["edades"]] + [float("inf")]
    for a, b, motivo in datos.get("cu_paradas", []):
        b = min(b, t)
        if b <= a:
            continue
        total += b - a
        if motivo == CASAS:
            casas += b - a
        for k in range(len(cortes) - 1):  # el rato, repartido por edades
            tramo = min(b, cortes[k + 1]) - max(a, cortes[k])
            if tramo > 0:
                por_edad[k + 1] = por_edad.get(k + 1, 0.0) + tramo
    return {"total": round(total), "casas": round(casas), "edades": {e: round(s) for e, s in por_edad.items()}}


def analizar(ruta: Path) -> dict:
    try:
        return analizar_bytes(Path(ruta).read_bytes())
    except OSError as e:
        raise AnalisisError(f"no se pudo leer {Path(ruta).name}: {e}") from None


def aldeanos_en(serie: list, t: float) -> int:
    """Aldeanos puestos en cola hasta el segundo t."""
    total = 0
    for momento, n in serie:
        if momento > t:
            break
        total = n
    return total


NO_MILITARES = {ALDEANO, 13, 17, 128, 545, 2148}  # pesquero, barca y carreta mercante, transportes


def estado_en(datos: dict, t: float, duracion: float) -> dict:
    """Lo de un jugador hasta el segundo t (todo lo que mandó hacer hasta entonces):
    {"aldeanos": n, "militares": {unidad: n} (de más a menos), "apm": eAPM medio,
    "tecnologias": [[t, id]], "edades": [[edad, clic, llegada]], "cu": cu_parado}."""
    t = min(max(t, 0.0), float(duracion))
    militares: dict[int, int] = {}
    tecnologias: list[list] = []
    vistas: set[int] = set()
    for momento, tipo, id_, n in datos["eventos"]:
        if momento > t:
            break
        if tipo == UNIDAD and id_ not in NO_MILITARES:
            militares[id_] = militares.get(id_, 0) + n
        elif tipo == TECNOLOGIA and id_ not in vistas:
            vistas.add(id_)
            tecnologias.append([momento, id_])
    acciones = datos["acciones"]
    minuto = int(t // 60)
    total = sum(acciones[:minuto])
    if minuto < len(acciones):  # del minuto en curso, la parte hasta t (el último puede ser más corto)
        total += acciones[minuto] * min(1.0, (t - 60 * minuto) / max(1.0, min(60.0, duracion - 60 * minuto)))
    edades = sorted([int(e), c, ll] for e, (c, ll) in datos["edades"].items() if c <= t)
    return {"aldeanos": aldeanos_en(datos["aldeanos"], t),
            "militares": dict(sorted(militares.items(), key=lambda kv: -kv[1])),
            "apm": round(total / (t / 60)) if t >= 1 else 0,
            "tecnologias": tecnologias, "edades": edades, "cu": cu_parado(datos, t)}


# --- Repeticiones de prueba ----------------------------------------------------


def accion_prueba(jugador: int, comando: int, datos: bytes) -> bytes:
    """Un comando en el formato de DE (para las pruebas)."""
    cuerpo = bytes([comando]) + struct.pack("<bh", jugador, len(datos)) + datos
    return struct.pack("<II", OP_ACCION, len(cuerpo)) + cuerpo + struct.pack("<I", 0)


def sync_prueba(ms: int) -> bytes:
    """Sincronización corta: solo el incremento (la siguiente operación hace de marca)."""
    return struct.pack("<II", OP_SYNC, ms)


def construir_prueba(jugador: int, edificio: int) -> bytes:
    return accion_prueba(jugador, A_CONSTRUIR, struct.pack("<h2xffI", 1, 10.0, 10.0, edificio) + bytes(12) + bytes(4))


def investigar_prueba(jugador: int, tech: int) -> bytes:
    return accion_prueba(jugador, A_INVESTIGAR, struct.pack("<Ihh5x", 1, 1, tech) + bytes(4))


def cola_prueba(jugador: int, unidad: int, cantidad: int = 1) -> bytes:
    # El edificio es el objeto 1, el mismo en el que investiga investigar_prueba.
    return accion_prueba(jugador, A_COLA, struct.pack("<h4xhhh4xI", 1, 109, unidad, cantidad, 1))


def escribir_prueba(ruta: Path, jugadores: list, operaciones: bytes, **kw) -> Path:
    """Una repetición de prueba (cabecera de cabecera.escribir_prueba) con este cuerpo."""
    CB.escribir_prueba(ruta, jugadores, **kw)
    datos = ruta.read_bytes()
    tam = struct.unpack_from("<I", datos)[0]
    meta = struct.pack("<II", 5, 500) + bytes(20) + struct.pack("<I", 0)  # versión, metadatos
    # Como en las de verdad, empieza con una sincronización.
    ruta.write_bytes(datos[:tam] + meta + sync_prueba(0) + operaciones + struct.pack("<I", OP_POSTGAME))
    return ruta
