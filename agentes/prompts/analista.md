# Prompt del agente analista (resumen del informe)

Versión: 2 · Modelo objetivo: qwen2.5:3b · temperatura 0 · salida JSON · máx. 500 tokens

Se llama una vez por informe (global y por sede), con 1 reintento. Recibe **solo** el JSON de hechos
calculado en código: métricas agregadas, predicción y backtest. Nunca recibe descripciones ni datos personales.
El texto del prompt vive en `harness/analista.py` (`SISTEMA_ANALISTA`); este archivo documenta su diseño.

## Cambios de la versión 2 (prueba real con qwen2.5:3b)

En la versión 1, Qwen recibía las métricas crudas y cometió tres errores:
- restó 51,7 − 50,7 y escribió "disminuyó 1.0 %";
- confundió mes con semana;
- llamó "próxima" a la semana de parciales en curso.

Ahora recibe **hechos en lenguaje llano** (`hechos_para_redactar`):
- el mes en palabras;
- el cambio ya calculado ("bajó 1,0 puntos");
- "esta semana" / "la próxima semana" con fechas;
- el tipo de semana;
- la confiabilidad en una frase.

Además, el resumen debe seguir un orden fijo de 5 puntos.

## Verificación posterior (ADR-015)

1. **Cifras inventadas:** todo número mayor que 10, o escrito con decimales, debe estar en los hechos (igual o redondeado). Acepta formato colombiano (`5.118`, `50,7`).
2. **Cifras obligatorias:** el resumen debe mencionar el porcentaje recuperado y las pérdidas esperadas de la primera semana. Un texto vago se rechaza.

Si falla dos veces, se usa la plantilla fija. El texto rechazado queda en la traza, en el paso `verificar_cifras`, campo `rechazado`.

## Ejemplo de hechos que recibe el LLM

```json
{"sede": "Todas las sedes",
 "recuperacion": {"mes": "octubre de 2026", "objetos_reportados": 5118, "porcentaje_recuperado": 50.7,
                  "porcentaje_recuperado_mes_anterior": 51.7, "cambio_frente_al_mes_anterior": "bajó 1,0 puntos",
                  "categoria_que_menos_se_recupera": "Otros (22,8 %)"},
 "donde_y_cuando_se_pierde_mas": ["Aulas, los lunes de 09 a 12 h (1.185 pérdidas en el histórico)"],
 "prediccion": [{"cuando": "esta semana", "fechas": "9 al 15 de noviembre", "tipo_de_semana": "semana de parciales",
                 "perdidas_esperadas": 2093, "rango_probable": "entre 2.018 y 2.169"}],
 "confiabilidad_de_la_prediccion": "buena: en las últimas 12 semanas se equivocó en promedio 32,1 objetos por semana, frente a 197 de una estimación simple"}
```
