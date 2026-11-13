"""Tierlist de tecnologías que sale en el overlay al terminar la guía.

El manifiesto de la guía (content/guias/build.py) trae los niveles (S, A, B, C) y los
ajustes por mapa y civilización; el .xsdat (versión 3) trae la civilización y el estado
de cada tecnología. Aquí se juntan: se aplican los ajustes (cada «sube» o «baja» mueve
la tecnología un nivel), se quitan las que la civilización no tiene y cada una queda
marcada como pendiente, en curso o hecha.
"""

from dataclasses import dataclass, field

import civilizaciones
from lector import Estado

NIVELES = ("S", "A", "B", "C")
PENDIENTE, EN_CURSO, HECHA, SIN = 0, 1, 2, 3  # estados del .xsdat (3 = la civilización no la tiene)


@dataclass(frozen=True)
class Tecnologia:
    clave: str
    nombre: str
    estado: int  # PENDIENTE, EN_CURSO o HECHA
    id: int | None = None  # ID del juego (para su icono)


@dataclass
class Tierlist:
    civilizacion: str  # nombre de la civilización ("" si no se conoce)
    mapa: str  # nombre del mapa ("Arena"; "" si no se conoce)
    niveles: list[tuple[str, list[Tecnologia]]] = field(default_factory=list)  # solo los que tienen alguna

    @property
    def hechas(self) -> int:
        return sum(1 for _, techs in self.niveles for t in techs if t.estado == HECHA)

    @property
    def total(self) -> int:
        return sum(len(techs) for _, techs in self.niveles)


def id_mapa(nombre: str) -> str:
    """Id de mapas.json a partir del nombre del .xsdat: "[AoE2C] Black Forest" -> "black_forest"."""
    nombre = nombre.strip()
    if nombre.lower().startswith("[aoe2c]"):
        nombre = nombre[len("[aoe2c]"):]
    return "_".join(nombre.lower().split())


def nombre_mapa(nombre: str) -> str:
    """Nombre para mostrar: "[AoE2C] Black Forest" -> "Black Forest"."""
    nombre = nombre.strip()
    return nombre[len("[AoE2C]"):].strip() if nombre.lower().startswith("[aoe2c]") else nombre


def construir(guia: dict, estado: Estado, ingles: bool = False) -> Tierlist | None:
    """La tierlist de esta partida, o None si la guía no tiene o el registro no trae
    los estados (guías de antes de la versión 3 del .xsdat)."""
    datos = guia.get("tierlist")
    if not datos or estado.tier is None or len(estado.tier) != len(datos["techs"]):
        return None
    civ = datos.get("civilizaciones", {}).get(str(estado.civ), {})
    ajuste_mapa = datos.get("mapas", {}).get(id_mapa(estado.mapa), {})
    estados = dict(zip(datos["techs"], estado.tier))
    sin = set(civ.get("sin", []))

    nivel_de: dict[str, int] = {}
    orden: list[str] = []
    for n, nivel in enumerate(NIVELES):
        for clave in datos["niveles"].get(nivel, []):
            nivel_de[clave] = n
            orden.append(clave)
    for ajuste in (ajuste_mapa, civ):
        for clave in ajuste.get("sube", []):
            if clave in nivel_de:
                nivel_de[clave] = max(0, nivel_de[clave] - 1)
        for clave in ajuste.get("baja", []):
            if clave in nivel_de:
                nivel_de[clave] = min(len(NIVELES) - 1, nivel_de[clave] + 1)

    filas: list[list[Tecnologia]] = [[] for _ in NIVELES]
    for clave in orden:
        e = estados.get(clave, PENDIENTE)
        if e == SIN or clave in sin:
            continue
        nombres = datos["nombres"].get(clave) or [clave, clave]
        filas[nivel_de[clave]].append(Tecnologia(clave, nombres[1 if ingles else 0], min(e, HECHA),
                                                civilizaciones.TECNOLOGIAS.get(clave)))
    # Dentro de cada nivel, las pendientes primero: son las que quedan por investigar.
    niveles = [(nivel, sorted(fila, key=lambda t: t.estado == HECHA)) for nivel, fila in zip(NIVELES, filas) if fila]
    if not niveles:
        return None
    nombre_civ = civ.get("nombre_en" if ingles else "nombre", "")
    return Tierlist(nombre_civ, nombre_mapa(estado.mapa), niveles)
