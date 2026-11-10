import Link from "next/link";
import type { ReactNode } from "react";

import estilos from "./Acceso.module.css";

/** Marco común de login, olvidé y restablecer: una sola columna, sin distracciones. */
export function Acceso({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <main className={estilos.fondo}>
      <div className={estilos.caja}>
        <Link href="/" className={estilos.volver}>
          Ir al portal público
        </Link>
        <h1 className={estilos.titulo}>{titulo}</h1>
        {children}
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
