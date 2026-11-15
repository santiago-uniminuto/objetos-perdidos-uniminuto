// Cliente de la API. Misma origen (Caddy sirve web y /api), así la cookie httpOnly
// SameSite=Strict viaja sola y JavaScript nunca ve el token.

export class ErrorApi extends Error {
  estado: number;
  codigo: string;
  detalle?: unknown;

  constructor(estado: number, codigo: string, mensaje: string, detalle?: unknown) {
    super(mensaje);
    this.estado = estado;
    this.codigo = codigo;
    this.detalle = detalle;
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

/** Sube una foto (multipart). La API la valida, la reduce y le quita los metadatos. */
export async function subirFoto(coleccion: "reportes" | "hallazgos", objetoId: string, archivo: File): Promise<FotoInfo> {
  const datos = new FormData();
  datos.append("archivo", archivo);
  return api<FotoInfo>(`/${coleccion}/${objetoId}/fotos`, { method: "POST", body: datos });
}

export const urlFoto = (id: string, tamano: "mini" | "grande" = "mini", publica = false) =>
  `/api/v1/${publica ? "publico/" : ""}fotos/${id}/${tamano}`;

/** POST que crea algo: con Idempotency-Key, un doble clic o un reintento no duplica el registro. */
export function crear<T>(ruta: string, json: unknown, clave: string): Promise<T> {
  return api<T>(ruta, { method: "POST", json, headers: { "Idempotency-Key": clave } });
}

export function mensajePorEstado(estado: number): string {
  if (estado === 429) return "Demasiadas consultas seguidas. Espera un minuto y vuelve a intentar.";
  if (estado >= 500) return "El servidor no respondió. Revisa que los contenedores estén arriba e intenta de nuevo.";
  return "No se pudo completar la acción.";
}

// ---------------------------------------------------------------- tipos de la API
export type Sede = { id: number; codigo: string; nombre: string; ciudad: string; region: string; direccion: string | null };

/** Agrupa las sedes por región, en el orden en que llegan (la sede principal primero). */
export function sedesPorRegion(sedes: Sede[]): [string, Sede[]][] {
  const grupos = new Map<string, Sede[]>();
  for (const s of sedes) grupos.set(s.region, [...(grupos.get(s.region) ?? []), s]);
  return [...grupos];
}

export type Catalogos = {
  sedes: Sede[];
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
  fotos: string[];
};

export type PaginaPublica = { items: ObjetoPublico[]; siguiente: string | null; instrucciones: string };

export type Usuario = {
  id: string; nombre: string; rol: "admin_sede" | "auditor"; sede_id: number | null;
  /** Nombre y ciudad de la sede; null para el auditor */
  sede: string | null; ciudad: string | null;
};

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
  ultima_corrida: string | null;
  proxima_corrida: string | null;
  cada_horas: number;
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

export type FotoInfo = { id: string; orden: number; ancho: number; alto: number };

export type Estudiante = {
  id: string;
  tipo_documento: string;
  numero_documento: string;
  nombres: string;
  apellidos: string;
  correo_institucional: string | null;
  anonimizado_en: string | null;
  consentimiento_vigente: { finalidades: string[]; otorgado_en: string } | null;
};

export type ObjetoLista = {
  id: string;
  creado_en: string;
  estado: string;
  categoria: string;
  zona: string | null;
  descripcion_publica: string;
  fecha_perdida?: string;
  fecha_hallazgo?: string;
  ubicacion_bodega?: string | null;
  vence_en?: string;
  foto: string | null;
};

export type ObjetoDetalle = ObjetoLista & {
  categoria_id: number;
  zona_id: number | null;
  descripcion: string;
  detalle_control?: string | null;
  hora_aprox: string | null;
  encontrado_por?: string | null;
  nombres?: string;
  apellidos?: string;
  tipo_documento?: string;
  numero_documento?: string;
  correo_institucional?: string | null;
  fotos: FotoInfo[];
};
