-- ============================================================
--  init/01_enums.sql
--  Se ejecuta automáticamente al levantar el contenedor
--  por primera vez (docker-entrypoint-initdb.d)
-- ============================================================

CREATE TYPE genero_enum AS ENUM (
    'MASCULINO', 'FEMENINO', 'INTERSEXUAL', 'NO_INFORMA'
);

CREATE TYPE tipo_documento_enum AS ENUM (
    'CC', 'CE', 'TI', 'PA', 'RC', 'NUIP', 'SC', 'AS', 'MS', 'CD', 'SIN_DOCUMENTO'
);

CREATE TYPE tipo_victima_enum AS ENUM (
    'PERSONA', 'HOGAR', 'COMUNIDAD'
);

CREATE TYPE tipo_poblacion_enum AS ENUM (
    'DESPLAZADO', 'NO_DESPLAZADO'
);

CREATE TYPE estado_victima_enum AS ENUM (
    'INCLUIDO', 'NO_INCLUIDO', 'EXCLUIDO',
    'EN_VALORACION', 'CESACION_CIRCUNSTANCIAS'
);

CREATE TYPE tipo_desplazamiento_enum AS ENUM (
    'INDIVIDUAL', 'MASIVO', 'GOTA_A_GOTA'
);

CREATE TYPE zona_enum AS ENUM (
    'URBANO', 'RURAL', 'CENTRO_POBLADO'
);

CREATE TYPE pertenencia_etnica_enum AS ENUM (
    'NINGUNA', 'INDIGENA', 'GITANO_ROM', 'RAIZAL',
    'PALENQUERO', 'AFROCOLOMBIANO', 'NO_INFORMA'
);