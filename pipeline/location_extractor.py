"""
Location Extractor Module
Extracts structured location data from raw location strings.

Part of: Global Location Expansion Epic - Phase 1

This module provides deterministic location extraction from job posting location strings,
with pattern matching against the location_mapping.yaml configuration.

Location object structure:
- type: "city" | "country" | "region" | "remote" | "unknown"
- country_code: ISO 3166-1 alpha-2 (US, GB, SG, etc.)
- city: snake_case city name (san_francisco, london, etc.)
- region: EMEA | AMER | APAC (for regional remote)
- scope: "global" | "country" | "region" (for remote jobs)

Example usage:
    from pipeline.location_extractor import extract_locations

    locations = extract_locations("London, UK")
    # Returns: [{"type": "city", "country_code": "GB", "city": "london"}]

    locations = extract_locations("Remote - US")
    # Returns: [{"type": "remote", "scope": "country", "country_code": "US"}]

    locations = extract_locations("NYC or Remote")
    # Returns: [
    #     {"type": "city", "country_code": "US", "city": "new_york"},
    #     {"type": "remote", "scope": "country", "country_code": "US"}
    # ]
"""

import os
import re
from typing import Dict, List, Optional, Tuple
import yaml


# =============================================================================
# Configuration Loading
# =============================================================================

_config_cache: Optional[Dict] = None


def load_location_config() -> Dict:
    """
    Load location mapping configuration from YAML file.
    Caches the config in memory for subsequent calls.

    Returns:
        Dict containing cities, countries, regions, and remote_patterns
    """
    global _config_cache

    if _config_cache is not None:
        return _config_cache

    # Find config file relative to this module
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "config",
        "location_mapping.yaml"
    )

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Location config not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        _config_cache = yaml.safe_load(f)

    return _config_cache


def clear_config_cache():
    """Clear the config cache (useful for testing)."""
    global _config_cache
    _config_cache = None


# =============================================================================
# Pattern Matching Functions
# =============================================================================

def match_city_pattern(text: str, config: Dict) -> Optional[Dict]:
    """
    Match text against city patterns.

    Args:
        text: Normalized (lowercase) location text
        config: Location config dict

    Returns:
        Location object if match found, None otherwise
    """
    cities = config.get("cities", {})

    for city_key, city_data in cities.items():
        patterns = city_data.get("patterns", [])
        for pattern in patterns:
            # Use word boundary matching to avoid false positives
            # E.g., "sg" should match "sg" but not within "responsibilities"
            if re.search(r'\b' + re.escape(pattern.lower()) + r'\b', text, re.IGNORECASE):
                return {
                    "type": "city",
                    "country_code": city_data["country_code"],
                    "city": city_key
                }

    return None


def match_remote_pattern(text: str, config: Dict) -> Optional[Dict]:
    """
    Match text against remote patterns.

    Args:
        text: Normalized (lowercase) location text
        config: Location config dict

    Returns:
        Location object if match found, None otherwise
    """
    result, _ = _match_remote_pattern_with_info(text, config)
    return result


def _match_remote_pattern_with_info(text: str, config: Dict) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Match text against remote patterns, returning both the match and the matched pattern.

    Args:
        text: Normalized (lowercase) location text
        config: Location config dict

    Returns:
        Tuple of (Location object, matched pattern string) or (None, None) if no match
    """
    remote_patterns = config.get("remote_patterns", {})

    # Check specific remote patterns first (us_only, uk_only, emea, etc.)
    # These are more specific than global remote
    for pattern_key, pattern_data in remote_patterns.items():
        if pattern_key == "global":
            continue  # Check global last

        patterns = pattern_data.get("patterns", [])
        for pattern in patterns:
            if pattern.lower() in text:
                location = {
                    "type": "remote",
                    "scope": pattern_data.get("scope", "unknown")
                }
                # Add country_code or region based on scope
                if "country_code" in pattern_data:
                    location["country_code"] = pattern_data["country_code"]
                if "region" in pattern_data:
                    location["region"] = pattern_data["region"]
                return location, pattern.lower()

    # Check global remote patterns last
    global_patterns = remote_patterns.get("global", {}).get("patterns", [])
    for pattern in global_patterns:
        if pattern.lower() in text:
            return {
                "type": "remote",
                "scope": "global"
            }, pattern.lower()

    return None, None


def match_region_pattern(text: str, config: Dict) -> Optional[Dict]:
    """
    Match text against region patterns (for regional jobs, not remote).

    Args:
        text: Normalized (lowercase) location text
        config: Location config dict

    Returns:
        Location object if match found, None otherwise
    """
    regions = config.get("regions", {})

    for region_key, region_data in regions.items():
        patterns = region_data.get("patterns", [])
        for pattern in patterns:
            if pattern.lower() in text:
                return {
                    "type": "region",
                    "region": region_key
                }

    return None


def match_country_pattern(text: str, config: Dict) -> Optional[Dict]:
    """
    Match text against country aliases.

    Args:
        text: Normalized (lowercase) location text
        config: Location config dict

    Returns:
        Location object if match found, None otherwise
    """
    countries = config.get("countries", {})

    for country_code, country_data in countries.items():
        aliases = country_data.get("aliases", [])
        # Check display name and aliases
        names_to_check = [country_data["display_name"].lower()] + [a.lower() for a in aliases]
        for name in names_to_check:
            # Use word boundary matching to avoid partial matches
            # e.g., "UK" should match "UK" but not "Ukraine"
            if re.search(r'\b' + re.escape(name) + r'\b', text, re.IGNORECASE):
                return {
                    "type": "country",
                    "country_code": country_code
                }

    return None


# =============================================================================
# Multi-Location Parsing
# =============================================================================

def split_multi_location(raw_location: str) -> List[str]:
    """
    Split a multi-location string into individual location parts.

    Handles common separators like:
    - "London or Stockholm"
    - "NYC / Remote"
    - "Remote - New York"
    - "San Francisco, Remote"
    - "Berlin; Amsterdam"

    Args:
        raw_location: Raw location string

    Returns:
        List of individual location strings
    """
    # Normalize separators
    text = raw_location

    # Split on common separators
    # Order matters: check longer patterns first
    separators = [
        r'\s+or\s+',      # "London or Stockholm"
        r'\s+-\s+',       # "Remote - New York" (requires spaces around hyphen)
        r'\s*/\s*',       # "NYC / Remote"
        r'\s*;\s*',       # "Berlin; Amsterdam"
        r'\s*\|\s*',      # "London | NYC"
    ]

    for sep in separators:
        parts = re.split(sep, text, flags=re.IGNORECASE)
        if len(parts) > 1:
            return [p.strip() for p in parts if p.strip()]

    # No multi-location separator found, return as single location
    return [text.strip()]


# =============================================================================
# Working Arrangement Detection (Not Locations)
# =============================================================================

# Some companies put working arrangement in the location field instead of actual locations
# These are NOT geographic locations - handle them specially
WORKING_ARRANGEMENT_TERMS = {
    # Terms that indicate remote work (return remote type)
    'remote': {'type': 'remote', 'scope': 'global'},
    'work from home': {'type': 'remote', 'scope': 'global'},
    'wfh': {'type': 'remote', 'scope': 'global'},
    'anywhere': {'type': 'remote', 'scope': 'global'},
    'fully remote': {'type': 'remote', 'scope': 'global'},
    'remote only': {'type': 'remote', 'scope': 'global'},

    # Terms that are working arrangements but NOT locations (return unknown)
    # We can't infer geographic location from these
    'hybrid': None,  # None means return unknown
    'in-office': None,
    'in office': None,
    'on-site': None,
    'onsite': None,
    'office-based': None,
    'office based': None,
}


def check_working_arrangement_term(text: str) -> Optional[Dict]:
    """
    Check if text is a working arrangement term (not a location).

    Some companies (e.g., Cloudflare) put "Hybrid" or "In-Office" in
    the location field. These are working arrangements, not locations.

    Args:
        text: Normalized (lowercase) location text

    Returns:
        - Location dict if it's a remote term (e.g., {"type": "remote", "scope": "global"})
        - Empty dict {} if it's a non-location arrangement (Hybrid, In-Office)
        - None if it's not a working arrangement term (continue with location matching)
    """
    text_lower = text.lower().strip()

    # Exact match check
    if text_lower in WORKING_ARRANGEMENT_TERMS:
        result = WORKING_ARRANGEMENT_TERMS[text_lower]
        if result is None:
            return {}  # Signal: it's an arrangement term but not a location
        return result.copy()

    return None  # Not a working arrangement term


# =============================================================================
# Main Extraction Function
# =============================================================================

def extract_locations(
    raw_location: str,
    description_text: Optional[str] = None,
    infer_remote_scope: bool = True
) -> List[Dict]:
    """
    Extract structured locations from a raw location string.

    This is the main entry point for location extraction. It:
    1. Checks for working arrangement terms (Hybrid, Remote, In-Office)
    2. Splits multi-location strings
    3. Matches each part against patterns (remote, city, country, region)
    4. Infers remote scope from co-located cities if applicable
    5. Returns a list of location objects

    Args:
        raw_location: Raw location string from job posting
        description_text: Optional job description for additional context
        infer_remote_scope: Whether to infer remote scope from co-located cities

    Returns:
        List of location objects. Returns [{"type": "unknown"}] if no match found.

    Examples:
        >>> extract_locations("London, UK")
        [{"type": "city", "country_code": "GB", "city": "london"}]

        >>> extract_locations("Remote - US")
        [{"type": "remote", "scope": "country", "country_code": "US"}]

        >>> extract_locations("NYC or Remote")
        [
            {"type": "city", "country_code": "US", "city": "new_york"},
            {"type": "remote", "scope": "country", "country_code": "US"}
        ]

        >>> extract_locations("Hybrid")
        [{"type": "unknown"}]  # Working arrangement, not a location
    """
    if not raw_location or not raw_location.strip():
        return [{"type": "unknown"}]

    # Early check: is the entire string just a working arrangement term?
    arrangement = check_working_arrangement_term(raw_location)
    if arrangement is not None:
        if arrangement:  # Remote type
            return [arrangement]
        else:  # Empty dict = arrangement term but not location (Hybrid, In-Office)
            return [{"type": "unknown"}]

    config = load_location_config()
    locations: List[Dict] = []

    # Early check: try matching the FULL string against country-specific remote patterns
    # BEFORE splitting. This catches "Remote - US" which would otherwise be split into
    # ["Remote", "US"] and incorrectly classified as global remote + country.
    # Only return early if the remote pattern covers most of the string (>50% of length),
    # to avoid matching substrings in multi-location strings like "NYC; Remote, US".
    full_text_lower = raw_location.lower().strip()
    remote_match, matched_pattern = _match_remote_pattern_with_info(full_text_lower, config)
    if remote_match and remote_match.get("scope") != "global" and matched_pattern:
        # Only return early if pattern covers >50% of the string
        coverage = len(matched_pattern) / len(full_text_lower)
        if coverage > 0.5:
            return [remote_match]

    # Split into parts if multi-location
    parts = split_multi_location(raw_location)

    # Track cities found (for inferring remote scope)
    cities_found: List[Dict] = []

    for part in parts:
        text = part.lower().strip()

        if not text:
            continue

        # Try matching in order of specificity
        # 1. Check remote patterns first (most specific patterns like "Remote - US")
        remote_match = match_remote_pattern(text, config)
        if remote_match:
            locations.append(remote_match)
            continue

        # 2. Check city patterns
        city_match = match_city_pattern(text, config)
        if city_match:
            locations.append(city_match)
            cities_found.append(city_match)
            continue

        # 3. Check country patterns (standalone country mentions)
        country_match = match_country_pattern(text, config)
        if country_match:
            locations.append(country_match)
            continue

        # 4. Check region patterns
        region_match = match_region_pattern(text, config)
        if region_match:
            locations.append(region_match)
            continue

    # Infer remote scope from co-located cities
    if infer_remote_scope and cities_found:
        for i, loc in enumerate(locations):
            if loc.get("type") == "remote" and loc.get("scope") == "global":
                # If we have a global remote and a city, infer scope from city
                # e.g., "NYC or Remote" -> Remote should be US scope
                inferred_country = cities_found[0].get("country_code")
                if inferred_country:
                    locations[i] = {
                        "type": "remote",
                        "scope": "country",
                        "country_code": inferred_country
                    }

    # Deduplicate locations (same location mentioned multiple ways)
    locations = _deduplicate_locations(locations)

    # If no locations found, return unknown
    if not locations:
        return [{"type": "unknown"}]

    return locations


def _deduplicate_locations(locations: List[Dict]) -> List[Dict]:
    """
    Remove duplicate locations from the list.

    Args:
        locations: List of location objects

    Returns:
        Deduplicated list of locations
    """
    seen = set()
    result = []

    for loc in locations:
        # Create a hashable key from the location
        key_parts = [loc.get("type", "")]
        if "country_code" in loc:
            key_parts.append(loc["country_code"])
        if "city" in loc:
            key_parts.append(loc["city"])
        if "region" in loc:
            key_parts.append(loc["region"])
        if "scope" in loc:
            key_parts.append(loc["scope"])

        key = tuple(key_parts)

        if key not in seen:
            seen.add(key)
            result.append(loc)

    return result


# =============================================================================
# Utility Functions
# =============================================================================

def is_location_match(
    raw_location: str,
    target_cities: Optional[List[str]] = None,
    target_countries: Optional[List[str]] = None,
    include_remote: bool = True
) -> bool:
    """
    Check if a raw location string matches target cities/countries.

    Useful for pre-filtering jobs before expensive operations.

    Args:
        raw_location: Raw location string
        target_cities: List of city keys to match (e.g., ["london", "new_york"])
        target_countries: List of country codes to match (e.g., ["GB", "US"])
        include_remote: Whether to include remote jobs in matches

    Returns:
        True if location matches any target, False otherwise
    """
    locations = extract_locations(raw_location)

    for loc in locations:
        loc_type = loc.get("type")

        # Check remote
        if loc_type == "remote" and include_remote:
            # If we have target countries, check remote scope
            if target_countries:
                remote_country = loc.get("country_code")
                if remote_country and remote_country in target_countries:
                    return True
                # Global remote matches any country
                if loc.get("scope") == "global":
                    return True
            else:
                # No country filter, any remote matches
                return True

        # Check city
        if loc_type == "city":
            city = loc.get("city")
            country = loc.get("country_code")

            if target_cities and city in target_cities:
                return True
            if target_countries and country in target_countries:
                return True

        # Check country
        if loc_type == "country":
            country = loc.get("country_code")
            if target_countries and country in target_countries:
                return True

    return False


def get_active_cities() -> List[str]:
    """
    Get list of active city keys from config.

    Returns:
        List of active city keys (e.g., ["london", "new_york", "denver"])
    """
    config = load_location_config()
    return config.get("active_cities", [])


def get_legacy_city_code_mapping() -> Dict[str, Dict]:
    """
    Get mapping from legacy city codes to new location objects.

    Returns:
        Dict mapping city_code -> location object
    """
    config = load_location_config()
    return config.get("legacy_city_codes", {})


# =============================================================================
# Module Test
# =============================================================================

if __name__ == "__main__":
    # Quick test of the module
    test_cases = [
        "London, UK",
        "San Francisco, CA",
        "Singapore",
        "NYC",
        "Denver, Colorado",
        "Remote",
        "Remote - US",
        "Remote - UK",
        "Remote - EMEA",
        "NYC or Remote",
        "London or Stockholm",
        "San Francisco / Remote",
        "Bay Area",
        "Work from home",
        "Anywhere",
        "",
        "Unknown Location XYZ",
    ]

    print("Location Extractor Test")
    print("=" * 60)

    for test in test_cases:
        result = extract_locations(test)
        print(f"\n'{test}'")
        print(f"  -> {result}")

    print("\n" + "=" * 60)
    print("Active cities:", get_active_cities())
