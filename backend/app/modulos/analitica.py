"""GET /analitica/resumen: último informe del agente analista (solo agregados, sin datos personales).

- admin_sede: el informe de su sede (o el global con ?alcance=global).
- auditor: el de cualquier sede (?sede_id=) o el global.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from psycopg import Connection

from app.db import get_conn
from app.errores import ErrorApp
from app.seguridad import Usuario, usuario_actual

router = APIRouter(prefix="/analitica", tags=["analítica"])


@router.get("/resumen")
def resumen(alcance: Literal["sede", "global"] = "sede", sede_id: int | None = Query(None, ge=1),
            u: Usuario = Depends(usuario_actual), conn: Connection = Depends(get_conn)) -> dict:
    if u.es_admin:
        if sede_id is not None and sede_id != u.sede_id:
            raise ErrorApp(403, "prohibido", "Solo puedes ver la analítica de tu sede o la global")
        sede = None if alcance == "global" else u.sede_id
    elif u.rol == "auditor":
        sede = None if alcance == "global" or sede_id is None else sede_id
    else:  # pragma: no cover - no hay más roles
        raise ErrorApp(403, "prohibido", "Rol sin acceso a la analítica")
    fila = conn.execute(
        "SELECT id, sede_id, creado_en, datos_hasta, metricas, prediccion, resumen, resumen_fuente, modelo_llm "
        "FROM informe_analitica WHERE sede_id IS NOT DISTINCT FROM %s ORDER BY creado_en DESC LIMIT 1", (sede,),
    ).fetchone()
    if fila is None:
        raise ErrorApp(404, "sin_informe", "Aún no hay informe de analítica: el agente analista corre cada pocas "
                                           "horas cuando el lake tiene datos")
    return fila
