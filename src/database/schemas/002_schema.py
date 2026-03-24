"""
=============================================================
  EJERCICIO 1 — SECCIÓN 3.2
  Diseño del Esquema Destino en PostgreSQL
=============================================================
Genera y ejecuta el DDL para la tabla universo_victimas con:
  - Tipos de datos adecuados para PostgreSQL (no VARCHAR para todo)
  - Restricciones NOT NULL donde corresponde
  - Índices sobre columnas de consulta frecuente
  - Columna de auditoría cargado_en TIMESTAMPTZ DEFAULT now()

USO:
  python 02_schema_rav.py              # solo imprime el DDL
  python 02_schema_rav.py --ejecutar   # conecta a PG y crea el esquema
"""

import os
import sys

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURACIÓN DE CONEXIÓN — editar aquí
# ══════════════════════════════════════════════════════════════════════════════
PG_HOST     = "localhost"
PG_PORT     = 5432
PG_DB       = "migracion_rav"
PG_USER     = "postgres"
PG_PASSWORD = "postgres"
PG_SCHEMA   = "public"
PG_TABLE    = "universo_victimas"

EJECUTAR    = False   # ← cambiar a True para aplicar en PostgreSQL
                      #   o pasar --ejecutar como argumento

# ══════════════════════════════════════════════════════════════════════════════
#  DDL — TABLA PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
#
#  Decisiones de diseño por columna:
#  ─────────────────────────────────────────────────────────────────────────────
#  | Columna                    | Tipo PG          | Razón                      |
#  |----------------------------|------------------|----------------------------|
#  | IDPERSONA, IDHOGAR…        | INTEGER          | Enteros inferidos, ≤ 2^31  |
#  | DOCUMENTO, REGISTRADURIA   | BIGINT           | Puede superar 2^31         |
#  | FECHANACIMIENTO…           | DATE             | Solo fecha, sin hora       |
#  | FEcharEPORTE, FECHAVALORACION | DATE          | Solo fecha                 |
#  | FECHAOCURRENCIA            | DATE             | Solo fecha                 |
#  | ORIGEN, FUENTE, PROGRAMA   | VARCHAR(50)      | Valores cortos conocidos   |
#  | TIPODOCUMENTO, GENERO…     | VARCHAR(30)      | Códigos/enumerados cortos  |
#  | PRIMERNOMBRE…APELLIDO      | VARCHAR(100)     | Nombres de personas        |
#  | HECHO, PRESUNTOACTOR       | TEXT             | Texto libre variable       |
#  | AFECTACIONES               | TEXT             | Texto libre, puede ser largo|
#  | CODDANE*                   | INTEGER          | Código DANE 5 dígitos      |
#  | DISCAPACIDAD               | SMALLINT         | 0/1 flag                   |
#  | Columnas 100% nulas        | TEXT NULL        | Se mantienen para fidelidad|
#  ─────────────────────────────────────────────────────────────────────────────

DDL_CREATE_TABLE = f"""
-- ─────────────────────────────────────────────────────────────────
--  Eliminar tabla si existe (útil en re-ejecuciones de desarrollo)
-- ─────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS {PG_SCHEMA}.{PG_TABLE};

-- ─────────────────────────────────────────────────────────────────
--  Tabla principal
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE {PG_SCHEMA}.{PG_TABLE} (

    -- ── Identificadores del registro ────────────────────────────
    id_fila         BIGSERIAL       PRIMARY KEY,          -- surrogate key, no viene del CSV
    ORIGEN          VARCHAR(50)     NOT NULL,
    FUENTE          VARCHAR(50)     NOT NULL,
    PROGRAMA        VARCHAR(50)     NOT NULL,
    IDPERSONA       INTEGER         NOT NULL,
    IDHOGAR         INTEGER         NOT NULL,

    -- ── Documento de identidad ──────────────────────────────────
    TIPODOCUMENTO   VARCHAR(30),                          -- 0.01% nulos → nullable
    DOCUMENTO       BIGINT          NOT NULL,             -- puede ser >2^31
    EXPEDICIONDOCUMENTO         TEXT,                     -- 100% nulo → TEXT NULL
    FECHAEXPEDICIONDOCUMENTO    TEXT,                     -- 100% nulo → TEXT NULL

    -- ── Datos personales ────────────────────────────────────────
    PRIMERNOMBRE    VARCHAR(100),                         -- 0.07% nulos → nullable
    SEGUNDONOMBRE   VARCHAR(100),                         -- 28% nulos  → nullable
    PRIMERAPELLIDO  VARCHAR(100),                         -- 0.05% nulos → nullable
    SEGUNDOAPELLIDO VARCHAR(100),                         -- 4.89% nulos → nullable
    NOMBRECOMPLETO  VARCHAR(250),                         -- 0.07% nulos → nullable
    FECHANACIMIENTO DATE,                                 -- muy pocos nulos
    PERTENENCIAETNICA   VARCHAR(100)    NOT NULL,
    GENERO              VARCHAR(30)     NOT NULL,

    -- ── Hecho victimizante ──────────────────────────────────────
    TIPOHECHO       VARCHAR(150),                         -- 97.56% nulos → nullable
    HECHO           TEXT            NOT NULL,             -- siempre presente
    FECHAOCURRENCIA DATE            NOT NULL,
    CODDANEMUNICIPIOOCURRENCIA  INTEGER NOT NULL,         -- código DANE 5 dígitos
    ZONAOCURRENCIA              VARCHAR(30),              -- 59% nulos
    UBICACIONOCURRENCIA         TEXT,                     -- 99.49% nulos
    PRESUNTOACTOR               TEXT,                     -- 46% nulos
    PRESUNTOVICTIMIZANTE        TEXT,                     -- 100% nulos

    -- ── Fechas de reporte y valoración ──────────────────────────
    FECHAREPORTE    DATE            NOT NULL,             -- FEcharEPORTE renombrada
    FECHAVALORACION DATE            NOT NULL,

    -- ── Clasificación de la víctima ─────────────────────────────
    TIPOPOBLACION   VARCHAR(50)     NOT NULL,
    TIPOVICTIMA     VARCHAR(50)     NOT NULL,
    ESTADOVICTIMA   VARCHAR(50)     NOT NULL,

    -- ── Residencia ──────────────────────────────────────────────
    PAIS            VARCHAR(50)     NOT NULL,
    CIUDAD          VARCHAR(100),                         -- 35.79% nulos
    CODDANEMUNICIPIORESIDENCIA  INTEGER NOT NULL,
    ZONARESIDENCIA              TEXT,                     -- 100% nulos
    UBICACIONRESIDENCIA         TEXT,                     -- 100% nulos
    DIRECCION                   TEXT,                     -- 100% nulos
    NUMTELEFONOFIJO             TEXT,                     -- 100% nulos
    NUMTELEFONOCELULAR          TEXT,                     -- 100% nulos
    EMAIL                       TEXT,                     -- 100% nulos

    -- ── Siniestro / caso ────────────────────────────────────────
    IDSINIESTRO     INTEGER         NOT NULL,
    IDMIJEFE        INTEGER         NOT NULL,
    TIPODESPLAZAMIENTO  VARCHAR(50),                      -- 0.86% nulos
    REGISTRADURIA       BIGINT      NOT NULL,
    VIGENCIADOCUMENTO   TEXT,                             -- 100% nulos
    CONSPERSONA         INTEGER     NOT NULL,
    RELACION            VARCHAR(100),                     -- 2.49% nulos

    -- ── Códigos DANE declaración/llegada ────────────────────────
    CODDANEDECLARACION  INTEGER     NOT NULL,
    CODDANELLEGADA      INTEGER     NOT NULL,
    CODIGOHECHO         INTEGER     NOT NULL,

    -- ── Discapacidad ────────────────────────────────────────────
    DISCAPACIDAD            SMALLINT    NOT NULL DEFAULT 0,
    DESCRIPCIONDISCAPACIDAD TEXT,                         -- 10% nulos

    -- ── Identificadores de ficha ────────────────────────────────
    FUD_FICHA       VARCHAR(50),                          -- 7.63% nulos
    AFECTACIONES    TEXT,                                 -- 41% nulos

    -- ── Auditoría ───────────────────────────────────────────────
    cargado_en      TIMESTAMPTZ     NOT NULL DEFAULT now()

);
"""

# ══════════════════════════════════════════════════════════════════════════════
#  DDL — ÍNDICES
# ══════════════════════════════════════════════════════════════════════════════
#
#  Criterios de selección de índices:
#  • Columnas usadas en WHERE / JOIN más comunes en consultas RAV
#  • Columnas de búsqueda de personas (documento, nombre)
#  • Columnas de filtro por fecha y geografía
#  • BRIN en fechas: muy eficiente para tablas grandes con datos secuenciales

DDL_INDEXES = f"""
-- ── Búsqueda de persona ────────────────────────────────────────────────────
CREATE INDEX idx_{PG_TABLE}_idpersona
    ON {PG_SCHEMA}.{PG_TABLE} (IDPERSONA);

CREATE INDEX idx_{PG_TABLE}_documento
    ON {PG_SCHEMA}.{PG_TABLE} (DOCUMENTO);

CREATE INDEX idx_{PG_TABLE}_nombre
    ON {PG_SCHEMA}.{PG_TABLE} (PRIMERAPELLIDO, PRIMERNOMBRE);

-- ── Filtros geográficos ────────────────────────────────────────────────────
CREATE INDEX idx_{PG_TABLE}_municipio_ocurrencia
    ON {PG_SCHEMA}.{PG_TABLE} (CODDANEMUNICIPIOOCURRENCIA);

CREATE INDEX idx_{PG_TABLE}_municipio_residencia
    ON {PG_SCHEMA}.{PG_TABLE} (CODDANEMUNICIPIORESIDENCIA);

-- ── Filtros temporales (BRIN: óptimo para tablas grandes con orden temporal) ─
CREATE INDEX idx_{PG_TABLE}_fecha_ocurrencia
    ON {PG_SCHEMA}.{PG_TABLE} USING BRIN (FECHAOCURRENCIA);

CREATE INDEX idx_{PG_TABLE}_fecha_reporte
    ON {PG_SCHEMA}.{PG_TABLE} USING BRIN (FECHAREPORTE);

CREATE INDEX idx_{PG_TABLE}_cargado_en
    ON {PG_SCHEMA}.{PG_TABLE} USING BRIN (cargado_en);

-- ── Filtros de clasificación ───────────────────────────────────────────────
CREATE INDEX idx_{PG_TABLE}_hecho
    ON {PG_SCHEMA}.{PG_TABLE} (CODIGOHECHO);

CREATE INDEX idx_{PG_TABLE}_estadovictima
    ON {PG_SCHEMA}.{PG_TABLE} (ESTADOVICTIMA);

CREATE INDEX idx_{PG_TABLE}_tipovictima
    ON {PG_SCHEMA}.{PG_TABLE} (TIPOVICTIMA);

-- ── Hogar (para consultas de núcleo familiar) ──────────────────────────────
CREATE INDEX idx_{PG_TABLE}_idhogar
    ON {PG_SCHEMA}.{PG_TABLE} (IDHOGAR);
"""

# ══════════════════════════════════════════════════════════════════════════════
#  DDL — COMENTARIOS EN TABLA Y COLUMNAS
# ══════════════════════════════════════════════════════════════════════════════
DDL_COMMENTS = f"""
COMMENT ON TABLE {PG_SCHEMA}.{PG_TABLE} IS
    'Universo de víctimas del conflicto armado — Sistema RAV / RUV. '
    'Fuente: 0002_UNIVERSO_VICTIMAS_LB.txt  |  13,178,321 registros  |  53 columnas originales';

COMMENT ON COLUMN {PG_SCHEMA}.{PG_TABLE}.id_fila     IS 'Surrogate key autoincremental — no proviene del CSV fuente';
COMMENT ON COLUMN {PG_SCHEMA}.{PG_TABLE}.cargado_en  IS 'Timestamp de auditoría: momento exacto en que se insertó la fila';
COMMENT ON COLUMN {PG_SCHEMA}.{PG_TABLE}.FECHAREPORTE IS 'Renombrada desde FEcharEPORTE (typo en fuente original)';
COMMENT ON COLUMN {PG_SCHEMA}.{PG_TABLE}.EXPEDICIONDOCUMENTO      IS '100% nulo en fuente — conservada por fidelidad al esquema original';
COMMENT ON COLUMN {PG_SCHEMA}.{PG_TABLE}.FECHAEXPEDICIONDOCUMENTO IS '100% nulo en fuente — conservada por fidelidad al esquema original';
COMMENT ON COLUMN {PG_SCHEMA}.{PG_TABLE}.PRESUNTOVICTIMIZANTE     IS '100% nulo en fuente — conservada por fidelidad al esquema original';
COMMENT ON COLUMN {PG_SCHEMA}.{PG_TABLE}.ZONARESIDENCIA           IS '100% nulo en fuente';
COMMENT ON COLUMN {PG_SCHEMA}.{PG_TABLE}.UBICACIONRESIDENCIA      IS '100% nulo en fuente';
COMMENT ON COLUMN {PG_SCHEMA}.{PG_TABLE}.DIRECCION                IS '100% nulo en fuente';
COMMENT ON COLUMN {PG_SCHEMA}.{PG_TABLE}.NUMTELEFONOFIJO          IS '100% nulo en fuente';
COMMENT ON COLUMN {PG_SCHEMA}.{PG_TABLE}.NUMTELEFONOCELULAR       IS '100% nulo en fuente';
COMMENT ON COLUMN {PG_SCHEMA}.{PG_TABLE}.EMAIL                    IS '100% nulo en fuente';
COMMENT ON COLUMN {PG_SCHEMA}.{PG_TABLE}.VIGENCIADOCUMENTO        IS '100% nulo en fuente';
"""

# ══════════════════════════════════════════════════════════════════════════════
#  FUNCIONES DE EJECUCIÓN
# ══════════════════════════════════════════════════════════════════════════════
def imprimir_ddl():
    """Imprime el DDL completo en consola."""
    separador = "\n" + "═" * 60 + "\n"
    print(separador + "  DDL — TABLA PRINCIPAL" + separador)
    print(DDL_CREATE_TABLE)
    print(separador + "  DDL — ÍNDICES" + separador)
    print(DDL_INDEXES)
    print(separador + "  DDL — COMENTARIOS" + separador)
    print(DDL_COMMENTS)


def ejecutar_en_postgres():
    """Conecta a PostgreSQL y ejecuta el DDL completo."""
    try:
        import psycopg2
    except ImportError:
        print("\n  ERROR: psycopg2 no instalado.")
        print("  Instalar con:  pip install psycopg2-binary\n")
        sys.exit(1)

    dsn = (
        f"host={PG_HOST} port={PG_PORT} dbname={PG_DB} "
        f"user={PG_USER} password={PG_PASSWORD}"
    )

    print(f"\n  Conectando a PostgreSQL → {PG_HOST}:{PG_PORT}/{PG_DB} ...")
    try:
        conn = psycopg2.connect(dsn)
        conn.autocommit = False
        cur  = conn.cursor()

        pasos = [
            ("Creando tabla", DDL_CREATE_TABLE),
            ("Creando índices", DDL_INDEXES),
            ("Aplicando comentarios", DDL_COMMENTS),
        ]

        for nombre, ddl in pasos:
            print(f"  ↳ {nombre}...", end=" ")
            cur.execute(ddl)
            print("OK")

        conn.commit()
        print(f"\n  ✔  Esquema '{PG_SCHEMA}.{PG_TABLE}' creado exitosamente.")

        # ── Verificación post-creación ────────────────────────────────────────
        cur.execute(f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position;
        """, (PG_SCHEMA, PG_TABLE))

        rows = cur.fetchall()
        print(f"\n  {'Columna':<35}  {'Tipo PG':<25}  {'Nullable'}")
        print(f"  {'─'*35}  {'─'*25}  {'─'*8}")
        for col, dtype, nullable in rows:
            print(f"  {col:<35}  {dtype:<25}  {nullable}")

        cur.execute(f"""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = %s AND tablename = %s;
        """, (PG_SCHEMA, PG_TABLE))

        print(f"\n  ÍNDICES CREADOS ({cur.rowcount} total):")
        for iname, idef in cur.fetchall():
            print(f"  • {iname}")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"\n  ERROR al ejecutar DDL: {e}\n")
        sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
#  PUNTO DE ENTRADA
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\nSe omite la generación de esquema porque la tabla ya existe en la base de datos (DBeaver).\n")
    print("- Asegúrate de que la tabla universo_victimas_v1 está creada y con columnas correctas")
    print("- No es necesario ejecutar DDL en este proyecto, se usa solo como referencia documental")
