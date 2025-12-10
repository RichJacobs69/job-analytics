"""
Job Family Mapper - Ensures correct job_family assignment based on job_subfamily

This module enforces data consistency by mapping job_subfamily values to their
correct job_family, overriding any incorrect LLM classifications.
"""

import yaml
from pathlib import Path
from typing import Optional

# Load mapping once at module level
MAPPING_FILE = Path(__file__).parent.parent / "config" / "job_family_mapping.yaml"

def load_job_family_mapping() -> dict[str, str]:
    """
    Load job_subfamily -> job_family mapping from YAML config.

    Returns:
        dict: Mapping of job_subfamily (lowercase) to job_family
    """
    with open(MAPPING_FILE, 'r') as f:
        config = yaml.safe_load(f)

    # Flatten into subfamily -> family mapping
    mapping = {}
    for family, subfamilies in config.items():
        for subfamily in subfamilies:
            mapping[subfamily.lower()] = family.lower()

    return mapping

# Load mapping at module import
JOB_FAMILY_MAPPING = load_job_family_mapping()

def get_correct_job_family(job_subfamily: str) -> Optional[str]:
    """
    Get the correct job_family for a given job_subfamily.

    Args:
        job_subfamily: The job subfamily (e.g., 'ai_ml_pm', 'data_engineer')

    Returns:
        str: Correct job_family ('data' or 'product'), or None if not found

    Examples:
        >>> get_correct_job_family('ai_ml_pm')
        'product'
        >>> get_correct_job_family('data_engineer')
        'data'
        >>> get_correct_job_family('ml_engineer')
        'data'
    """
    if not job_subfamily:
        return None

    return JOB_FAMILY_MAPPING.get(job_subfamily.lower())

def validate_and_fix_job_family(job_subfamily: str, job_family: str) -> tuple[str, bool]:
    """
    Validate job_family matches job_subfamily, and fix if incorrect.

    Args:
        job_subfamily: The classified job subfamily
        job_family: The classified job family (may be incorrect)

    Returns:
        tuple: (corrected_job_family, was_corrected)

    Examples:
        >>> validate_and_fix_job_family('ai_ml_pm', 'data')
        ('product', True)  # Was incorrect, corrected to 'product'

        >>> validate_and_fix_job_family('data_engineer', 'data')
        ('data', False)  # Already correct
    """
    if not job_subfamily:
        return job_family, False

    correct_family = get_correct_job_family(job_subfamily)

    if correct_family is None:
        # Subfamily not in mapping - return original
        return job_family, False

    if correct_family != job_family.lower():
        # Mismatch detected - return corrected value
        return correct_family, True

    # Already correct
    return job_family, False

if __name__ == "__main__":
    # Test cases
    test_cases = [
        ("ai_ml_pm", "data"),        # Should correct to 'product'
        ("data_engineer", "data"),   # Should stay 'data'
        ("ml_engineer", "product"),  # Should correct to 'data'
        ("platform_pm", "data"),     # Should correct to 'product'
    ]

    print("Job Family Mapping Validation:")
    print("-" * 60)
    for subfamily, family in test_cases:
        corrected, was_fixed = validate_and_fix_job_family(subfamily, family)
        status = "FIXED" if was_fixed else "OK"
        print(f"{subfamily:20} | {family:10} -> {corrected:10} [{status}]")
