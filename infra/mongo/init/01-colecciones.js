// Se ejecuta solo la primera vez que se crea el volumen de MongoDB.
// Colecciones con validación $jsonSchema, índices y TTL. Ver documento de la Fase 3.

db = db.getSiblingDB("objetos_perdidos");

// ------------------------------------------------------------------
// 1. esquemas_categoria: define el formulario dinámico de cada categoría.
//    "privado: true" = el campo nunca se publica; sirve para la pregunta de control.
db.createCollection("esquemas_categoria", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["codigo", "campos", "version"],
      properties: {
        codigo: { bsonType: "string" },
        version: { bsonType: "int", minimum: 1 },
        campos: {
          bsonType: "array",
          items: {
            bsonType: "object",
            required: ["nombre", "tipo"],
            properties: {
              nombre: { bsonType: "string" },
              tipo: { enum: ["texto", "numero", "opcion", "booleano"] },
              opciones: { bsonType: "array" },
              requerido: { bsonType: "bool" },
              privado: { bsonType: "bool" },
            },
          },
        },
      },
    },
  },
});
db.esquemas_categoria.createIndex({ codigo: 1 }, { unique: true });

const t = (nombre, extra = {}) => ({ nombre, tipo: "texto", ...extra });
const op = (nombre, opciones, extra = {}) => ({ nombre, tipo: "opcion", opciones, ...extra });
db.esquemas_categoria.insertMany([
  { codigo: "electronicos", version: 1, campos: [op("tipo", ["celular", "portátil", "audífonos", "cargador", "tablet", "calculadora", "otro"], { requerido: true }), t("marca"), t("modelo"), t("color"), t("funda"), t("serial_ultimos4", { privado: true })] },
  { codigo: "documentos", version: 1, campos: [op("tipo", ["carné", "cédula", "tarjeta de identidad", "licencia", "tarjeta bancaria", "otro"], { requerido: true }), t("nombre_en_documento", { privado: true })] },
  { codigo: "ropa", version: 1, campos: [op("tipo", ["chaqueta", "buzo", "saco", "gorra", "bufanda", "otro"], { requerido: true }), t("color"), t("talla"), t("marca")] },
  { codigo: "accesorios", version: 1, campos: [op("tipo", ["billetera", "gafas", "reloj", "maleta", "sombrilla", "joya", "otro"], { requerido: true }), t("color"), t("material"), t("marca"), t("contenido", { privado: true })] },
  { codigo: "utiles", version: 1, campos: [op("tipo", ["cuaderno", "libro", "cartuchera", "carpeta", "otro"], { requerido: true }), t("color"), t("marca"), t("marcas_personales", { privado: true })] },
  { codigo: "llaves", version: 1, campos: [{ nombre: "cantidad", tipo: "numero" }, t("llavero"), op("uso", ["casa", "vehículo", "locker", "otro"])] },
  { codigo: "botellas", version: 1, campos: [t("marca"), t("color"), { nombre: "capacidad_ml", tipo: "numero" }, t("stickers", { privado: true })] },
  { codigo: "otros", version: 1, campos: [t("descripcion_libre", { requerido: true })] },
]);

// ------------------------------------------------------------------
// 2. atributos_objeto: valores de esos campos para cada reporte u hallazgo.
db.createCollection("atributos_objeto", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["objeto_tipo", "objeto_id", "sede_id", "categoria", "atributos", "creado_en"],
      properties: {
        objeto_tipo: { enum: ["perdido", "hallado"] },
        objeto_id: { bsonType: "string" },        // UUID de PostgreSQL
        sede_id: { bsonType: "int" },
        categoria: { bsonType: "string" },
        version_esquema: { bsonType: "int" },
        atributos: { bsonType: "object" },
        creado_en: { bsonType: "date" },
      },
    },
  },
});
db.atributos_objeto.createIndex({ objeto_tipo: 1, objeto_id: 1 }, { unique: true });
db.atributos_objeto.createIndex({ sede_id: 1, categoria: 1 });

// ------------------------------------------------------------------
// 3. trazas_agente: una por ejecución de agente (trazabilidad del harness).
db.createCollection("trazas_agente", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["ejecucion_id", "agente", "estado", "creado_en"],
      properties: {
        ejecucion_id: { bsonType: "string" },
        agente: { enum: ["matcher", "notificador", "analista"] },
        disparador: { bsonType: "object" },     // { tipo: "reporte.creado", ref: "<uuid>" }
        proveedor: { bsonType: "string" },
        modelo: { bsonType: "string" },
        pasos: { bsonType: "array" },           // [{ herramienta, entrada_resumen, salida_resumen, ms, ok }]
        salida: {},
        tokens: { bsonType: "object" },         // { entrada, salida }
        latencia_ms: { bsonType: ["int", "long", "double"] },
        estado: { enum: ["ok", "error", "limite_excedido", "respaldo"] },
        error: { bsonType: "string" },
        creado_en: { bsonType: "date" },
      },
    },
  },
});
db.trazas_agente.createIndex({ ejecucion_id: 1 }, { unique: true });
db.trazas_agente.createIndex({ agente: 1, creado_en: -1 });
db.trazas_agente.createIndex({ creado_en: 1 }, { expireAfterSeconds: 60 * 60 * 24 * 180 }); // 180 días

// ------------------------------------------------------------------
// 4. eventos: copia del outbox de PostgreSQL (CDC por outbox, ADR-004).
db.createCollection("eventos");
db.eventos.createIndex({ outbox_id: 1 }, { unique: true });     // idempotencia del ETL
db.eventos.createIndex({ agregado: 1, agregado_id: 1, creado_en: 1 });
db.eventos.createIndex({ creado_en: 1 }, { expireAfterSeconds: 60 * 60 * 24 * 365 }); // 1 año
