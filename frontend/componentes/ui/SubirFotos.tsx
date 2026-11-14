"use client";

import { useEffect, useRef, useState } from "react";

import estilos from "./ui.module.css";

export const MAX_FOTOS = 3;
const MAX_MB = 8;
const TIPOS = ["image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"];

/** Selector de hasta 3 fotos con vista previa local. Valida tamaño y tipo antes de subir nada;
 *  la API vuelve a validar, quita los metadatos y reduce la foto. */
export function SubirFotos({ archivos, onCambio, cupo = MAX_FOTOS, aviso }: {
  archivos: File[];
  onCambio: (archivos: File[]) => void;
  cupo?: number;
  aviso?: string;
}) {
  const entrada = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [arrastrando, setArrastrando] = useState(false);
  const [vistas, setVistas] = useState<string[]>([]);

  useEffect(() => {
    const urls = archivos.map((a) => URL.createObjectURL(a));
    setVistas(urls);
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [archivos]);

  function agregar(lista: FileList | null) {
    if (!lista) return;
    setError(null);
    const nuevos: File[] = [];
    for (const f of Array.from(lista)) {
      const esHeic = /\.(heic|heif)$/i.test(f.name);
      if (!TIPOS.includes(f.type) && !esHeic) { setError(`"${f.name}" no es una foto JPG, PNG, WebP o HEIC.`); continue; }
      if (f.size > MAX_MB * 1024 * 1024) { setError(`"${f.name}" pesa más de ${MAX_MB} MB.`); continue; }
      nuevos.push(f);
    }
    const total = [...archivos, ...nuevos];
    if (total.length > cupo) setError(`Máximo ${cupo} ${cupo === 1 ? "foto" : "fotos"}: se tomaron las primeras.`);
    onCambio(total.slice(0, cupo));
  }

  return (
    <div className={estilos.fotos}>
      <div className={estilos.fotosRejilla}>
        {vistas.map((src, i) => (
          <figure key={src} className={estilos.fotoPrevia}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={src} alt={`Foto ${i + 1} seleccionada`} />
            <button type="button" className={estilos.fotoQuitar} onClick={() => onCambio(archivos.filter((_, j) => j !== i))}
              aria-label={`Quitar la foto ${i + 1}`}>×</button>
          </figure>
        ))}
        {archivos.length < cupo && (
          <button type="button" className={estilos.fotoAgregar} data-arrastrando={arrastrando || undefined}
            onClick={() => entrada.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setArrastrando(true); }}
            onDragLeave={() => setArrastrando(false)}
            onDrop={(e) => { e.preventDefault(); setArrastrando(false); agregar(e.dataTransfer.files); }}>
            <strong>Agregar foto</strong>
            <span>o arrástrala aquí</span>
            <span className={estilos.fotoCupo}>
              {cupo - archivos.length === 1 ? "Queda 1 espacio" : `Quedan ${cupo - archivos.length} espacios`}
            </span>
          </button>
        )}
      </div>
      <input ref={entrada} type="file" accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif"
        multiple hidden onChange={(e) => { agregar(e.target.files); e.target.value = ""; }} />
      <small className="secundario">JPG, PNG, WebP o HEIC, hasta {MAX_MB} MB. {aviso}</small>
      {error && <small className="error" role="alert" style={{ color: "var(--error)", fontWeight: 700 }}>{error}</small>}
    </div>
  );
}
