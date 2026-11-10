# Prompt del agente analista (resumen del informe)

Versión: 1 · Modelo objetivo: qwen2.5:3b · temperatura 0 · salida JSON · máx. 500 tokens

Se llama una vez por informe (global y por sede), con 1 reintento. Recibe **solo** el JSON de hechos
calculado en código: métricas agregadas, predicción y backtest. Nunca recibe descripciones ni datos personales.
El texto del prompt vive en `harness/analista.py` (`SISTEMA_ANALISTA`); este archivo documenta su diseño.

## Verificación posterior (ADR-015)

Todo número mayor que 10 del resumen debe estar en los hechos, igual o redondeado a entero o a 1 decimal.
Acepta formato colombiano (`5.118`, `50,7`). Si falla dos veces, se usa la plantilla fija.

## Ejemplo de hechos (recortado)

```json
{"sede": "Todas las sedes",
 "metricas": {"mes": {"periodo": "2026-10", "reportados": 5118, "tasa_recuperacion_pct": 50.7,
                      "tasa_mes_anterior_pct": 51.7, "categoria_menos_recuperada": {"categoria": "Útiles", "tasa_pct": 34.9}},
              "zonas_criticas": [{"zona": "Aulas", "dia": "lunes", "franja": "09-12", "perdidas": 1185}]},
 "prediccion": {"semanas": [{"semana_inicio": "2026-11-09", "clase": "parciales", "esperado": 2093.2,
                             "minimo_90": 2018, "maximo_90": 2169}],
                "backtest": {"mae_modelo": 32.1, "mae_ingenuo": 197.0, "mejora_pct": 83.7, "gana_modelo": true}}}
```
