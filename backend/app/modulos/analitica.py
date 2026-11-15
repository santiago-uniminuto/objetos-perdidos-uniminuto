"""GET /analitica/resumen: último informe del agente analista (solo agregados, sin datos personales).

Admin y auditor ven cualquier sede (?sede_id=) o el global (?alcance=global): son solo agregados,
sin datos personales (ADR-019). Sin parámetros, el admin ve su propia sede.
"""

from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from psycopg import Connection

from app.config import get_settings
from app.db import get_conn
from app.errores import ErrorApp
from app.seguridad import Usuario, usuario_actual

router = APIRouter(prefix="/analitica", tags=["analítica"])


@router.get("/resumen")
def resumen(alcance: Literal["sede", "global"] = "sede", sede_id: int | None = Query(None, ge=1),
            u: Usuario = Depends(usuario_actual), conn: Connection = Depends(get_conn)) -> dict:
    if u.es_admin:
        sede = None if alcance == "global" else (sede_id or u.sede_id)
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
    return {**fila, **proxima_corrida(conn)}


def proxima_corrida(conn: Connection) -> dict:
    """Cuándo vuelve a correr el analista: última corrida (de cualquier sede) + ANALISTA_HORAS.

    El Programador de los agentes usa la misma regla, así que el contador de la página coincide con él.
    """
    horas = get_settings().analista_horas
    ultima = conn.execute("SELECT max(creado_en) AS t FROM informe_analitica").fetchone()["t"]
    return {"ultima_corrida": ultima, "cada_horas": horas,
            "proxima_corrida": ultima + timedelta(hours=horas) if ultima and horas > 0 else None}
