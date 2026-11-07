"""Arma el catálogo de contenido de AoE2C: los paquetes y catalogo.json.

Lee lo que ya está construido en build/ (raíz del monorepo) y escribe en build/catalogo/:

- guia-<id>-<versión>.zip: manifiesto del overlay + script .xs de cada guía
  (de content/guias/build.py).
- mod-<id>-<versión>.zip: la carpeta del mod tal como va en mods\\local
  (de content/mods/<id>/build.py), con su ficha content/mods/<id>/catalogo.json.
- Los mapas van como receta (content/mapas/mapas.json): la app los arma con el juego.
- catalogo.json: la lista, con la versión, el SHA-256 y la versión mínima de la app de
  cada elemento (formato en apps/desktop/catalogo.py).

Los .zip salen siempre iguales si no cambia su contenido (fechas fijas), así que su hash
solo cambia cuando cambia la guía o el mod. Esto es lo que publica el proceso
"contenido-*" de GitHub Actions (plan 7).

Uso: py content/catalogo.py [--salida CARPETA] [--sin-mods]

Al ejecutar la app desde el código, el panel usa build/catalogo/catalogo.json si existe.
"""

import json
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAIZ = HERE.parent
sys.path.insert(0, str(RAIZ / "apps" / "desktop"))
import catalogo as K  # noqa: E402

BUILD = RAIZ / "build"
GUIAS = BUILD / "guias"
XS = BUILD / "mods" / "guia-apertura-castillos" / "resources" / "_common" / "xs"
MAPAS = HERE / "mapas" / "mapas.json"
MODS = HERE / "mods"
MODS_ARMADOS = BUILD / "mods"
SALIDA = BUILD / "catalogo"
# Versión mínima de la app según el formato del manifiesto de la guía ("version" del manifiesto).
APP_MINIMA_GUIA = {2: "1.0.0"}
APP_MINIMA = "1.0.0"
FECHA_ZIP = (1980, 1, 1, 0, 0, 0)


def zip_fijo(destino: Path, archivos: list[tuple[str, Path]]) -> K.Paquete:
    """Zip con fechas y permisos fijos y en orden: mismo contenido, mismo hash."""
    with zipfile.ZipFile(destino, "w") as z:
        for nombre, ruta in sorted(archivos):
            info = zipfile.ZipInfo(nombre, FECHA_ZIP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, ruta.read_bytes(), compresslevel=9)
    return K.Paquete(destino.name, K.sha256_de(destino), destino.stat().st_size)


def guias(salida: Path) -> list[K.Elemento]:
    out = []
    manifiestos = sorted(GUIAS.glob("*.json"))
    if not manifiestos:
        raise SystemExit(f"no hay guías en {GUIAS}: ejecuta antes py content/guias/build.py")
    for ruta in manifiestos:
        m = json.loads(ruta.read_text(encoding="utf-8"))
        xs = XS / m["archivo_xs"]
        if not xs.is_file():
            raise SystemExit(f"falta {xs}: ejecuta antes py content/guias/build.py")
        if m.get("version") not in APP_MINIMA_GUIA:
            raise SystemExit(f"{ruta.name}: formato de manifiesto {m.get('version')} sin versión mínima de la app "
                             "(añádelo a APP_MINIMA_GUIA)")
        if "version_guia" not in m:
            raise SystemExit(f"{ruta.name}: le falta version_guia (vuelve a ejecutar build.py)")
        paquete = zip_fijo(salida / f"guia-{m['id']}-{m['version_guia']}.zip",
                           [(ruta.name, ruta), (xs.name, xs)])
        out.append(K.Elemento(
            "guia", m["id"], m["version_guia"], APP_MINIMA_GUIA[m["version"]],
            {"es": m["nombre"], "en": m["nombre"]}, {"es": m["descripcion"], "en": m["descripcion_en"]},
            {"archivo_xs": m["archivo_xs"], "nivel": m["nivel"], "mapas_recomendados": m["mapas_recomendados"]},
            paquete))
    return out


def mapas() -> list[K.Elemento]:
    out = []
    for m in json.loads(MAPAS.read_text(encoding="utf-8"))["mapas"]:
        datos = {"base": m["base"], "archivo": m["archivo"], "tipo": m["tipo"], "guias": m["guias"]}
        if m.get("imagen"):
            datos["imagen"] = m["imagen"]
        out.append(K.Elemento("mapa", m["id"], m["version"], m.get("app_minima", APP_MINIMA),
                              {"es": m["nombre"], "en": m["nombre"]}, m["descripcion"], datos))
    return out


def mods(salida: Path) -> list[K.Elemento]:
    out = []
    for ficha in sorted(MODS.glob("*/catalogo.json")):
        f = json.loads(ficha.read_text(encoding="utf-8"))
        carpeta = ficha.parent.name
        armado = MODS_ARMADOS / carpeta
        if f.get("id") != carpeta:
            raise SystemExit(f"{ficha}: 'id' debe ser el nombre de la carpeta ({carpeta})")
        if not (armado / "info.json").is_file():
            raise SystemExit(f"falta {armado}: ejecuta antes py content/mods/{carpeta}/build.py")
        archivos = [(p.relative_to(armado).as_posix(), p) for p in armado.rglob("*") if p.is_file()]
        paquete = zip_fijo(salida / f"mod-{carpeta}-{f['version']}.zip", archivos)
        out.append(K.Elemento("mod", carpeta, f["version"], f.get("app_minima", APP_MINIMA), f["nombre"],
                              f["descripcion"], {"carpeta": carpeta, "titulo": f["titulo"]}, paquete))
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    salida = Path(args[args.index("--salida") + 1]).resolve() if "--salida" in args else SALIDA
    if salida.exists():
        shutil.rmtree(salida)
    salida.mkdir(parents=True)
    elementos = guias(salida) + mapas() + ([] if "--sin-mods" in args else mods(salida))
    generado = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    texto = K.a_json(K.Catalogo(elementos), generado)
    try:
        cat = K.leer(texto, str(salida / K.NOMBRE), estricto=True)
    except K.CatalogoError as e:
        raise SystemExit(f"el catálogo no es válido: {e}")
    ids_mapas = {e.id for e in cat.de("mapa")}
    ids_guias = {e.id for e in cat.de("guia")}
    for e in cat.elementos:
        malos = set(e.datos.get("mapas_recomendados", [])) - ids_mapas | set(e.datos.get("guias", [])) - ids_guias
        if e.tipo in ("guia", "mapa") and malos:
            raise SystemExit(f"{e.tipo} {e.id}: recomienda ids que no están en el catálogo: {sorted(malos)}")
    (salida / K.NOMBRE).write_text(texto, encoding="utf-8")
    for e in cat.elementos:
        extra = f"  {e.paquete.archivo} ({e.paquete.tamano / 1024:.0f} KB)" if e.paquete else "  (se arma en la PC)"
        print(f"{e.tipo:5} {e.id:14} {e.version:8}{extra}")
    print(f"\n-> {salida / K.NOMBRE}")


if __name__ == "__main__":
    main()
