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
- **IP real del visitante (Fase 7):** Funnel pone la IP pública del visitante en `X-Forwarded-For` y la reemplaza, no la agrega, así que un visitante no puede falsificarla. Caddy descarta ese encabezado si no viene de un proxy de confianza, y la conexión le llega desde la red interna de Docker. Por eso el Caddyfile declara `trusted_proxies static private_ranges`. Es seguro porque Caddy solo escucha en `127.0.0.1`. Sin eso, todos los visitantes compartirían una IP: el límite de 60/min del portal sería global y la auditoría no distinguiría a nadie.
- La API revisa su configuración al arrancar en producción: se niega con `SECRET_KEY` corta o `COOKIE_SEGURA=false`, y avisa si `URL_PUBLICA` no es https, si el límite del portal parece de pruebas o si el correo sigue en Mailpit.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
| --- | --- |
| Cloudflare Tunnel con nombre | Requiere un dominio propio |
| ngrok gratis | Página de advertencia intermedia para navegadores |
| VPS / Oracle Cloud | Requiere tarjeta o pago |
