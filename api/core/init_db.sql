-- ============================================================
-- ESGPilot — Database Initialization Script
-- ============================================================
-- Creates all tables, indexes, Row-Level Security policies,
-- and seeds essential data.
--
-- Run order:
--   1. This script (init_db.sql)
--   2. docs/analytics_views.sql (materialized views)
--
-- Requirements: PostgreSQL 15+
-- ============================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ──────────────────────────────────────────────────────────
-- ENUM TYPES
-- ──────────────────────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE report_status AS ENUM ('draft', 'in_review', 'submitted', 'approved');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE suggestion_severity AS ENUM ('info', 'warn', 'critical');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE suggestion_status AS ENUM ('pending', 'accepted', 'ignored', 'applied');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE suggestion_scope AS ENUM ('field', 'section', 'form', 'portfolio');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE suggestion_source AS ENUM ('rule', 'slm', 'hybrid');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE user_role AS ENUM (
        'project_user', 'entity_admin', 'group_admin',
        'auditor', 'tenant_admin'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE field_type AS ENUM (
        'number', 'text', 'textarea', 'select', 'boolean', 'date', 'file'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ──────────────────────────────────────────────────────────
-- TABLES
-- ──────────────────────────────────────────────────────────

-- Tenants (top-level groups/organisations)
CREATE TABLE IF NOT EXISTS tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    plan            VARCHAR(50)  NOT NULL DEFAULT 'free',
    region          VARCHAR(10)  NOT NULL DEFAULT 'IN',
    settings        JSONB        NOT NULL DEFAULT '{}',
    api_key_hash    VARCHAR(255),
    allowed_origins JSONB        NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Entities (subsidiaries / partners)
CREATE TABLE IF NOT EXISTS entities (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    parent_id   UUID REFERENCES entities(id),
    name        VARCHAR(255) NOT NULL,
    cin         VARCHAR(21),
    sector      VARCHAR(100),
    size_band   VARCHAR(50) DEFAULT 'listed',  -- top_1000 | listed | unlisted
    state       VARCHAR(50),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_entities_tenant ON entities(tenant_id);
CREATE INDEX IF NOT EXISTS ix_entities_parent ON entities(parent_id);

-- Projects
CREATE TABLE IF NOT EXISTS projects (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id   UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    sector      VARCHAR(100),
    location    VARCHAR(255),
    start_date  DATE,
    status      VARCHAR(50) DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_projects_entity ON projects(entity_id);

-- Users
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email         VARCHAR(255) NOT NULL UNIQUE,
    name          VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          user_role NOT NULL DEFAULT 'project_user',
    entity_id     UUID REFERENCES entities(id),
    project_id    UUID REFERENCES projects(id),
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_users_tenant   ON users(tenant_id);
CREATE INDEX IF NOT EXISTS ix_users_email    ON users(email);

-- Reports
CREATE TABLE IF NOT EXISTS reports (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id   UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    fy           VARCHAR(10)  NOT NULL,   -- e.g. "FY2025"
    framework    VARCHAR(50)  NOT NULL,   -- e.g. "BRSR"
    status       report_status NOT NULL DEFAULT 'draft',
    submitted_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_reports_project_fy ON reports(project_id, fy);
CREATE UNIQUE INDEX IF NOT EXISTS uq_reports_project_fy_framework
    ON reports(project_id, fy, framework);

-- Field definitions (the machine-readable BRSR catalogue)
CREATE TABLE IF NOT EXISTS field_defs (
    id              VARCHAR(100) PRIMARY KEY,  -- e.g. "brsr_p6_ei7_scope1"
    framework       VARCHAR(50)  NOT NULL,
    section         VARCHAR(100) NOT NULL,
    code            VARCHAR(50)  NOT NULL,     -- e.g. "P6-EI-7"
    label           TEXT         NOT NULL,
    unit            VARCHAR(50),
    field_type      field_type   NOT NULL DEFAULT 'number',
    mandatory_for   JSONB        NOT NULL DEFAULT '{}',
    formula         TEXT,
    validations     JSONB        NOT NULL DEFAULT '{}',
    refs            JSONB        NOT NULL DEFAULT '{}',
    version         VARCHAR(20)  NOT NULL DEFAULT '2024'
);

CREATE INDEX IF NOT EXISTS ix_field_defs_framework ON field_defs(framework, section);

-- Field values (actual data entered per report)
CREATE TABLE IF NOT EXISTS field_values (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id    UUID NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    field_code   VARCHAR(100) NOT NULL,
    value_num    DOUBLE PRECISION,
    value_text   TEXT,
    unit         VARCHAR(50),
    source_type  VARCHAR(50),    -- meter | bill | estimate | calculated
    evidence_url TEXT,
    entered_by   UUID,           -- FK to users (denormalised for perf)
    entered_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_by  UUID
);

CREATE INDEX IF NOT EXISTS ix_field_values_report_field
    ON field_values(report_id, field_code);
CREATE UNIQUE INDEX IF NOT EXISTS uq_field_values_report_field
    ON field_values(report_id, field_code);

-- Suggestions (recommendations from rules engine / SLM)
CREATE TABLE IF NOT EXISTS suggestions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id     UUID NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    field_code    VARCHAR(100),
    scope         suggestion_scope   NOT NULL DEFAULT 'field',
    severity      suggestion_severity NOT NULL DEFAULT 'info',
    title         TEXT NOT NULL,
    why           TEXT,
    how_to_fix    TEXT,
    references    JSONB DEFAULT '[]',
    sdg_tags      JSONB DEFAULT '[]',
    confidence    DOUBLE PRECISION,
    source        suggestion_source NOT NULL DEFAULT 'rule',
    status        suggestion_status NOT NULL DEFAULT 'pending',
    payload       JSONB DEFAULT '{}',
    model_version VARCHAR(50),
    kb_version    VARCHAR(50),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_suggestions_report
    ON suggestions(report_id);
CREATE INDEX IF NOT EXISTS ix_suggestions_report_status
    ON suggestions(report_id, status);

-- Feedback (thumbs up/down on suggestions and chat messages)
CREATE TABLE IF NOT EXISTS feedback (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    suggestion_id UUID REFERENCES suggestions(id),
    message_id    VARCHAR(100),
    rating        SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    reason        TEXT,
    user_id       UUID NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- KB documents
CREATE TABLE IF NOT EXISTS kb_docs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title          TEXT NOT NULL,
    issuer         VARCHAR(255),
    doc_type       VARCHAR(50) NOT NULL DEFAULT 'guidance',
    version        VARCHAR(50),
    effective_from TIMESTAMPTZ,
    effective_to   TIMESTAMPTZ,
    superseded_by  UUID REFERENCES kb_docs(id),
    url            TEXT,
    sha256         VARCHAR(64),
    scope          VARCHAR(50) NOT NULL DEFAULT 'global',  -- global | tenant_{id}
    lang           VARCHAR(5)  NOT NULL DEFAULT 'en',
    licence        VARCHAR(100),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_kb_docs_scope     ON kb_docs(scope);
CREATE INDEX IF NOT EXISTS ix_kb_docs_framework ON kb_docs USING gin((doc_type::text));

-- KB chunks (mirrored in Qdrant for vector search)
CREATE TABLE IF NOT EXISTS kb_chunks (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id       UUID NOT NULL REFERENCES kb_docs(id) ON DELETE CASCADE,
    section_path TEXT,
    text         TEXT NOT NULL,
    page         INTEGER,
    meta         JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS ix_kb_chunks_doc ON kb_chunks(doc_id);

-- Emission factors (versioned lookup table)
CREATE TABLE IF NOT EXISTS emission_factors (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source       VARCHAR(100) NOT NULL,
    year         INTEGER      NOT NULL,
    region       VARCHAR(50)  NOT NULL DEFAULT 'IN',
    fuel_or_grid VARCHAR(100) NOT NULL,
    unit         VARCHAR(50)  NOT NULL,
    factor       DOUBLE PRECISION NOT NULL,
    gwp_basis    VARCHAR(20)  DEFAULT 'AR5'
);

CREATE INDEX IF NOT EXISTS ix_ef_source_year ON emission_factors(source, year);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ef_source_year_fuel
    ON emission_factors(source, year, region, fuel_or_grid);

-- Audit log (immutable append-only)
CREATE TABLE IF NOT EXISTS audit_log (
    id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID         NOT NULL,
    actor     VARCHAR(255) NOT NULL,
    action    VARCHAR(100) NOT NULL,
    payload   JSONB        DEFAULT '{}',
    ts        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_audit_log_tenant_ts ON audit_log(tenant_id, ts DESC);

-- ──────────────────────────────────────────────────────────
-- ROW-LEVEL SECURITY (RLS)
-- ──────────────────────────────────────────────────────────
-- Policy: every table is filtered by current_setting('app.tenant_id').
-- The application sets this at the start of each request.
-- Roles: app_user (normal), app_admin (tenant admin), app_service (internal)

-- Create roles if they don't exist
DO $$ BEGIN
    CREATE ROLE app_user    NOLOGIN NOINHERIT;
    CREATE ROLE app_admin   NOLOGIN NOINHERIT;
    CREATE ROLE app_service NOLOGIN NOINHERIT;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Grant table access
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_service;

-- Enable RLS
ALTER TABLE tenants       ENABLE ROW LEVEL SECURITY;
ALTER TABLE entities      ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects      ENABLE ROW LEVEL SECURITY;
ALTER TABLE users         ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports       ENABLE ROW LEVEL SECURITY;
ALTER TABLE field_values  ENABLE ROW LEVEL SECURITY;
ALTER TABLE suggestions   ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback      ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log     ENABLE ROW LEVEL SECURITY;

-- Service role bypasses RLS
CREATE POLICY service_bypass ON tenants      TO app_service USING (TRUE);
CREATE POLICY service_bypass ON entities     TO app_service USING (TRUE);
CREATE POLICY service_bypass ON projects     TO app_service USING (TRUE);
CREATE POLICY service_bypass ON users        TO app_service USING (TRUE);
CREATE POLICY service_bypass ON reports      TO app_service USING (TRUE);
CREATE POLICY service_bypass ON field_values TO app_service USING (TRUE);
CREATE POLICY service_bypass ON suggestions  TO app_service USING (TRUE);
CREATE POLICY service_bypass ON feedback     TO app_service USING (TRUE);
CREATE POLICY service_bypass ON audit_log    TO app_service USING (TRUE);

-- Tenant isolation policies (app_user sees only their tenant)
CREATE POLICY tenant_isolation ON tenants
    FOR ALL TO app_user, app_admin
    USING (id::TEXT = current_setting('app.tenant_id', TRUE));

CREATE POLICY tenant_isolation ON entities
    FOR ALL TO app_user, app_admin
    USING (tenant_id::TEXT = current_setting('app.tenant_id', TRUE));

CREATE POLICY tenant_isolation ON users
    FOR ALL TO app_user, app_admin
    USING (tenant_id::TEXT = current_setting('app.tenant_id', TRUE));

-- Projects visible via entity → tenant chain
CREATE POLICY tenant_isolation ON projects
    FOR ALL TO app_user, app_admin
    USING (
        entity_id IN (
            SELECT id FROM entities
            WHERE tenant_id::TEXT = current_setting('app.tenant_id', TRUE)
        )
    );

-- Reports visible via project → entity → tenant chain
CREATE POLICY tenant_isolation ON reports
    FOR ALL TO app_user, app_admin
    USING (
        project_id IN (
            SELECT p.id FROM projects p
            JOIN entities e ON e.id = p.entity_id
            WHERE e.tenant_id::TEXT = current_setting('app.tenant_id', TRUE)
        )
    );

-- Field values follow report isolation
CREATE POLICY tenant_isolation ON field_values
    FOR ALL TO app_user, app_admin
    USING (
        report_id IN (
            SELECT r.id FROM reports r
            JOIN projects p ON p.id = r.project_id
            JOIN entities e ON e.id = p.entity_id
            WHERE e.tenant_id::TEXT = current_setting('app.tenant_id', TRUE)
        )
    );

-- Suggestions follow report isolation
CREATE POLICY tenant_isolation ON suggestions
    FOR ALL TO app_user, app_admin
    USING (
        report_id IN (
            SELECT r.id FROM reports r
            JOIN projects p ON p.id = r.project_id
            JOIN entities e ON e.id = p.entity_id
            WHERE e.tenant_id::TEXT = current_setting('app.tenant_id', TRUE)
        )
    );

-- Feedback isolated by user's tenant
CREATE POLICY tenant_isolation ON feedback
    FOR ALL TO app_user, app_admin
    USING (
        user_id IN (
            SELECT id FROM users
            WHERE tenant_id::TEXT = current_setting('app.tenant_id', TRUE)
        )
    );

-- Audit log
CREATE POLICY tenant_isolation ON audit_log
    FOR ALL TO app_user, app_admin
    USING (tenant_id::TEXT = current_setting('app.tenant_id', TRUE));

-- ──────────────────────────────────────────────────────────
-- HELPER FUNCTIONS
-- ──────────────────────────────────────────────────────────

-- Set tenant context (called at request start by application)
CREATE OR REPLACE FUNCTION set_tenant_context(p_tenant_id TEXT)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    PERFORM set_config('app.tenant_id', p_tenant_id, TRUE);
END;
$$;

-- Append-only audit log trigger
CREATE OR REPLACE FUNCTION audit_log_insert()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log(tenant_id, actor, action, payload)
        VALUES (
            current_setting('app.tenant_id', TRUE)::UUID,
            current_setting('app.user_id', TRUE),
            TG_TABLE_NAME || '.' || TG_OP,
            row_to_json(OLD)::JSONB
        );
    ELSE
        INSERT INTO audit_log(tenant_id, actor, action, payload)
        VALUES (
            current_setting('app.tenant_id', TRUE)::UUID,
            current_setting('app.user_id', TRUE),
            TG_TABLE_NAME || '.' || TG_OP,
            row_to_json(NEW)::JSONB
        );
    END IF;
    RETURN NEW;
END;
$$;

-- Attach audit triggers to key tables
DO $$ BEGIN
    CREATE TRIGGER audit_field_values
        AFTER INSERT OR UPDATE OR DELETE ON field_values
        FOR EACH ROW EXECUTE FUNCTION audit_log_insert();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TRIGGER audit_suggestions
        AFTER INSERT OR UPDATE ON suggestions
        FOR EACH ROW EXECUTE FUNCTION audit_log_insert();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TRIGGER audit_reports
        AFTER INSERT OR UPDATE ON reports
        FOR EACH ROW EXECUTE FUNCTION audit_log_insert();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ──────────────────────────────────────────────────────────
-- SEED DATA
-- ──────────────────────────────────────────────────────────

-- Seed India grid emission factors (CEA)
INSERT INTO emission_factors (source, year, region, fuel_or_grid, unit, factor, gwp_basis)
VALUES
    ('CEA CO2 Baseline Database', 2019, 'IN', 'grid_electricity', 'tCO2e/MWh', 0.82, 'AR5'),
    ('CEA CO2 Baseline Database', 2020, 'IN', 'grid_electricity', 'tCO2e/MWh', 0.79, 'AR5'),
    ('CEA CO2 Baseline Database', 2021, 'IN', 'grid_electricity', 'tCO2e/MWh', 0.79, 'AR5'),
    ('CEA CO2 Baseline Database', 2022, 'IN', 'grid_electricity', 'tCO2e/MWh', 0.78, 'AR5'),
    ('CEA CO2 Baseline Database', 2023, 'IN', 'grid_electricity', 'tCO2e/MWh', 0.72, 'AR5'),
    ('CEA CO2 Baseline Database', 2024, 'IN', 'grid_electricity', 'tCO2e/MWh', 0.71, 'AR5')
ON CONFLICT (source, year, region, fuel_or_grid) DO UPDATE
    SET factor = EXCLUDED.factor;

-- Seed fuel emission factors (IPCC 2006)
INSERT INTO emission_factors (source, year, region, fuel_or_grid, unit, factor, gwp_basis)
VALUES
    ('IPCC 2006', 2024, 'IN', 'diesel',           'tCO2e/kL',           2.6413, 'AR5'),
    ('IPCC 2006', 2024, 'IN', 'petrol',            'tCO2e/kL',           2.2496, 'AR5'),
    ('IPCC 2006', 2024, 'IN', 'lpg',               'tCO2e/MT',           2.9830, 'AR5'),
    ('IPCC 2006', 2024, 'IN', 'cng',               'tCO2e/thousand_m3',  2.0424, 'AR5'),
    ('IPCC 2006', 2024, 'IN', 'natural_gas',       'tCO2e/thousand_m3',  2.0424, 'AR5'),
    ('IPCC 2006', 2024, 'IN', 'coal_bituminous',   'tCO2e/MT',           2.4475, 'AR5'),
    ('IPCC 2006', 2024, 'IN', 'coal_lignite',      'tCO2e/MT',           1.1095, 'AR5'),
    ('IPCC 2006', 2024, 'IN', 'furnace_oil',       'tCO2e/kL',           2.9557, 'AR5'),
    ('IPCC 2006', 2024, 'IN', 'biomass',           'tCO2e/MT',           0.0000, 'AR5')
ON CONFLICT (source, year, region, fuel_or_grid) DO UPDATE
    SET factor = EXCLUDED.factor;

-- ──────────────────────────────────────────────────────────
-- COMMENTS
-- ──────────────────────────────────────────────────────────

COMMENT ON TABLE tenants IS 'Top-level group/organisation. Each tenant has isolated data.';
COMMENT ON TABLE entities IS 'Subsidiary or partner within a tenant group.';
COMMENT ON TABLE projects IS 'Specific project under an entity (plant, site, sub-project).';
COMMENT ON TABLE users IS 'User within a tenant with role-based access.';
COMMENT ON TABLE reports IS 'ESG report for a project × FY × framework combination.';
COMMENT ON TABLE field_defs IS 'Machine-readable BRSR/GRI field catalogue. Drives rules engine.';
COMMENT ON TABLE field_values IS 'Actual values entered for each field in a report.';
COMMENT ON TABLE suggestions IS 'Rules engine / SLM recommendations for a report.';
COMMENT ON TABLE feedback IS 'User thumbs up/down on suggestions and chat messages.';
COMMENT ON TABLE kb_docs IS 'Knowledge base document registry.';
COMMENT ON TABLE kb_chunks IS 'KB document chunks mirrored in Qdrant vector store.';
COMMENT ON TABLE emission_factors IS 'Versioned emission factors for GHG calculations.';
COMMENT ON TABLE audit_log IS 'Immutable audit trail of all significant actions.';
