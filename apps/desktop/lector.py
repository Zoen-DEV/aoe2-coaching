"""Lee el estado de la guía que escribe el script XS del juego.

El script escribe, una vez por segundo, un archivo .xsdat con el nombre del mapa
(por ejemplo "[AoE2C] Arena.xsdat"). Todo son enteros de 32 bits:

    4722, versión (3), código de la guía, tiempo de juego, jugador, paso actual, número de pasos,
    hora de cada paso (-1 = pendiente, -2 = saltado), número de recuentos,
    cada recuento, número de tecnologías, estado de cada una (0/1/2),
    edad, población, espacio libre de población, casas en obra,
    civilización, número de tecnologías de la tierlist, estado de cada una (0/1/2, 3 = la
    civilización no la tiene), 9999

El código dice qué guía se está jugando (todos los mapas cargan el mismo script,
aoe2c_guia.xs, que es una copia de la guía elegida en el panel). La versión 2 no lleva
la civilización ni la tierlist (guías de antes de la 1.2.0 de la app). La versión 1 (sin
código) es la de antes; se reconoce la guía por el número de pasos y de datos.

Si el juego añade al final en vez de sobrescribir, el archivo contiene varios
registros seguidos; se usa el último completo.
"""

import json
import os
import struct
import time
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUIAS = HERE.parent.parent / "build" / "guias"  # los genera content/guias/build.py
INICIO, FIN, VERSION = 4722, 9999, 3


@dataclass
class Estado:
    tiempo: int
    jugador: int
    paso: int
    horas: list[int]
    datos: list[int]
    techs: list[int]
    edad: int
    poblacion: int
    libre: int
    casas_en_obra: int
    civ: int = 0  # ID de la civilización (0 = desconocida: registro de versión 1 o 2)
    tier: list[int] | None = None  # estado de cada tecnología de la tierlist (None = el registro no lo trae)
    mapa: str = ""  # nombre del .xsdat ("[AoE2C] Arena"); lo pone el Lector


def cargar_guias(carpeta: Path = GUIAS) -> dict[str, dict]:
    """Manifiestos generados por build.py, indexados por el id de la guía
    (fast_castle, scouts...), en orden de archivo."""
    guias = {}
    for path in sorted(carpeta.glob("*.json")):
        try:
            guia = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        guias[guia.get("id") or path.stem.removeprefix("guia_")] = guia
    return guias


def mapas_de(guias: dict[str, dict]) -> set[str]:
    """Nombres de los mapas [AoE2C] (en minúsculas), que son los de los .xsdat."""
    return {m.lower() for g in guias.values() for m in g.get("mapas", [])}


def es_mapa_aoe2c(nombre: str, conocidos: set[str] = frozenset()) -> bool:
    """Si un .xsdat es de un mapa [AoE2C]: los de los manifiestos y cualquier otro con el
    prefijo (los mapas que el catálogo añada después que la guía)."""
    nombre = nombre.lower()
    return nombre in conocidos or nombre.startswith("[aoe2c] ")


def parsear(data: bytes, guias) -> tuple[dict, Estado] | None:
    """Último registro completo, con la guía a la que corresponde. `guias` es un
    manifiesto, una lista o el diccionario de cargar_guias()."""
    if isinstance(guias, dict) and "pasos" in guias:
        guias = [guias]
    elif isinstance(guias, dict):
        guias = list(guias.values())
    marca = struct.pack("<i", INICIO)
    pos = data.rfind(marca)
    while pos >= 0:
        if pos % 4 == 0 and pos + 8 <= len(data):
            version = struct.unpack_from("<i", data, pos + 4)[0]
            if version in (2, 3) and pos + 12 <= len(data):
                codigo = struct.unpack_from("<i", data, pos + 8)[0]
                for guia in guias:
                    if guia.get("codigo") == codigo:
                        estado = _parsear_en(data, pos + 12, guia, version)
                        if estado:
                            return guia, estado
            elif version == 1:  # formato antiguo, sin código: la primera guía que encaje
                for guia in guias:
                    estado = _parsear_en(data, pos + 8, guia)
                    if estado:
                        return guia, estado
        pos = data.rfind(marca, 0, pos)
    return None


def _parsear_en(data: bytes, pos: int, guia: dict, version: int = 1) -> Estado | None:
    """Lee el cuerpo del registro (lo que va después de la cabecera)."""
    n_ints = (len(data) - pos) // 4
    vals = struct.unpack_from(f"<{n_ints}i", data, pos)
    try:
        i = 0
        tiempo, jugador, paso, n = vals[i : i + 4]
        i += 4
        if n != len(guia["pasos"]):
            return None
        horas = list(vals[i : i + n])
        i += n
        nd = vals[i]
        i += 1
        if nd != guia["num_datos"]:
            return None
        datos = list(vals[i : i + nd])
        i += nd
        nt = vals[i]
        i += 1
        if nt != guia["num_techs"]:
            return None
        techs = list(vals[i : i + nt])
        i += nt
        edad, poblacion, libre, en_obra = vals[i : i + 4]
        i += 4
        civ, tier = 0, None
        if version >= 3:
            civ, ntier = vals[i : i + 2]
            i += 2
            if ntier != len(guia.get("tierlist", {}).get("techs", [])):
                return None
            tier = list(vals[i : i + ntier])
            i += ntier
        fin = vals[i]
    except (IndexError, ValueError):
        return None
    if fin != FIN or not 0 <= paso <= n:
        return None
    return Estado(tiempo, jugador, paso, horas, datos, techs, edad, poblacion, libre, en_obra, civ, tier)


class Lector:
    """Busca el .xsdat más reciente de alguna guía y lo relee cuando cambia."""

    def __init__(self, perfil: Path | None = None, guias: dict[str, dict] | None = None) -> None:
        self.perfil = perfil  # carpeta del perfil del juego (rutas.py); None = no se lee nada
        self.guias = cargar_guias() if guias is None else guias
        self.mapas = mapas_de(self.guias)
        self.archivo: Path | None = None
        self.guia: dict | None = None
        self.estado: Estado | None = None
        self.mtime = 0.0
        self._ultima_busqueda = 0.0

    def _candidatos(self):
        # El juego escribe el archivo en la carpeta "profile" del perfil. Solo se miran
        # carpetas concretas, sin recorrer subcarpetas: una búsqueda amplia (por ejemplo
        # en Documentos) tardaba segundos y congelaba el overlay.
        if self.perfil is None:
            return
        perfil = Path(self.perfil)
        for carpeta in (perfil / "profile", perfil, perfil / "resources" / "_common" / "xs"):
            try:
                for entrada in os.scandir(carpeta):
                    if entrada.name.lower().endswith(".xsdat") and es_mapa_aoe2c(Path(entrada.name).stem, self.mapas):
                        yield Path(entrada.path)
            except OSError:
                continue

    def buscar(self) -> None:
        mejor = None
        for c in self._candidatos():
            try:
                m = c.stat().st_mtime
            except OSError:
                continue
            if mejor is None or m > mejor[0]:
                mejor = (m, c)
        if mejor and mejor[1] != self.archivo:
            self.archivo = mejor[1]
            self.mtime = 0.0  # otro mapa: se lee de nuevo aunque tenga la misma hora

    def actualizar(self) -> bool:
        """Relee el archivo si cambió. Devuelve True si hay estado nuevo."""
        ahora = time.time()
        if self.archivo is None or ahora - self._ultima_busqueda > 10:
            self._ultima_busqueda = ahora
            self.buscar()
        if self.archivo is None:
            return False
        try:
            m = self.archivo.stat().st_mtime
            if m == self.mtime:
                return False
            data = self.archivo.read_bytes()
        except OSError:
            return False
        leido = parsear(data, self.guias)
        if leido is None:
            return False  # archivo a medio escribir: se vuelve a intentar en la siguiente lectura
        self.mtime = m
        self.guia, self.estado = leido
        self.estado.mapa = self.archivo.stem
        return True

    def segundos_sin_datos(self) -> float:
        return time.time() - self.mtime if self.mtime else 1e9


def escribir_prueba(path: Path, guia: dict, estado: Estado, version: int = VERSION) -> None:
    """Escribe un .xsdat con el mismo formato que el juego (para probar el overlay)."""
    cabecera = [INICIO, version, guia["codigo"]] if version >= 2 else [INICIO, 1]
    vals = [*cabecera, estado.tiempo, estado.jugador, estado.paso, len(estado.horas), *estado.horas,
            len(estado.datos), *estado.datos, len(estado.techs), *estado.techs,
            estado.edad, estado.poblacion, estado.libre, estado.casas_en_obra]
    if version >= 3:
        tier = estado.tier if estado.tier is not None else [0] * len(guia.get("tierlist", {}).get("techs", []))
        vals += [estado.civ, len(tier), *tier]
    vals.append(FIN)
    path.write_bytes(struct.pack(f"<{len(vals)}i", *vals))
