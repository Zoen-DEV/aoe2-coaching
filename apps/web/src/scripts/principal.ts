/**
 * Comportamiento de la página: idioma, barra de navegación, descarga de la última
 * versión, scroll suave (Lenis) y animaciones con scroll (GSAP + ScrollTrigger).
 * Con "reducir movimiento" en el sistema, todo queda quieto y visible.
 */
import Lenis from "lenis";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { crearDemo } from "./demo";

gsap.registerPlugin(ScrollTrigger);

const REPO = "Zoen-DEV/aoe2-coaching";
const quieto = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const $ = <T extends Element = HTMLElement>(s: string, r: ParentNode = document) => r.querySelector<T>(s);
const $$ = <T extends Element = HTMLElement>(s: string, r: ParentNode = document) => [...r.querySelectorAll<T>(s)];

/* ---------- Idioma ---------- */
type Idioma = "es" | "en";
const meta = (window as any).__metaIdioma as Record<Idioma, { titulo: string; descripcion: string }>;

function ponerIdioma(idioma: Idioma) {
  document.documentElement.lang = idioma;
  try {
    localStorage.setItem("aoe2c-idioma", idioma);
  } catch {}
  if (meta) {
    document.title = meta[idioma].titulo;
    $('meta[name="description"]')?.setAttribute("content", meta[idioma].descripcion);
  }
  document.dispatchEvent(new CustomEvent("idioma"));
  requestAnimationFrame(() => ScrollTrigger.refresh());
}
$("[data-idioma]")?.addEventListener("click", () => {
  ponerIdioma(document.documentElement.lang === "es" ? "en" : "es");
});

/* ---------- Descarga: la última versión publicada en GitHub ---------- */
async function ultimaVersion() {
  try {
    const r = await fetch(`https://api.github.com/repos/${REPO}/releases?per_page=30`, {
      headers: { Accept: "application/vnd.github+json" },
    });
    if (!r.ok) return; // sin red o límite de la API: se quedan los enlaces del build
    const lista: any[] = await r.json();
    const pub = lista.find((x) => !x.draft && !x.prerelease && String(x.tag_name).startsWith("desktop-v"));
    const exe = pub?.assets?.find((a: any) => /^AoE2Coaching-Setup-.+\.exe$/.test(a.name));
    if (!pub || !exe) {
      // Aún no hay ninguna versión publicada: el botón lleva a la página de versiones.
      $$<HTMLAnchorElement>("[data-directa]").forEach((a) => (a.href = `https://github.com/${REPO}/releases`));
      return;
    }
    const version = String(pub.tag_name).replace("desktop-v", "");
    $$<HTMLAnchorElement>("[data-directa]").forEach((a) => (a.href = exe.browser_download_url));
    $$("[data-version]").forEach((el) => (el.textContent = `v${version}`));
  } catch {}
}
ultimaVersion();

/* ---------- Scroll suave ---------- */
let lenis: Lenis | null = null;
if (!quieto) {
  lenis = new Lenis({ duration: 1.15, easing: (t) => 1 - Math.pow(1 - t, 4) });
  lenis.on("scroll", ScrollTrigger.update);
  gsap.ticker.add((t) => lenis!.raf(t * 1000));
  gsap.ticker.lagSmoothing(0);
}

const nav = $("[data-nav]")!;
function irA(hash: string) {
  const destino = hash === "#inicio" ? 0 : $(hash);
  if (destino === null) return;
  nav.classList.remove("abierta");
  $("[data-menu]")?.setAttribute("aria-expanded", "false");
  if (lenis) lenis.scrollTo(destino as any, { offset: 0, duration: 1.6 });
  else if (destino === 0) window.scrollTo({ top: 0 });
  else (destino as HTMLElement).scrollIntoView();
}
$$<HTMLAnchorElement>('a[href^="#"]').forEach((a) =>
  a.addEventListener("click", (e) => {
    const hash = a.getAttribute("href")!;
    if (hash.length < 2) return;
    e.preventDefault();
    history.replaceState(null, "", hash);
    irA(hash);
  }),
);

/* ---------- Barra de navegación ---------- */
const progreso = $("[data-progreso]")!;
let ultimoY = 0;
function alHacerScroll() {
  const y = window.scrollY;
  nav.classList.toggle("solida", y > 30);
  const ocultar = y > window.innerHeight && y > ultimoY + 4 && !nav.classList.contains("abierta");
  if (ocultar) nav.classList.add("oculta");
  else if (y < ultimoY - 4 || y < window.innerHeight) nav.classList.remove("oculta");
  ultimoY = y;
  const max = document.documentElement.scrollHeight - window.innerHeight;
  progreso.style.transform = `scaleX(${max > 0 ? y / max : 0})`;
}
window.addEventListener("scroll", alHacerScroll, { passive: true });
alHacerScroll();

$("[data-menu]")?.addEventListener("click", (e) => {
  const abierta = nav.classList.toggle("abierta");
  nav.classList.remove("oculta");
  (e.currentTarget as HTMLElement).setAttribute("aria-expanded", String(abierta));
});

// Enlace activo según la sección en pantalla
$$<HTMLAnchorElement>("[data-enlace]").forEach((a) => {
  const sec = document.getElementById(a.dataset.enlace!);
  if (!sec) return;
  ScrollTrigger.create({
    trigger: sec,
    start: "top 45%",
    end: "bottom 45%",
    onToggle: (s) => a.classList.toggle("activo", s.isActive),
  });
});

/* ---------- Tarjeta del overlay ---------- */
const tarjeta = $("[data-tarjeta]");
const demo = tarjeta ? crearDemo(tarjeta) : null;
let progresoDemo = quieto ? 0.47 : 0;
demo?.pintar(progresoDemo);
document.addEventListener("idioma", () => demo?.pintar(progresoDemo));

/* ---------- Inclinación de las tarjetas de guías ---------- */
if (!quieto && window.matchMedia("(hover: hover)").matches) {
  $$("[data-inclinar]").forEach((el) => {
    el.addEventListener("pointermove", (e) => {
      const r = el.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width;
      const y = (e.clientY - r.top) / r.height;
      el.style.setProperty("--mx", `${x * 100}%`);
      el.style.setProperty("--my", `${y * 100}%`);
      gsap.to(el, { rotateY: (x - 0.5) * 7, rotateX: (0.5 - y) * 7, transformPerspective: 900, duration: 0.4, ease: "power2.out" });
    });
    el.addEventListener("pointerleave", () => gsap.to(el, { rotateX: 0, rotateY: 0, duration: 0.6, ease: "power3.out" }));
  });
}

/* ---------- Animaciones con scroll ---------- */
if (quieto) {
  $$("[data-ventana] [data-linea]").forEach((l) => ((l as unknown as SVGPathElement).style.strokeDashoffset = "0"));
  $$("[data-punto-g], [data-area]").forEach((p) => ((p as HTMLElement).style.opacity = "1"));
  $$("[data-paso]").forEach((li) => li.classList.add("encendido"));
  const tr = $("[data-trazo]") as unknown as SVGLineElement | null;
  if (tr) tr.style.strokeDashoffset = "0";
  $('[data-ss="detalle"]')?.classList.add("visible");
  $('[data-ss="ejecutar"]')?.classList.add("visible");
  const cursor = $('[data-ss="cursor"]');
  if (cursor) cursor.style.display = "none";
} else {
  animar();
}

function animar() {
  const mm = gsap.matchMedia();

  // Portada: entrada
  const intro = gsap.timeline({ defaults: { ease: "power3.out" } });
  intro
    .from("[data-capa]", { yPercent: 12, opacity: 0, duration: 1.8, stagger: 0.12 }, 0)
    .from("[data-intro]", { y: 40, opacity: 0, duration: 1.1, stagger: 0.12 }, 0.35);

  // Portada: parallax al bajar (las capas lejanas bajan más, así parecen moverse menos)
  const prof = [0.55, 0.42, 0.3, 0.16, 0.04];
  const hero = $("[data-hero]")!;
  $$("[data-capa]", hero).forEach((capa) => {
    const k = prof[Number(capa.dataset.capa)] ?? 0;
    gsap.to(capa, {
      yPercent: k * 60,
      ease: "none",
      scrollTrigger: { trigger: hero, start: "top top", end: "bottom top", scrub: true },
    });
  });
  gsap.to("[data-hero-texto]", {
    y: () => window.innerHeight * 0.35,
    opacity: 0,
    scale: 0.96,
    ease: "none",
    scrollTrigger: { trigger: hero, start: "top top", end: "70% top", scrub: true },
  });

  // Portada: parallax con el ratón
  if (window.matchMedia("(hover: hover)").matches) {
    const movs = $$("[data-capa]", hero).map((capa) => ({
      x: gsap.quickTo(capa, "x", { duration: 1.2, ease: "power3.out" }),
      k: [4, 10, 18, 28, 44][Number(capa.dataset.capa)] ?? 0,
    }));
    hero.addEventListener("pointermove", (e) => {
      const nx = e.clientX / window.innerWidth - 0.5;
      movs.forEach((m) => m.x(-nx * m.k));
    });
  }

  // Entradas al aparecer en pantalla
  ScrollTrigger.batch("[data-aparece]", {
    start: "top 88%",
    once: true,
    onEnter: (els) => gsap.to(els, { opacity: 1, y: 0, duration: 1, ease: "power3.out", stagger: 0.1, overwrite: true }),
  });

  // Tarjeta del overlay: la sección queda fija y los pasos avanzan con el scroll
  const escena = $("[data-demo-escena]");
  if (escena && demo) {
    gsap.from("[data-tarjeta]", {
      y: 80,
      opacity: 0,
      rotateY: -20,
      duration: 1.2,
      ease: "power3.out",
      scrollTrigger: { trigger: escena, start: "top 75%" },
    });
    mm.add(
      { grande: "(min-width: 901px)", pequena: "(max-width: 900px)" },
      (ctx) => {
        ScrollTrigger.create({
          trigger: escena,
          start: "top top",
          end: ctx.conditions!.grande ? "+=320%" : "+=260%",
          pin: true,
          scrub: true,
          anticipatePin: 1,
          onUpdate: (s) => {
            progresoDemo = s.progress;
            demo.pintar(s.progress);
          },
        });
      },
    );
  }

  // Pasos para empezar: la línea se dibuja y se encienden los círculos
  const trazo = $("[data-trazo]");
  const pasos = $$("[data-paso]");
  if (pasos.length) {
    gsap.from(pasos, {
      y: 50,
      opacity: 0,
      stagger: 0.15,
      duration: 1,
      ease: "power3.out",
      scrollTrigger: { trigger: "[data-pasos] ol", start: "top 85%" },
    });
    ScrollTrigger.create({
      trigger: "[data-pasos] ol",
      start: "top 75%",
      end: "bottom 55%",
      scrub: true,
      onUpdate: (s) => {
        if (trazo) trazo.style.strokeDashoffset = String(1000 * (1 - s.progress));
        pasos.forEach((li, i) => li.classList.toggle("encendido", s.progress >= i / (pasos.length - 1) - 0.02));
      },
    });
  }

  // Panel: la ventana se endereza y el gráfico se dibuja
  const ventana = $("[data-ventana]");
  if (ventana) {
    gsap.fromTo(
      ventana,
      { rotateX: 22, scale: 0.9, y: 80, opacity: 0.4, transformPerspective: 1400 },
      {
        rotateX: 0,
        scale: 1,
        y: 0,
        opacity: 1,
        ease: "none",
        scrollTrigger: { trigger: ventana, start: "top 95%", end: "top 35%", scrub: true },
      },
    );
    const graf = gsap.timeline({ scrollTrigger: { trigger: ventana, start: "top 55%" } });
    graf
      .to($("[data-linea]", ventana), { strokeDashoffset: 0, duration: 1.8, ease: "power2.inOut" })
      .to($$("[data-punto-g]", ventana), { opacity: 1, duration: 0.3, stagger: 0.1 }, 0.2)
      .to($("[data-area]", ventana), { opacity: 1, duration: 1 }, 0.9);
    $$("[data-contar]", ventana).forEach((el) => {
      const fin = Number(el.dataset.contar);
      const o = { v: 0 };
      graf.to(o, { v: fin, duration: 1.4, ease: "power2.out", onUpdate: () => (el.textContent = String(Math.round(o.v))) }, 0);
    });
  }

  // Mapas: galería horizontal fija en pantallas grandes
  mm.add("(min-width: 861px)", () => {
    const pista = $("[data-pista]");
    const pin = $("[data-mapas-pin]");
    if (!pista || !pin) return;
    const distancia = () => Math.max(0, pista.scrollWidth - window.innerWidth);
    gsap.to(pista, {
      x: () => -distancia(),
      ease: "none",
      scrollTrigger: {
        trigger: pin,
        start: "top top",
        end: () => `+=${distancia()}`,
        pin: true,
        scrub: 0.6,
        invalidateOnRefresh: true,
        anticipatePin: 1,
      },
    });
  });
  mm.add("(max-width: 860px)", () => {
    gsap.from(".mapa", { x: 80, opacity: 0, stagger: 0.1, duration: 1, ease: "power3.out", scrollTrigger: { trigger: "[data-pista]", start: "top 85%" } });
  });

  // MODs: la escena se acerca un poco al bajar
  const esc = $("[data-escena]");
  if (esc) {
    gsap.fromTo(esc.querySelector(".cesped"), { yPercent: -6 }, { yPercent: 6, ease: "none", scrollTrigger: { trigger: esc, scrub: true } });
  }

  // SmartScreen: el cursor pulsa "Más información" y "Ejecutar de todas formas"
  const ss = $("[data-smartscreen]");
  if (ss) {
    const cursor = $('[data-ss="cursor"]', ss)!;
    const mas = $('[data-ss="mas"]', ss)!;
    const detalle = $('[data-ss="detalle"]', ss)!;
    const ejecutar = $('[data-ss="ejecutar"]', ss)!;
    const centro = (el: HTMLElement) => {
      const a = ss.getBoundingClientRect();
      const b = el.getBoundingClientRect();
      return { left: b.left - a.left + b.width * 0.45, top: b.top - a.top + b.height * 0.55 };
    };
    const reiniciar = () => {
      detalle.classList.remove("visible");
      ejecutar.classList.remove("visible", "pulsado");
      mas.classList.remove("pulsado");
      gsap.set(cursor, { left: "75%", top: "85%", scale: 1, opacity: 0 });
    };
    const tl = gsap.timeline({ paused: true, onStart: reiniciar });
    tl.to(cursor, { opacity: 1, duration: 0.3 })
      .to(cursor, { ...{ left: () => centro(mas).left, top: () => centro(mas).top }, duration: 1, ease: "power2.inOut" })
      .to(cursor, { scale: 0.8, duration: 0.1, yoyo: true, repeat: 1 })
      .call(() => {
        mas.classList.add("pulsado");
        detalle.classList.add("visible");
        ejecutar.classList.add("visible");
      })
      .to(cursor, { left: () => centro(ejecutar).left, top: () => centro(ejecutar).top, duration: 1.1, ease: "power2.inOut" }, "+=0.6")
      .to(cursor, { scale: 0.8, duration: 0.1, yoyo: true, repeat: 1 })
      .call(() => ejecutar.classList.add("pulsado"));
    reiniciar();
    ScrollTrigger.create({ trigger: ss, start: "top 70%", onEnter: () => tl.restart(), onEnterBack: () => tl.restart() });
  }

  // Al terminar de cargar las fuentes cambian las medidas
  document.fonts?.ready.then(() => ScrollTrigger.refresh());
}
