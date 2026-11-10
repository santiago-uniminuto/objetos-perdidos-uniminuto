import Link from "next/link";

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
          Ingreso del personal
        </Link>
      </div>
    </header>
  );
}
