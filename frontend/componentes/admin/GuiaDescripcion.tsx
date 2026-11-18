"use client";

import { revisarDescripcion } from "@/lib/descripcion";

import estilos from "./Formulario.module.css";

/** Lo que la IA necesita para cruzar un reporte con un hallazgo, marcado mientras el admin escribe. */
export function GuiaDescripcion({ texto }: { texto: string }) {
  const r = revisarDescripcion(texto);
  const puntos = [
    { ok: r.que, nombre: "Qué es", ayuda: "celular, termo, chaqueta…" },
    { ok: r.marca, nombre: "Marca", ayuda: "si la tiene" },
    { ok: r.color, nombre: "Color", ayuda: "el del objeto, no el del forro" },
    { ok: r.detalle, nombre: "Un detalle único", ayuda: "sticker, rayón, modelo, talla…" },
  ];
  const vacio = texto.trim().length === 0;
  return (
    <div className={estilos.guia}>
      <ul className={estilos.guiaPuntos} aria-label="Lo que la IA usa para buscar coincidencias">
        {puntos.map((p) => (
          <li key={p.nombre} data-ok={(!vacio && p.ok) || undefined} title={p.ayuda}>
            <span aria-hidden="true">{!vacio && p.ok ? "✓" : "○"}</span> {p.nombre}
            <span className="visualmente-oculto">{!vacio && p.ok ? ": incluido" : `: falta (${p.ayuda})`}</span>
          </li>
        ))}
      </ul>
      {!vacio && !r.que && (
        <p className={estilos.guiaAviso} role="status">
          Empieza por <b>qué es</b> el objeto. Sin eso la IA solo sabe la categoría y compara peor
          {r.campos ? " (por ejemplo: «tipo: celular, marca: Apple, modelo: Pro Max, color: azul»)" : ""}.
        </p>
      )}
      <details className={estilos.guiaDetalle}>
        <summary>¿Cómo escribirla para que la IA lo encuentre?</summary>
        <ol>
          <li><b>Qué es + marca + modelo + color</b> al principio: «Celular Apple iPhone 13 Pro Max azul».</li>
          <li>Después, <b>lo que lo hace único</b>: «con forro transparente y la pantalla rota en la esquina».</li>
          <li>Si prefieres por campos, también sirve: «tipo: celular, marca: Apple, modelo: Pro Max, color: azul, detalles: forro transparente».</li>
          <li>El color es el <b>del objeto</b>. Si el forro es de otro color, dilo aparte: «forro rojo».</li>
          <li><b>Sin datos personales</b> (nombres, documentos, teléfonos): no ayudan a cruzar y la IA los borra.</li>
          <li>El secreto para la entrega (lo que solo sabe el dueño) va en <b>Detalle de control</b>, no aquí.</li>
        </ol>
        <p className="secundario pequeno">
          La IA compara lo que es, la marca, el color y los detalles de los dos lados, además de la fecha y la zona.
          «modelo: promax color: azul» solo le da el color: no sabe si es un celular o unos audífonos.
        </p>
      </details>
    </div>
  );
}
