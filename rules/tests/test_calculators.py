"""
ESGPilot — Unit Tests for Emission Calculators.

Tests Scope 1, Scope 2, intensity, energy conversion,
water balance, and waste totals.
"""

import pytest
from rules.calculators.emissions import (
    calculate_scope1_fuel,
    calculate_scope2_electricity,
    calculate_scope2_renewable_adjusted,
    calculate_intensity,
    convert_energy,
    calculate_water_balance,
    calculate_waste_totals,
    FUEL_EMISSION_FACTORS,
    INDIA_GRID_EF,
)


# ──────────────────────────────────────────────
# Scope 1 Tests
# ──────────────────────────────────────────────

class TestScope1:
    def test_diesel_basic(self):
        result = calculate_scope1_fuel("diesel", 100.0)
        expected = 100.0 * FUEL_EMISSION_FACTORS["diesel"]["factor"]
        assert abs(result.value_tco2e - expected) < 0.001
        assert result.fuel_or_source == "diesel"
        assert result.unit == "kL"

    def test_all_fuel_types_supported(self):
        fuels = ["diesel", "petrol", "lpg", "cng", "coal", "furnace_oil", "natural_gas", "biomass"]
        for fuel in fuels:
            result = calculate_scope1_fuel(fuel, 1.0)
            assert result is not None
            assert result.value_tco2e >= 0

    def test_biomass_is_zero_emissions(self):
        result = calculate_scope1_fuel("biomass", 100.0)
        assert result.value_tco2e == 0.0

    def test_unknown_fuel_raises(self):
        with pytest.raises(ValueError, match="Unknown fuel type"):
            calculate_scope1_fuel("unobtanium", 100.0)

    def test_case_insensitive_fuel(self):
        r1 = calculate_scope1_fuel("diesel", 10.0)
        r2 = calculate_scope1_fuel("DIESEL", 10.0)
        assert r1.value_tco2e == r2.value_tco2e

    def test_diesel_10kl_typical_value(self):
        """10 kL diesel ≈ 26.41 tCO2e (factor 2.6413)."""
        result = calculate_scope1_fuel("diesel", 10.0)
        assert abs(result.value_tco2e - 26.413) < 0.01

    def test_result_has_factor_metadata(self):
        result = calculate_scope1_fuel("coal", 50.0)
        assert result.factor_source == "IPCC 2006"
        assert result.gwp_basis == "AR5"
        assert result.factor_used == FUEL_EMISSION_FACTORS["coal"]["factor"]

    def test_zero_quantity(self):
        result = calculate_scope1_fuel("diesel", 0.0)
        assert result.value_tco2e == 0.0


# ──────────────────────────────────────────────
# Scope 2 Tests
# ──────────────────────────────────────────────

class TestScope2:
    def test_electricity_basic_2024(self):
        result = calculate_scope2_electricity(kwh=1_000_000, year=2024)
        expected = (1_000_000 / 1000) * INDIA_GRID_EF[2024]
        assert abs(result.value_tco2e - expected) < 0.001
        assert result.unit == "kWh"

    def test_1mwh_equals_grid_ef_in_tco2e(self):
        """1 MWh = 1,000 kWh. Result should equal grid EF."""
        result = calculate_scope2_electricity(kwh=1000.0, year=2024)
        assert abs(result.value_tco2e - INDIA_GRID_EF[2024]) < 0.001

    def test_custom_emission_factor(self):
        custom_ef = 0.50
        result = calculate_scope2_electricity(kwh=1000.0, custom_ef=custom_ef)
        assert abs(result.value_tco2e - 0.50) < 0.001
        assert result.factor_source == "Custom factor"

    def test_zero_electricity(self):
        result = calculate_scope2_electricity(kwh=0.0)
        assert result.value_tco2e == 0.0

    def test_unknown_year_uses_latest(self):
        """Year not in table → use latest available."""
        result = calculate_scope2_electricity(kwh=1000.0, year=2099)
        assert result.value_tco2e > 0

    def test_renewable_adjusted(self):
        result = calculate_scope2_renewable_adjusted(
            total_kwh=1_000_000,
            renewable_kwh=300_000,
            year=2024,
        )
        assert "location_based_tco2e" in result
        assert "market_based_tco2e" in result
        assert result["location_based_tco2e"] > result["market_based_tco2e"]
        assert abs(result["renewable_share_pct"] - 30.0) < 0.01

    def test_renewable_adjusted_full_renewable(self):
        result = calculate_scope2_renewable_adjusted(
            total_kwh=1_000_000,
            renewable_kwh=1_000_000,
            year=2024,
        )
        assert result["market_based_tco2e"] == 0.0
        assert result["renewable_share_pct"] == 100.0


# ──────────────────────────────────────────────
# Intensity Tests
# ──────────────────────────────────────────────

class TestIntensity:
    def test_basic_intensity(self):
        result = calculate_intensity(500.0, 100.0, "turnover_cr")
        assert result["intensity"] == 5.0
        assert "tCO2e/turnover_cr" in result["unit"]

    def test_zero_denominator(self):
        result = calculate_intensity(500.0, 0.0, "employees")
        assert result["intensity"] is None
        assert "error" in result

    def test_intensity_rounded_to_4dp(self):
        result = calculate_intensity(1.0, 3.0, "unit")
        assert result["intensity"] == round(1.0 / 3.0, 4)


# ──────────────────────────────────────────────
# Energy Conversion Tests
# ──────────────────────────────────────────────

class TestEnergyConversion:
    def test_kwh_to_gj(self):
        result = convert_energy(1000.0, "kwh", "GJ")
        assert abs(result["converted_value"] - 3.6) < 0.001

    def test_mwh_to_gj(self):
        result = convert_energy(1.0, "mwh", "GJ")
        assert abs(result["converted_value"] - 3.6) < 0.001

    def test_unknown_conversion_raises(self):
        with pytest.raises(ValueError):
            convert_energy(1.0, "furlongs_per_fortnight", "GJ")

    def test_1_mmbtu_to_gj(self):
        result = convert_energy(1.0, "mmbtu", "GJ")
        assert abs(result["converted_value"] - 1.05506) < 0.001

    def test_conversion_metadata(self):
        result = convert_energy(100.0, "kwh", "GJ")
        assert result["original_unit"] == "kwh"
        assert result["converted_unit"] == "GJ"
        assert result["original_value"] == 100.0


# ──────────────────────────────────────────────
# Water Balance Tests
# ──────────────────────────────────────────────

class TestWaterBalance:
    def test_balanced_water(self):
        result = calculate_water_balance(1000.0, 700.0, 300.0)
        assert result["balanced"] is True
        assert result["difference"] == 0.0

    def test_unbalanced_water(self):
        result = calculate_water_balance(1000.0, 600.0, 300.0)
        assert result["balanced"] is False
        assert result["difference"] > 0

    def test_recycled_percentage(self):
        result = calculate_water_balance(1000.0, 600.0, 400.0)
        assert result["recycled_pct"] == 40.0  # discharge/withdrawal * 100

    def test_zero_withdrawal(self):
        result = calculate_water_balance(0.0, 0.0, 0.0)
        assert result["balanced"] is True


# ──────────────────────────────────────────────
# Waste Total Tests
# ──────────────────────────────────────────────

class TestWasteTotals:
    def test_basic_totals(self):
        # calculate_waste_totals sums all values in each dict
        hazardous = {"generated": 100.0, "recycled": 30.0, "landfill": 70.0}
        non_hazardous = {"generated": 500.0, "recycled": 200.0, "landfill": 300.0}
        result = calculate_waste_totals(hazardous, non_hazardous)
        # hazardous sum = 200, non_hazardous sum = 1000
        assert result["hazardous_total_mt"] == 200.0
        assert result["non_hazardous_total_mt"] == 1000.0
        assert result["total_waste_mt"] == 1200.0

    def test_recovery_rates(self):
        hazardous = {"generated": 100.0, "recycled": 40.0}
        non_hazardous = {"generated": 200.0, "recycled": 100.0}
        result = calculate_waste_totals(hazardous, non_hazardous)
        assert result["hazardous_recovery_pct"] == 40.0
        assert result["non_hazardous_recovery_pct"] == 50.0
        assert result["overall_recovery_pct"] == pytest.approx(46.67, abs=0.01)

    def test_zero_waste(self):
        result = calculate_waste_totals({}, {})
        assert result["total_waste_mt"] == 0.0
