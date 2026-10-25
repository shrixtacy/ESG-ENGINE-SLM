"""
ESGPilot — Boundary Consistency Checks.

Validates that reported values are internally consistent across:
  - Scope boundaries (Scope 1 + Scope 2 = total GHG)
  - Energy balances (total = renewable + non-renewable)
  - Water balance (withdrawal = consumption + discharge)
  - Waste balance (total = sum of disposal methods)
  - Employee boundary (permanent + contractual = total)
  - CSR boundary (spent ≤ obligation; spent + unspent = total)

These are cross-field arithmetic checks on the deterministic engine.
All findings include the exact delta so the SLM can explain them.
"""

from dataclasses import dataclass, field
from typing import Optional

from rules.engine import Finding, FindingType, Severity


@dataclass
class BoundaryCheckResult:
    """Result of a boundary consistency check."""
    check_id: str
    passed: bool
    finding: Optional[Finding] = None


TOLERANCE = 0.01  # 1% relative tolerance for floating point


def _pct_diff(reported: float, expected: float) -> float:
    """Percent difference relative to expected."""
    if expected == 0:
        return abs(reported) * 100
    return abs((reported - expected) / expected) * 100


def _make_finding(
    rule_id: str,
    field_code: str,
    title: str,
    detail: str,
    reported: float,
    expected: float,
    severity: Severity = Severity.CRITICAL,
    refs: Optional[list[dict]] = None,
) -> Finding:
    return Finding(
        rule_id=rule_id,
        finding_type=FindingType.BOUNDARY,
        severity=severity,
        field_code=field_code,
        title=title,
        detail=detail,
        expected=f"{expected:.4f}",
        actual=f"{reported:.4f}",
        references=refs or [],
    )


# ──────────────────────────────────────────────
# GHG Boundary
# ──────────────────────────────────────────────

def check_ghg_total(
    scope1: Optional[float],
    scope2: Optional[float],
    reported_total: Optional[float],
) -> list[Finding]:
    """
    Verify: scope1 + scope2 = total GHG (Scope 1+2)
    BRSR P6 Essential Indicator 7.
    """
    findings = []
    if scope1 is None or scope2 is None or reported_total is None:
        return findings

    expected = scope1 + scope2
    pct = _pct_diff(reported_total, expected)

    if pct > TOLERANCE * 100:
        findings.append(_make_finding(
            rule_id="BOUND_GHG_TOTAL",
            field_code="brsr_p6_ei7_total",
            title="Total GHG (Scope 1+2) does not match sum of components",
            detail=(
                f"Scope 1 ({scope1} tCO2e) + Scope 2 ({scope2} tCO2e) = "
                f"{expected:.4f} tCO2e, but reported total is {reported_total} tCO2e "
                f"(difference: {reported_total - expected:+.4f} tCO2e, {pct:.1f}%). "
                "Check that units are consistent (all in tCO2e) and that "
                "market-based vs location-based Scope 2 are not mixed."
            ),
            reported=reported_total,
            expected=expected,
            refs=[{"doc": "BRSR Annexure I", "section": "Principle 6 EI-7", "version": "2023"}],
        ))

    return findings


# ──────────────────────────────────────────────
# Energy Boundary
# ──────────────────────────────────────────────

def check_energy_total(
    renewable: Optional[float],
    non_renewable: Optional[float],
    reported_total: Optional[float],
) -> list[Finding]:
    """
    Verify: renewable + non-renewable = total energy
    BRSR P6 Essential Indicator 6.
    """
    findings = []
    if renewable is None or non_renewable is None or reported_total is None:
        return findings

    expected = renewable + non_renewable
    pct = _pct_diff(reported_total, expected)

    if pct > TOLERANCE * 100:
        findings.append(_make_finding(
            rule_id="BOUND_ENERGY_TOTAL",
            field_code="brsr_p6_ei6_total",
            title="Total energy does not match renewable + non-renewable",
            detail=(
                f"Renewable ({renewable} GJ) + Non-renewable ({non_renewable} GJ) = "
                f"{expected:.2f} GJ, but reported total is {reported_total} GJ "
                f"(difference: {reported_total - expected:+.2f} GJ, {pct:.1f}%). "
                "Verify that all energy sources are accounted for in both categories."
            ),
            reported=reported_total,
            expected=expected,
            refs=[{"doc": "BRSR Annexure I", "section": "Principle 6 EI-6", "version": "2023"}],
        ))

    return findings


def check_renewable_share(
    renewable: Optional[float],
    total: Optional[float],
    reported_share_pct: Optional[float],
) -> list[Finding]:
    """Verify reported renewable energy share % matches actual calculation."""
    findings = []
    if renewable is None or total is None or reported_share_pct is None:
        return findings
    if total == 0:
        return findings

    expected_pct = (renewable / total) * 100
    diff = abs(reported_share_pct - expected_pct)

    if diff > 1.0:  # 1 percentage point tolerance
        findings.append(_make_finding(
            rule_id="BOUND_RENEW_SHARE",
            field_code="brsr_p6_ei6_renewable_pct",
            title="Renewable energy % does not match reported values",
            detail=(
                f"Calculated renewable share: {expected_pct:.1f}% "
                f"({renewable} GJ / {total} GJ), "
                f"but reported as {reported_share_pct:.1f}% "
                f"(difference: {diff:.1f} percentage points)."
            ),
            reported=reported_share_pct,
            expected=expected_pct,
            severity=Severity.WARN,
        ))

    return findings


# ──────────────────────────────────────────────
# Water Boundary
# ──────────────────────────────────────────────

def check_water_balance(
    withdrawal: Optional[float],
    consumption: Optional[float],
    discharge: Optional[float],
) -> list[Finding]:
    """
    Verify: withdrawal = consumption + discharge (water mass balance)
    BRSR P6 Essential Indicator 9.
    """
    findings = []
    if withdrawal is None or consumption is None or discharge is None:
        return findings

    expected_withdrawal = consumption + discharge
    pct = _pct_diff(withdrawal, expected_withdrawal)

    if pct > TOLERANCE * 100:
        findings.append(_make_finding(
            rule_id="BOUND_WATER_BALANCE",
            field_code="brsr_p6_ei9_withdrawal",
            title="Water balance violated: withdrawal ≠ consumption + discharge",
            detail=(
                f"Water consumption ({consumption} KL) + discharge ({discharge} KL) = "
                f"{expected_withdrawal:.2f} KL, but reported withdrawal is {withdrawal} KL "
                f"(difference: {withdrawal - expected_withdrawal:+.2f} KL, {pct:.1f}%). "
                "Common causes: third-party water / tanker supply not captured, "
                "recycled water double-counted, or units mismatch (KL vs m³)."
            ),
            reported=withdrawal,
            expected=expected_withdrawal,
            refs=[{"doc": "BRSR Annexure I", "section": "Principle 6 EI-9", "version": "2023"}],
        ))

    return findings


def check_water_stress_areas(
    total_withdrawal: Optional[float],
    stress_area_withdrawal: Optional[float],
) -> list[Finding]:
    """Verify stress-area withdrawal ≤ total withdrawal."""
    findings = []
    if total_withdrawal is None or stress_area_withdrawal is None:
        return findings

    if stress_area_withdrawal > total_withdrawal * 1.01:
        findings.append(_make_finding(
            rule_id="BOUND_WATER_STRESS",
            field_code="brsr_p6_ei9_stress",
            title="Water withdrawal from stress areas exceeds total withdrawal",
            detail=(
                f"Stress-area withdrawal ({stress_area_withdrawal} KL) > "
                f"total withdrawal ({total_withdrawal} KL). "
                "The stress-area subset cannot exceed the total."
            ),
            reported=stress_area_withdrawal,
            expected=total_withdrawal,
            severity=Severity.CRITICAL,
        ))

    return findings


# ──────────────────────────────────────────────
# Waste Boundary
# ──────────────────────────────────────────────

def check_waste_total(
    hazardous: Optional[float],
    non_hazardous: Optional[float],
    reported_total: Optional[float],
) -> list[Finding]:
    """Verify total waste = hazardous + non-hazardous."""
    findings = []
    if hazardous is None or non_hazardous is None or reported_total is None:
        return findings

    expected = hazardous + non_hazardous
    pct = _pct_diff(reported_total, expected)

    if pct > TOLERANCE * 100:
        findings.append(_make_finding(
            rule_id="BOUND_WASTE_TOTAL",
            field_code="brsr_p6_ei10_total",
            title="Total waste does not match hazardous + non-hazardous sum",
            detail=(
                f"Hazardous ({hazardous} MT) + Non-hazardous ({non_hazardous} MT) = "
                f"{expected:.2f} MT, but reported total is {reported_total} MT "
                f"(difference: {reported_total - expected:+.2f} MT, {pct:.1f}%)."
            ),
            reported=reported_total,
            expected=expected,
            refs=[{"doc": "BRSR Annexure I", "section": "Principle 6 EI-10", "version": "2023"}],
        ))

    return findings


def check_waste_disposal(
    generated: Optional[float],
    recycled: Optional[float],
    landfill: Optional[float],
    incinerated: Optional[float],
    other: Optional[float],
) -> list[Finding]:
    """Verify: generated = recycled + landfill + incinerated + other disposal."""
    findings = []
    vals = [recycled, landfill, incinerated, other]
    if generated is None or any(v is None for v in vals):
        return findings

    disposal_total = sum(v for v in vals if v is not None)
    pct = _pct_diff(generated, disposal_total)

    if pct > TOLERANCE * 100:
        findings.append(_make_finding(
            rule_id="BOUND_WASTE_DISPOSAL",
            field_code="brsr_p6_ei10_disposal",
            title="Waste generated does not match sum of disposal methods",
            detail=(
                f"Recycled + Landfill + Incinerated + Other = {disposal_total:.2f} MT, "
                f"but waste generated = {generated} MT "
                f"(difference: {generated - disposal_total:+.2f} MT, {pct:.1f}%). "
                "All generated waste must be accounted for across disposal pathways."
            ),
            reported=generated,
            expected=disposal_total,
            refs=[{"doc": "BRSR Annexure I", "section": "Principle 6 EI-10", "version": "2023"}],
        ))

    return findings


# ──────────────────────────────────────────────
# Employee Boundary
# ──────────────────────────────────────────────

def check_employee_total(
    permanent: Optional[float],
    contractual: Optional[float],
    reported_total: Optional[float],
) -> list[Finding]:
    """Verify total employees = permanent + contractual (for gender-disaggregated too)."""
    findings = []
    if permanent is None or contractual is None or reported_total is None:
        return findings

    expected = permanent + contractual
    pct = _pct_diff(reported_total, expected)

    if pct > TOLERANCE * 100:
        findings.append(_make_finding(
            rule_id="BOUND_EMP_TOTAL",
            field_code="brsr_p3_ei1_total",
            title="Total employees does not match permanent + contractual/other",
            detail=(
                f"Permanent ({int(permanent)}) + Contractual ({int(contractual)}) = "
                f"{int(expected)}, but reported total = {int(reported_total)} "
                f"(difference: {int(reported_total - expected):+d})."
            ),
            reported=reported_total,
            expected=expected,
            refs=[{"doc": "BRSR Annexure I", "section": "Principle 3 EI-1", "version": "2023"}],
        ))

    return findings


def check_gender_disaggregation(
    male: Optional[float],
    female: Optional[float],
    other_gender: Optional[float],
    reported_total: Optional[float],
) -> list[Finding]:
    """Verify gender-disaggregated sum = total."""
    findings = []
    if male is None or female is None or reported_total is None:
        return findings

    expected = male + female + (other_gender or 0)
    pct = _pct_diff(reported_total, expected)

    if pct > TOLERANCE * 100:
        findings.append(_make_finding(
            rule_id="BOUND_GENDER_SUM",
            field_code="brsr_p3_ei1_gender",
            title="Gender-disaggregated counts do not sum to reported total",
            detail=(
                f"Male ({int(male)}) + Female ({int(female)}) "
                + (f"+ Other ({int(other_gender)}) " if other_gender else "")
                + f"= {int(expected)}, but reported total = {int(reported_total)}."
            ),
            reported=reported_total,
            expected=expected,
            refs=[{"doc": "BRSR Annexure I", "section": "Principle 3", "version": "2023"}],
        ))

    return findings


# ──────────────────────────────────────────────
# CSR Boundary
# ──────────────────────────────────────────────

def check_csr_spend(
    obligation: Optional[float],
    spent: Optional[float],
    unspent: Optional[float],
    carried_forward: Optional[float],
) -> list[Finding]:
    """
    CSR checks:
    1. spent + unspent ≈ obligation
    2. spent ≤ obligation
    BRSR Section B — CSR disclosures / Companies Act s.135.
    """
    findings = []

    if obligation is not None and spent is not None:
        if spent > obligation * 1.01:
            # Allow small overruns but flag > 1%
            findings.append(_make_finding(
                rule_id="BOUND_CSR_OVERSPEND",
                field_code="brsr_secb_csr_spent",
                title="CSR spend exceeds statutory obligation",
                detail=(
                    f"Reported CSR spend (₹{spent:.2f} cr) exceeds "
                    f"2% obligation (₹{obligation:.2f} cr). "
                    "Confirm whether this includes carry-forward from prior years."
                ),
                reported=spent,
                expected=obligation,
                severity=Severity.WARN,
            ))

        if unspent is not None:
            expected_total = spent + unspent
            pct = _pct_diff(obligation, expected_total)
            if pct > 2.0:  # 2% tolerance
                findings.append(_make_finding(
                    rule_id="BOUND_CSR_BALANCE",
                    field_code="brsr_secb_csr_unspent",
                    title="CSR spent + unspent does not equal obligation",
                    detail=(
                        f"Spent (₹{spent:.2f} cr) + Unspent (₹{unspent:.2f} cr) = "
                        f"₹{expected_total:.2f} cr, but obligation = ₹{obligation:.2f} cr "
                        f"(difference: ₹{obligation - expected_total:+.2f} cr)."
                    ),
                    reported=expected_total,
                    expected=obligation,
                    severity=Severity.WARN,
                    refs=[{"doc": "Companies Act 2013", "section": "Section 135", "version": "2013"}],
                ))

    return findings


# ──────────────────────────────────────────────
# Dispatcher
# ──────────────────────────────────────────────

def run_boundary_checks(field_values: dict) -> list[Finding]:
    """
    Run all boundary checks given a flat field_values dict.
    Keys are field codes, values are dicts with 'value' key.

    This is the main entry point called by the RulesEngine.
    """
    def _get(code: str) -> Optional[float]:
        fv = field_values.get(code, {})
        val = fv.get("value")
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    findings = []

    # GHG
    findings += check_ghg_total(
        _get("brsr_p6_ei7_scope1"),
        _get("brsr_p6_ei7_scope2"),
        _get("brsr_p6_ei7_total"),
    )

    # Energy
    findings += check_energy_total(
        _get("brsr_p6_ei6_renewable"),
        _get("brsr_p6_ei6_nonrenewable"),
        _get("brsr_p6_ei6_total"),
    )
    findings += check_renewable_share(
        _get("brsr_p6_ei6_renewable"),
        _get("brsr_p6_ei6_total"),
        _get("brsr_p6_ei6_renewable_pct"),
    )

    # Water
    findings += check_water_balance(
        _get("brsr_p6_ei9_withdrawal"),
        _get("brsr_p6_ei9_consumption"),
        _get("brsr_p6_ei9_discharge"),
    )
    findings += check_water_stress_areas(
        _get("brsr_p6_ei9_withdrawal"),
        _get("brsr_p6_ei9_stress_withdrawal"),
    )

    # Waste
    findings += check_waste_total(
        _get("brsr_p6_ei10_hazardous"),
        _get("brsr_p6_ei10_nonhazardous"),
        _get("brsr_p6_ei10_total"),
    )
    findings += check_waste_disposal(
        _get("brsr_p6_ei10_total"),
        _get("brsr_p6_ei10_recycled"),
        _get("brsr_p6_ei10_landfill"),
        _get("brsr_p6_ei10_incinerated"),
        _get("brsr_p6_ei10_other_disposal"),
    )

    # Employees
    findings += check_employee_total(
        _get("brsr_p3_ei1_permanent"),
        _get("brsr_p3_ei1_contractual"),
        _get("brsr_p3_ei1_total"),
    )
    findings += check_gender_disaggregation(
        _get("brsr_p3_ei1_male"),
        _get("brsr_p3_ei1_female"),
        _get("brsr_p3_ei1_other_gender"),
        _get("brsr_p3_ei1_total"),
    )

    # CSR
    findings += check_csr_spend(
        _get("brsr_secb_csr_obligation"),
        _get("brsr_secb_csr_spent"),
        _get("brsr_secb_csr_unspent"),
        _get("brsr_secb_csr_carried"),
    )

    return findings
