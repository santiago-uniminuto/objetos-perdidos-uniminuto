"use client";

import Link from "next/link";
import { type InputHTMLAttributes, type ReactNode, useState } from "react";

import estilos from "./Acceso.module.css";

const PASOS = [
  { titulo: "Se reporta", texto: "El estudiante cuenta qué perdió, dónde y cuándo." },
  { titulo: "La IA sugiere", texto: "Compara con lo hallado en las sedes de la ciudad." },
  { titulo: "Tú verificas y entregas", texto: "Confirmas la identidad y cierras el caso." },
];

/**
 * Marco común de login, olvidé y restablecer: tarjeta de vidrio en dos paneles.
 * A la izquierda el formulario (lo único accionable); a la derecha, cómo funciona el sistema.
 * En celular el panel informativo baja y se compacta: el formulario siempre va primero.
 */
export function Acceso({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <main className={estilos.fondo}>
      <div className={estilos.decoracion} aria-hidden="true">
        <span className={estilos.rejilla} />
        <span className={`${estilos.halo} ${estilos.haloSenal}`} />
        <span className={`${estilos.halo} ${estilos.haloAzul}`} />
        <span className={estilos.anillo} />
        <span className={`${estilos.cuadro} ${estilos.cuadro1}`} />
        <span className={`${estilos.cuadro} ${estilos.cuadro2}`} />
        <span className={`${estilos.cuadro} ${estilos.cuadro3}`} />
      </div>

      <div className={estilos.tarjeta}>
        <section className={estilos.panelFormulario}>
          <Link href="/" className={estilos.volver}>
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <path d="M16 10H4m0 0 5-5m-5 5 5 5" />
            </svg>
            Ir al portal público
          </Link>
          <div className={estilos.encabezado}>
            <p className={estilos.antetitulo}>Objetos perdidos · UNIMINUTO</p>
            <h1 className={estilos.titulo}>{titulo}</h1>
          </div>
          <div className={estilos.contenido}>{children}</div>
          <p className={estilos.confianza}>
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <rect x="4" y="9" width="12" height="8" rx="2" />
              <path d="M7 9V6.5a3 3 0 0 1 6 0V9" />
            </svg>
            Conexión cifrada · Solo personal autorizado
          </p>
        </section>

        <aside className={estilos.panelInfo} aria-label="Cómo funciona">
          <div className={estilos.ilustracion} aria-hidden="true">
            <svg className={estilos.conector} viewBox="0 0 100 100" preserveAspectRatio="none">
              <path d="M22 30 C 30 75, 60 40, 78 74" />
            </svg>
            <div className={estilos.etiqueta}>
              <span className={estilos.ojal} />
              <div>
                <small>Reportado</small>
                <strong>Mochila azul</strong>
                <span>Biblioteca · hace 2 h</span>
              </div>
            </div>
            <div className={estilos.hallazgo}>
              <small>Hallazgo · otra sede</small>
              <strong>Morral azul oscuro</strong>
              <span>Cafetería · ayer</span>
            </div>
            <div className={estilos.chipCoincidencia}>
              <span className={estilos.punto} />
              Posible coincidencia
            </div>
          </div>

          <div className={estilos.textoInfo}>
            <h2>Cada objeto tiene camino de vuelta</h2>
            <ol className={estilos.pasos}>
              {PASOS.map((p) => (
                <li key={p.titulo}>
                  <strong>{p.titulo}</strong>
                  <span>{p.texto}</span>
                </li>
              ))}
            </ol>
          </div>
        </aside>
      </div>
    </main>
  );
}

export function Formulario({ onSubmit, children }: { onSubmit: () => void; children: ReactNode }) {
  return (
    <form
      className={estilos.formulario}
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      {children}
    </form>
  );
}

/** Campo de contraseña con botón para verla: reduce errores al escribir en el celular. */
export function Clave(props: Omit<InputHTMLAttributes<HTMLInputElement>, "type">) {
  const [visible, setVisible] = useState(false);
  return (
    <span className={estilos.clave}>
      <input {...props} type={visible ? "text" : "password"} />
      <button
        type="button"
        className={estilos.ojo}
        aria-label={visible ? "Ocultar contraseña" : "Mostrar contraseña"}
        aria-pressed={visible}
        onClick={() => setVisible((v) => !v)}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" />
          <circle cx="12" cy="12" r="3" />
          {visible && <path d="M4 4l16 16" />}
        </svg>
      </button>
    </span>
  );
}

/** Avance hacia el mínimo de caracteres: se ve antes de enviar, no después del error. */
export function Medidor({ largo, minimo }: { largo: number; minimo: number }) {
  const listo = largo >= minimo;
  return (
    <div className={estilos.medidor} data-listo={listo}>
      <span className={estilos.barra}>
        <span style={{ width: `${Math.min(100, (largo / minimo) * 100)}%` }} />
      </span>
      <span className={estilos.cuenta}>{listo ? "Largo suficiente" : `${largo}/${minimo} caracteres`}</span>
    </div>
  );
}
