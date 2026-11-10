// Producción: export estático (HTML/JS/CSS) que sirve Caddy; no hace falta un servidor Node
// corriendo en el portátil (ADR-017). En desarrollo, `next dev` reenvía /api a la API.
const desarrollo = process.env.NODE_ENV === "development";

/** @type {import('next').NextConfig} */
const config = desarrollo
  ? {
      async rewrites() {
        return [{ source: "/api/:ruta*", destination: `${process.env.API_URL ?? "http://localhost:8080"}/api/:ruta*` }];
      },
    }
  : { output: "export", trailingSlash: true, images: { unoptimized: true } };

export default config;
