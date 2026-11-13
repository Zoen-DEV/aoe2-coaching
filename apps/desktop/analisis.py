"""Lo que hizo cada jugador en una partida, sacado de los comandos de su repetición.

Detrás de la cabecera (cabecera.py), la repetición guarda la partida como una lista de
operaciones: comandos de los jugadores (construir, investigar, poner unidades en cola...)
y sincronizaciones que hacen avanzar el reloj del juego. Con ellas sale:

- el build order real: edificios, investigaciones y unidades, con el momento del clic;
- la subida de edad: el clic en Feudal, Castillos o Imperial y la llegada estimada
  (clic + lo que tarda la investigación sin bonificaciones de civilización);
- las acciones por minuto (los comandos que llegan a la repetición, eAPM);
- los aldeanos puestos en cola a lo largo de la partida.

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

    def de(n: int) -> dict:
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
            elif comando == A_INVESTIGAR:
                _, _, tech = struct.unpack_from("<Ihh", datos)
                if tech in EDADES:
                    edad = EDADES[tech]
                    if str(edad) not in j["edades"]:
                        j["edades"][str(edad)] = [t, round(t + DURACION_EDAD[tech], 1)]
                        j["eventos"].append([t, EDAD, tech, 1])
                else:
                    j["eventos"].append([t, TECNOLOGIA, tech, 1])
            elif comando == A_COLA:
                _, _, unidad, cantidad = struct.unpack_from("<h4xhhh", datos)
                if cantidad <= 0:
                    continue
                if unidad == ALDEANO:
                    total = (j["aldeanos"][-1][1] if j["aldeanos"] else 0) + cantidad
                    j["aldeanos"].append([t, total])
                else:
                    j["eventos"].append([t, UNIDAD, unidad, cantidad])
        except struct.error:
            continue
    if not jugadores and duracion <= 0:
        raise AnalisisError("la repetición no tiene comandos")
    return {"duracion": round(duracion), "jugadores": jugadores}


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
    "tecnologias": [[t, id]], "edades": [[edad, clic, llegada]]}."""
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
            "tecnologias": tecnologias, "edades": edades}


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
    return accion_prueba(jugador, A_COLA, struct.pack("<h4xhhh4x", 1, 109, unidad, cantidad) + bytes(4))


def escribir_prueba(ruta: Path, jugadores: list, operaciones: bytes, **kw) -> Path:
    """Una repetición de prueba (cabecera de cabecera.escribir_prueba) con este cuerpo."""
    CB.escribir_prueba(ruta, jugadores, **kw)
    datos = ruta.read_bytes()
    tam = struct.unpack_from("<I", datos)[0]
    meta = struct.pack("<II", 5, 500) + bytes(20) + struct.pack("<I", 0)  # versión, metadatos
    # Como en las de verdad, empieza con una sincronización.
    ruta.write_bytes(datos[:tam] + meta + sync_prueba(0) + operaciones + struct.pack("<I", OP_POSTGAME))
    return ruta
