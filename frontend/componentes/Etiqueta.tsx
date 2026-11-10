import Link from "next/link";

import type { ObjetoPublico } from "@/lib/api";
import { fechaLarga, haceCuanto } from "@/lib/formato";

import estilos from "./Etiqueta.module.css";

/** Un objeto perdido como etiqueta de cartulina con ojal: lo único "ilustrado" del portal. */
export function Etiqueta({ objeto, enlace = true }: { objeto: ObjetoPublico; enlace?: boolean }) {
  return (
    <article className={estilos.etiqueta}>
      <span className={estilos.ojal} aria-hidden="true" />
      <div className={estilos.cuerpo}>
        <h3 className={estilos.categoria}>{objeto.categoria}</h3>
        <p className={estilos.descripcion}>{objeto.descripcion}</p>
        <dl className={estilos.datos}>
          <div>
            <dt>Dónde</dt>
            <dd>{objeto.zona ?? "Sin zona"}</dd>
          </div>
          <div>
            <dt>Cuándo</dt>
            <dd>
              <time dateTime={objeto.fecha} title={fechaLarga(objeto.fecha)}>
                {haceCuanto(objeto.fecha)}
              </time>
            </dd>
          </div>
        </dl>
        {objeto.estado === "en_coincidencia" && (
          <p className={estilos.revision}>Ya hay un posible hallazgo en revisión</p>
        )}
        {enlace && (
          <Link className={estilos.enlace} href={`/objeto/?id=${objeto.id}`}>
            Ver etiqueta<span className="visualmente-oculto"> de {objeto.categoria}</span>
          </Link>
        )}
      </div>
    </article>
  );
}
