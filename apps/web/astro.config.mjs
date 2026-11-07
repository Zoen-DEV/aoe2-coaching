// Página oficial de AoE2 Coaching. Ver docs/05-pagina-oficial.md.
import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://aoe2c.zoen.dev",
  // Todo es estático: Vercel solo sirve la carpeta dist.
  output: "static",
  build: { inlineStylesheets: "auto" },
});
