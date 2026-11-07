/**
 * Iconos de los pasos (trazos de 24x24), dibujados para la web: no se usa arte del juego.
 * La clave es el "icono" de cada paso de las build orders.
 */
export const ICONOS: Record<string, string> = {
  casa: '<path d="M4 11 12 4l8 7"/><path d="M6 10v10h12V10"/><path d="M10 20v-5h4v5"/>',
  oveja:
    '<ellipse cx="12" cy="13" rx="6.5" ry="4.5"/><circle cx="19" cy="10.5" r="2"/><path d="M8 17.5V20M15 17.5V20"/>',
  campamento_maderero:
    '<path d="M14 4 20 10l-2.5 2.5-6-6z"/><path d="M12.5 8.5 4 17l3 3 8.5-8.5"/>',
  jabali:
    '<path d="M4 14c0-4 3.5-6.5 8-6.5S20 10 20 13.5c0 2.5-2 4-4.5 4H8C5.5 17.5 4 16 4 14Z"/><path d="M7 17.5V20M15 17.5V20M19.5 12l2-1"/>',
  molino: '<path d="M12 12 6 6M12 12l6-6M12 12l6 6M12 12l-6 6"/><path d="M10 20h4l-1-8h-2z"/>',
  campamento_minero: '<path d="M4 9c4-4 12-4 16 0"/><path d="M12 7v13"/>',
  centro_urbano: '<path d="M3 20h18"/><path d="M5 20V11l7-6 7 6v9"/><path d="M9 20v-5h6v5"/><path d="M12 5V2.5h3"/>',
  granja: '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 10h16M4 16h16M10 4v16"/>',
  mercado: '<path d="M4 10h16l-1.5-5h-13z"/><path d="M5.5 10v10h13V10"/><path d="M10 20v-5h4v5"/>',
  aldeano: '<circle cx="12" cy="7" r="3"/><path d="M6 20c0-4 2.7-7 6-7s6 3 6 7"/>',
  castillo:
    '<path d="M4 20V8h3v2h2V8h2v2h2V8h2v2h2V8h3v12z"/><path d="M10 20v-4a2 2 0 0 1 4 0v4"/>',
  cuartel: '<path d="M6 4 18 16M18 4 6 16"/><path d="M4 18l2-2M20 18l-2-2"/>',
  establo: '<path d="M7 20v-6c0-3 2-6 5-7l3-3 1 3c2 1.5 3 3.5 3 6v7"/><path d="M11 12h.01"/>',
  explorador: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>',
};

export function icono(clave: string, clase = ""): string {
  const trazos = ICONOS[clave] ?? '<circle cx="12" cy="12" r="7"/>';
  return `<svg class="${clase}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${trazos}</svg>`;
}
