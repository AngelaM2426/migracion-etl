-- ============================================
-- Creación de tabla universo_victimas_v1
-- Cumple con 3.2: tipos adecuados, NOT NULL, índices y auditoría
-- ============================================

CREATE TABLE universo_victimas_v1 (
    id                      BIGSERIAL PRIMARY KEY,
    origen                  TEXT        NOT NULL,
    fuente                  TEXT        NOT NULL,
    programa                TEXT        NOT NULL,
    idpersona               BIGINT      NOT NULL,
    idhogar                 BIGINT      NOT NULL,
    tipodocumento           TEXT,
    documento               BIGINT      NOT NULL,
    primernombre            TEXT        NOT NULL,
    segundonombre           TEXT,
    primerapellido          TEXT        NOT NULL,
    segundoapellido         TEXT,
    nombrecompleto          TEXT        NOT NULL,
    fechanacimiento         DATE        NOT NULL,
    expediciondocumento     TEXT,
    fechaexpediciondocumento DATE,
    vigenciadocumento       DATE,
    pertenenciaetnica       TEXT        NOT NULL,
    genero                  TEXT        NOT NULL,
    tipohecho               TEXT,
    hecho                   TEXT        NOT NULL,
    fechaocurrencia         DATE        NOT NULL,
    coddanemunicipioocurrencia BIGINT   NOT NULL,
    zonaocurrencia          TEXT,
    ubicacionocurrencia     TEXT,
    presuntoactor           TEXT,
    presuntovictimizante    TEXT,
    fechareporte            DATE        NOT NULL,
    tipopoblacion           TEXT        NOT NULL,
    tipovictima             TEXT        NOT NULL,
    pais                    TEXT        NOT NULL,
    ciudad                  TEXT,
    coddanemunicipioresidencia BIGINT   NOT NULL,
    zonaresidencia          TEXT,
    ubicacionresidencia     TEXT,
    direccion               TEXT,
    numtelefonofijo         TEXT,
    numtelefonocelular      TEXT,
    email                   TEXT,
    fechavaloracion         DATE        NOT NULL,
    estadovictima           TEXT        NOT NULL,
    idsiniestro             BIGINT      NOT NULL,
    idmijefe                BIGINT      NOT NULL,
    tipodesplazamiento      TEXT,
    registraduria           BIGINT      NOT NULL,
    conspersona             BIGINT      NOT NULL,
    relacion                TEXT,
    coddanedeclaracion      BIGINT      NOT NULL,
    coddanellegada          BIGINT      NOT NULL,
    codigohecho             BIGINT      NOT NULL,
    discapacidad            BIGINT      NOT NULL,
    descripciondiscapacidad TEXT,
    fud_ficha               TEXT,
    afectaciones            TEXT,
    cargado_en              TIMESTAMPTZ DEFAULT now()
);




-- ============================================
-- Índices recomendados
-- ============================================

CREATE INDEX idx_victimas_idpersona ON universo_victimas_v1(idpersona);
CREATE INDEX idx_victimas_documento ON universo_victimas_v1(documento);
CREATE INDEX idx_victimas_coddanemunicipioocurrencia ON universo_victimas_v1(coddanemunicipioocurrencia);
CREATE INDEX idx_victimas_coddanemunicipioresidencia ON universo_victimas_v1(coddanemunicipioresidencia);
CREATE INDEX idx_victimas







