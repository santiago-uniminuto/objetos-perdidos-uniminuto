import Link from "next/link";
import type { ReactNode } from "react";

import { Foto } from "@/componentes/ui/Foto";
import { type ObjetoPublico, urlFoto } from "@/lib/api";
import { fechaLarga, haceCuanto } from "@/lib/formato";

import estilos from "./Etiqueta.module.css";

/** Dibujos en trazo para cuando el reporte no trae foto (se eligen por el nombre de la categoría). */
const ICONOS: [RegExp, ReactNode][] = [
  [/document|carn|c[eé]dula/i, <><rect x="4" y="12" width="40" height="26" rx="4" /><circle cx="16" cy="24" r="4.5" /><path d="M9 33c1.5-3.4 4-5 7-5s5.5 1.6 7 5M28 21h10M28 27h10M28 32h6" /></>],
  [/electr|celular|tel[eé]fono|aud[ií]fono|cargador|port[aá]til/i, <><rect x="15" y="5" width="18" height="38" rx="4" /><path d="M21 9h6M22 38h4" /><circle cx="24" cy="21" r="5" /></>],
  [/botella|termo|vaso/i, <><path d="M19 6h10v6l3 5v22a4 4 0 0 1-4 4h-8a4 4 0 0 1-4-4V17l3-5Z" /><path d="M16 22h16M16 32h16" /></>],
  [/llave/i, <><circle cx="15" cy="24" r="8.5" /><circle cx="15" cy="24" r="3" /><path d="M23.5 24H42M36 24v6M41 24v4" /></>],
  [/ropa|chaqueta|buzo|prenda/i, <><path d="M17 7 8 12l3 9 5-2v22h16V19l5 2 3-9-9-5c-1 3-4 5-7 5s-6-2-7-5Z" /></>],
  [/accesorio|reloj|gafa|lente|joya|billetera|bolso|maleta|morral/i, <><circle cx="24" cy="24" r="10" /><path d="M24 18v6l4 3M19 14l2-8h6l2 8M19 34l2 8h6l2-8" /></>],
  [/[uú]til|cuaderno|libro|calculadora|cartuchera/i, <><path d="M10 8h24a4 4 0 0 1 4 4v28H14a4 4 0 0 1-4-4Z" /><path d="M10 34a4 4 0 0 1 4-4h24M16 8v22M22 16h10M22 21h7" /></>],
];
const ICONO_OTRO = <><path d="M8 17 24 9l16 8v16l-16 8-16-8Z" /><path d="m8 17 16 8 16-8M24 25v16" /></>;

export function IconoCategoria({ categoria, className }: { categoria: string; className?: string }) {
  const trazo = ICONOS.find(([patron]) => patron.test(categoria))?.[1] ?? ICONO_OTRO;
  return (
    <svg className={className} viewBox="0 0 48 48" aria-hidden="true">
      {trazo}
    </svg>
  );
}

/** Código corto y estable para nombrar la etiqueta (sale del id público, no de datos del dueño). */
const codigo = (id: string) => `N.º ${id.replace(/-/g, "").slice(-4).toUpperCase()}`;

/**
 * Un objeto perdido como etiqueta de cartulina kraft.
 * En la lista (enlace=true) todas miden lo mismo: foto o dibujo arriba, texto recortado a 2 líneas.
 * En el detalle (enlace=false) muestra todo el texto.
 */
export function Etiqueta({ objeto, enlace = true, foto = true }: { objeto: ObjetoPublico; enlace?: boolean; foto?: boolean }) {
  const primera = foto ? objeto.fotos?.[0] : undefined;
  const dibujo = (
    <div className={estilos.dibujo}>
      <IconoCategoria categoria={objeto.categoria} className={estilos.icono} />
      <span>Sin foto</span>
    </div>
  );

  return (
    <article className={estilos.etiqueta} data-modo={enlace ? "tarjeta" : "completa"}>
      <div className={estilos.talon} aria-hidden="true">
        <span className={estilos.ojal} />
        <span className={estilos.codigo}>{codigo(objeto.id)}</span>
      </div>

      <div className={estilos.cuerpo}>
        {foto && (
          <div className={estilos.medio}>
            {primera ? (
              <Foto className={estilos.foto} src={urlFoto(primera, enlace ? "mini" : "grande", true)}
                alt={`Foto de referencia: ${objeto.descripcion}`} loading="lazy" width={480} height={360}
                respaldo={dibujo} />
            ) : (
              dibujo
            )}
          </div>
        )}

        <div className={estilos.texto}>
          <p className={estilos.categoria}>{objeto.categoria}</p>
          <h3 className={estilos.descripcion} title={objeto.descripcion}>
            {objeto.descripcion}
          </h3>
          <dl className={estilos.datos}>
            <div>
              <dt>
                <svg viewBox="0 0 20 20" aria-hidden="true">
                  <path d="M10 17.5s-5-4.4-5-8.6a5 5 0 0 1 10 0c0 4.2-5 8.6-5 8.6Z" />
                  <circle cx="10" cy="8.8" r="1.8" />
                </svg>
                <span className="visualmente-oculto">Dónde</span>
              </dt>
              <dd title={objeto.zona ?? undefined}>{objeto.zona ?? "Sin zona"}</dd>
            </div>
            <div>
              <dt>
                <svg viewBox="0 0 20 20" aria-hidden="true">
                  <circle cx="10" cy="10" r="7" />
                  <path d="M10 6v4l2.6 1.8" />
                </svg>
                <span className="visualmente-oculto">Cuándo</span>
              </dt>
              <dd>
                <time dateTime={objeto.fecha} title={fechaLarga(objeto.fecha)}>
                  {haceCuanto(objeto.fecha)}
                </time>
              </dd>
            </div>
          </dl>
          {objeto.estado === "en_coincidencia" && (
            <p className={estilos.revision}>
              <span aria-hidden="true" /> Posible hallazgo en revisión
            </p>
          )}
        </div>

        {enlace && (
          <div className={estilos.pie}>
            <Link className={estilos.enlace} href={`/objeto/?id=${objeto.id}`}>
              Ver etiqueta<span className="visualmente-oculto"> de {objeto.categoria}</span>
              <svg viewBox="0 0 20 20" aria-hidden="true">
                <path d="M4 10h12m0 0-5-5m5 5-5 5" />
              </svg>
            </Link>
          </div>
        )}
      </div>
    </article>
  );
}
