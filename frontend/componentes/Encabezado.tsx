import Link from "next/link";
import type { ReactNode } from "react";

import estilos from "./Encabezado.module.css";

export function Encabezado() {
  return (
    <header className={estilos.encabezado}>
      <div className={`envoltura ${estilos.fila}`}>
        <Link href="/" className={estilos.marca}>
          <span className={estilos.simbolo} aria-hidden="true" />
          Objetos perdidos <span className={estilos.institucion}>UNIMINUTO</span>
        </Link>
        <Link href="/admin/" className={estilos.personal}>
          <svg viewBox="0 0 20 20" aria-hidden="true">
            <circle cx="10" cy="7" r="3.2" />
            <path d="M3.8 17c.9-3 3.3-4.6 6.2-4.6s5.3 1.6 6.2 4.6" />
          </svg>
          <span>
            Ingreso <span className={estilos.ocultarMovil}>del personal</span>
          </span>
        </Link>
      </div>
    </header>
  );
}

/**
 * Marco del portal público: fondo azul tinta con rejilla y halos fijos, encabezado de vidrio y pie.
 * Lo comparten la lista y el detalle de un objeto.
 */
export function MarcoPublico({ children }: { children: ReactNode }) {
  return (
    <div className={estilos.pagina}>
      <div className={estilos.decoracion} aria-hidden="true">
        <span className={estilos.rejilla} />
        <span className={`${estilos.halo} ${estilos.haloSenal}`} />
        <span className={`${estilos.halo} ${estilos.haloAzul}`} />
      </div>
      <Encabezado />
      {children}
      <footer className={estilos.pie}>
        <div className={`envoltura ${estilos.filaPie}`}>
          <p>
            <span className={estilos.simbolo} aria-hidden="true" /> Objetos perdidos · Comunidad UNIMINUTO
          </p>
          <p>Aquí no se publican datos personales de nadie.</p>
        </div>
      </footer>
    </div>
  );
}
