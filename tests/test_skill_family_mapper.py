"""
Test skill family mapper module

Pure unit tests for pipeline/skill_family_mapper.py.
Tests mapping from skill names to family codes using YAML config.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.skill_family_mapper import (
    get_skill_family,
    enrich_skills_with_families,
    get_mapping_stats,
    SKILL_TO_FAMILY,
)


class TestGetSkillFamily:
    """Test get_skill_family() lookups"""

    def test_python_maps_to_programming(self):
        """Python should map to programming family"""
        assert get_skill_family("Python") == "programming"

    def test_sql_maps_to_programming(self):
        """SQL should map to programming family"""
        assert get_skill_family("SQL") == "programming"

    def test_case_insensitive(self):
        """Lookup should be case-insensitive"""
        family1 = get_skill_family("python")
        family2 = get_skill_family("PYTHON")
        family3 = get_skill_family("Python")
        assert family1 == family2 == family3

    def test_unknown_skill_returns_none(self):
        """Unknown skill should return None"""
        assert get_skill_family("CompletelyMadeUpSkillXYZ123") is None

    def test_empty_skill_returns_none(self):
        """Empty skill should return None"""
        assert get_skill_family("") is None

    def test_none_skill_returns_none(self):
        """None skill should return None"""
        assert get_skill_family(None) is None

    def test_whitespace_handling(self):
        """Skills with extra whitespace should still match"""
        result = get_skill_family("  Python  ")
        assert result == "programming"


class TestEnrichSkillsWithFamilies:
    """Test enrich_skills_with_families() batch function"""

    def test_basic_enrichment(self):
        """Enrich known skills with family codes"""
        skills = [
            {"name": "Python"},
            {"name": "SQL"}
        ]
        enriched = enrich_skills_with_families(skills)
        assert len(enriched) == 2
        assert enriched[0]["family_code"] == "programming"
        assert enriched[1]["family_code"] == "programming"

    def test_unknown_skill_gets_none(self):
        """Unknown skills should get family_code=None"""
        skills = [{"name": "UnknownSkillXYZ"}]
        enriched = enrich_skills_with_families(skills)
        assert enriched[0]["family_code"] is None

    def test_mixed_known_unknown(self):
        """Mix of known and unknown skills"""
        skills = [
            {"name": "Python"},
            {"name": "CompletelyFakeSkill"}
        ]
        enriched = enrich_skills_with_families(skills)
        assert enriched[0]["family_code"] is not None
        assert enriched[1]["family_code"] is None

    def test_empty_list(self):
        """Empty list should return empty list"""
        result = enrich_skills_with_families([])
        assert result == []

    def test_none_input(self):
        """None input should return None"""
        result = enrich_skills_with_families(None)
        assert result is None

    def test_preserves_existing_fields(self):
        """Enrichment should preserve existing fields"""
        skills = [{"name": "Python", "extra_field": "value"}]
        enriched = enrich_skills_with_families(skills)
        assert enriched[0]["extra_field"] == "value"
        assert enriched[0]["family_code"] == "programming"


class TestMappingConfig:
    """Test that YAML config loaded correctly"""

    def test_mapping_not_empty(self):
        """Mapping should have entries"""
        assert len(SKILL_TO_FAMILY) > 0

    def test_mapping_stats(self):
        """Stats function should return valid data"""
        stats = get_mapping_stats()
        assert stats["total_skills_mapped"] > 0
        assert stats["families"] > 0
        assert isinstance(stats["skills_per_family"], dict)

    def test_multiple_families_exist(self):
        """Multiple family codes should exist"""
        families = set(SKILL_TO_FAMILY.values())
        assert len(families) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
