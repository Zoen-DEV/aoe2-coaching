/**
 * Datos de la web, leídos al armar la página de las mismas fuentes que el catálogo
 * (content/catalogo.py): las build orders, mapas.json y la ficha de cada mod. Así la
 * lista de la web coincide con lo que instala el panel, aunque aún no haya una
 * publicación contenido-* en GitHub.
 */
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { resolve, join } from "node:path";

// La web se arma desde apps/web (también en Vercel), así que la raíz del monorepo está dos niveles arriba.
const RAIZ = resolve(process.cwd(), "../..");
const CONTENT = join(RAIZ, "content");

export const REPO = "Zoen-DEV/aoe2-coaching";
export const URL_REPO = `https://github.com/${REPO}`;
export const URL_RELEASES = `${URL_REPO}/releases`;

export type Texto = { es: string; en: string };

export interface Condicion {
  tipo: "cantidad" | "hecho";
  clave: string; // casa, pastores, telar...
  min: number;
}

export interface Paso {
  titulo: Texto;
  texto: Texto;
  icono: string;
  referencia: string;
  condiciones: Condicion[];
}

export interface Guia {
  id: string;
  version: string;
  nombre: string;
  descripcion: Texto;
  nivel: string;
  mapas: string[];
  pasos: Paso[];
  final: Texto;
  meta: string; // hora de referencia del último paso
}

export interface Mapa {
  id: string;
  nombre: string;
  tipo: Texto;
  descripcion: Texto;
  guias: string[];
}

export interface Mod {
  id: string;
  version: string;
  nombre: Texto;
  descripcion: Texto;
}

function json(ruta: string): any {
  return JSON.parse(readFileSync(ruta, "utf-8"));
}

function condiciones(lista: any[] = []): Condicion[] {
  return lista.map((c) => {
    for (const k of ["edificio", "aldeanos", "unidades"]) {
      if (c[k]) return { tipo: "cantidad", clave: c[k], min: c.min ?? 1 } as Condicion;
    }
    if (c.tecnologia) return { tipo: "hecho", clave: c.tecnologia, min: 1 } as Condicion;
    return { tipo: "hecho", clave: `edad_${c.edad}`, min: 1 } as Condicion;
  });
}

export function version(): string {
  const py = readFileSync(join(RAIZ, "apps/desktop/version.py"), "utf-8");
  return py.match(/VERSION\s*=\s*"([^"]+)"/)?.[1] ?? "1.0.0";
}

const ORDEN_NIVEL: Record<string, number> = { facil: 0, media: 1, dificil: 2 };

export function guias(): Guia[] {
  const carpeta = join(CONTENT, "guias/build_orders");
  return readdirSync(carpeta)
    .filter((f) => f.endsWith(".json"))
    .map((f) => {
      const d = json(join(carpeta, f));
      const pasos: Paso[] = d.pasos.map((p: any) => ({
        titulo: { es: p.titulo, en: p.titulo_en ?? p.titulo },
        texto: { es: p.texto, en: p.texto_en ?? p.texto },
        icono: p.icono,
        referencia: p.referencia,
        condiciones: condiciones(p.condiciones),
      }));
      return {
        id: d.id,
        version: d.version,
        nombre: d.nombre,
        descripcion: { es: d.descripcion, en: d.descripcion_en ?? d.descripcion },
        nivel: d.nivel,
        mapas: d.mapas_recomendados ?? [],
        pasos,
        final: { es: d.titulo_final ?? "", en: d.titulo_final_en ?? d.titulo_final ?? "" },
        meta: pasos.at(-1)?.referencia ?? "",
      };
    })
    .sort((a, b) => (ORDEN_NIVEL[a.nivel] ?? 9) - (ORDEN_NIVEL[b.nivel] ?? 9));
}

export function mapas(): Mapa[] {
  return json(join(CONTENT, "mapas/mapas.json")).mapas.map((m: any) => ({
    id: m.id,
    nombre: m.nombre,
    tipo: m.tipo,
    descripcion: m.descripcion,
    guias: m.guias ?? [],
  }));
}

export function mods(): Mod[] {
  const carpeta = join(CONTENT, "mods");
  return readdirSync(carpeta)
    .map((id) => join(carpeta, id, "catalogo.json"))
    .filter(existsSync)
    .map((ruta) => {
      const d = json(ruta);
      return { id: d.id, version: d.version, nombre: d.nombre, descripcion: d.descripcion };
    });
}

export const NIVELES: Record<string, Texto> = {
  facil: { es: "Fácil", en: "Easy" },
  media: { es: "Media", en: "Medium" },
  dificil: { es: "Difícil", en: "Hard" },
};

/** Nombres de lo que cuentan las condiciones de los pasos (barras de la tarjeta). */
export const CONDICIONES: Record<string, Texto> = {
  casa: { es: "Casas", en: "Houses" },
  molino: { es: "Molino", en: "Mill" },
  campamento_maderero: { es: "Campamentos madereros", en: "Lumber camps" },
  campamento_minero: { es: "Campamento minero", en: "Mining camp" },
  granja: { es: "Granjas", en: "Farms" },
  mercado: { es: "Mercado", en: "Market" },
  herreria: { es: "Herrería", en: "Blacksmith" },
  cuartel: { es: "Cuartel", en: "Barracks" },
  establo: { es: "Establo", en: "Stable" },
  pastores: { es: "Pastores", en: "Shepherds" },
  lenadores: { es: "Leñadores", en: "Lumberjacks" },
  cazadores: { es: "Cazadores", en: "Hunters" },
  recolectores: { es: "Bayas", en: "Berries" },
  comida: { es: "En comida", en: "On food" },
  mineros_oro: { es: "En oro", en: "On gold" },
  todos: { es: "Aldeanos", en: "Villagers" },
  exploradores: { es: "Exploradores", en: "Scouts" },
  telar: { es: "Telar", en: "Loom" },
  edad_feudal: { es: "Edad Feudal", en: "Feudal Age" },
  edad_castillos: { es: "Edad de los Castillos", en: "Castle Age" },
  hacha_doble_filo: { es: "Hacha de doble filo", en: "Double-Bit Axe" },
  collera: { es: "Collera", en: "Horse Collar" },
};
