# ADR-016: El portal público solo muestra objetos perdidos; cuentas del personal y restablecimiento

- **Estado:** aceptada (modifica ADR-007 en qué se publica)
- **Fecha:** 2026-11-10
- **Responsable:** Equipo completo

## Contexto

1. Hasta ahora la vista pública mostraba lo perdido y lo **hallado**. El equipo señaló un riesgo práctico: si se publica "celular negro encontrado en Biblioteca", pueden llegar 30 supuestos dueños, y cada reclamo falso le cuesta tiempo al admin y riesgo de entregar a quien no es.
2. Faltaba definir cómo entra el personal al sistema y qué pasa si olvida la contraseña.

## Decisión

### Portal público
- Solo se publican los **reportes de pérdida**, con categoría, zona, fecha y la descripción pública, sin dueño y sin el detalle de control. Así, quien encuentra algo sabe que alguien lo busca y lo lleva a la oficina.
- Los **hallazgos no se publican**. El cruce con lo perdido lo hace el matcher en privado y el admin verifica al dueño con la pregunta de control antes de entregar.
- Quien perdió algo que no aparece en la lista lo reporta en la oficina y recibe un correo si llega una coincidencia.

### Cuentas del personal
- **No hay registro abierto.** Las cuentas de admin de sede y de auditor se crean por consola (`python -m app.crear_usuario`), cada una con su correo institucional y su contraseña (Argon2).
- Login con correo y contraseña. La sesión va en una cookie httpOnly, Secure y SameSite=Strict, y dura 30 minutos. Tras 5 intentos fallidos, la cuenta se bloquea 15 minutos.
- **Olvidé mi contraseña:** el usuario pide un enlace en la página de login.
  - El enlace llega a su correo institucional, sirve una sola vez y vence en 30 minutos.
  - En la base solo queda el SHA-256 del token.
  - La respuesta es la misma exista o no la cuenta.
  - Hay límite de 5 solicitudes cada 15 minutos por IP y de 3 por hora por correo.
  - Pedir un enlace nuevo anula los anteriores.
  - Restablecer la contraseña también desbloquea la cuenta.
- **Plan B sin correo:** otra persona del equipo con acceso al servidor genera el enlace por consola (`--restablecer`) y se lo entrega al dueño de la cuenta. Nadie conoce ni dicta contraseñas ajenas.
- Con sesión iniciada, cada usuario puede cambiar su contraseña: debe dar la actual y la nueva debe tener al menos 12 caracteres.
- Todo queda en la auditoría: solicitudes, cambios, y desactivaciones o reactivaciones de cuentas.

## Consecuencias

- Menos exposición y menos reclamos falsos. A cambio, el dueño de un objeto hallado no lo descubre navegando: depende de haber hecho el reporte y del correo del notificador.
- Después de restablecer la contraseña, una sesión abierta en otro equipo sigue viva hasta 30 minutos, porque el JWT no tiene estado. Es aceptable por la duración corta. Si hiciera falta, se agrega una versión de credenciales al token.
- El correo de restablecimiento usa el mismo SMTP del notificador: Mailpit en desarrollo y Gmail con contraseña de aplicación en producción. `URL_PUBLICA` debe apuntar a la dirección de Funnel.
