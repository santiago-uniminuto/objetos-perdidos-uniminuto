"use client";

import { useState } from "react";

/** <img> que, si el archivo no está (p. ej. se reinició el almacenamiento), muestra el respaldo
 *  en vez del ícono de imagen rota. */
export function Foto({ respaldo = null, ...props }: React.ImgHTMLAttributes<HTMLImageElement> & { respaldo?: React.ReactNode }) {
  const [fallo, setFallo] = useState(false);
  if (fallo) return <>{respaldo}</>;
  // eslint-disable-next-line @next/next/no-img-element, jsx-a11y/alt-text
  return <img {...props} onError={() => setFallo(true)} />;
}
