"""
Skill Family Mapper
====================
Maps skill names to family codes using deterministic lookup.
LLM (Gemini) extracts skill names; Python assigns family codes.

Two-stage matching:
  1. Exact match (case-insensitive) against skill_family_mapping.yaml
  2. Normalized match -- reduces plurals and UK/US spelling variants
     (e.g., "Databases" -> "database", "Data Visualisation" -> "data visualization")

Short names (<=3 chars) skip normalization to protect "R", "Go", "C", etc.

Canonical names:
  The YAML entries define the canonical display form for each skill.
  get_canonical_name() returns the proper casing (e.g., "pytorch" -> "PyTorch").
  enrich_skills_with_families() normalizes names before database upsert.

Usage:
    from pipeline.skill_family_mapper import get_skill_family, get_canonical_name, enrich_skills_with_families

    # Single skill
    family = get_skill_family("Python")      # Returns "programming"
    family = get_skill_family("Databases")   # Returns "databases" (normalized)

    # Canonical name
    name = get_canonical_name("pytorch")     # Returns "PyTorch"
    name = get_canonical_name("jira")        # Returns "JIRA"

    # Batch enrichment (normalizes names + adds family codes)
    skills = [{"name": "python"}, {"name": "SNOWFLAKE"}]
    enriched = enrich_skills_with_families(skills)
    # Returns [{"name": "Python", "family_code": "programming"}, ...]
"""

import os
import yaml
from pathlib import Path
from typing import Optional

# =============================================================================
# Normalization
# =============================================================================

# Skills too short to safely stem (would create false matches)
_SHORT_SKILL_MIN_LEN = 4

def _normalize(name: str) -> str:
    """Normalize a skill name: lowercase, strip, reduce plurals/spelling variants.

    Only applied to words longer than 3 chars to protect short names like
    R, Go, C, SQL, SAS, etc.
    """
    n = name.lower().strip()
    if len(n) < _SHORT_SKILL_MIN_LEN:
        return n

    # UK -> US spelling
    n = n.replace("modelling", "modeling")
    n = n.replace("visualisation", "visualization")
    n = n.replace("organisation", "organization")
    n = n.replace("optimisation", "optimization")
    n = n.replace("cataloguing", "cataloging")

    # Plural -> singular (ordered from most specific to least)
    if n.endswith("ies") and len(n) > 5:
        n = n[:-3] + "y"          # technologies -> technology
    elif n.endswith("ses") and len(n) > 5:
        n = n[:-2]                # databases -> database
    elif n.endswith("s") and not n.endswith("ss") and not n.endswith("us"):
        n = n[:-1]                # roadmaps -> roadmap

    return n


# =============================================================================
# Load Mapping
# =============================================================================

def _load_skill_mapping() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Load skill -> family mapping from YAML config.

    Returns:
        (exact_map, normalized_map, canonical_map)
        - exact_map: lowercase -> family_code (direct lookup)
        - normalized_map: normalized -> family_code (fuzzy fallback)
        - canonical_map: lowercase -> YAML casing (canonical display name)
    """
    config_path = Path(__file__).parent.parent / "config" / "skill_family_mapping.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Skill family mapping not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw_mapping = yaml.safe_load(f)

    # Invert: family -> [skills] becomes skill -> family
    exact_map: dict[str, str] = {}
    normalized_map: dict[str, str] = {}
    canonical_map: dict[str, str] = {}

    for family_code, skill_list in raw_mapping.items():
        if not isinstance(skill_list, list):
            continue
        for skill in skill_list:
            lower = skill.lower().strip()
            exact_map[lower] = family_code
            normalized_map[_normalize(lower)] = family_code
            # First occurrence wins (preserves the primary canonical form)
            if lower not in canonical_map:
                canonical_map[lower] = skill.strip()

    return exact_map, normalized_map, canonical_map


# Global mappings loaded once at module import
SKILL_TO_FAMILY, SKILL_TO_FAMILY_NORMALIZED, SKILL_TO_CANONICAL = _load_skill_mapping()

# Build normalized -> canonical map for fuzzy canonical lookups
NORMALIZED_TO_CANONICAL: dict[str, str] = {}
for _lower, _canonical in SKILL_TO_CANONICAL.items():
    _norm = _normalize(_lower)
    if _norm not in NORMALIZED_TO_CANONICAL:
        NORMALIZED_TO_CANONICAL[_norm] = _canonical


# =============================================================================
# Public API
# =============================================================================

def get_skill_family(skill_name: str) -> Optional[str]:
    """
    Get family code for a skill name.

    Tries exact match first (case-insensitive), then falls back to
    normalized matching (plurals, UK/US spelling).

    Args:
        skill_name: The skill name (case-insensitive)

    Returns:
        Family code string or None if not found
    """
    if not skill_name:
        return None

    lower = skill_name.lower().strip()

    # 1. Exact match (fast path)
    if lower in SKILL_TO_FAMILY:
        return SKILL_TO_FAMILY[lower]

    # 2. Normalized match (plural/spelling fallback)
    normalized = _normalize(lower)
    if normalized in SKILL_TO_FAMILY_NORMALIZED:
        return SKILL_TO_FAMILY_NORMALIZED[normalized]

    return None


def get_canonical_name(skill_name: str) -> str:
    """
    Get the canonical display name for a skill.

    Lookup order:
      1. Exact match in SKILL_TO_CANONICAL (lowercase -> YAML casing)
      2. Normalized match in NORMALIZED_TO_CANONICAL (handles plurals/spelling)
      3. Fallback: title-case the input for unknown skills

    Args:
        skill_name: The skill name (any casing)

    Returns:
        Canonical display name string
    """
    if not skill_name:
        return skill_name or ""

    lower = skill_name.lower().strip()

    # 1. Exact match
    if lower in SKILL_TO_CANONICAL:
        return SKILL_TO_CANONICAL[lower]

    # 2. Normalized match
    normalized = _normalize(lower)
    if normalized in NORMALIZED_TO_CANONICAL:
        return NORMALIZED_TO_CANONICAL[normalized]

    # 3. Unknown skill: title-case as best guess
    return skill_name.strip().title()


def enrich_skills_with_families(skills: list[dict]) -> list[dict]:
    """
    Enrich a list of skills with family codes and canonical names.

    Args:
        skills: List of skill dicts with at least {"name": "..."}

    Returns:
        Same list with family_code added and name normalized to canonical form
    """
    if not skills:
        return skills

    for skill in skills:
        name = skill.get("name", "")
        skill["name"] = get_canonical_name(name)
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
        "total_normalized": len(SKILL_TO_FAMILY_NORMALIZED),
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
    print(f"Total skills mapped (exact): {stats['total_skills_mapped']}")
    print(f"Total skills mapped (normalized): {stats['total_normalized']}")
    print(f"Number of families: {stats['families']}")
    print()
    print("Skills per family:")
    for family, count in sorted(stats["skills_per_family"].items(), key=lambda x: -x[1]):
        print(f"  {family}: {count}")

    print()
    print("Test lookups (family + canonical name):")
    test_skills = [
        "Python",
        "SQL",
        "Snowflake",
        "dbt",
        "PyTorch",
        "LangChain",
        "Kubernetes",
        "Unknown Skill XYZ",
        "TENSORFLOW",       # case insensitivity
        "power bi",         # lowercase
        "Databases",        # plural -> database
        "Roadmaps",         # plural -> roadmap
        "Data Visualisation",  # UK spelling
        "R",                # short name, must not false match
        "Go",               # short name, must not false match
        "jira",             # should canonicalize to JIRA
        "pytorch",          # should canonicalize to PyTorch
    ]
    for skill in test_skills:
        family = get_skill_family(skill)
        canonical = get_canonical_name(skill)
        print(f"  {skill} -> family={family}, canonical={canonical}")
