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
        {/* a los lados (pantallas anchas): etiquetas y una llave en trazo fino, y vidrios flotando */}
        <svg className={`${estilos.trazo} ${estilos.trazoEtiqueta}`} viewBox="0 0 124 74">
          <path d="M22 2h100v70H22L2 52V22Z" />
          <circle cx="15" cy="37" r="5" />
          <path d="M32 6v62" strokeDasharray="3 4" />
          <path d="M44 26h56M44 40h40M44 52h28" />
        </svg>
        <svg className={`${estilos.trazo} ${estilos.trazoLlave}`} viewBox="0 0 120 50">
          <circle cx="22" cy="25" r="16" />
          <circle cx="22" cy="25" r="6" />
          <path d="M38 25h76M98 25v12M108 25v9M88 25v7" />
        </svg>
        <svg className={`${estilos.trazo} ${estilos.trazoEtiqueta2}`} viewBox="0 0 124 74">
          <path d="M22 2h100v70H22L2 52V22Z" />
          <circle cx="15" cy="37" r="5" />
          <path d="M32 6v62" strokeDasharray="3 4" />
        </svg>
        <span className={`${estilos.cuadro} ${estilos.cuadroIzq}`} />
        <span className={`${estilos.cuadro} ${estilos.cuadroDer}`} />
        <span className={`${estilos.cuadro} ${estilos.cuadroDer2}`} />
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
