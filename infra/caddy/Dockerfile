# Caddy con el frontend adentro (ADR-017): Next.js se compila a HTML/JS/CSS estáticos y
# Caddy los sirve. Un contenedor menos que un servidor Node: importa con 16 GB de RAM.
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM caddy:2-alpine
COPY infra/caddy/Caddyfile /etc/caddy/Caddyfile
COPY --from=web /web/out /srv/web
