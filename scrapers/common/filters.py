"""
Shared filtering utilities for ATS scrapers.

Provides title pattern matching, location pattern matching, and HTML stripping
used by all scraper modules (Greenhouse, Lever, Ashby, Workable, SmartRecruiters).

Originally lived in greenhouse_scraper.py; extracted here to decouple from
Playwright and allow shared access.

USAGE:
    from scrapers.common.filters import (
        load_title_patterns, load_location_patterns,
        is_relevant_role, matches_target_location,
        strip_html
    )
"""

import re
import logging
import yaml
from html import unescape
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def load_title_patterns(config_path: Optional[Path] = None) -> List[str]:
    """
    Load job title filter patterns from YAML config.

    Args:
        config_path: Path to YAML config file. If None, uses default location.

    Returns:
        List of regex patterns for matching relevant job titles
    """
    if config_path is None:
        # Default: config/greenhouse/title_patterns.yaml relative to project root
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / 'config' / 'greenhouse' / 'title_patterns.yaml'

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            patterns = config.get('relevant_title_patterns', [])
            logger.debug(f"Loaded {len(patterns)} title filter patterns from {config_path}")
            return patterns
    except FileNotFoundError:
        logger.warning(f"Title patterns config not found at {config_path}. Filtering disabled.")
        return []
    except Exception as e:
        logger.warning(f"Failed to load title patterns: {e}. Filtering disabled.")
        return []


def load_location_patterns(config_path: Optional[Path] = None) -> List[str]:
    """
    Load target location filter patterns from YAML config.

    Args:
        config_path: Path to YAML config file. If None, uses default location.

    Returns:
        List of location strings to match (case-insensitive substring matching)
    """
    if config_path is None:
        # Default: config/greenhouse/location_patterns.yaml relative to project root
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / 'config' / 'greenhouse' / 'location_patterns.yaml'

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            patterns = config.get('target_locations', [])
            logger.debug(f"Loaded {len(patterns)} location filter patterns from {config_path}")
            return patterns
    except FileNotFoundError:
        logger.warning(f"Location patterns config not found at {config_path}. Location filtering disabled.")
        return []
    except Exception as e:
        logger.warning(f"Failed to load location patterns: {e}. Location filtering disabled.")
        return []


def matches_target_location(location: str, target_patterns: List[str]) -> bool:
    """
    Check if job location matches target locations (London, NYC, Denver, Remote).

    Uses case-insensitive substring matching against target patterns.

    Args:
        location: Job location string (e.g., "London, UK", "New York, NY", "Remote")
        target_patterns: List of location substrings to match against

    Returns:
        True if location matches any target pattern
    """
    if not location or not target_patterns:
        return False

    location_lower = location.lower()
    patterns_lower = [p.lower() for p in target_patterns]

    # Split multi-location strings (e.g., "San Francisco, CA; New York, NY; Austin, TX").
    # We keep the full string plus split tokens to catch both combined and separated cases.
    tokens = [location_lower]
    split_tokens = [
        token.strip()
        for token in re.split(r'[;/|•\n]', location_lower)
        if token and token.strip()
    ]
    tokens.extend(split_tokens)

    return any(
        pattern in token
        for token in tokens
        for pattern in patterns_lower
    )


def is_relevant_role(title: str, patterns: List[str]) -> bool:
    """
    Check if job title matches Data/Product family patterns.

    Args:
        title: Job title string to evaluate
        patterns: List of regex patterns to match against

    Returns:
        True if title matches any pattern in the list

    Examples:
        >>> patterns = ['data (analyst|engineer)', 'product manager']
        >>> is_relevant_role('Senior Data Engineer', patterns)
        True
        >>> is_relevant_role('Account Executive', patterns)
        False
    """
    if not patterns:
        # No patterns loaded - accept all jobs (filtering disabled)
        return True

    title_lower = title.lower()
    for pattern in patterns:
        try:
            if re.search(pattern, title_lower):
                return True
        except re.error as e:
            logger.warning(f"Invalid regex pattern '{pattern}': {e}")
            continue

    return False


@dataclass
class Job:
    """Structured job posting (legacy Greenhouse format).

    Kept for backward compatibility with test_pipeline_integration.py and
    test_e2e_greenhouse_filtered.py.
    """
    company: str
    title: str
    location: str
    department: Optional[str] = None
    job_type: Optional[str] = None
    description: str = ""
    url: str = ""
    job_id: Optional[str] = None


def strip_html(html_content: str) -> str:
    """
    Strip HTML tags and decode entities from content.

    Args:
        html_content: Raw HTML string

    Returns:
        Plain text string
    """
    if not html_content:
        return ""

    # Decode HTML entities first (API may return &lt;div&gt; instead of <div>)
    clean = unescape(html_content)
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', ' ', clean)
    # Normalize whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean
