"""Historial de partidas de la guía de apertura.

El overlay ya lee el estado de la partida cada segundo (ver lector.py). Este módulo
lo convierte en un registro por partida, con la hora de cada paso y de los hitos
(clic en Feudal, Feudal, clic en Castillos, Castillos), y lo guarda en
historial.json. No hace falta tocar el script XS del juego.

También calcula lo que se muestra en la ventana del historial: mejor marca, media,
tendencia y en qué tramos de la apertura se pierde más tiempo.
"""

import json
import os
from datetime import datetime
from pathlib import Path

import rutas  # noqa: E402
from textos import de, t as tx  # noqa: E402

ARCHIVO = rutas.HISTORIAL  # en %APPDATA%\AoE2Coaching\
SIN_DATOS = 4.0  # segundos sin datos nuevos para dar la partida por parada (pausa o fin)
VENTANA_MEDIA = 10  # partidas que entran en la media y en los puntos débiles

HITOS = [  # clave, nombre, edad y si es el clic (iniciada) o la llegada (terminada)
    ("clic_feudal", "Clic Feudal", "feudal", 1),
    ("feudal", "Feudal", "feudal", 2),
    ("clic_castillos", "Clic Castillos", "castillos", 1),
    ("castillos", "Castillos", "castillos", 2),
]
TECH_EDAD = {"feudal": "edad_feudal", "castillos": "edad_castillos"}
INVESTIGACION = {"feudal": 130, "castillos": 160}  # segundos que tarda cada edad en el centro urbano
ETIQUETA_EDAD = {"feudal": "Edad Feudal", "castillos": "Edad de los Castillos"}

# Qué hitos enseña cada guía. "meta" es la hora del último paso de la guía (en
# Scouts, los 6 exploradores). Las partidas antiguas, sin "vista", son de Fast Castle.
VISTA_FAST_CASTLE = {"hitos": ["clic_feudal", "feudal", "clic_castillos", "castillos"],
                     "series": ["feudal", "castillos"], "principal": "castillos", "nombre_meta": "Edad de los Castillos",
                     "nombre_meta_en": "Castle Age"}


def vista_de_guia(guia: dict) -> dict:
    return {
        "hitos": list(guia.get("hitos") or VISTA_FAST_CASTLE["hitos"]),
        "series": list(guia.get("series") or VISTA_FAST_CASTLE["series"]),
        "principal": guia.get("hito_principal") or "castillos",
        "nombre_meta": guia.get("nombre_meta") or guia["pasos"][-1]["titulo"],
        "nombre_meta_en": guia.get("nombre_meta_en") or guia["pasos"][-1].get("titulo_en", ""),
    }


def vista(registro: dict) -> dict:
    return registro.get("vista") or VISTA_FAST_CASTLE


def nombre_hito(registro: dict, clave: str) -> str:
    """Nombre del hito en el idioma elegido ("Castillos", "6 exploradores"...)."""
    return de(vista(registro), "nombre_meta") if clave == "meta" else tx(f"hito_{clave}")


def principal(registro: dict) -> str:
    """Clave del hito que resume la partida (Castillos en Fast Castle, la meta en Scouts)."""
    return vista(registro)["principal"]


def valor_principal(registro: dict):
    return registro["hitos"].get(principal(registro))


def migrar(registro: dict) -> dict:
    """Completa una partida guardada por una versión anterior (sin "meta" ni "vista")."""
    ultimo = registro["pasos"][-1] if registro.get("pasos") else None
    registro.setdefault("vista", dict(VISTA_FAST_CASTLE, nombre_meta=ultimo["titulo"] if ultimo else ""))
    registro.setdefault("hitos", {}).setdefault("meta", ultimo["hora"] if ultimo else None)
    registro.setdefault("referencias", {}).setdefault("meta", ultimo["referencia"] if ultimo else None)
    return registro


# --- Hitos a partir de la guía ------------------------------------------------


def indice_tech(guia: dict, edad: str) -> int | None:
    """Posición de la tecnología de la edad en el .xsdat."""
    techs = guia.get("techs")
    if techs and TECH_EDAD[edad] in techs:
        return techs.index(TECH_EDAD[edad])
    for p in guia["pasos"]:  # manifiestos antiguos: se reconoce por la etiqueta
        for c in p["condiciones"]:
            if c["tipo"] != "contador" and c["etiqueta"] == ETIQUETA_EDAD[edad]:
                return c["indice"]
    return None


def paso_del_hito(guia: dict, edad: str, objetivo: int) -> int | None:
    """Paso de la guía que equivale al hito: su única condición es esa edad
    iniciada (clic) o alcanzada (llegada)."""
    idx = indice_tech(guia, edad)
    for i, p in enumerate(guia["pasos"]):
        if len(p["condiciones"]) != 1 or idx is None:
            continue
        c = p["condiciones"][0]
        if c["tipo"] == "contador" or c["indice"] != idx:
            continue
        if objetivo == 1 and c["tipo"] == "tecnologia" and c["objetivo"] == 1:
            return i
        if objetivo == 2 and (c["tipo"] == "edad" or c["objetivo"] == 2):
            return i
    return None


def referencias_hitos(guia: dict) -> dict[str, int | None]:
    """Hora de referencia de cada hito: la del paso equivalente o, para la llegada
    sin paso propio, la del clic más lo que tarda la investigación."""
    refs: dict[str, int | None] = {}
    for clave, _, edad, objetivo in HITOS:
        i = paso_del_hito(guia, edad, objetivo)
        if i is not None:
            refs[clave] = guia["pasos"][i]["referencia"]
        elif objetivo == 2 and refs.get("clic_" + edad) is not None:
            refs[clave] = refs["clic_" + edad] + INVESTIGACION[edad]
        else:
            refs[clave] = None
    refs["meta"] = guia["pasos"][-1]["referencia"]
    return refs


# --- Seguimiento de la partida en curso ----------------------------------------


def nuevo_registro(guia: dict, mapa: str, fecha: datetime) -> dict:
    return {
        "id": fecha.strftime("%Y%m%d-%H%M%S"),
        "fecha": fecha.isoformat(timespec="seconds"),
        "mapa": mapa,
        "guia": guia["nombre"],
        "duracion": 0,
        "completada": False,
        "pasos": [{"titulo": p["titulo"], "titulo_en": p.get("titulo_en", ""), "referencia": p["referencia"],
                   "hora": None} for p in guia["pasos"]],
        "hitos": {**{clave: None for clave, *_ in HITOS}, "meta": None},
        "referencias": referencias_hitos(guia),
        "vista": vista_de_guia(guia),
        "escritura": 0.0,
    }


class Historial:
    """Lista de partidas guardada en un JSON, de la más antigua a la más reciente."""

    def __init__(self, archivo: Path | None = ARCHIVO):
        self.archivo = archivo  # None = solo en memoria (demo y pruebas)
        self.registros: list[dict] = []
        self.cargar()

    def cargar(self):
        if not self.archivo:
            return
        try:
            datos = json.loads(self.archivo.read_text(encoding="utf-8"))
            self.registros = [migrar(r) for r in datos.get("partidas", []) if isinstance(r, dict) and "id" in r]
        except (OSError, ValueError, AttributeError):
            self.registros = []

    def guardar(self):
        if not self.archivo:
            return
        tmp = self.archivo.with_suffix(".tmp")
        try:
            self.archivo.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps({"version": 1, "partidas": self.registros}, ensure_ascii=False, indent=1),
                           encoding="utf-8")
            os.replace(tmp, self.archivo)
        except OSError:
            pass

    def poner(self, registro: dict):
        """Añade el registro o sustituye el que tenga el mismo id."""
        for i, r in enumerate(self.registros):
            if r["id"] == registro["id"]:
                self.registros[i] = registro
                break
        else:
            self.registros.append(registro)
            self.registros.sort(key=lambda r: r["fecha"])

    def quitar(self, id_: str):
        self.registros = [r for r in self.registros if r["id"] != id_]

    def buscar(self, id_: str | None) -> dict | None:
        return next((r for r in self.registros if r["id"] == id_), None)

    def de_guia(self, nombre: str | None) -> list[dict]:
        return [r for r in self.registros if nombre is None or r["guia"] == nombre]

    def ultima_guia(self) -> str | None:
        return self.registros[-1]["guia"] if self.registros else None

    def guias(self) -> list[tuple[str, int]]:
        """Guías con partidas guardadas y cuántas, de la última jugada a la más antigua."""
        cuenta: dict[str, int] = {}
        for r in reversed(self.registros):
            cuenta[r["guia"]] = cuenta.get(r["guia"], 0) + 1
        return list(cuenta.items())


def pasos_hechos(registro: dict) -> int:
    return sum(1 for p in registro["pasos"] if p["hora"] is not None)


class Seguimiento:
    """Convierte las lecturas del .xsdat en registros del historial.

    - Una partida nueva empieza cuando cambia el mapa o el reloj vuelve atrás.
    - Los clics y las llegadas a cada edad se anotan al ver cambiar el estado de la
      tecnología (precisión de 1 s). Si el overlay se abrió tarde y no lo vio, se usa
      la hora del paso equivalente de la guía.
    - Cuando dejan de llegar datos (fin de la partida o pausa), se guarda y se avisa
      con `terminada` para que la ventana del historial se abra.
    - Al arrancar, si el último archivo es de una partida que no está en el
      historial (se jugó con el overlay cerrado), se importa.
    """

    def __init__(self, historial: Historial):
        self.historial = historial
        self.actual: dict | None = None
        self.vivo = False
        self.ultimo_tiempo = 0
        self.ultimo_estado_tech: dict[str, tuple[int, int]] = {}  # edad: (tiempo, estado)
        self.revisado_al_inicio = False
        self.terminada: str | None = None  # id de la partida que se acaba de parar
        self._firma_guardada = None

    def observar(self, guia: dict | None, estado, frescura: float, mapa: str | None, escritura: float,
                 ahora: datetime | None = None):
        if guia is None or estado is None or not mapa:
            return
        ahora = ahora or datetime.now()
        if frescura >= SIN_DATOS:
            if self.vivo:
                self.vivo = False
                self._guardar(forzar=True)
                if self.actual and pasos_hechos(self.actual) > 0:
                    self.terminada = self.actual["id"]
            elif not self.revisado_al_inicio:
                self._importar(guia, estado, mapa, escritura)
            self.revisado_al_inicio = True
            return
        self.revisado_al_inicio = True

        nueva = (self.actual is None or self.actual["mapa"] != mapa or self.actual["guia"] != guia["nombre"]
                 or estado.tiempo + 5 < self.ultimo_tiempo)
        if nueva:
            if self.actual is not None:
                self._guardar(forzar=True)
            self.actual = self._continuar(guia, estado, mapa, escritura) or self._nuevo(guia, mapa, ahora)
            self.ultimo_estado_tech = {}
            self._firma_guardada = None
        self.vivo = True
        self._anotar(guia, estado, escritura)
        self.ultimo_tiempo = estado.tiempo
        self._guardar()

    def _nuevo(self, guia: dict, mapa: str, fecha: datetime) -> dict:
        """Registro nuevo con un id que no esté ya en el historial."""
        r = nuevo_registro(guia, mapa, fecha)
        base, n = r["id"], 2
        while self.historial.buscar(r["id"]) is not None:
            r["id"] = f"{base}-{n}"
            n += 1
        return r

    def _continuar(self, guia: dict, estado, mapa: str, escritura: float) -> dict | None:
        """Si el overlay se reinició a mitad de partida, sigue el último registro
        en lugar de crear otro."""
        if not self.historial.registros:
            return None
        r = self.historial.registros[-1]
        if r["mapa"] != mapa or r["guia"] != guia["nombre"] or r["duracion"] > estado.tiempo:
            return None
        if escritura - r.get("escritura", 0) > 3 * 3600:
            return None
        for p, h in zip(r["pasos"], estado.horas):
            if p["hora"] is not None and p["hora"] != h:
                return None
        return r

    def _anotar(self, guia: dict, estado, escritura: float):
        r = self.actual
        r["duracion"] = estado.tiempo
        r["completada"] = estado.paso >= len(guia["pasos"])
        r["escritura"] = escritura
        for p, h in zip(r["pasos"], estado.horas):
            p["hora"] = h if h >= 0 else None
            if h == -2:
                p["saltado"] = True
        r["hitos"]["meta"] = r["pasos"][-1]["hora"] if r["pasos"] else None
        for clave, _, edad, objetivo in HITOS:
            idx = indice_tech(guia, edad)
            if idx is None or idx >= len(estado.techs):
                continue
            valor = estado.techs[idx]
            if r["hitos"][clave] is None and valor >= objetivo:
                anterior = self.ultimo_estado_tech.get(edad)
                # Solo vale si se vio el cambio (la lectura anterior era de hace poco y aún no lo cumplía).
                if anterior is not None and anterior[1] < objetivo and estado.tiempo - anterior[0] <= 3:
                    r["hitos"][clave] = estado.tiempo
                else:
                    i = paso_del_hito(guia, edad, objetivo)
                    if i is not None and estado.horas[i] >= 0:
                        r["hitos"][clave] = estado.horas[i]
        for edad in TECH_EDAD:
            idx = indice_tech(guia, edad)
            if idx is not None and idx < len(estado.techs):
                self.ultimo_estado_tech[edad] = (estado.tiempo, estado.techs[idx])

    def _importar(self, guia: dict, estado, mapa: str, escritura: float):
        if any(abs(r.get("escritura", 0) - escritura) < 2 for r in self.historial.registros):
            return
        r = self._nuevo(guia, mapa, datetime.fromtimestamp(escritura))
        self.actual = r
        self._anotar(guia, estado, escritura)
        self.actual = None
        if pasos_hechos(r) > 0:
            self.historial.poner(r)
            self.historial.guardar()

    def _guardar(self, forzar: bool = False):
        r = self.actual
        if r is None or pasos_hechos(r) == 0:
            return  # partidas sin ningún paso hecho no se guardan
        firma = (tuple(p["hora"] for p in r["pasos"]), tuple(r["hitos"].values()), r["completada"])
        if firma == self._firma_guardada and not forzar:
            return
        self._firma_guardada = firma
        self.historial.poner(r)
        self.historial.guardar()


# --- Estadísticas -------------------------------------------------------------


def media(valores: list[float]) -> float | None:
    return sum(valores) / len(valores) if valores else None


def resumen_hito(registros: list[dict], clave: str, n: int = VENTANA_MEDIA, excluir: str | None = None) -> dict:
    """Última marca, mejor, media de las últimas n y media de las n anteriores."""
    valores = [(r["id"], r["hitos"].get(clave)) for r in registros if r["id"] != excluir]
    valores = [(i, v) for i, v in valores if v is not None]
    solo = [v for _, v in valores]
    return {
        "ultimo": solo[-1] if solo else None,
        "mejor": min(solo) if solo else None,
        "media": media(solo[-n:]),
        "media_anterior": media(solo[-2 * n:-n]),
        "cuenta": len(solo),
    }


def tramos(registro: dict) -> list[dict]:
    """Por cada paso: su hora, desfase respecto a la referencia y tiempo perdido o
    ganado en el tramo (cuánto creció el desfase desde el paso hecho anterior)."""
    out = []
    desfase_anterior = 0
    for i, p in enumerate(registro["pasos"]):
        fila = {"n": i + 1, "titulo": de(p, "titulo"), "referencia": p["referencia"], "hora": p["hora"],
                "saltado": p.get("saltado", False), "desfase": None, "tramo": None}
        if p["hora"] is not None:
            fila["desfase"] = p["hora"] - p["referencia"]
            fila["tramo"] = fila["desfase"] - desfase_anterior
            desfase_anterior = fila["desfase"]
        out.append(fila)
    return out


def puntos_debiles(registros: list[dict], n: int = VENTANA_MEDIA) -> list[dict]:
    """Tramos de la apertura ordenados por el tiempo medio que se pierde en ellos,
    en las últimas n partidas."""
    ultimos = registros[-n:]
    if not ultimos:
        return []
    acumulado: dict[int, list[int]] = {}
    titulos: dict[int, str] = {}
    for r in ultimos:
        for fila in tramos(r):
            titulos.setdefault(fila["n"], fila["titulo"])
            if fila["tramo"] is not None:
                acumulado.setdefault(fila["n"], []).append(fila["tramo"])
    out = [{"n": k, "titulo": titulos[k], "media": media(v), "cuenta": len(v)} for k, v in acumulado.items()]
    out.sort(key=lambda d: -d["media"])
    return out


def comparacion_final(historial: Historial, registro: dict | None) -> str:
    """Una línea para la tarjeta final de la guía: esta partida frente a las anteriores."""
    if registro is None or valor_principal(registro) is None:
        return ""
    t = valor_principal(registro)
    anteriores = [r for r in historial.de_guia(registro["guia"]) if r["id"] != registro["id"]]
    res = resumen_hito(anteriores, principal(registro))
    if res["cuenta"] == 0:
        return tx("hi_primera")
    partes = []
    if t < res["mejor"]:
        partes.append(tx("hi_nueva_mejor", hora=reloj(res["mejor"])))
    else:
        partes.append(tx("hi_tu_mejor", hora=reloj(res["mejor"])))
    dif = round(t - res["media"])
    signo = "+" if dif > 0 else "−" if dif < 0 else "±"
    partes.append(tx("hi_media", hora=reloj(round(res["media"])), dif=f"{signo}{duracion(abs(dif))}"))
    return " · ".join(partes)


def reloj(seg: int | float | None) -> str:
    if seg is None:
        return "—"
    seg = max(0, int(round(seg)))
    return f"{seg // 60}:{seg % 60:02d}"


def duracion(seg: int) -> str:
    seg = int(round(seg))
    return f"{seg} s" if seg < 60 else reloj(seg)


# --- Datos de ejemplo (demo y capturas) ----------------------------------------


def historial_de_ejemplo(guia: dict, partidas: int = 14) -> Historial:
    """Historial inventado: una mejora gradual con algún tropiezo."""
    import random
    rnd = random.Random(7)
    h = Historial(None)
    base = datetime(2026, 10, 20, 19, 0)
    for k in range(partidas):
        fecha = base.replace(day=20 + k // 2, hour=19 + (k % 2) * 2)
        r = nuevo_registro(guia, ["[AoE2C] Arena", "[AoE2C] Arabia"][k % 2], fecha)
        retraso = max(0.0, 140 - 9 * k + rnd.randint(-15, 25))
        acumulado = 0.0
        for i, p in enumerate(r["pasos"]):
            acumulado += retraso / len(r["pasos"]) * (2.4 if i in (4, 5, 10) else 0.7)
            p["hora"] = int(p["referencia"] + acumulado + rnd.randint(-3, 3))
        r["duracion"] = r["pasos"][-1]["hora"] + 40
        r["completada"] = True
        def hora(edad, objetivo):
            i = paso_del_hito(guia, edad, objetivo)
            return r["pasos"][i]["hora"] if i is not None else None
        clic_f, clic_c = hora("feudal", 1), hora("castillos", 1)
        feudal = hora("feudal", 2) or (clic_f + INVESTIGACION["feudal"] + rnd.randint(0, 6) if clic_f else None)
        castillos = hora("castillos", 2) or (clic_c + INVESTIGACION["castillos"] if clic_c else None)
        r["hitos"] = {"clic_feudal": clic_f, "feudal": feudal, "clic_castillos": clic_c, "castillos": castillos,
                      "meta": r["pasos"][-1]["hora"]}
        h.poner(r)
    return h
