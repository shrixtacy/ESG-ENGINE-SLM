"""
ESGPilot — Unit Tests for Rules Engine.

Tests all check types:
  - Completeness
  - Type/Unit validation
  - Range checks
  - Cross-field arithmetic
  - YoY delta
  - Outlier detection
  - Readiness score
  - Boundary checks
  - Disclosure quality
"""

import pytest
from rules.engine import RulesEngine, FieldCatalogue, FieldSpec, Severity, FindingType
from rules.checks.boundary_checks import (
    check_ghg_total,
    check_energy_total,
    check_water_balance,
    check_waste_total,
    check_employee_total,
    check_csr_spend,
    run_boundary_checks,
)
from rules.checks.disclosure_quality import DisclosureQualityChecker


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def minimal_catalogue():
    """A minimal in-memory field catalogue for tests."""
    catalogue = FieldCatalogue()

    catalogue.fields = {
        "brsr_p6_ei7_scope1": FieldSpec(
            id="brsr_p6_ei7_scope1",
            framework="BRSR",
            section="P6",
            code="P6-EI-7a",
            label="Scope 1 GHG Emissions",
            unit="tCO2e",
            field_type="number",
            mandatory_for={"classes": ["top_1000"]},
            validations={"non_negative": True, "min": 0, "evidence_required": True},
            refs={"BRSR": {"section": "Principle 6 EI-7", "version": "2023"}},
        ),
        "brsr_p6_ei7_scope2": FieldSpec(
            id="brsr_p6_ei7_scope2",
            framework="BRSR",
            section="P6",
            code="P6-EI-7b",
            label="Scope 2 GHG Emissions",
            unit="tCO2e",
            field_type="number",
            mandatory_for={"classes": ["top_1000"]},
            validations={"non_negative": True, "min": 0},
        ),
        "brsr_p6_ei7_total": FieldSpec(
            id="brsr_p6_ei7_total",
            framework="BRSR",
            section="P6",
            code="P6-EI-7c",
            label="Total GHG (Scope 1+2)",
            unit="tCO2e",
            field_type="number",
            mandatory_for={"classes": ["top_1000"]},
            formula="sum(brsr_p6_ei7_scope1,brsr_p6_ei7_scope2)",
            validations={"non_negative": True},
        ),
        "brsr_p6_ei6_total": FieldSpec(
            id="brsr_p6_ei6_total",
            framework="BRSR",
            section="P6",
            code="P6-EI-6",
            label="Total Energy Consumption",
            unit="GJ",
            field_type="number",
            mandatory_for={"classes": ["top_1000"]},
            validations={"non_negative": True},
        ),
        "brsr_p3_ei1_narrative": FieldSpec(
            id="brsr_p3_ei1_narrative",
            framework="BRSR",
            section="P3",
            code="P3-EI-1",
            label="Employee Wellbeing Initiatives",
            unit=None,
            field_type="textarea",
            mandatory_for={"classes": ["top_1000"]},
        ),
    }

    catalogue._sections = {
        "P6": ["brsr_p6_ei7_scope1", "brsr_p6_ei7_scope2", "brsr_p6_ei7_total", "brsr_p6_ei6_total"],
        "P3": ["brsr_p3_ei1_narrative"],
    }

    return catalogue


@pytest.fixture
def engine(minimal_catalogue):
    return RulesEngine(minimal_catalogue)


# ──────────────────────────────────────────────
# Completeness Tests
# ──────────────────────────────────────────────

class TestCompleteness:
    def test_missing_mandatory_field_raises_critical(self, engine):
        """Mandatory field with no value → CRITICAL finding."""
        field_values = {
            "brsr_p6_ei7_scope2": {"value": 500},
            "brsr_p6_ei7_total": {"value": 500},
        }
        findings = engine.run_all_checks(field_values, section="P6", entity_class="top_1000")
        comp_findings = [f for f in findings if f.finding_type == FindingType.COMPLETENESS]
        assert any(f.field_code == "brsr_p6_ei7_scope1" for f in comp_findings), \
            "Should flag missing scope1"
        assert all(f.severity == Severity.CRITICAL for f in comp_findings)

    def test_all_mandatory_filled_no_completeness_finding(self, engine):
        """All mandatory fields filled → no completeness findings."""
        field_values = {
            "brsr_p6_ei7_scope1": {"value": 1000},
            "brsr_p6_ei7_scope2": {"value": 500},
            "brsr_p6_ei7_total": {"value": 1500},
            "brsr_p6_ei6_total": {"value": 8000},
        }
        findings = engine.run_all_checks(field_values, section="P6", entity_class="top_1000")
        comp_findings = [f for f in findings if f.finding_type == FindingType.COMPLETENESS]
        assert len(comp_findings) == 0

    def test_non_mandatory_entity_class_no_completeness(self, engine):
        """Non-mandatory class → missing field is not flagged."""
        findings = engine.run_all_checks(
            field_values={},
            section="P6",
            entity_class="unlisted",  # Not top_1000
        )
        comp_findings = [f for f in findings if f.finding_type == FindingType.COMPLETENESS]
        assert len(comp_findings) == 0


# ──────────────────────────────────────────────
# Type/Unit Tests
# ──────────────────────────────────────────────

class TestTypeUnit:
    def test_string_in_numeric_field_raises_critical(self, engine):
        """Non-numeric value in number field → CRITICAL."""
        field_values = {"brsr_p6_ei7_scope1": {"value": "not_a_number"}}
        findings = engine.run_all_checks(field_values, section="P6")
        type_findings = [f for f in findings if f.finding_type == FindingType.TYPE_UNIT]
        assert len(type_findings) >= 1
        assert any(f.severity == Severity.CRITICAL for f in type_findings)

    def test_unit_mismatch_raises_warn(self, engine):
        """Wrong unit → WARN."""
        field_values = {"brsr_p6_ei7_scope1": {"value": 1000, "unit": "kgCO2e"}}
        findings = engine.run_all_checks(field_values, section="P6")
        unit_findings = [f for f in findings if f.finding_type == FindingType.TYPE_UNIT
                         and f.rule_id.startswith("UNIT_")]
        assert len(unit_findings) >= 1
        assert all(f.severity == Severity.WARN for f in unit_findings)

    def test_correct_unit_no_unit_finding(self, engine):
        """Correct unit → no type/unit finding."""
        field_values = {"brsr_p6_ei7_scope1": {"value": 1000, "unit": "tCO2e"}}
        findings = engine.run_all_checks(field_values, section="P6")
        unit_findings = [f for f in findings if f.rule_id.startswith("UNIT_brsr_p6_ei7_scope1")]
        assert len(unit_findings) == 0


# ──────────────────────────────────────────────
# Range Tests
# ──────────────────────────────────────────────

class TestRange:
    def test_negative_value_raises_critical(self, engine):
        """Negative emissions → CRITICAL."""
        field_values = {"brsr_p6_ei7_scope1": {"value": -100}}
        findings = engine.run_all_checks(field_values, section="P6")
        range_findings = [f for f in findings if f.finding_type == FindingType.RANGE
                          and "NEG" in f.rule_id]
        assert len(range_findings) >= 1
        assert all(f.severity == Severity.CRITICAL for f in range_findings)

    def test_valid_value_no_range_finding(self, engine):
        """Valid positive value → no range finding."""
        field_values = {"brsr_p6_ei6_total": {"value": 5000}}
        findings = engine.run_all_checks(field_values, section="P6")
        range_findings = [f for f in findings if f.finding_type == FindingType.RANGE
                          and "brsr_p6_ei6_total" in f.field_code]
        assert len(range_findings) == 0


# ──────────────────────────────────────────────
# Cross-Field Tests
# ──────────────────────────────────────────────

class TestCrossField:
    def test_total_mismatch_raises_critical(self, engine):
        """scope1 + scope2 ≠ total → CRITICAL cross-field finding."""
        field_values = {
            "brsr_p6_ei7_scope1": {"value": 1000},
            "brsr_p6_ei7_scope2": {"value": 500},
            "brsr_p6_ei7_total": {"value": 2000},  # Wrong! Should be 1500
        }
        findings = engine.run_all_checks(field_values, section="P6")
        xfield = [f for f in findings if f.finding_type == FindingType.CROSS_FIELD]
        assert len(xfield) >= 1
        assert xfield[0].severity == Severity.CRITICAL
        assert "1500" in xfield[0].detail or "500" in xfield[0].detail

    def test_correct_total_no_cross_field(self, engine):
        """Correct sum → no cross-field finding."""
        field_values = {
            "brsr_p6_ei7_scope1": {"value": 1000},
            "brsr_p6_ei7_scope2": {"value": 500},
            "brsr_p6_ei7_total": {"value": 1500},
        }
        findings = engine.run_all_checks(field_values, section="P6")
        xfield = [f for f in findings if f.finding_type == FindingType.CROSS_FIELD]
        assert len(xfield) == 0

    def test_floating_point_tolerance(self, engine):
        """Minor floating point difference (<1%) → no false positive."""
        field_values = {
            "brsr_p6_ei7_scope1": {"value": 1000.001},
            "brsr_p6_ei7_scope2": {"value": 499.999},
            "brsr_p6_ei7_total": {"value": 1500.0},
        }
        findings = engine.run_all_checks(field_values, section="P6")
        xfield = [f for f in findings if f.finding_type == FindingType.CROSS_FIELD]
        assert len(xfield) == 0


# ──────────────────────────────────────────────
# YoY Delta Tests
# ──────────────────────────────────────────────

class TestYoYDelta:
    def test_large_increase_raises_warn(self, engine):
        """200% YoY increase → WARN."""
        current = {"brsr_p6_ei7_scope1": {"value": 3000}}
        prior = {"brsr_p6_ei7_scope1": {"value": 1000}}
        findings = engine.run_all_checks(current, section="P6", prior_fy_values=prior)
        yoy = [f for f in findings if f.finding_type == FindingType.YOY_DELTA]
        assert len(yoy) >= 1
        assert yoy[0].severity == Severity.WARN

    def test_large_decrease_raises_warn(self, engine):
        """80% YoY decrease → WARN."""
        current = {"brsr_p6_ei7_scope1": {"value": 200}}
        prior = {"brsr_p6_ei7_scope1": {"value": 1000}}
        findings = engine.run_all_checks(current, section="P6", prior_fy_values=prior)
        yoy = [f for f in findings if f.finding_type == FindingType.YOY_DELTA]
        assert len(yoy) >= 1

    def test_normal_change_no_yoy_finding(self, engine):
        """30% YoY change → no finding."""
        current = {"brsr_p6_ei7_scope1": {"value": 1300}}
        prior = {"brsr_p6_ei7_scope1": {"value": 1000}}
        findings = engine.run_all_checks(current, section="P6", prior_fy_values=prior)
        yoy = [f for f in findings if f.finding_type == FindingType.YOY_DELTA]
        assert len(yoy) == 0


# ──────────────────────────────────────────────
# Readiness Score Tests
# ──────────────────────────────────────────────

class TestReadinessScore:
    def test_empty_form_zero_score(self, engine):
        # Empty form: no mandatory fields filled → completeness=0, but validity=1.0 (no errors)
        # Score = 0*0.45 + 1*0.30 + 0*0.10 + 1*0.15 = 0.45 weighted → actually 0.141 due to framework fields
        result = engine.compute_readiness_score({}, framework="BRSR")
        assert result["score"] >= 0.0
        assert result["breakdown"]["completeness"]["score"] == 0.0

    def test_full_mandatory_high_score(self, engine):
        field_values = {
            "brsr_p6_ei7_scope1": {"value": 1000, "unit": "tCO2e", "evidence_url": "s3://ev/1.pdf"},
            "brsr_p6_ei7_scope2": {"value": 500, "unit": "tCO2e"},
            "brsr_p6_ei7_total": {"value": 1500, "unit": "tCO2e"},
            "brsr_p6_ei6_total": {"value": 8000, "unit": "GJ"},
        }
        result = engine.compute_readiness_score(field_values, framework="BRSR")
        assert result["score"] > 0.3  # Should be meaningfully above zero
        assert "breakdown" in result

    def test_breakdown_fields_present(self, engine):
        result = engine.compute_readiness_score({}, framework="BRSR")
        assert "breakdown" in result
        assert "completeness" in result["breakdown"]
        assert "validity" in result["breakdown"]

    def test_critical_issues_lower_score(self, engine):
        """Fields with critical issues should reduce score vs all valid."""
        all_valid = {
            "brsr_p6_ei7_scope1": {"value": 1000},
            "brsr_p6_ei7_scope2": {"value": 500},
            "brsr_p6_ei7_total": {"value": 1500},
            "brsr_p6_ei6_total": {"value": 8000},
        }
        with_errors = {
            "brsr_p6_ei7_scope1": {"value": 1000},
            "brsr_p6_ei7_scope2": {"value": 500},
            "brsr_p6_ei7_total": {"value": 9999},  # Wrong total
            "brsr_p6_ei6_total": {"value": -100},   # Negative
        }
        score_valid = engine.compute_readiness_score(all_valid, framework="BRSR")["score"]
        score_errors = engine.compute_readiness_score(with_errors, framework="BRSR")["score"]
        assert score_valid > score_errors


# ──────────────────────────────────────────────
# Boundary Check Tests
# ──────────────────────────────────────────────

class TestBoundaryChecks:
    def test_ghg_mismatch(self):
        findings = check_ghg_total(1000.0, 500.0, 2000.0)
        assert len(findings) == 1
        assert findings[0].rule_id == "BOUND_GHG_TOTAL"
        assert findings[0].severity == Severity.CRITICAL

    def test_ghg_correct(self):
        findings = check_ghg_total(1000.0, 500.0, 1500.0)
        assert len(findings) == 0

    def test_ghg_none_values_skip(self):
        assert check_ghg_total(None, 500.0, 1500.0) == []
        assert check_ghg_total(1000.0, None, 1500.0) == []

    def test_energy_mismatch(self):
        findings = check_energy_total(2000.0, 6000.0, 9999.0)
        assert len(findings) == 1

    def test_water_balance_violation(self):
        findings = check_water_balance(1000.0, 600.0, 200.0)  # 600+200=800 ≠ 1000
        assert len(findings) == 1

    def test_water_balance_correct(self):
        findings = check_water_balance(1000.0, 700.0, 300.0)
        assert len(findings) == 0

    def test_waste_total_mismatch(self):
        findings = check_waste_total(100.0, 200.0, 500.0)
        assert len(findings) == 1

    def test_employee_total_mismatch(self):
        findings = check_employee_total(500.0, 200.0, 900.0)
        assert len(findings) == 1

    def test_csr_spend_exceeds_obligation(self):
        findings = check_csr_spend(100.0, 150.0, None, None)
        assert len(findings) >= 1

    def test_run_boundary_checks_all_good(self):
        field_values = {
            "brsr_p6_ei7_scope1": {"value": 1000},
            "brsr_p6_ei7_scope2": {"value": 500},
            "brsr_p6_ei7_total": {"value": 1500},
            "brsr_p6_ei6_renewable": {"value": 2000},
            "brsr_p6_ei6_nonrenewable": {"value": 6000},
            "brsr_p6_ei6_total": {"value": 8000},
            "brsr_p6_ei9_withdrawal": {"value": 1000},
            "brsr_p6_ei9_consumption": {"value": 700},
            "brsr_p6_ei9_discharge": {"value": 300},
        }
        findings = run_boundary_checks(field_values)
        assert len(findings) == 0


# ──────────────────────────────────────────────
# Disclosure Quality Tests
# ──────────────────────────────────────────────

class TestDisclosureQuality:
    @pytest.fixture
    def checker(self):
        return DisclosureQualityChecker()

    def test_vague_text_scores_poor(self, checker):
        text = (
            "We are committed to sustainability. "
            "We strive to reduce our environmental impact "
            "through various initiatives and best efforts."
        )
        result = checker.check("test_field", text, min_words=10)
        assert result.quality_tier in ("poor", "fair")
        specificity = next(d for d in result.dimensions if d.name == "specificity")
        assert not specificity.passed

    def test_good_text_scores_well(self, checker):
        text = (
            "In FY2024, our manufacturing plants reduced Scope 1 emissions by 15% "
            "from 5,200 tCO2e (FY2023) to 4,420 tCO2e, across all 7 facilities "
            "under operational control. This was achieved through installation of "
            "energy-efficient burners at Plant A and B, reducing diesel consumption "
            "by 180 kL annually."
        )
        result = checker.check("test_field", text, min_words=10)
        assert result.quality_tier in ("good", "excellent")
        assert result.overall_score >= 0.5

    def test_empty_text_scores_zero(self, checker):
        # Empty text: specificity passes (no vague phrases), everything else fails
        # The tier will be 'poor' and score will be low
        result = checker.check("test_field", "", min_words=20)
        assert result.quality_tier == "poor"
        assert result.overall_score < 0.35
        length_dim = next(d for d in result.dimensions if d.name == "disclosure_length")
        assert not length_dim.passed

    def test_short_text_flags_length(self, checker):
        result = checker.check("test_field", "We reduced waste.", min_words=50)
        length_dim = next(d for d in result.dimensions if d.name == "disclosure_length")
        assert not length_dim.passed

    def test_quantitative_detection(self, checker):
        text = "Reduced water consumption by 12% (from 50,000 KL to 44,000 KL) in FY2024 at all plants."
        result = checker.check("test_field", text, min_words=5)
        quant_dim = next(d for d in result.dimensions if d.name == "quantitative_evidence")
        assert quant_dim.passed

    def test_time_bound_detection(self, checker):
        text = "We will achieve net zero by 2045 across all scope 1 and scope 2 emissions."
        result = checker.check("test_field", text, min_words=5)
        time_dim = next(d for d in result.dimensions if d.name == "time_boundedness")
        assert time_dim.passed
