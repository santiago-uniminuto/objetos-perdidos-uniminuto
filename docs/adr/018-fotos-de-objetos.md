# ADR-018: Fotos de los objetos

- **Estado:** aceptada
- **Fecha:** 2026-11-14
- **Responsable:** Equipo completo

## Contexto

Una foto identifica un objeto mucho mejor que un texto. Pero también puede contener datos personales: caras, nombres, un documento, o las coordenadas GPS que el celular guarda dentro del archivo. Además, publicar la foto de algo encontrado facilita los reclamos falsos (ADR-016).

## Decisión (aprobada por el equipo)

- **Máximo 3 fotos por objeto**, tanto en reportes de pérdida como en hallazgos. Solo se pueden agregar mientras el caso está abierto.
- **Visibilidad:**
  - Las fotos de objetos **perdidos** salen en el portal público.
  - Las de objetos **hallados**, nunca.
  - Las de la categoría **documentos** (carné, cédula), nunca, aunque sean de un reporte de pérdida.
  - La vista `vista_publica_fotos` es la única por la que el público accede a fotos.
- **Procesamiento en la API (Pillow):**
  - Límite de 8 MB y de 40 megapíxeles, para frenar las "bombas de descompresión".
  - Formatos aceptados: JPG, PNG, WebP y HEIC (iPhone).
  - La foto se endereza según su orientación y se re-codifica a WebP en dos tamaños, 1600 px y 480 px. Así pierde **todos** los metadatos, incluido el GPS.
  - El original no se guarda. Una prueba de integración verifica que el GPS y la marca del celular desaparecen.
- **Almacenamiento:** SeaweedFS, en el bucket `fotos` (`FOTOS_BUCKET`). PostgreSQL solo guarda la ficha: orden, tamaño y SHA-256 del original. Con ese hash se evita subir dos veces la misma foto. Ninguna URL del almacén se expone: la API sirve las imágenes con su propia autorización.
- **Retención:**
  - Las fotos se borran **90 días después de cerrar el caso**, con un hilo de la API cada 12 horas y un advisory lock.
  - Si el estudiante ejerce su derecho de supresión (anonimizar), las fotos de sus reportes se borran **de inmediato**.
- Subir y borrar fotos queda en la auditoría.

## Consecuencias

- El portal ayuda más a quien encontró algo. El riesgo que queda es que la foto de un objeto perdido muestre algo personal (una cara, un nombre escrito). El formulario se lo advierte al admin, y el admin puede borrar la foto en cualquier momento.
- Las fotos dependen de SeaweedFS (perfil `datos`). Si no está arriba, subir una foto responde 503 con un mensaje claro y el resto del sistema sigue funcionando.
- **Trabajo futuro:** comparar fotos con un modelo de visión en el matcher (por ejemplo, Qwen2.5-VL). No se incluye ahora por la VRAM de la RTX 3050 (4 GB), que ya ocupan bge-m3 y qwen2.5:3b.
