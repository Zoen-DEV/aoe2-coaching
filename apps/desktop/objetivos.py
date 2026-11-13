"""Tiempo objetivo de cada paso de una guía en una partida clasificatoria (guía de ritmo).

En una clasificatoria no hay script XS que diga qué pasos van hechos: el overlay solo
sabe la hora de la partida. Para cada paso calcula a qué hora debería llegar este
jugador, a partir de sus prácticas con la guía (historial.py):

- base = mediana de sus últimas VENTANA prácticas en ese paso (sin saltados ni sin hacer);
- objetivo = base − ACERCAR × (base − referencia): un poco mejor que lo que suele hacer,
  nunca por debajo de la referencia de la guía;
- ajuste a la clasificatoria: si se sabe a qué hora hace clic en Feudal en sus ranked y en
  sus prácticas, todos los pasos se multiplican por (mediana en ranked / mediana en prácticas);
- con menos de MINIMO_PRACTICAS en ese paso: referencia × factor de su tramo de elo
  (TRAMOS_ELO).

Las guías con variantes por civilización se adaptan a la del jugador (lector.adaptar_a_civ)
y solo cuentan las prácticas de ese mismo paso en esa variante.

Todo es puro (sin archivos ni red): lo que hay que leer lo pasa quien llama.
"""

from dataclasses import dataclass
from statistics import median

from lector import adaptar_a_civ

VENTANA = 10          # prácticas (y ranked) que entran en cada mediana
MINIMO_PRACTICAS = 3  # por debajo, el paso sale del tramo de elo
ACERCAR = 0.25        # parte de la distancia a la referencia que se pide recortar

# Elo mínimo del tramo -> cuánto más lento que la referencia se juega, en general.
# La primera fila es la de elo desconocido (aún sin datos o sin rating).
TRAMOS_ELO = [
    (None, 1.20),
    (0, 1.35),
    (800, 1.25),
    (1000, 1.18),
    (1200, 1.12),
    (1400, 1.07),
    (1700, 1.03),
    (2000, 1.00),
]

PRACTICA, ELO = "practica", "elo"  # de dónde sale el objetivo de un paso


@dataclass(frozen=True)
class Objetivo:
    paso: int
    referencia: int  # la de la guía (ya adaptada a la civilización)
    segundos: int    # hora objetivo
    origen: str      # PRACTICA o ELO
    practicas: int   # prácticas que entraron en la base


def factor_elo(elo: int | None, tramos: list = TRAMOS_ELO) -> float:
    if elo is None:
        return tramos[0][1]
    factor = tramos[1][1]
    for minimo, f in tramos[1:]:
        if elo >= minimo:
            factor = f
    return factor


def _tiene_variantes(paso: dict) -> bool:
    return bool(paso.get("civs"))


def horas_practica(registros: list[dict], guia: dict, i: int, paso_adaptado: dict) -> list[int]:
    """Horas del paso i en las prácticas de esta guía, de la más vieja a la más reciente.
    Fuera los saltados y los que no llegó a hacer. Si el paso cambia con la civilización,
    solo las prácticas con esa misma variante (mismo título y referencia)."""
    original = guia["pasos"][i]
    horas = []
    for r in registros:
        if r.get("guia") != guia["nombre"] or i >= len(r.get("pasos", [])):
            continue
        p = r["pasos"][i]
        if p.get("titulo") != paso_adaptado["titulo"] and p.get("titulo") != original["titulo"]:
            continue  # la guía cambió de pasos: este no es el mismo
        if _tiene_variantes(original) and (p.get("titulo") != paso_adaptado["titulo"]
                                           or p.get("referencia") != paso_adaptado["referencia"]):
            continue  # otra variante de civilización
        h = p.get("hora")
        if p.get("saltado") or h is None or h == "saltado" or not isinstance(h, (int, float)) or h < 0:
            continue
        horas.append(h)
    return horas


def clic_feudal_practicas(registros: list[dict], guia_nombre: str | None = None) -> list[float]:
    """Clics en Feudal de las prácticas (de una guía, o de todas con None)."""
    return [r["hitos"]["clic_feudal"] for r in registros
            if (guia_nombre is None or r.get("guia") == guia_nombre)
            and isinstance((r.get("hitos") or {}).get("clic_feudal"), (int, float))]


def factor_ranked(clics_ranked: list[float], clics_practica: list[float]) -> float | None:
    """Mediana del clic en Feudal en ranked / en prácticas (las últimas VENTANA de cada lado).
    None si falta alguno de los dos."""
    ranked = [c for c in clics_ranked if c and c > 0][-VENTANA:]
    practica = [c for c in clics_practica if c and c > 0][-VENTANA:]
    if not ranked or not practica:
        return None
    return median(ranked) / median(practica)


def calcular(guia: dict, registros: list[dict], civ: int = 0, elo: int | None = None,
             clics_ranked: list[float] | None = None) -> list[Objetivo]:
    """El objetivo de cada paso de la guía (manifiesto sin adaptar) para esta civilización.
    registros: el historial de prácticas, del más viejo al más reciente."""
    adaptada = adaptar_a_civ(guia, civ) if civ else guia
    f_ranked = factor_ranked(clics_ranked or [], clic_feudal_practicas(registros, guia["nombre"]))
    f_elo = factor_elo(elo)
    objetivos = []
    for i, paso in enumerate(adaptada["pasos"]):
        ref = paso["referencia"]
        horas = horas_practica(registros, guia, i, paso)[-VENTANA:]
        if len(horas) >= MINIMO_PRACTICAS:
            base = median(horas)
            segundos = max(ref, base - ACERCAR * (base - ref))
            if f_ranked is not None:
                segundos = max(ref, segundos * f_ranked)
            objetivos.append(Objetivo(i, ref, round(segundos), PRACTICA, len(horas)))
        else:
            objetivos.append(Objetivo(i, ref, round(ref * f_elo), ELO, len(horas)))
    # Una hora objetivo no puede ir antes que la del paso anterior.
    for i in range(1, len(objetivos)):
        if objetivos[i].segundos < objetivos[i - 1].segundos:
            o = objetivos[i]
            objetivos[i] = Objetivo(o.paso, o.referencia, objetivos[i - 1].segundos, o.origen, o.practicas)
    return objetivos


def paso_actual(objetivos: list[Objetivo], tiempo: float) -> int:
    """El paso que toca a esta hora: el primero cuyo objetivo aún no pasó (len si ya
    pasaron todos)."""
    for o in objetivos:
        if o.segundos >= tiempo:
            return o.paso
    return len(objetivos)
