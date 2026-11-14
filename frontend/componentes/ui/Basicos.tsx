import type { ReactNode } from "react";

import estilos from "./ui.module.css";

const ESTADOS: Record<string, { nombre: string; tono: "abierto" | "proceso" | "cerrado" | "vencido" }> = {
  registrado: { nombre: "Registrado", tono: "abierto" },
  publicado: { nombre: "Publicado", tono: "abierto" },
  en_coincidencia: { nombre: "Con posible coincidencia", tono: "proceso" },
  entregado: { nombre: "Entregado", tono: "cerrado" },
  cerrado: { nombre: "Cerrado", tono: "cerrado" },
  expirado: { nombre: "Venció la custodia", tono: "vencido" },
  donado: { nombre: "Donado", tono: "vencido" },
  descartado: { nombre: "Descartado", tono: "vencido" },
};

/** Estado de un caso: siempre con texto (el color solo acompaña). */
export function Insignia({ estado, tipo = "perdido" }: { estado: string; tipo?: "perdido" | "hallado" }) {
  // un hallazgo "publicado" no sale en el portal (ADR-016): para el admin está en custodia
  const e = tipo === "hallado" && estado === "publicado" ? { nombre: "En custodia", tono: "abierto" as const }
    : ESTADOS[estado] ?? { nombre: estado, tono: "abierto" as const };
  return <span className={estilos.insignia} data-tono={e.tono}>{e.nombre}</span>;
}

/** Estado vacío: dice qué pasa y qué hacer. La caja isométrica es el único dibujo. */
export function Vacio({ titulo, children, accion }: { titulo: string; children?: ReactNode; accion?: ReactNode }) {
  return (
    <div className={estilos.vacio}>
      <CajaIsometrica />
      <div>
        <h3>{titulo}</h3>
        {children && <p className="secundario">{children}</p>}
        {accion && <div style={{ marginTop: "0.9rem" }}>{accion}</div>}
      </div>
    </div>
  );
}

function CajaIsometrica() {
  // caja de objetos perdidos en isométrico (30°): tapa abierta y una etiqueta amarilla colgando
  return (
    <svg viewBox="0 0 120 100" width="120" height="100" aria-hidden="true" className={estilos.caja}>
      <path d="M60 30 L100 50 L60 70 L20 50 Z" fill="#c7d6eb" />
      <path d="M20 50 L60 70 L60 95 L20 75 Z" fill="#93afd6" />
      <path d="M100 50 L60 70 L60 95 L100 75 Z" fill="#5a84bc" />
      <path d="M20 50 L60 30 L46 18 L8 38 Z" fill="#eaf0f8" stroke="#14284a" strokeWidth="1.2" />
      <path d="M100 50 L60 30 L74 18 L112 38 Z" fill="#eaf0f8" stroke="#14284a" strokeWidth="1.2" />
      <path d="M20 50 L60 70 L100 50 M60 70 L60 95 M20 50 L20 75 L60 95 L100 75 L100 50" fill="none"
        stroke="#14284a" strokeWidth="1.4" strokeLinejoin="round" />
      <path d="M78 64 L80 82" stroke="#14284a" strokeWidth="1" />
      <path d="M74 82 L88 79 L90 88 L76 91 Z" fill="#f4c21a" stroke="#14284a" strokeWidth="1" />
    </svg>
  );
}

/** Pasos de un formulario: es una secuencia real, por eso lleva números. */
export function Pasos({ pasos, actual }: { pasos: string[]; actual: number }) {
  return (
    <ol className={estilos.pasos}>
      {pasos.map((p, i) => (
        <li key={p} data-estado={i < actual ? "hecho" : i === actual ? "actual" : "pendiente"}
          aria-current={i === actual ? "step" : undefined}>
          <span className={estilos.pasoNumero}>{i < actual ? "✓" : i + 1}</span>
          <span>{p}</span>
        </li>
      ))}
    </ol>
  );
}

export function Campo({ etiqueta, ayuda, error, children }: {
  etiqueta: string; ayuda?: string; error?: string | null; children: ReactNode;
}) {
  return (
    <label className={`campo ${error ? "campo-error" : ""}`}>
      <span>{etiqueta}</span>
      {children}
      {error ? <small className="error">{error}</small> : ayuda && <small>{ayuda}</small>}
    </label>
  );
}
