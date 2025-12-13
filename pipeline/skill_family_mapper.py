"""
Skill Family Mapper
====================
Maps skill names to family codes using deterministic lookup.
LLM extracts skill names only; Python assigns families.

Usage:
    from skill_family_mapper import get_skill_family, enrich_skills_with_families

    # Single skill
    family = get_skill_family("Python")  # Returns "programming"

    # Batch enrichment
    skills = [{"name": "Python"}, {"name": "Snowflake"}]
    enriched = enrich_skills_with_families(skills)
    # Returns [{"name": "Python", "family_code": "programming"}, ...]
"""

import os
import yaml
from pathlib import Path
from typing import Optional

# =============================================================================
# Load Mapping
# =============================================================================

def _load_skill_mapping() -> dict[str, str]:
    """Load skill -> family mapping from YAML config."""
    config_path = Path(__file__).parent.parent / "config" / "skill_family_mapping.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Skill family mapping not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw_mapping = yaml.safe_load(f)

    # Invert: family -> [skills] becomes skill -> family
    skill_to_family: dict[str, str] = {}

    for family_code, skill_list in raw_mapping.items():
        if not isinstance(skill_list, list):
            continue
        for skill in skill_list:
            normalized = skill.lower().strip()
            skill_to_family[normalized] = family_code

    return skill_to_family


# Global mapping loaded once at module import
SKILL_TO_FAMILY: dict[str, str] = _load_skill_mapping()


# =============================================================================
# Public API
# =============================================================================

def get_skill_family(skill_name: str) -> Optional[str]:
    """
    Get family code for a skill name.

    Args:
        skill_name: The skill name (case-insensitive)

    Returns:
        Family code string or None if not found
    """
    if not skill_name:
        return None

    normalized = skill_name.lower().strip()

    # Direct match
    if normalized in SKILL_TO_FAMILY:
        return SKILL_TO_FAMILY[normalized]

    # Try without special characters (e.g., "C++" -> "c++")
    # Already handled by normalization

    return None


def enrich_skills_with_families(skills: list[dict]) -> list[dict]:
    """
    Enrich a list of skills with family codes.

    Args:
        skills: List of skill dicts with at least {"name": "..."}

    Returns:
        Same list with family_code added to each skill
    """
    if not skills:
        return skills

    for skill in skills:
        name = skill.get("name", "")
        family = get_skill_family(name)
        skill["family_code"] = family

    return skills


def get_mapping_stats() -> dict:
    """Get statistics about the current mapping."""
    families = {}
    for skill, family in SKILL_TO_FAMILY.items():
        if family not in families:
            families[family] = 0
        families[family] += 1

    return {
        "total_skills_mapped": len(SKILL_TO_FAMILY),
        "families": len(families),
        "skills_per_family": families,
    }


# =============================================================================
# CLI / Testing
# =============================================================================

if __name__ == "__main__":
    print("Skill Family Mapper")
    print("=" * 50)

    stats = get_mapping_stats()
    print(f"Total skills mapped: {stats['total_skills_mapped']}")
    print(f"Number of families: {stats['families']}")
    print()
    print("Skills per family:")
    for family, count in sorted(stats["skills_per_family"].items(), key=lambda x: -x[1]):
        print(f"  {family}: {count}")

    print()
    print("Test lookups:")
    test_skills = [
        "Python",
        "SQL",
        "Snowflake",
        "dbt",
        "PyTorch",
        "LangChain",
        "Kubernetes",
        "Unknown Skill XYZ",
        "TENSORFLOW",  # Test case insensitivity
        "power bi",    # Test lowercase
    ]
    for skill in test_skills:
        family = get_skill_family(skill)
        print(f"  {skill} -> {family}")
