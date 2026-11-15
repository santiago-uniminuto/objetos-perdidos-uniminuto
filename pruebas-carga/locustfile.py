"""Pruebas de carga (Fase 6) · RNF-01 y RNF-03.

Dos perfiles de usuario, en la proporción de un día real de oficina:

* VisitantePortal (85 %): estudiantes consultando el portal público. Lista por sede con filtros,
  pagina con el cursor, abre un detalle y pide los catálogos. Es la ruta que debe aguantar picos.
* AdminSede (15 %): el administrador trabajando. Listados, bandeja de coincidencias, analítica y,
  de vez en cuando, registra un reporte (escritura real con Idempotency-Key).

Metas que se verifican al terminar (el proceso sale con código 1 si no se cumplen):
* p95 de la lectura pública < 300 ms (RNF-01)
* errores < 1 %
* el throughput total se reporta; la meta de >= 200 peticiones/s (RNF-03) se mide con caché caliente.

Uso (ver README.md):
    locust -f pruebas-carga/locustfile.py --host http://localhost:8080 \
           --headless -u 100 -r 10 -t 3m --csv pruebas-carga/resultados/base

Variables:
    CARGA_ADMIN_EMAIL / CARGA_ADMIN_CLAVE  cuenta de admin para el perfil AdminSede (si faltan, solo portal)
    CARGA_SEDES                             sedes a consultar, p. ej. "1,2,3" (por defecto 1..7, Bogotá)
    CARGA_ESCRIBIR                          "0" para no crear reportes (prueba solo de lectura)
    CARGA_PAUSA                             factor de las pausas entre clics: 1 = uso real (por defecto),
                                            0 = sin pausas (prueba de capacidad: peticiones/s máximas)
"""

import os
import random
import uuid
from datetime import date, timedelta

from locust import HttpUser, between, events, tag, task

API = "/api/v1"
SEDES = [int(s) for s in os.environ.get("CARGA_SEDES", "1,2,3,4,5,6,7").split(",")]
# La sede principal concentra más tráfico (más estudiantes): pesa el doble
PESOS_SEDE = [3 if s == 1 else 1 for s in SEDES]
CATEGORIAS = ["documentos", "electronicos", "ropa", "accesorios", "utiles", "llaves", "botellas", "otros"]
ESCRIBIR = os.environ.get("CARGA_ESCRIBIR", "1") != "0"
PAUSA = float(os.environ.get("CARGA_PAUSA", "1"))

META_P95_MS = 300        # RNF-01: uso real (con pausas)
META_RPS = 200           # RNF-03: capacidad (CARGA_PAUSA=0)
META_ERRORES = 0.01


def _sede() -> int:
    return random.choices(SEDES, weights=PESOS_SEDE)[0]


class VisitantePortal(HttpUser):
    """Estudiante sin cuenta en el portal público."""

    weight = 85
    wait_time = between(1 * PAUSA, 4 * PAUSA)   # lee la página antes de hacer otra cosa

    def on_start(self):
        self.vistos: list[str] = []

    @tag("lectura", "publico")
    @task(6)
    def listar(self):
        q = {"sede": _sede(), "limite": 24}
        if random.random() < 0.35:
            q["categoria"] = random.choice(CATEGORIAS)
        if random.random() < 0.15:
            q["desde"] = (date.today() - timedelta(days=random.choice((7, 30)))).isoformat()
        with self.client.get(f"{API}/publico/objetos", params=q, name="publico: listar",
                             catch_response=True) as r:
            if r.status_code != 200:
                r.failure(f"HTTP {r.status_code}")
                return
            datos = r.json()
            self.vistos = [o["id"] for o in datos["items"]][:10] or self.vistos
            # Uno de cada cuatro baja a la segunda página
            if datos.get("siguiente") and random.random() < 0.25:
                self.client.get(f"{API}/publico/objetos", params={**q, "cursor": datos["siguiente"]},
                                name="publico: página 2")

    @tag("lectura", "publico")
    @task(2)
    def detalle(self):
        if self.vistos:
            self.client.get(f"{API}/publico/objetos/{random.choice(self.vistos)}", name="publico: detalle")

    @tag("lectura", "publico")
    @task(1)
    def catalogos(self):
        self.client.get(f"{API}/catalogos", name="catálogos")


class AdminSede(HttpUser):
    """Administrador de sede trabajando en el panel (requiere CARGA_ADMIN_EMAIL y CARGA_ADMIN_CLAVE)."""

    weight = 15
    wait_time = between(2 * PAUSA, 6 * PAUSA)

    def on_start(self):
        email, clave = os.environ.get("CARGA_ADMIN_EMAIL"), os.environ.get("CARGA_ADMIN_CLAVE")
        self.activo = bool(email and clave)
        if not self.activo:
            return
        r = self.client.post(f"{API}/auth/login", json={"email": email, "contrasena": clave}, name="auth: login")
        self.activo = r.status_code == 200
        # La cookie de sesión lleva Secure (COOKIE_SEGURA=true, lo correcto en producción con HTTPS). El
        # navegador la acepta en http://localhost, pero requests no la reenvía por http: sin esto, todo lo
        # del admin daría 401. Solo afecta a este cliente de pruebas, no a la API.
        for cookie in self.client.cookies:
            cookie.secure = False
        self.estudiante = None
        if self.activo and ESCRIBIR:
            self.estudiante = self._estudiante()

    def _estudiante(self) -> str | None:
        """Un estudiante sintético por usuario virtual, con consentimiento (requisito para reportar)."""
        r = self.client.post(f"{API}/estudiantes", name="admin: crear estudiante", json={
            "tipo_documento": "CC", "numero_documento": str(uuid.uuid4().int)[:10], "nombres": "Carga",
            "apellidos": "Sintética", "correo_institucional": "carga@pruebas.uniminuto.edu.co"})
        if r.status_code != 201:
            return None
        est = r.json()["id"]
        self.client.post(f"{API}/consentimientos", name="admin: consentimiento",
                         json={"estudiante_id": est, "finalidades": ["gestion_objeto"]})
        return est

    @tag("lectura", "admin")
    @task(4)
    def listar_reportes(self):
        if self.activo:
            self.client.get(f"{API}/reportes", params={"limite": 20}, name="admin: reportes")

    @tag("lectura", "admin")
    @task(3)
    def listar_hallazgos(self):
        if self.activo:
            self.client.get(f"{API}/hallazgos", params={"limite": 20}, name="admin: hallazgos")

    @tag("lectura", "admin")
    @task(3)
    def bandeja(self):
        if self.activo:
            self.client.get(f"{API}/coincidencias", params={"estado": "sugerida"}, name="admin: coincidencias")

    @tag("lectura", "admin")
    @task(1)
    def analitica(self):
        if self.activo:
            with self.client.get(f"{API}/analitica/resumen", name="admin: analítica", catch_response=True) as r:
                if r.status_code == 404:   # aún sin informe del analista: no es un error de carga
                    r.success()

    @tag("escritura", "admin")
    @task(1)
    def registrar_reporte(self):
        if not (self.activo and self.estudiante):
            return
        self.client.post(f"{API}/reportes", name="admin: registrar reporte",
                         headers={"Idempotency-Key": uuid.uuid4().hex}, json={
                             "estudiante_id": self.estudiante, "categoria_id": random.randint(1, 8),
                             "descripcion": "Objeto de prueba de carga (carga)",
                             "descripcion_publica": "Objeto de prueba de carga",
                             "fecha_perdida": date.today().isoformat()})


@events.quitting.add_listener
def verificar_metas(environment, **_):
    """Al terminar: compara contra las metas y deja el código de salida (útil en CI o en un script)."""
    stats = environment.stats
    publicas = [e for (nombre, _), e in stats.entries.items() if nombre.startswith("publico:")]
    total = stats.total
    if not total.num_requests:
        return
    errores = total.num_failures / total.num_requests
    p95_publico = max((e.get_response_time_percentile(0.95) for e in publicas), default=0)
    print("\n=== Metas de la Fase 6 ===")
    print(f"Peticiones: {total.num_requests}  ·  {total.total_rps:.1f} peticiones/s  ·  errores {errores:.2%}")
    if PAUSA == 0:
        # Capacidad: se satura a propósito; la latencia sube por la cola (ley de Little) y no es la meta
        print(f"Capacidad (RNF-03): {total.total_rps:.1f} peticiones/s  (meta >= {META_RPS})  ·  "
              f"p95 lectura pública {p95_publico:.0f} ms (informativo, saturado)")
        ok = total.total_rps >= META_RPS and errores < META_ERRORES
    else:
        print(f"p95 lectura pública (peor ruta): {p95_publico:.0f} ms  (meta < {META_P95_MS} ms)")
        ok = p95_publico < META_P95_MS and errores < META_ERRORES
    print("RESULTADO:", "CUMPLE" if ok else "NO CUMPLE")
    if not ok:
        environment.process_exit_code = 1
