"""
ESGPilot — Rules Engine Core.

The rules engine is the deterministic backbone of ESGPilot.
It performs ALL numeric computations, validations, and scoring.
The SLM never calculates — it only explains rule outputs.

Check types (per BUILD_SPEC §FR-4):
  - Completeness (mandatory fields filled)
  - Type/unit validation
  - Range checks (plausibility)
  - Cross-field arithmetic (total = Σ parts)
  - YoY delta (unusual changes)
  - Intensity plausibility
  - Boundary consistency
  - Evidence-attached (source + evidence for critical fields)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import yaml
import os


class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    CRITICAL = "critical"


class FindingType(str, Enum):
    COMPLETENESS = "completeness"
    TYPE_UNIT = "type_unit"
    RANGE = "range"
    CROSS_FIELD = "cross_field"
    YOY_DELTA = "yoy_delta"
    INTENSITY = "intensity"
    BOUNDARY = "boundary"
    EVIDENCE = "evidence"
    DISCLOSURE_QUALITY = "disclosure_quality"


@dataclass
class Finding:
    """A single rule finding / issue."""
    rule_id: str
    finding_type: FindingType
    severity: Severity
    field_code: str
    title: str
    detail: str
    expected: Optional[str] = None
    actual: Optional[str] = None
    references: list[dict] = field(default_factory=list)
    sdg_tags: list[str] = field(default_factory=list)
    auto_fixable: bool = False
    suggested_value: Optional[str] = None


@dataclass
class FieldSpec:
    """Machine-readable specification for a single field."""
    id: str
    framework: str
    section: str
    code: str
    label: str
    unit: Optional[str] = None
    field_type: str = "number"
    mandatory_for: dict = field(default_factory=dict)
    formula: Optional[str] = None
    validations: dict = field(default_factory=dict)
    refs: dict = field(default_factory=dict)
    version: str = "2024"


class FieldCatalogue:
    """
    Loads and manages the BRSR field catalogue.
    The catalogue is the most important artifact — drives
    rules, form mapping, and retrieval filters.
    """

    def __init__(self, catalogue_path: Optional[str] = None):
        self.fields: dict[str, FieldSpec] = {}
        self._sections: dict[str, list[str]] = {}
        if catalogue_path:
            self.load(catalogue_path)

    def load(self, path: str):
        """Load field catalogue from YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        for field_data in data.get("fields", []):
            import dataclasses
            known = {f.name for f in dataclasses.fields(FieldSpec)}
            filtered = {k: v for k, v in field_data.items() if k in known}
            spec = FieldSpec(**filtered)
            self.fields[spec.id] = spec
            section = spec.section
            if section not in self._sections:
                self._sections[section] = []
            self._sections[section].append(spec.id)

    def get_field(self, field_id: str) -> Optional[FieldSpec]:
        return self.fields.get(field_id)

    def get_section_fields(self, section: str) -> list[FieldSpec]:
        field_ids = self._sections.get(section, [])
        return [self.fields[fid] for fid in field_ids if fid in self.fields]

    def get_mandatory_fields(self, entity_class: str = "top_1000") -> list[FieldSpec]:
        """Return fields mandatory for a given entity class."""
        results = []
        for spec in self.fields.values():
            if entity_class in spec.mandatory_for.get("classes", []):
                results.append(spec)
        return results

    def get_all_sections(self) -> list[str]:
        return list(self._sections.keys())

    def get_framework_fields(self, framework: str) -> list[FieldSpec]:
        return [f for f in self.fields.values() if f.framework == framework]


class RulesEngine:
    """
    Deterministic rules engine.
    Runs checks on field values and returns findings.
    Pure Python, no LLM dependency — reusable by batch jobs.
    """

    def __init__(self, catalogue: FieldCatalogue):
        self.catalogue = catalogue

    def run_all_checks(
        self,
        field_values: dict[str, dict],
        section: Optional[str] = None,
        entity_class: str = "top_1000",
        prior_fy_values: Optional[dict[str, dict]] = None,
        peer_values: Optional[list[dict[str, dict]]] = None,
    ) -> list[Finding]:
        """
        Run all checks on a set of field values.

        Args:
            field_values: {field_code: {"value": ..., "unit": ..., "source_type": ...}}
            section: If set, only check fields in this section
            entity_class: Entity classification for mandatory rules
            prior_fy_values: Previous FY values for YoY checks
            peer_values: List of peer field values for outlier detection
        """
        findings = []
        fields_to_check = (
            self.catalogue.get_section_fields(section)
            if section
            else list(self.catalogue.fields.values())
        )

        for spec in fields_to_check:
            fv = field_values.get(spec.id, {})

            # 1. Completeness
            findings.extend(self._check_completeness(spec, fv, entity_class))

            # 2. Type/Unit
            if fv.get("value") is not None:
                findings.extend(self._check_type_unit(spec, fv))

            # 3. Range
            if fv.get("value") is not None:
                findings.extend(self._check_range(spec, fv))

            # 4. Evidence
            findings.extend(self._check_evidence(spec, fv))

        # 5. Cross-field checks (need all values)
        findings.extend(self._check_cross_field(field_values, fields_to_check))

        # 6. YoY delta
        if prior_fy_values:
            findings.extend(self._check_yoy_delta(field_values, prior_fy_values, fields_to_check))

        # 7. Outlier detection (vs peers)
        if peer_values and len(peer_values) >= 5:
            findings.extend(self._check_outliers(field_values, peer_values, fields_to_check))

        return findings

    def _check_completeness(
        self, spec: FieldSpec, fv: dict, entity_class: str
    ) -> list[Finding]:
        """Check if mandatory fields are filled."""
        findings = []
        is_mandatory = entity_class in spec.mandatory_for.get("classes", [])

        if is_mandatory and not fv.get("value"):
            findings.append(Finding(
                rule_id=f"COMP_{spec.id}",
                finding_type=FindingType.COMPLETENESS,
                severity=Severity.CRITICAL,
                field_code=spec.id,
                title=f"Mandatory field not filled: {spec.label}",
                detail=(
                    f"Field '{spec.code}' ({spec.label}) is mandatory for "
                    f"{entity_class} entities under {spec.framework} but has no value."
                ),
                references=self._refs_to_list(spec.refs),
            ))
        return findings

    def _check_type_unit(self, spec: FieldSpec, fv: dict) -> list[Finding]:
        """Validate value type and unit match the spec."""
        findings = []
        value = fv.get("value")
        unit = fv.get("unit")

        # Type check
        if spec.field_type == "number":
            try:
                float(value)
            except (ValueError, TypeError):
                findings.append(Finding(
                    rule_id=f"TYPE_{spec.id}",
                    finding_type=FindingType.TYPE_UNIT,
                    severity=Severity.CRITICAL,
                    field_code=spec.id,
                    title=f"Non-numeric value in numeric field: {spec.label}",
                    detail=f"Expected a number but got '{value}'.",
                    expected=f"Numeric value in {spec.unit or 'appropriate unit'}",
                    actual=str(value),
                ))

        # Unit check
        if spec.unit and unit and unit.lower() != spec.unit.lower():
            findings.append(Finding(
                rule_id=f"UNIT_{spec.id}",
                finding_type=FindingType.TYPE_UNIT,
                severity=Severity.WARN,
                field_code=spec.id,
                title=f"Unit mismatch: {spec.label}",
                detail=f"Expected unit '{spec.unit}' but got '{unit}'.",
                expected=spec.unit,
                actual=unit,
            ))

        return findings

    def _check_range(self, spec: FieldSpec, fv: dict) -> list[Finding]:
        """Check if value falls within plausible range."""
        findings = []
        validations = spec.validations or {}
        value = fv.get("value")

        if value is None:
            return findings

        try:
            num_value = float(value)
        except (ValueError, TypeError):
            return findings

        min_val = validations.get("min")
        max_val = validations.get("max")

        if min_val is not None and num_value < float(min_val):
            findings.append(Finding(
                rule_id=f"RANGE_MIN_{spec.id}",
                finding_type=FindingType.RANGE,
                severity=Severity.WARN,
                field_code=spec.id,
                title=f"Value below expected minimum: {spec.label}",
                detail=f"Value {num_value} is below minimum {min_val}.",
                expected=f">= {min_val}",
                actual=str(num_value),
            ))

        if max_val is not None and num_value > float(max_val):
            findings.append(Finding(
                rule_id=f"RANGE_MAX_{spec.id}",
                finding_type=FindingType.RANGE,
                severity=Severity.WARN,
                field_code=spec.id,
                title=f"Value above expected maximum: {spec.label}",
                detail=f"Value {num_value} is above maximum {max_val}.",
                expected=f"<= {max_val}",
                actual=str(num_value),
            ))

        # Non-negative check for emissions, energy, waste, water
        if validations.get("non_negative", False) and num_value < 0:
            findings.append(Finding(
                rule_id=f"RANGE_NEG_{spec.id}",
                finding_type=FindingType.RANGE,
                severity=Severity.CRITICAL,
                field_code=spec.id,
                title=f"Negative value not allowed: {spec.label}",
                detail=f"Value {num_value} cannot be negative for this field.",
                expected=">= 0",
                actual=str(num_value),
            ))

        return findings

    def _check_evidence(self, spec: FieldSpec, fv: dict) -> list[Finding]:
        """Check if critical fields have evidence attached."""
        findings = []
        validations = spec.validations or {}

        if validations.get("evidence_required", False):
            if not fv.get("evidence_url") and not fv.get("source_type"):
                findings.append(Finding(
                    rule_id=f"EVID_{spec.id}",
                    finding_type=FindingType.EVIDENCE,
                    severity=Severity.WARN,
                    field_code=spec.id,
                    title=f"Evidence missing: {spec.label}",
                    detail=(
                        f"Field '{spec.code}' requires source evidence "
                        f"(meter reading, bill, calculation basis). "
                        f"Please attach evidence or specify source type."
                    ),
                ))
        return findings

    def _check_cross_field(
        self, field_values: dict[str, dict], specs: list[FieldSpec]
    ) -> list[Finding]:
        """Check cross-field arithmetic (total = sum of parts)."""
        findings = []

        for spec in specs:
            formula = spec.formula
            if not formula:
                continue

            # Parse simple sum formulas like "sum(field_a, field_b, field_c)"
            if formula.startswith("sum(") and formula.endswith(")"):
                parts = formula[4:-1].split(",")
                parts = [p.strip() for p in parts]

                total_val = field_values.get(spec.id, {}).get("value")
                if total_val is None:
                    continue

                try:
                    total = float(total_val)
                except (ValueError, TypeError):
                    continue

                part_sum = 0.0
                all_parts_present = True
                for part_id in parts:
                    part_val = field_values.get(part_id, {}).get("value")
                    if part_val is None:
                        all_parts_present = False
                        break
                    try:
                        part_sum += float(part_val)
                    except (ValueError, TypeError):
                        all_parts_present = False
                        break

                if all_parts_present and abs(total - part_sum) > 0.01 * max(abs(total), 1):
                    findings.append(Finding(
                        rule_id=f"XFIELD_{spec.id}",
                        finding_type=FindingType.CROSS_FIELD,
                        severity=Severity.CRITICAL,
                        field_code=spec.id,
                        title=f"Total does not match sum of parts: {spec.label}",
                        detail=(
                            f"Reported total is {total} but sum of components "
                            f"({', '.join(parts)}) is {part_sum}. "
                            f"Difference: {abs(total - part_sum):.2f}."
                        ),
                        expected=str(part_sum),
                        actual=str(total),
                    ))

        return findings

    def _check_yoy_delta(
        self,
        current: dict[str, dict],
        prior: dict[str, dict],
        specs: list[FieldSpec],
    ) -> list[Finding]:
        """Flag unusual year-over-year changes (>100% increase or >50% decrease)."""
        findings = []

        for spec in specs:
            if spec.field_type != "number":
                continue

            curr_val = current.get(spec.id, {}).get("value")
            prev_val = prior.get(spec.id, {}).get("value")

            if curr_val is None or prev_val is None:
                continue

            try:
                curr = float(curr_val)
                prev = float(prev_val)
            except (ValueError, TypeError):
                continue

            if prev == 0:
                if curr > 0:
                    findings.append(Finding(
                        rule_id=f"YOY_{spec.id}",
                        finding_type=FindingType.YOY_DELTA,
                        severity=Severity.WARN,
                        field_code=spec.id,
                        title=f"New non-zero value (was zero last FY): {spec.label}",
                        detail=f"Was 0 last FY, now {curr}. Please verify.",
                    ))
                continue

            pct_change = ((curr - prev) / abs(prev)) * 100

            # Configurable thresholds — could be per-field in validations
            increase_threshold = spec.validations.get("yoy_increase_threshold", 100)
            decrease_threshold = spec.validations.get("yoy_decrease_threshold", -50)

            if pct_change > increase_threshold:
                findings.append(Finding(
                    rule_id=f"YOY_UP_{spec.id}",
                    finding_type=FindingType.YOY_DELTA,
                    severity=Severity.WARN,
                    field_code=spec.id,
                    title=f"Large YoY increase ({pct_change:.0f}%): {spec.label}",
                    detail=(
                        f"Value changed from {prev} to {curr} "
                        f"({pct_change:+.1f}%). This exceeds the {increase_threshold}% threshold. "
                        f"Please verify this is correct."
                    ),
                    expected=f"Within ±{increase_threshold}% of {prev}",
                    actual=f"{pct_change:+.1f}%",
                ))

            if pct_change < decrease_threshold:
                findings.append(Finding(
                    rule_id=f"YOY_DN_{spec.id}",
                    finding_type=FindingType.YOY_DELTA,
                    severity=Severity.WARN,
                    field_code=spec.id,
                    title=f"Large YoY decrease ({pct_change:.0f}%): {spec.label}",
                    detail=(
                        f"Value changed from {prev} to {curr} "
                        f"({pct_change:+.1f}%). Please verify."
                    ),
                    expected=f"Within {decrease_threshold}% of {prev}",
                    actual=f"{pct_change:+.1f}%",
                ))

        return findings

    def _check_outliers(
        self,
        current: dict[str, dict],
        peers: list[dict[str, dict]],
        specs: list[FieldSpec],
    ) -> list[Finding]:
        """
        Detect outliers vs peer group using robust z-score (IQR).
        Only runs if n >= 5 peers (per spec).
        """
        import statistics

        findings = []
        if len(peers) < 5:
            return findings

        for spec in specs:
            if spec.field_type != "number":
                continue

            curr_val = current.get(spec.id, {}).get("value")
            if curr_val is None:
                continue

            try:
                curr = float(curr_val)
            except (ValueError, TypeError):
                continue

            peer_nums = []
            for p in peers:
                pv = p.get(spec.id, {}).get("value")
                if pv is not None:
                    try:
                        peer_nums.append(float(pv))
                    except (ValueError, TypeError):
                        pass

            if len(peer_nums) < 5:
                continue

            # IQR-based outlier detection
            sorted_vals = sorted(peer_nums)
            n = len(sorted_vals)
            q1 = sorted_vals[n // 4]
            q3 = sorted_vals[3 * n // 4]
            iqr = q3 - q1

            if iqr == 0:
                continue

            lower_fence = q1 - 1.5 * iqr
            upper_fence = q3 + 1.5 * iqr

            if curr < lower_fence or curr > upper_fence:
                median = statistics.median(peer_nums)
                direction = "above" if curr > upper_fence else "below"
                percentile = sum(1 for v in peer_nums if v <= curr) / len(peer_nums) * 100

                findings.append(Finding(
                    rule_id=f"OUTLIER_{spec.id}",
                    finding_type=FindingType.RANGE,
                    severity=Severity.WARN,
                    field_code=spec.id,
                    title=f"Outlier vs peers: {spec.label}",
                    detail=(
                        f"Your value ({curr}) is {direction} the peer range. "
                        f"Peer median: {median:.2f}, IQR: [{q1:.2f}, {q3:.2f}]. "
                        f"Your percentile: {percentile:.0f}th. "
                        f"This may be correct — please verify."
                    ),
                ))

        return findings

    def compute_readiness_score(
        self,
        field_values: dict[str, dict],
        framework: str = "BRSR",
        entity_class: str = "top_1000",
    ) -> dict:
        """
        Compute framework readiness score = weighted completeness × validity × quality.
        Always returns explainable breakdown.
        """
        framework_fields = self.catalogue.get_framework_fields(framework)
        if not framework_fields:
            return {"score": 0, "breakdown": {}, "message": "No fields found for framework"}

        # Completeness
        mandatory = [f for f in framework_fields if entity_class in f.mandatory_for.get("classes", [])]
        filled_mandatory = sum(1 for f in mandatory if field_values.get(f.id, {}).get("value") is not None)
        completeness = filled_mandatory / max(len(mandatory), 1)

        # Optional fields
        optional = [f for f in framework_fields if f not in mandatory]
        filled_optional = sum(1 for f in optional if field_values.get(f.id, {}).get("value") is not None)
        optional_rate = filled_optional / max(len(optional), 1)

        # Validity (run checks, count errors)
        findings = self.run_all_checks(field_values, entity_class=entity_class)
        critical_count = sum(1 for f in findings if f.severity == Severity.CRITICAL)
        warn_count = sum(1 for f in findings if f.severity == Severity.WARN)
        total_fields = len(framework_fields)
        validity = max(0, 1 - (critical_count * 0.1 + warn_count * 0.03))

        # Evidence quality
        evidence_fields = [f for f in framework_fields if f.validations.get("evidence_required")]
        evidenced = sum(
            1 for f in evidence_fields
            if field_values.get(f.id, {}).get("evidence_url") or field_values.get(f.id, {}).get("source_type")
        )
        evidence_rate = evidenced / max(len(evidence_fields), 1)

        # Weighted score
        score = round(
            completeness * 0.45 + validity * 0.30 + optional_rate * 0.10 + evidence_rate * 0.15,
            3,
        )

        return {
            "score": score,
            "breakdown": {
                "completeness": {
                    "score": round(completeness, 3),
                    "weight": 0.45,
                    "filled": filled_mandatory,
                    "total": len(mandatory),
                },
                "validity": {
                    "score": round(validity, 3),
                    "weight": 0.30,
                    "critical_issues": critical_count,
                    "warnings": warn_count,
                },
                "optional_coverage": {
                    "score": round(optional_rate, 3),
                    "weight": 0.10,
                    "filled": filled_optional,
                    "total": len(optional),
                },
                "evidence_quality": {
                    "score": round(evidence_rate, 3),
                    "weight": 0.15,
                    "evidenced": evidenced,
                    "total": len(evidence_fields),
                },
            },
            "total_fields": total_fields,
            "findings_count": len(findings),
        }

    @staticmethod
    def _refs_to_list(refs: dict) -> list[dict]:
        """Convert refs dict to list of reference objects."""
        result = []
        for framework, ref in refs.items():
            if isinstance(ref, str):
                result.append({"doc": framework, "section": ref})
            elif isinstance(ref, dict):
                result.append({"doc": framework, **ref})
        return result
