// Revisión de la descripción completa mientras el admin escribe: ¿tiene lo que la IA usa para cruzar?
// Es una guía, no un bloqueo. Vocabulario alineado con agentes/ia/normalizador.py (heurística).

const plano = (s: string) => s.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();

const TIPOS = [
  "celular", "portatil", "computador", "audifonos", "cargador", "tablet", "calculadora", "mouse", "usb", "airpods",
  "carne", "cedula", "tarjeta", "licencia", "pasaporte", "chaqueta", "buzo", "saco", "gorra", "bufanda", "chompa",
  "sudadera", "chaleco", "billetera", "gafas", "lentes", "reloj", "maleta", "morral", "mochila", "sombrilla", "paraguas",
  "cartuchera", "estuche", "pulsera", "anillo", "collar", "cuaderno", "libro", "carpeta", "agenda", "regla", "llavero",
  "llaves", "llave", "termo", "botella", "vaso", "pocillo", "tomatodo", "mug", "esfero", "lapicero", "bolso", "cartera",
  "chaqueta", "audifono", "parlante", "control", "disco",
];
const MARCAS = [
  "stanley", "samsung", "apple", "iphone", "xiaomi", "motorola", "huawei", "lenovo", "hp", "dell", "asus", "acer", "jbl",
  "sony", "casio", "totto", "adidas", "nike", "puma", "contigo", "hydro flask", "ray-ban", "rayban", "norma", "scribe",
  "tous", "quiksilver", "under armour", "north face", "columbia", "logitech", "kipling", "jansport", "oppo", "redmi",
];
const COLORES = [
  "azul", "negro", "negra", "blanco", "blanca", "rojo", "roja", "verde", "amarillo", "amarilla", "morado", "morada", "gris",
  "dorado", "dorada", "cafe", "marron", "beige", "rosado", "rosada", "naranja", "transparente", "plateado", "plateada",
  "celeste", "turquesa", "vinotinto", "lila", "fucsia", "crema",
];
const DETALLE = /\b(con|tiene|sticker|calcomania|forro|funda|estuche|rayad|rot[oa]|golpe|desgast|llavero|iniciales|modelo|referencia|talla|litros?|pulgadas|gb|marcad|grabad|parche|cremallera|bolsillo|correa|tapa)\w*/;

const tiene = (texto: string, palabras: string[]) => palabras.some((p) => new RegExp(`\\b${p.replace(/[-\s]/g, "[-\\s]?")}s?\\b`).test(texto));

export type Revision = { que: boolean; marca: boolean; color: boolean; detalle: boolean; campos: boolean };

export function revisarDescripcion(texto: string): Revision {
  const t = plano(texto);
  return {
    que: tiene(t, TIPOS) || /\b(tipo|objeto)\s*:\s*\w/.test(t),
    marca: tiene(t, MARCAS) || /\bmarca\s*:\s*\w/.test(t),
    color: tiene(t, COLORES),
    detalle: DETALLE.test(t),
    campos: /\b(modelo|marca|color|tipo)\s*:/.test(t),
  };
}
