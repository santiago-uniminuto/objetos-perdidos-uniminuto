// La explicación del matcher llega como texto: "[alta] Ambos son termos azules. Coincide en: color, tipo. Difiere en: marca."
// Se separa para mostrar la confianza y las listas por aparte, sin depender de cómo lo redactó el LLM.

export type Explicacion = { confianza: "alta" | "media" | "baja" | null; texto: string; coincide: string[]; difiere: string[] };

export function leerExplicacion(cruda: string | null | undefined): Explicacion | null {
  if (!cruda?.trim()) return null;
  let resto = cruda.trim();
  let confianza: Explicacion["confianza"] = null;
  const m = /^\[(alta|media|baja)\]\s*/i.exec(resto);
  if (m) {
    confianza = m[1]!.toLowerCase() as Explicacion["confianza"];
    resto = resto.slice(m[0].length);
  }
  const lista = (etiqueta: string): string[] => {
    const r = new RegExp(`${etiqueta}:\\s*([^]*?)\\.(?=\\s*(?:Coincide en:|Difiere en:|$))`, "i").exec(resto);
    if (!r) return [];
    resto = resto.replace(r[0], "").trim();
    return r[1]!.split(",").map((s) => s.trim()).filter(Boolean);
  };
  const coincide = lista("Coincide en");
  const difiere = lista("Difiere en");
  return { confianza, texto: resto.trim(), coincide, difiere };
}
