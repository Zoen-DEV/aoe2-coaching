"""Construye el mod "AoE2 Coaching" (guía de apertura hasta Castillos).

Por cada build order de build_orders/*.json genera un script XS con la guía (los
pasos se convierten en funciones XS) y el manifiesto que lee el overlay.

Los mapas (mapas.json) son copias de mapas oficiales que cargan un script común,
aoe2c_guia.xs. Ese archivo es una copia del script de la guía elegida en el panel
de AoE2C (instalador.py lo cambia); así los mismos mapas sirven para todas las guías.

El mod se escribe en build/mods/guia-apertura-castillos/ (con la estructura que espera el
juego) y los manifiestos del overlay en build/guias/, los dos en la raíz del monorepo.

Uso: py content/guias/build.py [build_order.json ...] [--install] [--ascii] [--pruebas]

--install  copia el mod a la carpeta de mods locales y los .xs a la carpeta xs
           del perfil (el juego no encuentra los .xs que están dentro de un mod).
--ascii    escribe los textos sin tildes ni eñes, en vez de construirlas con chr().
--pruebas  añade los mapas de prueba de content/guias/pruebas/ (copias de Arena que cargan
           scripts de diagnóstico).
"""

import json
import re
import shutil
import zlib
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAIZ = HERE.parent.parent  # raíz del monorepo
SALIDA = RAIZ / "build"  # todo lo generado (ignorado por git)
GAME = Path(r"C:\Program Files (x86)\Steam\steamapps\common\AoE2DE")
GAME_MAPS = GAME / "resources" / "_common" / "drs" / "gamedata_x2"
PROFILE = Path(r"C:\Users\User\Games\Age of Empires 2 DE\76561199524040890")
LOCAL_MODS = PROFILE / "mods" / "local"
PROFILE_XS = PROFILE / "resources" / "_common" / "xs"
INSTALL_NAME = "guia-apertura-castillos"

BUILD_ORDERS = HERE / "build_orders"
CATALOGO_MAPAS = RAIZ / "content" / "mapas" / "mapas.json"
XS_COMUN = "aoe2c_guia.xs"  # el script que cargan todos los mapas: copia de la guía elegida
GUIA_POR_DEFECTO = "fast_castle"
CONFIG_OVERLAY = RAIZ / "apps" / "desktop" / "config.json"  # guarda la guía elegida en el panel
XS_SOURCES = HERE / "xs"
PRUEBAS_DIR = HERE / "pruebas"
PRUEBAS = [  # (script de diagnóstico, nombre del mapa); el mapa base es Arena
    ("prueba_panel.xs", "Arena Prueba 4 panel.rms"),
]
MOD_DIR = SALIDA / "mods" / INSTALL_NAME
OUT_XS = MOD_DIR / "resources" / "_common" / "xs"
OUT_RMS = MOD_DIR / "resources" / "_common" / "random-map-scripts"

INFO = {
    "Title": "AoE2 Coaching",
    "Description": (
        "Mapas con una guía paso a paso de la apertura (Fast Castle, Scouts...). La guía se elige en el "
        "panel de AoE2C. Cada paso se marca solo al cumplirse y te dice si vas adelantado o tarde. "
        "En la sala elige Estilo de mapa: Personalizado y un mapa \"[AoE2C] ...\"."
    ),
    "Author": "enzoholgadodev",
}

# Ancho aproximado del panel de instrucciones (caracteres por línea antes de partirla).
ANCHO_PANEL = 50
MAX_TITULO = 32

# --- Vocabulario de las build orders ----------------------------------------
# IDs comprobados con los datos del juego (resources/_common/dat/CivTechTrees,
# random_map.def y Effects.xs). Las etiquetas son las del progreso del panel.

EDIFICIOS = {  # nombre: (ID, etiqueta singular, etiqueta plural)
    "casa": (70, "Casa", "Casas"),
    "molino": (68, "Molino", "Molinos"),
    "campamento_maderero": (562, "Campamento", "Campamentos"),
    "campamento_minero": (584, "Campamento minero", "Campamentos mineros"),
    "granja": (50, "Granja", "Granjas"),
    "mercado": (84, "Mercado", "Mercados"),
    "herreria": (103, "Herrería", "Herrerías"),
    "cuartel": (12, "Cuartel", "Cuarteles"),
    "centro_urbano": (109, "Centro urbano", "Centros urbanos"),
    "establo": (101, "Establo", "Establos"),
}

# Unidades militares (se cuentan las vivas; la inicial también cuenta).
UNIDADES = {  # nombre: (etiqueta, IDs)
    "exploradores": ("Exploradores", [448]),  # caballería de exploración
}

# El aldeano cambia de unidad según su tarea; cada tarea tiene una ID por sexo.
_TAREAS_BASE = {
    "pastores": ("Pastores", [590, 592]),
    "lenadores": ("Leñadores", [123, 218]),
    "cazadores": ("Cazadores", [122, 216]),
    "recolectores": ("Bayas", [120, 354]),
    "mineros_oro": ("Oro", [579, 581]),
    "mineros_piedra": ("Piedra", [124, 220]),
    "granjeros": ("Granjeros", [214, 259, 1891, 1892]),  # incluye pastoreo en pastos
    "pescadores": ("Pescadores", [56, 57, 2333, 2334]),  # incluye ostras
    "constructores": ("Constructores", [118, 212]),
}
TAREAS = dict(_TAREAS_BASE)
TAREAS["comida"] = (
    "En comida",
    [i for k in ("pastores", "cazadores", "recolectores", "granjeros", "pescadores") for i in _TAREAS_BASE[k][1]],
)
TAREAS["todos"] = ("Aldeanos", None)  # None = recurso "población de aldeanos" del jugador

TECNOLOGIAS = {  # nombre: (ID, etiqueta)
    "telar": (22, "Telar"),
    "edad_feudal": (101, "Edad Feudal"),
    "edad_castillos": (102, "Edad de los Castillos"),
    "edad_imperial": (103, "Edad Imperial"),
    "hacha_doble_filo": (202, "Hacha de doble filo"),
    "sierra_de_arco": (203, "Sierra de arco"),
    "collera": (14, "Collera"),
    "arado_pesado": (13, "Arado pesado"),
    "carretilla": (213, "Carretilla"),
    "mineria_aurifera": (55, "Minería aurífera"),
}
ESTADOS_TECH = {"iniciada": 1, "terminada": 2}  # iniciada = en cola, investigándose o terminada

EDADES = {  # nombre: (valor del recurso "edad actual", tecnología de la edad)
    "feudal": (1, "edad_feudal"),
    "castillos": (2, "edad_castillos"),
    "imperial": (3, "edad_imperial"),
}

ICONOS = {  # icono del panel: ID de la unidad o edificio que se muestra
    "casa": 70,
    "molino": 68,
    "campamento_maderero": 562,
    "campamento_minero": 584,
    "granja": 50,
    "mercado": 84,
    "herreria": 103,
    "cuartel": 12,
    "centro_urbano": 109,
    "castillo": 82,
    "aldeano": 83,
    "oveja": 594,
    "jabali": 48,
    "establo": 101,
    "explorador": 448,
}

ID_CASA = EDIFICIOS["casa"][0]
CLAVES_BUILD_ORDER = {
    "id", "nombre", "descripcion", "descripcion_en", "nivel", "mapas_recomendados", "hitos", "series",
    "hito_principal", "titulo_final", "icono_final", "archivo_xs", "margen_segundos", "aviso_casas",
    "overlay", "panel_juego",
    "pasos_hechos_visibles", "pasos_siguientes_visibles", "mensaje_final", "pasos",
}
OVERLAY_GUIAS = SALIDA / "guias"  # manifiestos que lee el overlay externo
CLAVES_MAPA = {"id", "base", "archivo", "nombre", "tipo", "descripcion", "guias"}
CLAVES_MAPA_OPCIONALES = {"imagen"}
HITOS_VALIDOS = ["clic_feudal", "feudal", "clic_castillos", "castillos", "meta"]  # meta = último paso
NIVELES = ("facil", "media", "dificil")
CLAVES_PASO = {"titulo", "texto", "icono", "referencia", "condiciones"}


class BuildOrderError(Exception):
    pass


# --- Lectura y validación ----------------------------------------------------


def parse_time(value: str, where: str) -> int:
    m = re.fullmatch(r"(\d+):([0-5]\d)", str(value))
    if not m:
        raise BuildOrderError(f"{where}: la referencia debe tener el formato m:ss, no {value!r}")
    return int(m.group(1)) * 60 + int(m.group(2))


def check_chars(value: str, where: str) -> None:
    """Solo ASCII imprimible y caracteres latinos (U+00A0 a U+00FF): el panel del
    juego muestra los demás como "?"."""
    bad = sorted({c for c in value if not (32 <= ord(c) < 127 or 0xA0 <= ord(c) <= 0xFF)})
    if bad:
        raise BuildOrderError(f"{where}: caracteres que el juego no muestra {bad} en {value!r}. "
                              "Usa solo letras latinas (á, ñ, ü...), · « » ¡ ¿ y similares.")


def check_text(value, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BuildOrderError(f"{where}: falta el texto")
    for bad, why in (("%", "cuelga el juego en el chat"), ('"', "rompe las cadenas de XS"),
                     ("'", "XS no admite comillas simples"), ("\\", "XS no admite barras invertidas"),
                     ("<", "el juego lo toma como etiqueta de color")):
        if bad in value:
            raise BuildOrderError(f"{where}: el texto no puede llevar {bad!r} ({why}): {value!r}")
    check_chars(value, where)
    return value


def check_condition(cond: dict, where: str) -> dict:
    if not isinstance(cond, dict):
        raise BuildOrderError(f"{where}: cada condición es un objeto JSON")
    kinds = [k for k in ("edificio", "aldeanos", "unidades", "tecnologia", "edad") if k in cond]
    if len(kinds) != 1:
        raise BuildOrderError(f"{where}: cada condición lleva una sola clave de tipo "
                              f"(edificio, aldeanos, unidades, tecnologia o edad): {cond}")
    kind = kinds[0]
    allowed = {"edificio": {"edificio", "min"}, "aldeanos": {"aldeanos", "min"}, "unidades": {"unidades", "min"},
               "tecnologia": {"tecnologia", "estado"}, "edad": {"edad"}}[kind]
    extra = set(cond) - allowed
    if extra:
        raise BuildOrderError(f"{where}: claves desconocidas {sorted(extra)} en {cond}")
    table = {"edificio": EDIFICIOS, "aldeanos": TAREAS, "unidades": UNIDADES, "tecnologia": TECNOLOGIAS,
             "edad": EDADES}[kind]
    if cond[kind] not in table:
        raise BuildOrderError(f"{where}: {kind} desconocido {cond[kind]!r}. Valores válidos: {', '.join(table)}")
    if kind in CONTADORES:
        if not isinstance(cond.get("min"), int) or cond["min"] < 1:
            raise BuildOrderError(f"{where}: 'min' debe ser un entero mayor que 0 en {cond}")
    if kind == "tecnologia" and cond.get("estado") not in ESTADOS_TECH:
        raise BuildOrderError(f"{where}: 'estado' debe ser {' o '.join(ESTADOS_TECH)} en {cond}")
    return cond


CONTADORES = ("edificio", "aldeanos", "unidades")  # condiciones que comparan un recuento con un mínimo


def check_count(data: dict, key: str, name: str) -> None:
    if not isinstance(data[key], int) or not 0 <= data[key] <= 5:
        raise BuildOrderError(f"{name}: {key} debe ser un entero entre 0 y 5")


def load_build_order(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    name = path.name
    missing = CLAVES_BUILD_ORDER - set(data)
    extra = set(data) - CLAVES_BUILD_ORDER
    if missing:
        raise BuildOrderError(f"{name}: faltan las claves {sorted(missing)}")
    if extra:
        raise BuildOrderError(f"{name}: claves desconocidas {sorted(extra)}")
    for key in ("nombre", "mensaje_final", "titulo_final"):
        check_text(data[key], f"{name} > {key}")
    for key in ("descripcion", "descripcion_en"):
        if not isinstance(data[key], str) or not data[key].strip():
            raise BuildOrderError(f"{name}: falta el texto de {key}")
    if not re.fullmatch(r"[a-z0-9_]+", str(data["id"])):
        raise BuildOrderError(f"{name}: id debe ser minúsculas, números y _ (por ejemplo fast_castle)")
    if data["archivo_xs"] == XS_COMUN:
        raise BuildOrderError(f"{name}: {XS_COMUN} está reservado para el script común de los mapas")
    if not re.fullmatch(r"[A-Za-z0-9_]+\.xs", data["archivo_xs"]):
        raise BuildOrderError(f"{name}: archivo_xs debe ser un nombre simple sin espacios que acabe en .xs")
    if data["nivel"] not in NIVELES:
        raise BuildOrderError(f"{name}: nivel debe ser {', '.join(NIVELES)}")
    ids_mapas = {m["id"] for m in load_maps()}
    if not isinstance(data["mapas_recomendados"], list) or set(data["mapas_recomendados"]) - ids_mapas:
        raise BuildOrderError(f"{name}: mapas_recomendados debe ser una lista de ids de mapas.json "
                              f"({', '.join(sorted(ids_mapas))})")
    hitos = data["hitos"]
    if (not isinstance(hitos, list) or not hitos or set(hitos) - set(HITOS_VALIDOS)
            or len(set(hitos)) != len(hitos)):
        raise BuildOrderError(f"{name}: hitos debe ser una lista sin repetir de {', '.join(HITOS_VALIDOS)}")
    if not isinstance(data["series"], list) or not 1 <= len(data["series"]) <= 2 or set(data["series"]) - set(hitos):
        raise BuildOrderError(f"{name}: series lleva 1 o 2 de los hitos (las líneas del gráfico de evolución)")
    if data["hito_principal"] not in hitos:
        raise BuildOrderError(f"{name}: hito_principal debe ser uno de los hitos")
    if data["icono_final"] not in ICONOS:
        raise BuildOrderError(f"{name}: icono_final desconocido {data['icono_final']!r}")
    if not isinstance(data["margen_segundos"], int) or data["margen_segundos"] < 0:
        raise BuildOrderError(f"{name}: margen_segundos debe ser un entero >= 0")
    for key in ("aviso_casas", "overlay", "panel_juego"):
        if not isinstance(data[key], bool):
            raise BuildOrderError(f"{name}: {key} debe ser true o false")
    if not (data["overlay"] or data["panel_juego"]):
        raise BuildOrderError(f"{name}: overlay y panel_juego no pueden estar los dos en false")
    check_count(data, "pasos_hechos_visibles", name)
    check_count(data, "pasos_siguientes_visibles", name)
    steps = data["pasos"]
    if not isinstance(steps, list) or not steps:
        raise BuildOrderError(f"{name}: 'pasos' debe ser una lista con al menos un paso")
    last = -1
    for n, step in enumerate(steps, 1):
        where = f"{name} > paso {n}"
        missing = CLAVES_PASO - set(step)
        extra = set(step) - CLAVES_PASO
        if missing or extra:
            raise BuildOrderError(f"{where}: faltan {sorted(missing)} / sobran {sorted(extra)}")
        check_text(step["titulo"], f"{where} > titulo")
        check_text(step["texto"], f"{where} > texto")
        if len(step["titulo"]) > MAX_TITULO:
            print(f"aviso: {where}: el título tiene {len(step['titulo'])} caracteres; "
                  f"con más de {MAX_TITULO} su línea del panel se parte en dos")
        if step["icono"] not in ICONOS:
            raise BuildOrderError(f"{where}: icono desconocido {step['icono']!r}. Valores válidos: {', '.join(ICONOS)}")
        step["segundos"] = parse_time(step["referencia"], where)
        if step["segundos"] < last:
            print(f"aviso: {where}: la referencia {step['referencia']} es anterior a la del paso previo")
        last = step["segundos"]
        if not step["condiciones"]:
            raise BuildOrderError(f"{where}: necesita al menos una condición")
        for cond in step["condiciones"]:
            check_condition(cond, where)
    return data


# --- Generación de XS ----------------------------------------------------------
# Los textos se escriben tal cual (con tildes); encode_strings los convierte
# después en expresiones ASCII.


def xs_str(text: str) -> str:
    return '"' + text + '"'


def counters(bo: dict) -> list[tuple[str, str]]:
    """Recuentos que necesitan las condiciones, en orden: [("edificio", "casa"), ("aldeanos", "pastores")...]."""
    out: list[tuple[str, str]] = []
    for step in bo["pasos"]:
        for cond in step["condiciones"]:
            for kind in CONTADORES:
                if kind in cond and (kind, cond[kind]) not in out:
                    out.append((kind, cond[kind]))
    return out


def techs(bo: dict) -> list[str]:
    """Tecnologías cuyo estado se vuelca al overlay, en orden (las de las condiciones
    y las de las edades)."""
    out: list[str] = []
    for step in bo["pasos"]:
        for cond in step["condiciones"]:
            name = cond.get("tecnologia") or (EDADES[cond["edad"]][1] if "edad" in cond else None)
            if name and name not in out:
                out.append(name)
    return out


def counter_lines(kind: str, name: str) -> list[str]:
    """Líneas XS que dejan un recuento en la variable n (sumando de uno en uno)."""
    if kind == "edificio":
        return [f"n = guiaTerminados(jugador, {EDIFICIOS[name][0]});"]
    ids = UNIDADES[name][1] if kind == "unidades" else TAREAS[name][1]
    if ids is None:
        return ["n = guiaAldeanosTotal(jugador);"]
    return [f"n = guiaUnidades(jugador, {ids[0]});"] + [f"n = n + guiaUnidades(jugador, {x});" for x in ids[1:]]


def cond_value_expr(cond: dict, index: dict) -> str:
    """Expresión XS con el valor actual que se compara en la condición."""
    for kind in CONTADORES:
        if kind in cond:
            return f"guiaDato({index[(kind, cond[kind])]})"
    if "tecnologia" in cond:
        return f"guiaEstadoTech(jugador, {TECNOLOGIAS[cond['tecnologia']][0]})"
    return "guiaEdad(jugador)"


def cond_label(cond: dict) -> str:
    """Etiqueta de una condición de recuento ("Casas", "Leñadores", "Exploradores"...)."""
    if "edificio" in cond:
        _, singular, plural = EDIFICIOS[cond["edificio"]]
        return singular if cond["min"] == 1 else plural
    if "unidades" in cond:
        return UNIDADES[cond["unidades"]][0]
    return TAREAS[cond["aldeanos"]][0]


def es_contador(cond: dict) -> bool:
    return any(k in cond for k in CONTADORES)


def cond_target(cond: dict) -> int:
    if es_contador(cond):
        return cond["min"]
    if "tecnologia" in cond:
        return ESTADOS_TECH[cond["estado"]]
    return EDADES[cond["edad"]][0]


def cond_progress_expr(cond: dict, index: dict) -> str:
    """Expresión XS (cadena) con el progreso de la condición, p. ej. "Casas 1/2"."""
    if es_contador(cond):
        label = cond_label(cond)
        n = cond["min"]
        return f'"{label} " + guiaMin({cond_value_expr(cond, index)}, {n}) + "/{n}"'
    if "tecnologia" in cond:
        tech, label = TECNOLOGIAS[cond["tecnologia"]]
    else:
        tech, label = TECNOLOGIAS[EDADES[cond["edad"]][1]]
    return f'"{label}: " + guiaTextoEstado(guiaEstadoTech(jugador, {tech}))'


def if_chain(func_header: str, var_type: str, cases: list[str], default: str) -> str:
    """Función XS que devuelve un valor según el número de paso (lo guarda en una
    variable antes del return, que en XS es más fiable que devolver expresiones)."""
    lines = [func_header, "{", f"    {var_type} v = {default};"]
    for i, value in enumerate(cases):
        lines += [f"    if (paso == {i})", "    {", f"        v = {value};", "    }"]
    lines += ["    return (v);", "}", ""]
    return "\n".join(lines)


def generate_steps_xs(bo: dict) -> str:
    steps = bo["pasos"]
    cnt = counters(bo)
    index = {c: i for i, c in enumerate(cnt)}
    out = [
        "// ---------------------------------------------------------------------------",
        "// Build order generada desde build_orders (no editar aqui).",
        "// ---------------------------------------------------------------------------",
        "",
        f"const int cGuiaCodigo = {codigo_guia(bo)};",
        f"const int cGuiaNumPasos = {len(steps)};",
        f"const int cGuiaNumDatos = {max(1, len(cnt))};",
        f"const int cGuiaMargen = {bo['margen_segundos']};",
        f"const int cGuiaAvisoCasas = {1 if bo['aviso_casas'] else 0};",
        f"const int cGuiaOverlay = {1 if bo['overlay'] else 0};",
        f"const int cGuiaPanelJuego = {1 if bo['panel_juego'] else 0};",
        f"const int cGuiaHechosVisibles = {bo['pasos_hechos_visibles']};",
        f"const int cGuiaSiguientesVisibles = {bo['pasos_siguientes_visibles']};",
        f"const int cGuiaIdCasa = {ID_CASA};",
        "",
        "string guiaNombre()",
        "{",
        f"    string v = {xs_str(bo['nombre'])};",
        "    return (v);",
        "}",
        "",
        "string guiaMensajeFinal()",
        "{",
        f"    string v = {xs_str(bo['mensaje_final'])};",
        "    return (v);",
        "}",
        "",
    ]

    # Recuentos del jugador, una vez por segundo.
    out += ["void guiaTomarDatos(int jugador = 0)", "{", "    int n = 0;"]
    for i, (kind, name) in enumerate(cnt):
        out.append(f"    // {i}: {kind} {name}")
        out += [f"    {line}" for line in counter_lines(kind, name)]
        out.append(f"    xsArraySetInt(gGuiaDatos, {i}, n);")
    out += ["}", ""]

    # Estado de las tecnologías, para el archivo del overlay (mismo orden que el manifiesto).
    tlist = techs(bo)
    out += ["void guiaEscribirTechs(int jugador = 0)", "{", f"    xsWriteInt({len(tlist)});", "    int e = 0;"]
    for name in tlist:
        out += [f"    e = guiaEstadoTech(jugador, {TECNOLOGIAS[name][0]});  // {name}", "    xsWriteInt(e);"]
    out += ["}", ""]

    # Condición de cada paso: se cumplen todas o ninguna.
    out += ["bool guiaCumplido(int jugador = 0, int paso = 0)", "{"]
    for i, step in enumerate(steps):
        out += [f"    if (paso == {i})", "    {"]
        for cond in step["condiciones"]:
            out += [f"        if ({cond_value_expr(cond, index)} < {cond_target(cond)})", "        {",
                    "            return (false);", "        }"]
        out += ["        return (true);", "    }"]
    out += ["    return (false);", "}", ""]

    # Progreso del paso actual.
    out += ["string guiaProgreso(int jugador = 0, int paso = 0)", "{", '    string v = "";']
    for i, step in enumerate(steps):
        expr = ' + " · " + '.join(cond_progress_expr(c, index) for c in step["condiciones"])
        expr = expr.replace('" + "', "")  # une literales seguidos: "/1" + " · " -> "/1 · "
        out += [f"    if (paso == {i})", "    {", f"        v = {expr};", "    }"]
    out += ["    return (v);", "}", ""]

    out.append(if_chain("string guiaTitulo(int paso = 0)", "string", [xs_str(s["titulo"]) for s in steps], '""'))
    out.append(if_chain("string guiaTexto(int paso = 0)", "string", [xs_str(s["texto"]) for s in steps], '""'))
    out.append(if_chain("int guiaIcono(int paso = 0)", "int", [str(ICONOS[s["icono"]]) for s in steps], "-1"))
    out.append(if_chain("int guiaReferencia(int paso = 0)", "int", [str(s["segundos"]) for s in steps], "0"))
    return "\n".join(out)


def build_manifest(bo: dict) -> dict:
    """Datos que necesita el overlay: los textos y cómo leer el archivo .xsdat
    (qué recuento y qué tecnología va en cada posición)."""
    idx = {c: i for i, c in enumerate(counters(bo))}
    tidx = {t: i for i, t in enumerate(techs(bo))}
    pasos = []
    for s in bo["pasos"]:
        conds = []
        for c in s["condiciones"]:
            if es_contador(c):
                kind = next(k for k in CONTADORES if k in c)
                conds.append({"tipo": "contador", "indice": idx[(kind, c[kind])], "min": c["min"],
                              "etiqueta": cond_label(c)})
            elif "tecnologia" in c:
                conds.append({"tipo": "tecnologia", "indice": tidx[c["tecnologia"]],
                              "objetivo": ESTADOS_TECH[c["estado"]], "etiqueta": TECNOLOGIAS[c["tecnologia"]][1]})
            else:
                tech = EDADES[c["edad"]][1]
                conds.append({"tipo": "edad", "objetivo": EDADES[c["edad"]][0], "indice": tidx[tech],
                              "etiqueta": TECNOLOGIAS[tech][1]})
        pasos.append({"titulo": s["titulo"], "texto": s["texto"], "icono": s["icono"],
                      "referencia": s["segundos"], "condiciones": conds})
    return {
        "version": 2,
        "id": bo["id"],
        "codigo": codigo_guia(bo),  # va en el .xsdat: así el overlay sabe qué guía se está jugando
        "nombre": bo["nombre"],
        "descripcion": bo["descripcion"],
        "descripcion_en": bo["descripcion_en"],
        "nivel": bo["nivel"],
        "mapas_recomendados": bo["mapas_recomendados"],
        "hitos": bo["hitos"],
        "series": bo["series"],
        "hito_principal": bo["hito_principal"],
        "nombre_meta": bo["pasos"][-1]["titulo"],
        "titulo_final": bo["titulo_final"],
        "icono_final": bo["icono_final"],
        "archivo_xs": bo["archivo_xs"],
        "mapas": [Path(m["archivo"]).stem for m in load_maps()],
        "margen_segundos": bo["margen_segundos"],
        "aviso_casas": bo["aviso_casas"],
        "pasos_siguientes_visibles": bo["pasos_siguientes_visibles"],
        "mensaje_final": bo["mensaje_final"],
        "num_datos": max(1, len(idx)),
        "num_techs": len(tidx),
        "techs": list(tidx),  # nombre de cada tecnología, en el orden del .xsdat (para el historial)
        "pasos": pasos,
    }


def codigo_guia(bo: dict) -> int:
    """Número fijo de la guía (sale de su id), para reconocerla en el .xsdat."""
    return zlib.crc32(bo["id"].encode("ascii")) & 0x7FFFFFFF


def load_maps() -> list[dict]:
    """Catálogo de mapas (mapas.json), comprobado."""
    mapas = json.loads(CATALOGO_MAPAS.read_text(encoding="utf-8"))["mapas"]
    vistos = set()
    for n, mapa in enumerate(mapas, 1):
        where = f"mapas.json > mapa {n}"
        if not isinstance(mapa, dict) or not CLAVES_MAPA <= set(mapa) <= CLAVES_MAPA | CLAVES_MAPA_OPCIONALES:
            raise BuildOrderError(f"{where}: claves {sorted(CLAVES_MAPA)} (y opcional imagen): {mapa}")
        if not re.fullmatch(r"[A-Za-z0-9 _()\[\]-]+\.rms", mapa["archivo"]):
            raise BuildOrderError(f"{where}: 'archivo' debe ser un nombre ASCII que acabe en .rms")
        if not (GAME_MAPS / mapa["base"]).is_file():
            raise BuildOrderError(f"{where}: no existe el mapa base {GAME_MAPS / mapa['base']}")
        if mapa["id"] in vistos or mapa["archivo"].lower() in vistos:
            raise BuildOrderError(f"{where}: id o archivo repetido")
        vistos |= {mapa["id"], mapa["archivo"].lower()}
    return mapas


def build_xs(bo: dict, source: Path) -> str:
    header = [
        "// ===========================================================================",
        f"// Guia de apertura: {ascii_only(bo['nombre'])}",
        f"// Generado por mods/guia-apertura-castillos/build.py desde build_orders/{source.name}.",
        "// No editar a mano: cambia el JSON o los archivos de xs/ y vuelve a construir.",
        "// Las tildes de los textos van como chr(byte) con sus bytes UTF-8, porque el",
        "// compilador XS no acepta caracteres no ASCII en el codigo.",
        "// ===========================================================================",
        "",
    ]
    parts = [
        "\n".join(header),
        (XS_SOURCES / "utiles.xs").read_text(encoding="utf-8"),
        generate_steps_xs(bo),
        (XS_SOURCES / "motor.xs").read_text(encoding="utf-8"),
    ]
    return "\n".join(p.rstrip("\n") + "\n" for p in parts)


ASCII_EXTRA = {"ñ": "n", "Ñ": "N", "¡": "", "¿": "", "»": ">>", "«": "<<", "·": "-", "º": "o", "ª": "a"}


def ascii_only(text: str) -> str:
    for a, b in ASCII_EXTRA.items():
        text = text.replace(a, b)
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


MAX_LITERAL = 70  # trozo máximo de cada literal (por si el compilador limita su longitud)


def xs_literal(content: str, where: str) -> str:
    """Convierte el contenido de un literal XS en una expresión ASCII: los caracteres
    no ASCII pasan a chr(byte) con sus bytes UTF-8 y los textos largos se trocean."""
    if all(ord(c) < 128 for c in content) and len(content) <= MAX_LITERAL:
        return '"' + content + '"'
    check_chars(content.replace("\\n", " "), where)
    parts: list[str] = []
    run = ""
    for c in content:
        if ord(c) < 128:
            run += c
            if len(run) >= MAX_LITERAL and not run.endswith("\\"):
                parts.append('"' + run + '"')
                run = ""
        else:
            if run:
                parts.append('"' + run + '"')
                run = ""
            parts += [f"chr({b})" for b in c.encode("utf-8")]
    if run:
        parts.append('"' + run + '"')
    return "(" + " + ".join(parts) + ")"


def encode_strings(code: str, name: str) -> str:
    """Aplica xs_literal a cada literal de cadena del código (no toca los comentarios)."""
    out_lines = []
    for n, line in enumerate(code.split("\n"), 1):
        out = []
        i = 0
        while i < len(line):
            c = line[i]
            if c == '"':
                j = i + 1
                while j < len(line) and line[j] != '"':
                    j += 2 if line[j] == "\\" else 1
                if j >= len(line):
                    raise BuildOrderError(f"{name}:{n}: cadena sin cerrar")
                out.append(xs_literal(line[i + 1 : j], f"{name}:{n}"))
                i = j + 1
            elif line.startswith("//", i):
                out.append(line[i:])
                break
            else:
                out.append(c)
                i += 1
        out_lines.append("".join(out))
    return "\n".join(out_lines)


# --- Comprobaciones del XS generado ------------------------------------------


def strip_xs(code: str) -> tuple[str, list[str]]:
    """Devuelve el código sin comentarios (cadenas sustituidas por "") y la lista de cadenas."""
    strings: list[str] = []

    def keep_string(m: re.Match) -> str:
        strings.append(m.group(0)[1:-1])
        return '""'

    out_lines = []
    in_block = False
    for line in code.split("\n"):
        if in_block:
            if "*/" in line:
                line = line.split("*/", 1)[1]
                in_block = False
            else:
                out_lines.append("")
                continue
        line = re.sub(r'"(?:[^"\\\n]|\\.)*"', keep_string, line)
        line = line.split("//", 1)[0]
        if "/*" in line:
            line, in_block = line.split("/*", 1)[0], True
        out_lines.append(line)
    return "\n".join(out_lines), strings


def lint_xs(code: str, name: str) -> None:
    """Busca las trampas de XS que el juego no explica bien al fallar."""
    errors = []
    bare, strings = strip_xs(code)
    # El compilador XS rechaza cualquier byte no ASCII, también dentro de cadenas y
    # comentarios (da un error por byte). Las tildes se construyen al ejecutar.
    for n, line in enumerate(code.split("\n"), 1):
        bad = sorted({c for c in line if ord(c) > 127})
        if bad:
            errors.append(f"{name}:{n}: caracteres no ASCII {bad} (XS no los acepta en el código)")
    for n, line in enumerate(bare.split("\n"), 1):
        where = f"{name}:{n}"
        if "'" in line:
            errors.append(f"{where}: comillas simples")
        if re.search(r"!(?!=)", line):
            errors.append(f"{where}: XS no tiene el operador !")
        if re.search(r"(\+=|-=|\*=|/=|\+\+[A-Za-z_]|--[A-Za-z_])", line):
            errors.append(f"{where}: XS no tiene operadores compuestos ni prefijos")
        if re.search(r"\breturn\b(?!\s*;)(?!\s*\()", line):
            errors.append(f"{where}: return sin paréntesis")
        if re.search(r"(^|[=(,]\s*)-[A-Za-z_]", line):
            errors.append(f"{where}: XS no tiene menos unario")
    for text in strings:
        if "%" in text:
            errors.append(f"{name}: texto con %: {text!r}")
        if len(text) > MAX_LITERAL + 10:
            errors.append(f"{name}: literal de {len(text)} caracteres (máximo {MAX_LITERAL + 10}): {text[:40]!r}...")
    # Paréntesis y llaves equilibrados.
    for a, b in ("()", "{}"):
        depth = 0
        for n, line in enumerate(bare.split("\n"), 1):
            depth += line.count(a) - line.count(b)
            if depth < 0:
                errors.append(f"{name}:{n}: {b} sin abrir")
                depth = 0
        if depth:
            errors.append(f"{name}: faltan {depth} {b!r}")
    # Las funciones propias (guia*) tienen que estar definidas antes de usarse.
    defined: set[str] = set()
    for n, line in enumerate(bare.split("\n"), 1):
        d = re.match(r"\s*(?:int|bool|float|string|void|vector)\s+(guia\w+)\s*\(", line)
        for call in re.finditer(r"\b(guia\w+)\s*\(", line):
            fn = call.group(1)
            if d and call.start(1) == d.start(1):
                continue
            if fn not in defined:
                errors.append(f"{name}:{n}: se llama a {fn} antes de definirla")
        if d:
            if d.group(1) in defined:
                errors.append(f"{name}:{n}: {d.group(1)} definida dos veces")
            defined.add(d.group(1))
    if errors:
        raise SystemExit("El XS generado tiene errores:\n  " + "\n  ".join(errors))


# --- Mapa ----------------------------------------------------------------------


def build_rms(xs_name: str, title: str, base_name: str, source_name: str) -> bytes:
    base = (GAME_MAPS / base_name).read_bytes()
    if b"#includeXS" in base:
        raise SystemExit(f"{base_name} ya incluye un script XS; no se puede añadir la guía sin sustituirlo")
    header = (
        f"#includeXS {xs_name}\r\n"
        f"/* {ascii_only(title)}. Copia de {base_name} que carga el script\r\n"
        f"   {xs_name}. Generado por mods/guia-apertura-castillos/build.py desde {source_name}. */\r\n"
        "\r\n"
    )
    return header.encode("ascii") + base


# --- Imagen del mapa -------------------------------------------------------------

GAME_MAP_ICONS = GAME / "resources" / "_common" / "wpfg" / "resources" / "mapicons"
_qt_app = None


def build_map_image(base_name: str, dest: Path, imagen: str | None = None) -> None:
    """Imagen de la sala para el mapa: la del mapa oficial (rm_<base>.png, 420x420)
    con una banda "AoE2 Coaching" encima. El juego la toma de un .png con el mismo
    nombre que el .rms, en la misma carpeta."""
    global _qt_app
    source = GAME_MAP_ICONS / (imagen or f"rm_{Path(base_name).stem.lower()}.png")
    if not source.is_file():
        print(f"  aviso: no hay imagen oficial para {base_name} ({source.name}); el mapa queda sin imagen")
        return
    # Sin QT_QPA_PLATFORM=offscreen: en Windows esa plataforma no carga las fuentes del sistema.
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPen
    if QGuiApplication.instance() is None:
        _qt_app = QGuiApplication([])

    img = QImage(str(source)).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    w, h = img.width(), img.height()
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    # Banda centrada, oscura y con borde dorado, como las placas del juego.
    bw, bh = w * 0.80, h * 0.20
    banda = QRectF((w - bw) / 2, (h - bh) / 2, bw, bh)
    for i in range(8, 0, -1):  # sombra
        s = QPainterPath()
        s.addRoundedRect(banda.adjusted(-i, -i + 4, i, i + 4), 12 + i, 12 + i)
        p.fillPath(s, QColor(0, 0, 0, 10))
    path = QPainterPath()
    path.addRoundedRect(banda, 12, 12)
    fondo = QLinearGradient(banda.topLeft(), banda.bottomLeft())
    fondo.setColorAt(0, QColor(32, 26, 18, 238))
    fondo.setColorAt(1, QColor(14, 12, 9, 238))
    p.fillPath(path, fondo)
    p.setPen(QPen(QColor(214, 176, 92), 3))
    p.drawPath(path)
    p.setPen(QPen(QColor(214, 176, 92, 90), 1))
    p.drawRoundedRect(banda.adjusted(6, 6, -6, -6), 8, 8)

    f = QFont("Segoe UI")
    f.setPixelSize(int(bh * 0.46))
    f.setWeight(QFont.Weight.Bold)
    p.setFont(f)
    texto = QRectF(banda.left(), banda.top() + 1, banda.width(), banda.height())
    p.setPen(QColor(0, 0, 0, 170))
    p.drawText(texto.translated(0, 2), Qt.AlignmentFlag.AlignCenter, "AoE2 Coaching")
    p.setPen(QColor(248, 232, 196))
    p.drawText(texto, Qt.AlignmentFlag.AlignCenter, "AoE2 Coaching")
    p.end()
    if not img.save(str(dest)):
        raise SystemExit(f"no se pudo guardar {dest}")


# --- Construcción e instalación ----------------------------------------------


def print_summary(bo: dict) -> None:
    print(f"\n{bo['nombre']}: {len(bo['pasos'])} pasos")
    for n, step in enumerate(bo["pasos"], 1):
        print(f"  {n:2}. [{step['referencia']:>5}] {step['titulo']}")


def finish_xs(code: str, name: str, ascii_mode: bool) -> str:
    """Deja el script en ASCII puro (sin tildes o con tildes construidas con chr) y lo comprueba."""
    try:
        code = ascii_only(code) if ascii_mode else encode_strings(code, name)
    except BuildOrderError as e:
        raise SystemExit(f"Error en el script: {e}")
    lint_xs(code, name)
    return code


def build(paths: list[Path], ascii_mode: bool, pruebas: bool = False) -> list[dict]:
    if MOD_DIR.exists():
        shutil.rmtree(MOD_DIR)
    OUT_XS.mkdir(parents=True)
    OUT_RMS.mkdir(parents=True)
    (MOD_DIR / "info.json").write_text(json.dumps(INFO, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    OVERLAY_GUIAS.mkdir(parents=True, exist_ok=True)
    for old in OVERLAY_GUIAS.glob("*.json"):
        old.unlink()

    built = []
    seen_xs, seen_ids = set(), set()
    for path in paths:
        try:
            bo = load_build_order(path)
        except BuildOrderError as e:
            raise SystemExit(f"Error en la build order: {e}")
        if bo["archivo_xs"] in seen_xs:
            raise SystemExit(f"{path.name}: archivo_xs repetido en otra build order")
        seen_xs.add(bo["archivo_xs"])
        if bo["id"] in seen_ids:
            raise SystemExit(f"{path.name}: id repetido en otra build order")
        seen_ids.add(bo["id"])

        xs = finish_xs(build_xs(bo, path), bo["archivo_xs"], ascii_mode)
        (OUT_XS / bo["archivo_xs"]).write_text(xs, encoding="ascii", newline="\n")
        manifest_path = OVERLAY_GUIAS / (Path(bo["archivo_xs"]).stem + ".json")
        manifest_path.write_text(json.dumps(build_manifest(bo), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print_summary(bo)
        print(f"  -> {OUT_XS / bo['archivo_xs']}")
        print(f"  -> {manifest_path}")
        built.append(bo)

    if not built:
        raise SystemExit("no se construyó ninguna guía")
    # Script común de los mapas: copia de la guía elegida en el panel (o la de por defecto).
    activa = guia_activa(built)
    (OUT_XS / XS_COMUN).write_text((OUT_XS / activa["archivo_xs"]).read_text(encoding="ascii"),
                                   encoding="ascii", newline="\n")
    print(f"\nScript común {XS_COMUN} = {activa['nombre']} (la guía elegida en el panel)")

    print("\nMapas:")
    try:
        mapas = load_maps()
    except BuildOrderError as e:
        raise SystemExit(f"Error en mapas.json: {e}")
    for mapa in mapas:
        title = f"Mapa de AoE2 Coaching ({mapa['nombre']})"
        (OUT_RMS / mapa["archivo"]).write_bytes(build_rms(XS_COMUN, title, mapa["base"], "mapas.json"))
        print(f"  -> {OUT_RMS / mapa['archivo']}")
        imagen = OUT_RMS / (Path(mapa["archivo"]).stem + ".png")
        build_map_image(mapa["base"], imagen, mapa.get("imagen"))
        if imagen.exists():
            print(f"  -> {imagen}")

    if pruebas:
        print("\nMapas de prueba:")
        for xs_name, rms_name in PRUEBAS:
            xs = finish_xs((PRUEBAS_DIR / xs_name).read_text(encoding="utf-8"), xs_name, ascii_mode)
            (OUT_XS / xs_name).write_text(xs, encoding="ascii", newline="\n")
            (OUT_RMS / rms_name).write_bytes(build_rms(xs_name, "Prueba de la guia", "Arena.rms", f"pruebas/{xs_name}"))
            print(f"  -> {OUT_RMS / rms_name}")
    return built


def install(built: list[dict]) -> None:
    """Sincroniza el mod con la carpeta de mods locales sin borrarla entera, para
    que funcione aunque el juego esté abierto y tenga algún archivo en uso."""
    target = LOCAL_MODS / INSTALL_NAME
    wanted = {p.relative_to(MOD_DIR) for p in MOD_DIR.rglob("*") if p.is_file()}
    for rel in sorted(wanted):
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MOD_DIR / rel, dest)
    if target.exists():
        for p in sorted(target.rglob("*"), reverse=True):
            rel = p.relative_to(target)
            try:
                if p.is_file() and rel not in wanted:
                    p.unlink()
                    print(f"borrado (ya no forma parte del mod): {rel}")
                elif p.is_dir() and not any(p.iterdir()):
                    p.rmdir()
            except OSError as e:
                print(f"aviso: no se pudo borrar {p}: {e}")
    print(f"\ninstalado en {target}")
    PROFILE_XS.mkdir(parents=True, exist_ok=True)
    for xs in sorted(OUT_XS.glob("*.xs")):  # incluye aoe2c_guia.xs con la guía elegida
        dest = PROFILE_XS / xs.name
        shutil.copy2(xs, dest)
        print(f"script copiado a {dest}")


def guia_activa(built: list[dict]) -> dict:
    """La guía elegida en el panel (overlay/config.json), o la de por defecto."""
    try:
        elegida = json.loads(CONFIG_OVERLAY.read_text(encoding="utf-8")).get("guia_activa")
    except (OSError, ValueError, AttributeError):
        elegida = None
    por_id = {bo["id"]: bo for bo in built}
    return por_id.get(elegida) or por_id.get(GUIA_POR_DEFECTO) or built[0]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    unknown = flags - {"--install", "--ascii", "--pruebas"}
    if unknown:
        raise SystemExit(f"opciones desconocidas: {', '.join(sorted(unknown))}\n{__doc__}")
    paths = [Path(a).resolve() for a in args] or sorted(BUILD_ORDERS.glob("*.json"))
    if not paths:
        raise SystemExit(f"no hay build orders en {BUILD_ORDERS}")
    built = build(paths, "--ascii" in flags, "--pruebas" in flags)
    if "--install" in flags:
        install(built)


if __name__ == "__main__":
    main()
