# ADR-017: Frontend Next.js exportado como estático y servido por Caddy

- **Estado:** aceptada
- **Fecha:** 2026-11-10
- **Responsable:** Frontend / DevOps

## Contexto

El frontend tiene un portal público y un panel con sesión. Todo el despliegue corre en un portátil de 16 GB que también ejecuta PostgreSQL, Mongo, SeaweedFS, Redis, los agentes y Ollama. Un servidor Node de Next.js agregaría unos 150-300 MB de RAM y otro proceso que vigilar.

## Decisión

- Se usa Next.js 16 (App Router, TypeScript estricto) con `output: "export"`. El build produce HTML, JS y CSS estáticos.
- Una imagen multietapa (`infra/caddy/Dockerfile`) compila el frontend con Node y copia `out/` en la imagen de Caddy. **No hay contenedor `web` aparte.**
- Todos los datos se piden desde el navegador a `/api/v1` en el **mismo origen**. Así la cookie de sesión (httpOnly, SameSite=Strict) viaja sola, no hace falta CORS y JavaScript nunca ve el token.
- No hay rutas dinámicas: el detalle usa `?id=` y el restablecimiento usa `?token=`. Por eso el export estático no necesita conocer los ids al compilar.
- La protección del panel la hace la **API**. Cada pantalla pide `/auth/yo` y, si recibe 401, envía al login. El HTML del panel es público, pero no contiene datos.
- Caddy agrega una CSP estricta a la web (`'self'`, sin recursos externos; las fuentes van dentro del build) y caché inmutable para `/_next/static`.
- En desarrollo, `npm run dev` reenvía `/api` a `http://localhost:8080`, es decir, a Caddy con la API del Compose.

## Consecuencias

- Hay un contenedor menos, el arranque es instantáneo y la web sigue arriba aunque la API se reinicie.
- No hay renderizado en servidor. Para el portal no importa, porque no se busca posicionamiento en buscadores y la vista pública cambia a cada rato.
- La CSP necesita `'unsafe-inline'` en scripts por los datos de hidratación del export. Se acepta: no se inyecta HTML de usuarios y todo el contenido dinámico se escapa con React.
