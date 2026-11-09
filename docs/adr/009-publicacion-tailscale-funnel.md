# ADR-009: Publicación con Tailscale Funnel + Caddy

- **Estado:** aceptada
- **Fecha:** 2026-11-07
- **Responsable:** Frontend / DevOps

## Contexto

Presupuesto $0, sin dominio propio, servidor = portátil detrás de NAT (casa y universidad). El curso exige URL pública con HTTPS.

## Decisión

Caddy escucha en `127.0.0.1:8080` y enruta `/api` a FastAPI y `/` al frontend. Tailscale Funnel publica ese puerto en `https://<equipo>.<tailnet>.ts.net` con certificado automático.

## Consecuencias

- URL fija y gratuita; no se abren puertos en el router.
- Disponible solo mientras el portátil esté encendido y conectado.
- La URL es pública: todo lo que no sea `/publico` exige login.
- Respaldo: `cloudflared tunnel --url http://localhost:8080` (URL aleatoria).

## Alternativas consideradas

| Alternativa | Por qué se descartó |
| --- | --- |
| Cloudflare Tunnel con nombre | Requiere un dominio propio |
| ngrok gratis | Página de advertencia intermedia para navegadores |
| VPS / Oracle Cloud | Requiere tarjeta o pago |
