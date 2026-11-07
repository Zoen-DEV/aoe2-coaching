/**
 * Tarjeta del overlay en la sección "Cómo funciona": `pintar(p)` la pone en el punto
 * p (0 a 1) del recorrido. Usa los pasos reales de la guía (datos-demo, del build).
 */
type Texto = { es: string; en: string };
interface Cond { tipo: "cantidad" | "hecho"; clave: string; min: number }
interface Paso { titulo: Texto; texto: Texto; icono: string; referencia: string; condiciones: Cond[] }
interface Datos {
  nombre: string;
  total: number;
  pasos: Paso[];
  condiciones: Record<string, Texto>;
  iconos: Record<string, string>;
}

// Desfase de ejemplo en cada paso (segundos): + tarde, − adelantado.
const DESFASE = [-2, 4, 9, 22, 12, 3, -6, -10, 0];
const PASOS_DEMO = DESFASE.length;

const idioma = () => (document.documentElement.lang === "en" ? "en" : "es");
const seg = (ref: string) => {
  const [m, s] = ref.split(":").map(Number);
  return m * 60 + s;
};
const reloj = (t: number) => {
  const s = Math.max(0, Math.round(t));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};
const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

export function crearDemo(raiz: HTMLElement) {
  const nodo = document.getElementById("datos-demo");
  if (!nodo) return null;
  const d: Datos = JSON.parse(nodo.textContent || "{}");
  const n = Math.min(PASOS_DEMO, d.pasos.length);
  const $ = (k: string) => raiz.querySelector<HTMLElement>(`[data-t="${k}"]`)!;
  const puntos = [...document.querySelectorAll<HTMLElement>("[data-punto]")];
  let pasoPintado = -1;
  let idiomaPintado = "";

  function icono(clave: string) {
    const t = d.iconos[clave] ?? '<circle cx="12" cy="12" r="7"/>';
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${t}</svg>`;
  }

  function pintar(p: number) {
    const L = idioma();
    const x = Math.min(Math.max(p, 0), 0.9999) * n;
    const i = Math.floor(x);
    const f = x - i;
    const paso = d.pasos[i];
    const ref = seg(paso.referencia);
    const refAnterior = i ? seg(d.pasos[i - 1].referencia) + DESFASE[i - 1] : 0;
    const desfase = DESFASE[i];
    const t = refAnterior + (ref + desfase - refAnterior) * f;

    $("reloj").textContent = reloj(t);
    $("general").style.width = `${((i + f) / d.total) * 100}%`;

    // Ritmo
    const ritmo = $("ritmo");
    const dd = Math.round(desfase * Math.min(1, f * 1.5));
    ritmo.className = "t-ritmo " + (Math.abs(dd) <= 5 ? "bien" : dd > 0 ? "tarde" : "antes");
    ritmo.textContent = Math.abs(dd) <= 5 ? (L === "es" ? "A tiempo" : "On time") : `${dd > 0 ? "+" : "−"}${Math.abs(dd)} s`;

    // Objetivo
    const falta = ref - t;
    $("objetivo").textContent =
      (L === "es" ? `Objetivo ${paso.referencia} · ` : `Target ${paso.referencia} · `) +
      (falta >= 0
        ? L === "es" ? `faltan ${reloj(falta)}` : `${reloj(falta)} left`
        : L === "es" ? `${Math.round(-falta)} s tarde` : `${Math.round(-falta)} s late`);
    $("objetivo").style.color = falta >= 0 ? "var(--secundario)" : "var(--atencion)";

    if (i !== pasoPintado || L !== idiomaPintado) {
      $("paso").innerHTML = L === "es" ? `Paso <b>${i + 1}</b> de ${d.total}` : `Step <b>${i + 1}</b> of ${d.total}`;
      $("icono").innerHTML = icono(paso.icono);
      $("titulo").textContent = paso.titulo[L];
      $("texto").textContent = paso.texto[L];
      $("conds").innerHTML = paso.condiciones
        .map((c) => {
          const nombre = d.condiciones[c.clave]?.[L] ?? c.clave;
          return `<div class="t-cond" data-min="${c.min}" data-tipo="${c.tipo}"><div class="t-cond-fila"><span>${esc(nombre)}</span><b></b></div><div class="t-cond-barra"><i></i></div></div>`;
        })
        .join("");
      $("siguientes").innerHTML = d.pasos
        .slice(i + 1, i + 4)
        .map((s, k) => `<li><span class="n">${i + k + 2}</span><span>${esc(s.titulo[L])}</span><span class="h">${s.referencia}</span></li>`)
        .join("");
      if (i > 0) {
        const ant = d.pasos[i - 1];
        const df = DESFASE[i - 1];
        const hora = reloj(seg(ant.referencia) + df);
        const signo = Math.abs(df) <= 0 ? "±0" : `${df > 0 ? "+" : "−"}${Math.abs(df)}`;
        $("hecho").textContent = `✓ ${ant.titulo[L]} · ${hora} (${signo} s)`;
      } else {
        $("hecho").textContent = "";
      }
      if (pasoPintado !== -1 && i !== pasoPintado) {
        const a = $("actual");
        a.classList.remove("entra");
        void a.offsetWidth;
        a.classList.add("entra");
      }
      pasoPintado = i;
      idiomaPintado = L;
    }

    // Barras de las condiciones
    const avance = Math.min(1, f * 1.2);
    raiz.querySelectorAll<HTMLElement>(".t-cond").forEach((el, k) => {
      const min = Number(el.dataset.min);
      const escalon = Math.min(1, Math.max(0, avance * 1.15 - k * 0.12));
      const hecho = el.dataset.tipo === "hecho";
      const valor = hecho ? (escalon >= 1 ? 1 : 0) : Math.floor(min * escalon);
      el.querySelector("b")!.textContent = hecho ? (valor ? "✓" : "…") : `${valor}/${min}`;
      el.querySelector<HTMLElement>(".t-cond-barra i")!.style.width = `${(hecho ? (valor ? 1 : escalon * 0.8) : valor / min) * 100}%`;
      el.classList.toggle("ok", valor >= (hecho ? 1 : min));
    });

    // Aviso de casas, en el último tramo
    const aviso = $("aviso");
    const conAviso = p >= 0.75 && f < 0.6;
    aviso.classList.toggle("visible", conAviso);
    if (conAviso) {
      const pob = 18 + i * 2;
      $("aviso-texto").textContent = L === "es" ? `Población ${pob}/${pob + 1} · construye una casa` : `Population ${pob}/${pob + 1} · build a house`;
    }

    // Punto destacado a la izquierda
    const activo = Math.min(puntos.length - 1, Math.floor(p * puntos.length));
    puntos.forEach((el, k) => el.classList.toggle("activo", k === activo));
  }

  return { pintar };
}
