"""Lake en carpeta local (sin SeaweedFS) y calendario académico."""

from datetime import date

import pyarrow as pa
import pyarrow.fs as pafs

from lago.almacen import Lago
from lago.calendario import es_parciales, semana_semestre, tabla_semanas


def _lago(tmp_path) -> Lago:
    return Lago(pafs.LocalFileSystem(), str(tmp_path))


def test_agregar_leer_y_compactar(tmp_path):
    lago = _lago(tmp_path)
    for i in range(6):
        lago.agregar("bronze/eventos/fecha=2026-03-02", pa.table({"outbox_id": [i * 2, i * 2 + 1]}))
    lago.agregar("bronze/eventos/fecha=2026-03-03", pa.table({"outbox_id": [100]}))
    assert lago.leer("bronze/eventos").num_rows == 13

    assert lago.compactar("bronze/eventos", max_partes=4) == 1  # solo la partición con 6 archivos
    archivos = list((tmp_path / "bronze/eventos/fecha=2026-03-02").glob("*.parquet"))
    assert len(archivos) == 1 and archivos[0].name.startswith("compacto-")
    tabla = lago.leer("bronze/eventos")
    assert sorted(tabla["outbox_id"].to_pylist()) == [*range(12), 100]  # nada se pierde ni se duplica


def test_reemplazar_es_idempotente(tmp_path):
    lago = _lago(tmp_path)
    t = pa.table({"anio": [2025, 2026], "x": [1, 2]})
    lago.reemplazar("silver/x", t, ["anio"])
    lago.reemplazar("silver/x", t, ["anio"])
    assert lago.leer("silver/x").num_rows == 2
    assert lago.leer("no/existe") is None and lago.dataset("no/existe") is None


def test_calendario():
    assert semana_semestre(date(2026, 2, 2)) == 1
    assert semana_semestre(date(2026, 3, 23)) == 8 and es_parciales(date(2026, 3, 23))
    assert semana_semestre(date(2026, 1, 10)) is None  # vacaciones
    filas = tabla_semanas(date(2026, 1, 1), date(2026, 12, 31))
    assert sum(f["es_parciales"] for f in filas) == 4  # semanas 8 y 16 de los dos semestres
