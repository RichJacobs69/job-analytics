"""
Test skill family mapper module

Pure unit tests for pipeline/skill_family_mapper.py.
Tests mapping from skill names to family codes using YAML config,
and canonical name normalization.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.skill_family_mapper import (
    get_skill_family,
    get_canonical_name,
    enrich_skills_with_families,
    get_mapping_stats,
    SKILL_TO_FAMILY,
    SKILL_TO_CANONICAL,
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


class TestGetCanonicalName:
    """Test get_canonical_name() canonical display name lookups"""

    def test_known_skill_returns_yaml_casing(self):
        """Known skills return their YAML-defined casing"""
        assert get_canonical_name("python") == "Python"
        assert get_canonical_name("PYTHON") == "Python"

    def test_jira_returns_uppercase(self):
        """JIRA is an acronym and should be uppercase"""
        assert get_canonical_name("jira") == "JIRA"
        assert get_canonical_name("Jira") == "JIRA"
        assert get_canonical_name("JIRA") == "JIRA"

    def test_pytorch_preserves_casing(self):
        """PyTorch has specific brand casing"""
        assert get_canonical_name("pytorch") == "PyTorch"
        assert get_canonical_name("PYTORCH") == "PyTorch"

    def test_tensorflow_preserves_casing(self):
        """TensorFlow has specific brand casing"""
        assert get_canonical_name("tensorflow") == "TensorFlow"

    def test_lowercase_brand_stays_lowercase(self):
        """Intentionally lowercase brands stay lowercase"""
        assert get_canonical_name("dbt") == "dbt"
        assert get_canonical_name("pytest") == "pytest"
        assert get_canonical_name("fastapi") == "fastapi"

    def test_acronyms_uppercase(self):
        """Acronyms should be uppercase"""
        assert get_canonical_name("sql") == "SQL"
        assert get_canonical_name("aws") == "AWS"
        assert get_canonical_name("etl") == "ETL"

    def test_unknown_skill_gets_title_cased(self):
        """Unknown skills get title-cased as fallback"""
        assert get_canonical_name("some unknown tool") == "Some Unknown Tool"

    def test_empty_returns_empty(self):
        """Empty string returns empty string"""
        assert get_canonical_name("") == ""

    def test_none_returns_empty(self):
        """None returns empty string"""
        assert get_canonical_name(None) == ""

    def test_whitespace_handling(self):
        """Extra whitespace is stripped"""
        assert get_canonical_name("  python  ") == "Python"

    def test_sql_variants(self):
        """SQL variants preserve their conventions"""
        assert get_canonical_name("pl/sql") == "PL/SQL"
        assert get_canonical_name("t-sql") == "T-SQL"
        assert get_canonical_name("sparksql") == "SparkSQL"


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

    def test_name_normalization(self):
        """Names should be normalized to canonical form"""
        skills = [
            {"name": "python"},
            {"name": "JIRA"},
            {"name": "pytorch"},
        ]
        enriched = enrich_skills_with_families(skills)
        assert enriched[0]["name"] == "Python"
        assert enriched[1]["name"] == "JIRA"
        assert enriched[2]["name"] == "PyTorch"

    def test_unknown_skill_gets_none_family_and_title_case(self):
        """Unknown skills get family_code=None and title-cased name"""
        skills = [{"name": "unknown cool tool"}]
        enriched = enrich_skills_with_families(skills)
        assert enriched[0]["family_code"] is None
        assert enriched[0]["name"] == "Unknown Cool Tool"

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
        assert enriched[0]["name"] == "Python"

    def test_lowercase_brand_preserved(self):
        """Lowercase brands should stay lowercase after enrichment"""
        skills = [{"name": "dbt"}]
        enriched = enrich_skills_with_families(skills)
        assert enriched[0]["name"] == "dbt"
        assert enriched[0]["family_code"] == "data_modeling"


class TestMappingConfig:
    """Test that YAML config loaded correctly"""

    def test_mapping_not_empty(self):
        """Mapping should have entries"""
        assert len(SKILL_TO_FAMILY) > 0

    def test_canonical_map_not_empty(self):
        """Canonical map should have entries"""
        assert len(SKILL_TO_CANONICAL) > 0

    def test_canonical_map_matches_family_map(self):
        """Every skill in family map should have a canonical entry"""
        for skill in SKILL_TO_FAMILY:
            assert skill in SKILL_TO_CANONICAL, f"Missing canonical entry for: {skill}"

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
