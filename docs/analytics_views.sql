-- ============================================================
-- ESGPilot — Analytics Views
-- ============================================================
-- These views are the ONLY objects the SLM NL→SQL layer may
-- query. Never expose raw tables to the query validator.
--
-- All views include tenant_id for RLS enforcement.
-- The application layer injects tenant + role predicates.
-- ============================================================

-- ──────────────────────────────────────────────────────────
-- Normalised metric view (main analytics surface)
-- One row per project × FY × metric
-- ──────────────────────────────────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS v_metric_normalised AS
SELECT
    p.id                                        AS project_id,
    p.name                                      AS project_name,
    e.id                                        AS entity_id,
    e.name                                      AS entity_name,
    e.sector,
    e.state,
    e.size_band,
    t.id                                        AS tenant_id,
    r.fy,
    r.framework,

    -- ── GHG Emissions ──────────────────────────────────────
    (SELECT fv.value_num
     FROM field_values fv
     WHERE fv.report_id = r.id AND fv.field_code = 'brsr_p6_ei7_scope1'
     LIMIT 1)                                   AS scope1,

    (SELECT fv.value_num
     FROM field_values fv
     WHERE fv.report_id = r.id AND fv.field_code = 'brsr_p6_ei7_scope2'
     LIMIT 1)                                   AS scope2,

    COALESCE(
        (SELECT fv.value_num FROM field_values fv
         WHERE fv.report_id = r.id AND fv.field_code = 'brsr_p6_ei7_scope1' LIMIT 1), 0
    ) +
    COALESCE(
        (SELECT fv.value_num FROM field_values fv
         WHERE fv.report_id = r.id AND fv.field_code = 'brsr_p6_ei7_scope2' LIMIT 1), 0
    )                                           AS scope1_2_total,

    -- ── Energy ─────────────────────────────────────────────
    (SELECT fv.value_num
     FROM field_values fv
     WHERE fv.report_id = r.id AND fv.field_code = 'brsr_p6_ei6_total'
     LIMIT 1)                                   AS energy_total,

    (SELECT fv.value_num
     FROM field_values fv
     WHERE fv.report_id = r.id AND fv.field_code = 'brsr_p6_ei6_renewable'
     LIMIT 1)                                   AS energy_renewable,

    -- ── Water ──────────────────────────────────────────────
    (SELECT fv.value_num
     FROM field_values fv
     WHERE fv.report_id = r.id AND fv.field_code = 'brsr_p6_ei9_withdrawal'
     LIMIT 1)                                   AS water_withdrawal,

    (SELECT fv.value_num
     FROM field_values fv
     WHERE fv.report_id = r.id AND fv.field_code = 'brsr_p6_ei9_consumption'
     LIMIT 1)                                   AS water_consumption,

    (SELECT fv.value_num
     FROM field_values fv
     WHERE fv.report_id = r.id AND fv.field_code = 'brsr_p6_ei9_discharge'
     LIMIT 1)                                   AS water_discharge,

    -- ── Waste ──────────────────────────────────────────────
    (SELECT fv.value_num
     FROM field_values fv
     WHERE fv.report_id = r.id AND fv.field_code = 'brsr_p6_ei10_total'
     LIMIT 1)                                   AS waste_generated,

    (SELECT fv.value_num
     FROM field_values fv
     WHERE fv.report_id = r.id AND fv.field_code = 'brsr_p6_ei10_hazardous'
     LIMIT 1)                                   AS hazardous_waste,

    (SELECT fv.value_num
     FROM field_values fv
     WHERE fv.report_id = r.id AND fv.field_code = 'brsr_p6_ei10_recycled'
     LIMIT 1)                                   AS waste_recycled,

    -- ── CSR ────────────────────────────────────────────────
    (SELECT fv.value_num
     FROM field_values fv
     WHERE fv.report_id = r.id AND fv.field_code = 'brsr_secb_csr_spent'
     LIMIT 1)                                   AS csr_expenditure,

    -- ── Workforce ──────────────────────────────────────────
    (SELECT fv.value_num
     FROM field_values fv
     WHERE fv.report_id = r.id AND fv.field_code = 'brsr_p3_ei1_total'
     LIMIT 1)                                   AS employees_total,

    (SELECT fv.value_num
     FROM field_values fv
     WHERE fv.report_id = r.id AND fv.field_code = 'brsr_p3_ei1_permanent'
     LIMIT 1)                                   AS employees_permanent,

    (SELECT fv.value_num
     FROM field_values fv
     WHERE fv.report_id = r.id AND fv.field_code = 'brsr_p3_ei2_training_hours'
     LIMIT 1)                                   AS training_hours,

    (SELECT fv.value_num
     FROM field_values fv
     WHERE fv.report_id = r.id AND fv.field_code = 'brsr_p3_ei3_fatalities'
     LIMIT 1)                                   AS fatalities,

    (SELECT fv.value_num
     FROM field_values fv
     WHERE fv.report_id = r.id AND fv.field_code = 'brsr_p3_ei3_incidents'
     LIMIT 1)                                   AS safety_incidents,

    -- ── Turnover (for intensity denominators) ──────────────
    (SELECT fv.value_num
     FROM field_values fv
     WHERE fv.report_id = r.id AND fv.field_code = 'brsr_seca_turnover'
     LIMIT 1)                                   AS turnover_cr,

    -- ── Derived Intensities (computed here, not by SLM) ────
    CASE
        WHEN (SELECT fv.value_num FROM field_values fv
              WHERE fv.report_id = r.id AND fv.field_code = 'brsr_seca_turnover' LIMIT 1) > 0
        THEN ROUND(
            (COALESCE((SELECT fv.value_num FROM field_values fv
                       WHERE fv.report_id = r.id AND fv.field_code = 'brsr_p6_ei7_scope1' LIMIT 1), 0) +
             COALESCE((SELECT fv.value_num FROM field_values fv
                       WHERE fv.report_id = r.id AND fv.field_code = 'brsr_p6_ei7_scope2' LIMIT 1), 0))
            /
            (SELECT fv.value_num FROM field_values fv
             WHERE fv.report_id = r.id AND fv.field_code = 'brsr_seca_turnover' LIMIT 1)
        , 4)
        ELSE NULL
    END                                         AS ghg_intensity,

    CASE
        WHEN (SELECT fv.value_num FROM field_values fv
              WHERE fv.report_id = r.id AND fv.field_code = 'brsr_seca_turnover' LIMIT 1) > 0
        THEN ROUND(
            COALESCE((SELECT fv.value_num FROM field_values fv
                      WHERE fv.report_id = r.id AND fv.field_code = 'brsr_p6_ei6_total' LIMIT 1), 0)
            /
            (SELECT fv.value_num FROM field_values fv
             WHERE fv.report_id = r.id AND fv.field_code = 'brsr_seca_turnover' LIMIT 1)
        , 4)
        ELSE NULL
    END                                         AS energy_intensity,

    CASE
        WHEN (SELECT fv.value_num FROM field_values fv
              WHERE fv.report_id = r.id AND fv.field_code = 'brsr_seca_turnover' LIMIT 1) > 0
        THEN ROUND(
            COALESCE((SELECT fv.value_num FROM field_values fv
                      WHERE fv.report_id = r.id AND fv.field_code = 'brsr_p6_ei9_consumption' LIMIT 1), 0)
            /
            (SELECT fv.value_num FROM field_values fv
             WHERE fv.report_id = r.id AND fv.field_code = 'brsr_seca_turnover' LIMIT 1)
        , 4)
        ELSE NULL
    END                                         AS water_intensity,

    r.status                                    AS report_status,
    r.submitted_at

FROM reports r
JOIN projects p       ON p.id = r.project_id
JOIN entities e       ON e.id = p.entity_id
JOIN tenants t        ON t.id = e.tenant_id
WHERE r.status IN ('submitted', 'approved')
WITH DATA;

-- Index for tenant-scoped queries
CREATE INDEX IF NOT EXISTS idx_v_metric_tenant_fy
    ON v_metric_normalised (tenant_id, fy);

CREATE INDEX IF NOT EXISTS idx_v_metric_entity_fy
    ON v_metric_normalised (entity_id, fy);


-- ──────────────────────────────────────────────────────────
-- Entity scorecard view
-- Aggregates all projects for an entity into a single row
-- ──────────────────────────────────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS v_entity_scorecard AS
SELECT
    m.tenant_id,
    m.entity_id,
    m.entity_name,
    m.sector,
    m.state,
    m.size_band,
    m.fy,

    -- Aggregated metrics (sum across projects)
    SUM(m.scope1)           AS scope1_total,
    SUM(m.scope2)           AS scope2_total,
    SUM(m.scope1_2_total)   AS ghg_total,
    SUM(m.energy_total)     AS energy_total,
    SUM(m.water_withdrawal) AS water_withdrawal_total,
    SUM(m.waste_generated)  AS waste_total,
    SUM(m.csr_expenditure)  AS csr_total,
    SUM(m.employees_total)  AS employees_total,
    SUM(m.fatalities)       AS fatalities_total,
    SUM(m.safety_incidents) AS safety_incidents_total,

    -- Turnover (sum for intensity base)
    SUM(m.turnover_cr)      AS turnover_total_cr,

    -- Weighted average intensities
    CASE WHEN SUM(m.turnover_cr) > 0
         THEN ROUND(SUM(m.scope1_2_total) / NULLIF(SUM(m.turnover_cr), 0), 4)
         ELSE NULL END       AS ghg_intensity,

    CASE WHEN SUM(m.turnover_cr) > 0
         THEN ROUND(SUM(m.energy_total) / NULLIF(SUM(m.turnover_cr), 0), 4)
         ELSE NULL END       AS energy_intensity,

    CASE WHEN SUM(m.turnover_cr) > 0
         THEN ROUND(SUM(m.water_consumption) / NULLIF(SUM(m.turnover_cr), 0), 4)
         ELSE NULL END       AS water_intensity,

    COUNT(DISTINCT m.project_id)  AS project_count

FROM v_metric_normalised m
GROUP BY
    m.tenant_id, m.entity_id, m.entity_name, m.sector, m.state, m.size_band, m.fy
WITH DATA;

CREATE INDEX IF NOT EXISTS idx_v_entity_scorecard_tenant_fy
    ON v_entity_scorecard (tenant_id, fy);


-- ──────────────────────────────────────────────────────────
-- Data quality heatmap view
-- ──────────────────────────────────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS v_data_quality AS
WITH mandatory_fields AS (
    -- Count mandatory fields per framework
    SELECT
        framework,
        COUNT(*) AS mandatory_count
    FROM field_defs
    WHERE mandatory_for ? 'top_1000'   -- JSONB contains key check
       OR mandatory_for::text LIKE '%top_1000%'
    GROUP BY framework
),
filled_fields AS (
    SELECT
        r.id                                AS report_id,
        r.project_id,
        r.fy,
        r.framework,
        e.id                                AS entity_id,
        e.name                              AS entity_name,
        t.id                                AS tenant_id,
        COUNT(fv.id)                        AS fields_filled,
        COUNT(CASE WHEN fv.evidence_url IS NOT NULL
                     OR fv.source_type IS NOT NULL THEN 1 END)
                                            AS fields_evidenced,
        COUNT(CASE WHEN fv.verified_by IS NOT NULL THEN 1 END)
                                            AS fields_verified
    FROM reports r
    JOIN projects p ON p.id = r.project_id
    JOIN entities e ON e.id = p.entity_id
    JOIN tenants t  ON t.id = e.tenant_id
    LEFT JOIN field_values fv ON fv.report_id = r.id
    GROUP BY r.id, r.project_id, r.fy, r.framework, e.id, e.name, t.id
),
suggestion_counts AS (
    SELECT
        report_id,
        COUNT(*) FILTER (WHERE severity = 'critical') AS critical_issues,
        COUNT(*) FILTER (WHERE severity = 'warn')     AS warn_issues
    FROM suggestions
    WHERE status = 'pending'
    GROUP BY report_id
)
SELECT
    ff.tenant_id,
    ff.entity_id,
    ff.entity_name,
    ff.report_id,
    ff.project_id,
    ff.fy,
    ff.framework,
    ff.fields_filled,
    ff.fields_evidenced,
    ff.fields_verified,
    COALESCE(mf.mandatory_count, 0)         AS mandatory_count,
    CASE WHEN COALESCE(mf.mandatory_count, 0) > 0
         THEN ROUND(ff.fields_filled::numeric / mf.mandatory_count, 3)
         ELSE 0
    END                                     AS completeness_rate,
    COALESCE(sc.critical_issues, 0)         AS critical_issues,
    COALESCE(sc.warn_issues, 0)             AS warn_issues,
    CASE
        WHEN COALESCE(sc.critical_issues, 0) > 0 THEN 'red'
        WHEN COALESCE(sc.warn_issues, 0) > 3     THEN 'amber'
        WHEN ff.fields_filled = 0               THEN 'grey'
        ELSE 'green'
    END                                     AS quality_status

FROM filled_fields ff
LEFT JOIN mandatory_fields mf ON mf.framework = ff.framework
LEFT JOIN suggestion_counts sc ON sc.report_id = ff.report_id
WITH DATA;

CREATE INDEX IF NOT EXISTS idx_v_data_quality_tenant_fy
    ON v_data_quality (tenant_id, fy);

CREATE INDEX IF NOT EXISTS idx_v_data_quality_entity
    ON v_data_quality (entity_id, fy);


-- ──────────────────────────────────────────────────────────
-- Refresh function (call after batch report submission)
-- ──────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION refresh_analytics_views()
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY v_metric_normalised;
    REFRESH MATERIALIZED VIEW CONCURRENTLY v_entity_scorecard;
    REFRESH MATERIALIZED VIEW CONCURRENTLY v_data_quality;
END;
$$;

COMMENT ON MATERIALIZED VIEW v_metric_normalised IS
    'Normalised per-project ESG metrics. Refreshed on report submission. Used by NL→SQL layer.';
COMMENT ON MATERIALIZED VIEW v_entity_scorecard IS
    'Entity-level aggregated scorecard (sum across projects). Used for portfolio comparison.';
COMMENT ON MATERIALIZED VIEW v_data_quality IS
    'Data quality heatmap per report. Drives the admin quality dashboard.';
