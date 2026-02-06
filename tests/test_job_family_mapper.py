"""
Test job family mapper module

Pure unit tests for pipeline/job_family_mapper.py.
Tests mapping from job_subfamily to job_family using YAML config.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.job_family_mapper import (
    get_correct_job_family,
    validate_and_fix_job_family,
    load_job_family_mapping,
    JOB_FAMILY_MAPPING,
)


class TestGetCorrectJobFamily:
    """Test get_correct_job_family() lookups"""

    def test_data_engineer_maps_to_data(self):
        """data_engineer should map to data family"""
        assert get_correct_job_family("data_engineer") == "data"

    def test_ml_engineer_maps_to_data(self):
        """ml_engineer should map to data family"""
        assert get_correct_job_family("ml_engineer") == "data"

    def test_core_pm_maps_to_product(self):
        """core_pm should map to product family"""
        assert get_correct_job_family("core_pm") == "product"

    def test_ai_ml_pm_maps_to_product(self):
        """ai_ml_pm should map to product family"""
        assert get_correct_job_family("ai_ml_pm") == "product"

    def test_delivery_manager_maps_to_delivery(self):
        """delivery_manager should map to delivery family"""
        assert get_correct_job_family("delivery_manager") == "delivery"

    def test_unknown_subfamily_returns_none(self):
        """Unknown subfamily should return None"""
        assert get_correct_job_family("unknown_role_xyz") is None

    def test_empty_subfamily_returns_none(self):
        """Empty subfamily should return None"""
        assert get_correct_job_family("") is None

    def test_none_subfamily_returns_none(self):
        """None subfamily should return None"""
        assert get_correct_job_family(None) is None

    def test_case_insensitive(self):
        """Lookup should be case-insensitive"""
        assert get_correct_job_family("Data_Engineer") == "data"
        assert get_correct_job_family("DATA_ENGINEER") == "data"


class TestValidateAndFixJobFamily:
    """Test validate_and_fix_job_family() correction logic"""

    def test_correct_family_not_changed(self):
        """Correct family should not be changed"""
        family, was_corrected = validate_and_fix_job_family("data_engineer", "data")
        assert family == "data"
        assert was_corrected is False

    def test_incorrect_family_corrected(self):
        """Incorrect family should be corrected"""
        family, was_corrected = validate_and_fix_job_family("ai_ml_pm", "data")
        assert family == "product"
        assert was_corrected is True

    def test_ml_engineer_misclassified_as_product(self):
        """ml_engineer misclassified as product should be corrected to data"""
        family, was_corrected = validate_and_fix_job_family("ml_engineer", "product")
        assert family == "data"
        assert was_corrected is True

    def test_unknown_subfamily_preserves_original(self):
        """Unknown subfamily should preserve original family"""
        family, was_corrected = validate_and_fix_job_family("unknown_xyz", "data")
        assert family == "data"
        assert was_corrected is False

    def test_empty_subfamily_preserves_original(self):
        """Empty subfamily should preserve original family"""
        family, was_corrected = validate_and_fix_job_family("", "product")
        assert family == "product"
        assert was_corrected is False


class TestLoadJobFamilyMapping:
    """Test YAML config loading"""

    def test_mapping_loads_without_error(self):
        """Config YAML should load without errors"""
        mapping = load_job_family_mapping()
        assert isinstance(mapping, dict)
        assert len(mapping) > 0

    def test_all_families_present(self):
        """All expected families should be in the mapping"""
        families_in_mapping = set(JOB_FAMILY_MAPPING.values())
        assert "data" in families_in_mapping
        assert "product" in families_in_mapping
        assert "delivery" in families_in_mapping

    def test_known_subfamilies_present(self):
        """Known subfamilies should be in the mapping"""
        assert "data_engineer" in JOB_FAMILY_MAPPING
        assert "core_pm" in JOB_FAMILY_MAPPING
        assert "delivery_manager" in JOB_FAMILY_MAPPING


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
