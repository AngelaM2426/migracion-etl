-- ============================================================
--  init/02_tabla.sql
--  Corre después de 01_enums.sql (orden alfabético)
-- ============================================================

CREATE TABLE universo_victimas_v1 (

    id                          BIGSERIAL       PRIMARY KEY,

    origen                      VARCHAR(100)    NOT NULL,
    fuente                      VARCHAR(100)    NOT NULL,
    programa                    VARCHAR(100)    NOT NULL,

    idpersona                   BIGINT          NOT NULL,
    idhogar                     BIGINT          NOT NULL,

    tipodocumento               tipo_documento_enum,
    documento                   BIGINT          NOT NULL,

    primernombre                VARCHAR(100)    NOT NULL,
    segundonombre               VARCHAR(100),
    primerapellido              VARCHAR(100)    NOT NULL,
    segundoapellido             VARCHAR(100),
    nombrecompleto              VARCHAR(300),

    fechanacimiento             DATE            NOT NULL,

    expediciondocumento         VARCHAR(150),
    fechaexpediciondocumento    DATE,
    vigenciadocumento           DATE,

    pertenenciaetnica           pertenencia_etnica_enum NOT NULL,
    genero                      genero_enum             NOT NULL,

    tipohecho                   VARCHAR(100),
    hecho                       VARCHAR(200)    NOT NULL,
    codigohecho                 INTEGER         NOT NULL,
    fechaocurrencia             DATE            NOT NULL,
    coddanemunicipioocurrencia  INTEGER         NOT NULL,
    zonaocurrencia              zona_enum,
    ubicacionocurrencia         VARCHAR(300),
    presuntoactor               VARCHAR(200),
    presuntovictimizante        VARCHAR(200),

    fechareporte                DATE            NOT NULL,
    fechavaloracion             DATE            NOT NULL,

    tipopoblacion               tipo_poblacion_enum     NOT NULL,
    tipovictima                 tipo_victima_enum       NOT NULL,
    estadovictima               estado_victima_enum     NOT NULL,
    tipodesplazamiento          VARCHAR(50),

    pais                        CHAR(3)         NOT NULL,
    ciudad                      VARCHAR(150),
    coddanemunicipioresidencia  INTEGER         NOT NULL,

    zonaresidencia              zona_enum,
    ubicacionresidencia         VARCHAR(300),
    direccion                   VARCHAR(400),
    numtelefonofijo             VARCHAR(20),
    numtelefonocelular          VARCHAR(20),
    email                       VARCHAR(254),

    idsiniestro                 BIGINT          NOT NULL,
    idmijefe                    BIGINT          NOT NULL,
    registraduria               BIGINT          NOT NULL,
    conspersona                 INTEGER         NOT NULL,
    relacion                    VARCHAR(100),
    coddanedeclaracion          INTEGER         NOT NULL,
    coddanellegada              INTEGER         NOT NULL,

    discapacidad                SMALLINT        NOT NULL
                                    CHECK (discapacidad IN (0, 1)),
    descripciondiscapacidad     TEXT,

    fud_ficha                   VARCHAR(50),
    afectaciones                TEXT,

    cargado_en                  TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- Índices
CREATE INDEX idx_uv_documento         ON universo_victimas_v1 (tipodocumento, documento);
CREATE INDEX idx_uv_idpersona         ON universo_victimas_v1 (idpersona);
CREATE INDEX idx_uv_idhogar           ON universo_victimas_v1 (idhogar);
CREATE INDEX idx_uv_fechaocurrencia   ON universo_victimas_v1 (fechaocurrencia);
CREATE INDEX idx_uv_fechareporte      ON universo_victimas_v1 (fechareporte);
CREATE INDEX idx_uv_mpio_ocurrencia   ON universo_victimas_v1 (coddanemunicipioocurrencia);
CREATE INDEX idx_uv_mpio_residencia   ON universo_victimas_v1 (coddanemunicipioresidencia);
CREATE INDEX idx_uv_estadovictima     ON universo_victimas_v1 (estadovictima);
CREATE INDEX idx_uv_hecho             ON universo_victimas_v1 (hecho);
CREATE INDEX idx_uv_cargado_en        ON universo_victimas_v1 (cargado_en);