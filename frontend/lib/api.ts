// Cliente de la API. Misma origen (Caddy sirve web y /api), así la cookie httpOnly
// SameSite=Strict viaja sola y JavaScript nunca ve el token.

export class ErrorApi extends Error {
  constructor(public estado: number, public codigo: string, mensaje: string, public detalle?: unknown) {
    super(mensaje);
  }
}

export async function api<T>(ruta: string, opciones: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...resto } = opciones;
  const r = await fetch(`/api/v1${ruta}`, {
    credentials: "same-origin",
    ...resto,
    headers: { Accept: "application/json", ...(json !== undefined ? { "Content-Type": "application/json" } : {}), ...headers },
    body: json !== undefined ? JSON.stringify(json) : resto.body,
  });
  if (r.ok) return (r.status === 204 ? undefined : await r.json()) as T;
  let cuerpo: { codigo?: string; mensaje?: string; detalle?: unknown } = {};
  try {
    cuerpo = await r.json();
  } catch {
    /* respuesta sin JSON (p. ej. la API está caída detrás de Caddy) */
  }
  throw new ErrorApi(r.status, cuerpo.codigo ?? "error", cuerpo.mensaje ?? mensajePorEstado(r.status), cuerpo.detalle);
}

export function mensajePorEstado(estado: number): string {
  if (estado === 429) return "Demasiadas consultas seguidas. Espera un minuto y vuelve a intentar.";
  if (estado >= 500) return "El servidor no respondió. Revisa que los contenedores estén arriba e intenta de nuevo.";
  return "No se pudo completar la acción.";
}

// ---------------------------------------------------------------- tipos de la API
export type Catalogos = {
  sedes: { id: number; codigo: string; nombre: string; ciudad: string }[];
  zonas: { id: number; sede_id: number; nombre: string }[];
  categorias: { id: number; codigo: string; nombre: string; es_documento: boolean }[];
};

export type ObjetoPublico = {
  tipo: "perdido";
  id: string;
  categoria: string;
  zona: string | null;
  descripcion: string;
  fecha: string;
  estado: "publicado" | "en_coincidencia";
  publicado_en: string;
};

export type PaginaPublica = { items: ObjetoPublico[]; siguiente: string | null; instrucciones: string };

export type Usuario = { id: string; nombre: string; rol: "admin_sede" | "auditor"; sede_id: number | null };

export type SemanaPrediccion = {
  semana_inicio: string;
  clase: "parciales" | "vacaciones" | "inicio" | "normal";
  esperado: number;
  minimo_90: number;
  maximo_90: number;
};

export type Informe = {
  id: string;
  sede_id: number | null;
  creado_en: string;
  datos_hasta: string;
  resumen: string;
  resumen_fuente: "llm" | "plantilla";
  modelo_llm: string | null;
  metricas: {
    sede: string;
    mes?: {
      periodo: string;
      reportados: number;
      recuperados: number;
      tasa_recuperacion_pct: number;
      tasa_mes_anterior_pct: number | null;
      dias_tipicos_hasta_recuperar: number | null;
      categoria_menos_recuperada: { categoria: string; tasa_pct: number } | null;
      categoria_mas_recuperada: { categoria: string; tasa_pct: number } | null;
    };
    zonas_criticas?: { zona: string; dia: string; franja: string; perdidas: number }[];
    mapa_calor?: { zona: string; franja: string; perdidas: number }[];
    matching_4_semanas?: { sugeridas: number; precision_pct: number };
  };
  prediccion: {
    semanas: SemanaPrediccion[];
    historia?: { semana_inicio: string; perdidas: number; clase: SemanaPrediccion["clase"] }[];
    backtest: { mae_modelo: number; mae_ingenuo: number; mejora_pct: number; gana_modelo: boolean; semanas_evaluadas: number } | null;
  };
};
