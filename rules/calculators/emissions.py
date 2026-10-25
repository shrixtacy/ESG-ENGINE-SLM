"""
ESGPilot — GHG Emission Calculators.

Deterministic calculations for Scope 1, 2, 3 emissions,
intensity ratios, energy conversions, water balance, waste totals.
Factors are versioned by year/source.
"""

from dataclasses import dataclass
from typing import Optional


# ──────────────────────────────────────────────
# Emission Factor Data (versioned)
# ──────────────────────────────────────────────

# India grid emission factor (CEA CO2 Baseline Database)
# tCO2/MWh — varies by year
INDIA_GRID_EF = {
    2020: 0.79,
    2021: 0.79,
    2022: 0.78,
    2023: 0.72,
    2024: 0.71,
    2025: 0.71,
}

# Fuel emission factors (tCO2 per unit) — IPCC defaults / India GHG Programme
FUEL_EMISSION_FACTORS = {
    "diesel": {"unit": "kL", "factor": 2.6413, "source": "IPCC 2006", "gwp": "AR5"},
    "petrol": {"unit": "kL", "factor": 2.2496, "source": "IPCC 2006", "gwp": "AR5"},
    "lpg": {"unit": "MT", "factor": 2.9830, "source": "IPCC 2006", "gwp": "AR5"},
    "cng": {"unit": "thousand_m3", "factor": 2.0424, "source": "IPCC 2006", "gwp": "AR5"},
    "png": {"unit": "thousand_m3", "factor": 2.0424, "source": "IPCC 2006", "gwp": "AR5"},
    "coal": {"unit": "MT", "factor": 2.4475, "source": "IPCC 2006", "gwp": "AR5"},
    "furnace_oil": {"unit": "kL", "factor": 2.9557, "source": "IPCC 2006", "gwp": "AR5"},
    "natural_gas": {"unit": "thousand_m3", "factor": 2.0424, "source": "IPCC 2006", "gwp": "AR5"},
    "biomass": {"unit": "MT", "factor": 0.0, "source": "IPCC 2006", "gwp": "AR5"},  # Carbon neutral
}

# Energy conversion factors
ENERGY_CONVERSIONS = {
    "kwh_to_gj": 0.0036,
    "mwh_to_gj": 3.6,
    "kcal_to_gj": 4.184e-6,
    "mmbtu_to_gj": 1.05506,
    "toe_to_gj": 41.868,
    "kl_diesel_to_gj": 35.69,
    "kl_petrol_to_gj": 32.24,
    "mt_coal_to_gj": 19.59,
    "mt_lpg_to_gj": 47.31,
    "thousand_m3_cng_to_gj": 36.37,
}

# GWP values (IPCC AR5 — used in BRSR)
GWP_AR5 = {
    "co2": 1,
    "ch4": 28,
    "n2o": 265,
    "hfc_134a": 1300,
    "sf6": 23500,
}


@dataclass
class EmissionResult:
    """Result of an emission calculation."""
    value_tco2e: float
    fuel_or_source: str
    quantity: float
    unit: str
    factor_used: float
    factor_source: str
    factor_year: int
    gwp_basis: str = "AR5"
    notes: str = ""


def calculate_scope1_fuel(
    fuel_type: str,
    quantity: float,
    year: int = 2024,
) -> EmissionResult:
    """
    Calculate Scope 1 emissions from fuel combustion.
    Activity data × emission factor = tCO2e
    """
    fuel = FUEL_EMISSION_FACTORS.get(fuel_type.lower())
    if not fuel:
        raise ValueError(f"Unknown fuel type: {fuel_type}. Available: {list(FUEL_EMISSION_FACTORS.keys())}")

    tco2e = quantity * fuel["factor"]

    return EmissionResult(
        value_tco2e=round(tco2e, 4),
        fuel_or_source=fuel_type,
        quantity=quantity,
        unit=fuel["unit"],
        factor_used=fuel["factor"],
        factor_source=fuel["source"],
        factor_year=year,
        gwp_basis=fuel["gwp"],
    )


def calculate_scope2_electricity(
    kwh: float,
    year: int = 2024,
    region: str = "IN",
    custom_ef: Optional[float] = None,
) -> EmissionResult:
    """
    Calculate Scope 2 emissions from purchased electricity.
    Uses India CEA grid emission factor or custom factor.
    """
    if custom_ef is not None:
        ef = custom_ef
        source = "Custom factor"
    else:
        ef = INDIA_GRID_EF.get(year, INDIA_GRID_EF.get(max(INDIA_GRID_EF.keys())))
        source = "CEA CO2 Baseline Database"

    mwh = kwh / 1000.0
    tco2e = mwh * ef

    return EmissionResult(
        value_tco2e=round(tco2e, 4),
        fuel_or_source="grid_electricity",
        quantity=kwh,
        unit="kWh",
        factor_used=ef,
        factor_source=source,
        factor_year=year,
    )


def calculate_scope2_renewable_adjusted(
    total_kwh: float,
    renewable_kwh: float,
    year: int = 2024,
) -> dict:
    """
    Calculate Scope 2 with renewable energy adjustment.
    Returns both location-based and market-based emissions.
    """
    ef = INDIA_GRID_EF.get(year, INDIA_GRID_EF.get(max(INDIA_GRID_EF.keys())))

    location_based = (total_kwh / 1000.0) * ef
    market_based = ((total_kwh - renewable_kwh) / 1000.0) * ef

    return {
        "location_based_tco2e": round(location_based, 4),
        "market_based_tco2e": round(market_based, 4),
        "renewable_share_pct": round(renewable_kwh / max(total_kwh, 1) * 100, 2),
        "grid_ef": ef,
        "year": year,
    }


def calculate_intensity(
    emissions_tco2e: float,
    denominator: float,
    denominator_type: str = "turnover_cr",
) -> dict:
    """
    Calculate emission intensity ratio.
    Common denominators: turnover (₹ crore), employees, MW, km, sq_m.
    """
    if denominator == 0:
        return {
            "intensity": None,
            "unit": f"tCO2e per {denominator_type}",
            "error": "Denominator is zero",
        }

    intensity = emissions_tco2e / denominator

    return {
        "intensity": round(intensity, 4),
        "emissions_tco2e": emissions_tco2e,
        "denominator": denominator,
        "denominator_type": denominator_type,
        "unit": f"tCO2e/{denominator_type}",
    }


def convert_energy(value: float, from_unit: str, to_unit: str = "GJ") -> dict:
    """Convert between energy units."""
    key = f"{from_unit.lower()}_to_{to_unit.lower()}"
    factor = ENERGY_CONVERSIONS.get(key)

    if factor is None:
        # Try reverse
        reverse_key = f"{to_unit.lower()}_to_{from_unit.lower()}"
        reverse_factor = ENERGY_CONVERSIONS.get(reverse_key)
        if reverse_factor:
            factor = 1 / reverse_factor
        else:
            raise ValueError(
                f"No conversion factor for {from_unit} → {to_unit}. "
                f"Available: {list(ENERGY_CONVERSIONS.keys())}"
            )

    return {
        "original_value": value,
        "original_unit": from_unit,
        "converted_value": round(value * factor, 4),
        "converted_unit": to_unit,
        "conversion_factor": factor,
    }


def calculate_water_balance(
    withdrawal: float,
    consumption: float,
    discharge: float,
) -> dict:
    """
    Check water balance: withdrawal = consumption + discharge.
    Returns balance check result.
    """
    expected_withdrawal = consumption + discharge
    difference = abs(withdrawal - expected_withdrawal)
    balanced = difference <= 0.01 * max(withdrawal, 1)

    return {
        "withdrawal": withdrawal,
        "consumption": consumption,
        "discharge": discharge,
        "expected_withdrawal": expected_withdrawal,
        "difference": round(difference, 2),
        "balanced": balanced,
        "recycled_pct": round(
            (discharge / max(withdrawal, 1)) * 100 if withdrawal > 0 else 0, 2
        ),
    }


def calculate_waste_totals(
    hazardous: dict[str, float],
    non_hazardous: dict[str, float],
) -> dict:
    """
    Calculate total waste, recovery rate, etc.
    Input dicts: {"generated": X, "recycled": Y, "landfill": Z, "incinerated": W}
    """
    hz_total = sum(hazardous.values())
    nhz_total = sum(non_hazardous.values())
    total = hz_total + nhz_total

    hz_recycled = hazardous.get("recycled", 0) + hazardous.get("reused", 0)
    nhz_recycled = non_hazardous.get("recycled", 0) + non_hazardous.get("reused", 0)

    hz_generated = hazardous.get("generated", hz_total)
    nhz_generated = non_hazardous.get("generated", nhz_total)

    return {
        "hazardous": hazardous,
        "non_hazardous": non_hazardous,
        "total_waste_mt": round(total, 2),
        "hazardous_total_mt": round(hz_total, 2),
        "non_hazardous_total_mt": round(nhz_total, 2),
        "hazardous_recovery_pct": round(
            hz_recycled / max(hz_generated, 1) * 100, 2
        ),
        "non_hazardous_recovery_pct": round(
            nhz_recycled / max(nhz_generated, 1) * 100, 2
        ),
        "overall_recovery_pct": round(
            (hz_recycled + nhz_recycled) / max(hz_generated + nhz_generated, 1) * 100, 2
        ),
    }
