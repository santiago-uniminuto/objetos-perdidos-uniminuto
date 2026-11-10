"""Agente notificador: avisa al dueño cuando el admin VERIFICA una coincidencia.

Sin LLM a propósito (Fase 4): la plantilla es fija, así que es imposible que el correo
revele detalles del objeto. Reglas:
- solo con consentimiento vigente para 'notificacion_correo' y estudiante no anonimizado;
- máximo 1 correo por coincidencia y 3 por estudiante al día;
- la lectura del correo del estudiante queda en la auditoría (usuario = sistema).
"""

from datetime import date

from psycopg import Connection
from psycopg.types.json import Jsonb

from harness.nucleo import Agente, Limites

ASUNTO = "Tenemos una posible coincidencia con tu objeto"
PLANTILLA = """Hola {nombre}:

En la oficina de objetos perdidos de {sede} registramos un objeto que podría ser el que reportaste.
Por tu seguridad, este correo no incluye detalles del objeto.

Acércate a la oficina con tu carné. Para confirmar que es tuyo te haremos una pregunta
sobre un detalle que solo el dueño conoce.

Este es un mensaje automático. Si no reportaste ningún objeto, puedes ignorarlo.
"""
MAX_DIARIO = 3
TTL_DEDUP = 180 * 24 * 3600


class Notificador(Agente):
    nombre = "notificador"
    limites = Limites(max_llamadas_llm=0, max_tokens=0, max_segundos=30)
    herramientas_permitidas = frozenset({"consultar_destinatario", "consultar_consentimiento", "enviar_correo"})

    def __init__(self, trazas, conn: Connection, redis, enviador):
        super().__init__(trazas)
        self.conn, self.r, self.enviador = conn, redis, enviador

    def _destinatario(self, coincidencia_id: str) -> dict | None:
        fila = self.conn.execute(
            "SELECT co.estado::text AS estado, e.id AS estudiante_id, split_part(e.nombres, ' ', 1) AS nombre, "
            "e.correo_institucional AS correo, e.anonimizado_en, s.id AS sede_id, s.nombre AS sede "
            "FROM coincidencia co JOIN reporte_perdida r "
            "ON (r.id, r.creado_en, r.sede_id) = (co.reporte_id, co.reporte_creado_en, co.sede_id) "
            "JOIN estudiante e ON e.id = r.estudiante_id JOIN sede s ON s.id = co.sede_id WHERE co.id = %s",
            (coincidencia_id,),
        ).fetchone()
        if fila:
            with self.conn.transaction():
                self.conn.execute(
                    "INSERT INTO auditoria (usuario_id, accion, entidad, entidad_id, sede_id, motivo, detalle) "
                    "VALUES (NULL, 'leer', 'estudiante', %s, %s, 'notificación automática de coincidencia', %s)",
                    (fila["estudiante_id"], fila["sede_id"], Jsonb({"agente": "notificador"})),
                )
        return fila

    def _consentimiento(self, estudiante_id) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM consentimiento WHERE estudiante_id = %s AND revocado_en IS NULL "
            "AND 'notificacion_correo' = ANY(finalidades)", (estudiante_id,),
        ).fetchone() is not None

    def manejar(self, evento: dict) -> dict:
        coincidencia_id = evento["payload"]["id"]
        d = self.usar("consultar_destinatario", self._destinatario, coincidencia_id, entrada=coincidencia_id,
                   sensible=True)
        if not d or d["estado"] != "verificada":
            return {"enviado": False, "motivo": "la coincidencia ya no está verificada"}
        if d["anonimizado_en"] or not d["correo"]:
            return {"enviado": False, "motivo": "sin correo disponible"}
        if not self.usar("consultar_consentimiento", self._consentimiento, d["estudiante_id"], entrada="vigente"):
            return {"enviado": False, "motivo": "sin consentimiento para notificar por correo"}

        # Memoria: un correo por coincidencia (aunque el evento se reprocese) y tope diario por estudiante
        if not self.r.set(f"notif:coincidencia:{coincidencia_id}", "1", nx=True, ex=TTL_DEDUP):
            return {"enviado": False, "motivo": "ya se notificó esta coincidencia"}
        llave_dia = f"notif:dia:{d['estudiante_id']}:{date.today().isoformat()}"
        enviados_hoy = self.r.incr(llave_dia)
        self.r.expire(llave_dia, 26 * 3600)
        if enviados_hoy > MAX_DIARIO:
            return {"enviado": False, "motivo": f"tope de {MAX_DIARIO} correos diarios"}

        cuerpo = PLANTILLA.format(nombre=d["nombre"], sede=d["sede"])
        try:
            self.usar("enviar_correo", self.enviador.enviar, d["correo"], ASUNTO, cuerpo, entrada="plantilla fija")
        except Exception:
            self.r.delete(f"notif:coincidencia:{coincidencia_id}")  # permite reintentar
            raise
        return {"enviado": True}
