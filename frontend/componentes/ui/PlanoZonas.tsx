"use client";

import estilos from "./ui.module.css";

/** "Dónde": las zonas de la sede como un plano esquemático (estilo blueprint), agrupadas por tipo de espacio.
 *  No es un mapa real del campus: agrupa para encontrar la zona más rápido que en una lista.
 *  Por dentro son radios: se maneja con flechas del teclado y lectores de pantalla. */
const GRUPOS: { nombre: string; zonas: string[] }[] = [
  { nombre: "Académico", zonas: ["Aulas", "Biblioteca", "Auditorios", "CRAI - zona de descanso"] },
  { nombre: "Servicios", zonas: ["Cafeterías", "Baños", "Admisiones", "Sala de profesores"] },
  { nombre: "Exteriores", zonas: ["Parqueadero", "Zonas verdes", "Terrazas"] },
];

export function PlanoZonas({ zonas, valor, onCambio }: {
  zonas: { id: number; nombre: string }[];
  valor: number | null;
  onCambio: (id: number | null) => void;
}) {
  const conocidas = new Set(GRUPOS.flatMap((g) => g.zonas));
  const grupos = [
    ...GRUPOS.map((g) => ({ ...g, items: g.zonas.map((n) => zonas.find((z) => z.nombre === n)).filter(Boolean) })),
    { nombre: "Otras", items: zonas.filter((z) => !conocidas.has(z.nombre)) },
  ].filter((g) => g.items.length > 0) as { nombre: string; items: { id: number; nombre: string }[] }[];

  return (
    <fieldset className={estilos.plano}>
      <legend className="visualmente-oculto">Zona donde se perdió o se encontró</legend>
      {grupos.map((g) => (
        <div key={g.nombre} className={estilos.planoGrupo}>
          <p className={estilos.planoTitulo}>{g.nombre}</p>
          <div className={estilos.planoZonas}>
            {g.items.map((z) => (
              <label key={z.id} className={estilos.zona} data-elegida={valor === z.id || undefined}>
                <input type="radio" name="zona" value={z.id} checked={valor === z.id} onChange={() => onCambio(z.id)} />
                <span>{z.nombre}</span>
              </label>
            ))}
          </div>
        </div>
      ))}
      <label className={estilos.zonaNoSe}>
        <input type="radio" name="zona" checked={valor === null} onChange={() => onCambio(null)} />
        <span>No sabe en qué zona</span>
      </label>
    </fieldset>
  );
}
