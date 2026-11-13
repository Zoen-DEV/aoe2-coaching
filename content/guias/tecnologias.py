"""Saca del juego los datos de las tecnologías de la tierlist y escribe tecnologias.json.

    py content/guias/tecnologias.py

Para cada tecnología de CATALOGO guarda su ID, edad y edificio, y su nombre en español
e inglés (los textos oficiales del juego). Para cada civilización (ID = posición en
civilizations.json, la misma que devuelve xsGetPlayerCivilization) guarda su nombre y
qué tecnologías del catálogo no tiene: las que su árbol no incluye y las de un edificio
militar que no puede construir (los mesoamericanos no tienen establo). Los edificios de
economía no cuentan: algunas civilizaciones los cambian por uno propio con otra ID.

Necesita el juego instalado; el resultado se sube a git porque build.py corre también en
GitHub Actions, sin el juego. Hay que volver a ejecutarlo cuando salga una civilización
nueva o se añada una tecnología al catálogo.
"""

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAIZ = HERE.parent.parent
sys.path.insert(0, str(RAIZ / "apps" / "desktop"))
import rutas  # noqa: E402

SALIDA = HERE / "tecnologias.json"
CIVILIZACIONES_APP = RAIZ / "apps" / "desktop" / "civilizaciones.py"  # los nombres, para la app
NOMBRES_APP = RAIZ / "apps" / "desktop" / "nombres_juego.py"  # unidades, edificios y tecnologías, para la app

# clave: ID de la tecnología (la que se pasa a xsGetTechState). Las mejoras de unidad
# (ballestero, caballería ligera...) usan la tecnología que hace la mejora.
CATALOGO = {
    # Economía.
    "telar": 22,
    "carretilla": 213,
    "carro_de_mano": 249,
    "vigilancia": 8,
    "hacha_doble_filo": 202,
    "sierra_de_arco": 203,
    "collera": 14,
    "arado_pesado": 13,
    "mineria_aurifera": 55,
    "pozo_aurifero": 182,
    "mineria_piedra": 278,
    "caravana": 48,
    "acunacion": 23,
    # Herrería.
    "emplumado": 199,
    "flecha_punzante": 200,
    "armadura_acolchada": 211,
    "armadura_cuero": 212,
    "forja": 67,
    "fundicion": 68,
    "cota_escamas": 74,
    "cota_malla": 76,
    "barda_escamas": 81,
    "barda_malla": 82,
    # Cuartel.
    "hombre_de_armas": 222,
    "espadachin": 207,
    "piquero": 197,
    "escuderos": 215,
    "incendio": 602,
    "gambesones": 875,
    "guerrero_aguila": 384,
    # Galería de tiro.
    "ballestero": 100,
    "hostigador_elite": 98,
    "anillo_pulgar": 437,
    # Establo.
    "linea_sangre": 435,
    "cria_caballos": 39,
    "caballeria_ligera": 254,
    # Universidad.
    "albanileria": 50,
    "balistica": 93,
    "matacanes": 322,
    "grua": 54,
}

EDIFICIOS_MILITARES = {12, 87, 101}  # cuartel, galería de tiro y establo
CARPETA_ICONOS = Path("widgetui") / "textures" / "ingame"
TIPOS_TECNOLOGIA = {"Research", "UniqueTech", "RegionalTech"}
TIPOS_MEJORA = {"UnitUpgrade", "RegionalUnit", "UniqueUnit"}  # llevan "Trigger Tech ID"


def cadenas(juego: Path, idioma: str) -> dict[int, str]:
    """Textos del juego (key-value-*.txt): ID -> texto."""
    out: dict[int, str] = {}
    for f in sorted((juego / "resources" / idioma / "strings" / "key-value").glob("*.txt")):
        for linea in f.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r'\s*(\d+)\s+"(.*)"\s*$', linea)
            if m:
                out.setdefault(int(m.group(1)), m.group(2))
    return out


def limpiar(texto: str) -> str:
    """Los nombres del árbol traen saltos de línea escritos como \\n para partirlos en su casilla."""
    return " ".join(texto.replace("\\n", " ").split())


def nodo_de(arbol: dict, tech: int) -> dict | None:
    for nodo in arbol["civ_techs_units"]:
        tipo = nodo.get("Node Type")
        if tipo in TIPOS_TECNOLOGIA and nodo.get("Node ID") == tech:
            return nodo
        if tipo in TIPOS_MEJORA and nodo.get("Trigger Tech ID") == tech:
            return nodo
    return None


def generar(juego: Path) -> dict:
    dat = juego / "resources" / "_common" / "dat"
    civs = json.loads((dat / "civilizations.json").read_text(encoding="utf-8"))["civilization_list"]
    es, en = cadenas(juego, "es"), cadenas(juego, "en")
    arboles = {}
    for c in civs[1:]:  # la 0 es Gaia
        ruta = dat / "CivTechTrees" / f"{c['tech_tree_name']}.json"
        if ruta.is_file():
            arboles[c["tech_tree_name"]] = json.loads(ruta.read_text(encoding="utf-8"))

    tecnologias = {}
    for clave, tech in CATALOGO.items():
        nodo = next((n for a in arboles.values() if (n := nodo_de(a, tech))), None)
        if nodo is None:
            raise SystemExit(f"{clave}: la tecnología {tech} no está en ningún árbol")
        sid = nodo["Name String ID"]
        tecnologias[clave] = {"id": tech, "edad": nodo["Age ID"] - 1, "edificio": nodo["Building ID"],
                              "nombre": limpiar(es.get(sid, nodo["Name"])),
                              "nombre_en": limpiar(en.get(sid, nodo["Name"]))}

    civilizaciones = {}
    for civ_id, c in enumerate(civs):
        arbol = arboles.get(c["tech_tree_name"])
        if civ_id == 0 or arbol is None:
            continue
        sin_edificio = {b["Node ID"] for b in arbol["civ_techs_buildings"]
                        if b.get("Node Status") == "NotAvailable" and b["Node ID"] in EDIFICIOS_MILITARES}
        sin = []
        for clave, datos in tecnologias.items():
            nodo = nodo_de(arbol, datos["id"])
            if nodo is None or nodo.get("Node Status") == "NotAvailable" or datos["edificio"] in sin_edificio:
                sin.append(clave)
        civilizaciones[str(civ_id)] = {"clave": c["internal_name"].lower(),
                                       "nombre": limpiar(es.get(c["name_string_id"], c["internal_name"])),
                                       "nombre_en": limpiar(en.get(c["name_string_id"], c["internal_name"])),
                                       "sin": sin}
    return {"_comentario": "Generado por tecnologias.py con los datos del juego (no editar a mano).",
            "tecnologias": tecnologias, "civilizaciones": civilizaciones}


def escribir_civilizaciones(datos: dict) -> None:
    """Los nombres de las civilizaciones para la app (panel de la partida en curso). Van en
    un módulo de Python porque la app empaquetada no lleva archivos de datos sueltos."""
    filas = "".join(f"    {int(i)}: ({c['nombre']!r}, {c['nombre_en']!r}),\n"
                    for i, c in sorted(datos["civilizaciones"].items(), key=lambda x: int(x[0])))
    techs = "".join(f"    {k!r}: {t['id']},\n" for k, t in datos["tecnologias"].items())
    CIVILIZACIONES_APP.write_text(
        '"""Nombres de las civilizaciones por ID (el del juego), en español e inglés, y el ID\n'
        'de cada tecnología de la tierlist (para su icono en el overlay).\n\n'
        'Generado por content/guias/tecnologias.py (no editar a mano)."""\n\n'
        f"NOMBRES = {{\n{filas}}}\n\n"
        f"TECNOLOGIAS = {{\n{techs}}}\n\n\n"
        "def nombre(civ: int, ingles: bool = False) -> str:\n"
        '    """Nombre de la civilización, o "" si no se conoce."""\n'
        "    par = NOMBRES.get(civ)\n"
        "    return (par[1] if ingles else par[0]) if par else \"\"\n",
        encoding="utf-8", newline="\n")


def archivos_iconos(juego: Path, carpeta: str) -> dict[int, str]:
    """Iconos del juego (widgetui/textures/ingame/<carpeta>): número -> ruta relativa
    ("tech/006_loom.DDS")."""
    out: dict[int, str] = {}
    for f in sorted((juego / CARPETA_ICONOS / carpeta).glob("*")):
        m = re.match(r"(\d+)_", f.name)
        if m and f.suffix.lower() == ".dds":
            out.setdefault(int(m.group(1)), f"{carpeta}/{f.name}")
    return out


def clave_icono(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", texto.lower()).strip("_")


def nombres_juego(juego: Path) -> dict[str, dict]:
    """Nombres de todas las unidades, edificios y tecnologías de los árboles de las
    civilizaciones (para el build order de las repeticiones): {grupo: {ID: (es, en)}}.
    También el icono de cada tecnología y unidad (ICONOS_*: {ID: ruta en
    widgetui/textures/ingame}); la app los lee del juego instalado, no van en el repo."""
    dat = juego / "resources" / "_common" / "dat"
    es, en = cadenas(juego, "es"), cadenas(juego, "en")
    out: dict[str, dict] = {"UNIDADES": {}, "EDIFICIOS": {}, "TECNOLOGIAS": {}, "ICONOS_TECNOLOGIAS": {},
                            "ICONOS_UNIDADES": {}}
    techs, unidades = archivos_iconos(juego, "tech"), archivos_iconos(juego, "units")
    por_nombre = {clave_icono(r.split("/")[1].split("_", 1)[1].rsplit(".", 1)[0]): r for r in techs.values()}

    def poner(grupo: str, id_: int, nodo: dict):
        if id_ is None or id_ < 0 or id_ in out[grupo]:
            return
        sid = nodo.get("Name String ID")
        out[grupo][id_] = (limpiar(es.get(sid, nodo["Name"])), limpiar(en.get(sid, nodo["Name"])))
        indice = nodo.get("Picture Index", -1)
        if grupo == "UNIDADES":
            icono = unidades.get(indice)
        elif grupo == "TECNOLOGIAS" and nodo.get("Node Type") in TIPOS_TECNOLOGIA:
            icono = techs.get(indice)
        elif grupo == "TECNOLOGIAS":  # mejora de unidad: su icono de tecnología o, si no hay, el de la unidad
            icono = por_nombre.get(clave_icono(nodo["Name"])) or unidades.get(indice)
        else:
            icono = None
        if icono:
            out[f"ICONOS_{grupo}"][id_] = icono

    # Primero las civilizaciones normales, en el orden del juego (Britanos, Francos...): las
    # de Chronicles llaman distinto a algunas cosas («Edad Cívica» en vez de «Edad Feudal»).
    civs = json.loads((dat / "civilizations.json").read_text(encoding="utf-8"))["civilization_list"]
    orden = [dat / "CivTechTrees" / f"{c['tech_tree_name']}.json" for c in civs[1:]]
    orden += [r for r in sorted((dat / "CivTechTrees").glob("*.json")) if r not in orden]
    for ruta in orden:
        if not ruta.is_file():
            continue
        arbol = json.loads(ruta.read_text(encoding="utf-8"))
        for nodo in arbol.get("civ_techs_buildings", []):
            poner("EDIFICIOS", nodo.get("Node ID"), nodo)
        for nodo in arbol.get("civ_techs_units", []):
            tipo = nodo.get("Node Type")
            if tipo in TIPOS_TECNOLOGIA:
                poner("TECNOLOGIAS", nodo.get("Node ID"), nodo)
            elif tipo in TIPOS_MEJORA or tipo == "Unit":
                poner("UNIDADES", nodo.get("Node ID"), nodo)
                if nodo.get("Trigger Tech ID", -1) >= 0:
                    poner("TECNOLOGIAS", nodo["Trigger Tech ID"], nodo)
            elif tipo == "BuildingNonTech":
                poner("EDIFICIOS", nodo.get("Node ID"), nodo)
    return out


def escribir_nombres(nombres: dict[str, dict]) -> None:
    partes = ['"""Nombres de unidades, edificios y tecnologías por ID (los del juego), en español e\n'
              'inglés, para el build order de las repeticiones, y la ruta de sus iconos en el juego\n'
              '(widgetui/textures/ingame, ver iconos_juego.py).\n\n'
              'Generado por content/guias/tecnologias.py (no editar a mano)."""\n']
    for grupo, valores in nombres.items():
        filas = "".join(f"    {i}: {v!r},\n" for i, v in sorted(valores.items()))
        partes.append(f"\n{grupo} = {{\n{filas}}}\n")
    NOMBRES_APP.write_text("".join(partes), encoding="utf-8", newline="\n")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if "--solo-app" in sys.argv[1:]:  # sin el juego: rehace civilizaciones.py desde tecnologias.json
        escribir_civilizaciones(json.loads(SALIDA.read_text(encoding="utf-8")))
        print(f"-> {CIVILIZACIONES_APP}")
        return
    juego, _ = rutas.para_scripts()
    datos = generar(Path(juego))
    SALIDA.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    escribir_civilizaciones(datos)
    nombres = nombres_juego(Path(juego))
    escribir_nombres(nombres)
    print(f"{sum(len(v) for v in nombres.values())} nombres -> {NOMBRES_APP}")
    print(f"{len(datos['tecnologias'])} tecnologías y {len(datos['civilizaciones'])} civilizaciones -> {SALIDA}")


if __name__ == "__main__":
    main()
