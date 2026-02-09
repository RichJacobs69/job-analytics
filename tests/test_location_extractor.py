"""
Unit tests for location_extractor.py module

Tests the deterministic location extraction from raw location strings.
Part of: Global Location Expansion Epic - Phase 1
"""

import pytest
from pipeline.location_extractor import (
    extract_locations,
    is_location_match,
    get_active_cities,
    split_multi_location,
    match_city_pattern,
    match_remote_pattern,
    match_country_pattern,
    match_region_pattern,
    load_location_config,
)


# =============================================================================
# Configuration Tests
# =============================================================================

def test_load_location_config():
    """Test that location config loads successfully"""
    config = load_location_config()

    assert config is not None
    assert "cities" in config
    assert "countries" in config
    assert "regions" in config
    assert "remote_patterns" in config
    assert "active_cities" in config


def test_active_cities():
    """Test that active cities list is correct for Phase 1"""
    active = get_active_cities()

    # Phase 1 scope: London, NYC, Denver, San Francisco, Singapore
    expected = ["london", "new_york", "denver", "san_francisco", "singapore"]

    assert set(active) == set(expected)


# =============================================================================
# Simple City Tests
# =============================================================================

def test_simple_city_london():
    """Test: 'London' -> london, GB"""
    result = extract_locations("London")

    assert len(result) == 1
    assert result[0] == {
        "type": "city",
        "country_code": "GB",
        "city": "london"
    }


def test_simple_city_london_with_country():
    """Test: 'London, UK' -> london, GB"""
    result = extract_locations("London, UK")

    assert len(result) == 1
    assert result[0]["city"] == "london"
    assert result[0]["country_code"] == "GB"


def test_simple_city_new_york():
    """Test: 'New York' -> new_york, US"""
    result = extract_locations("New York")

    assert len(result) == 1
    assert result[0]["city"] == "new_york"
    assert result[0]["country_code"] == "US"


def test_simple_city_nyc():
    """Test: 'NYC' -> new_york, US"""
    result = extract_locations("NYC")

    assert len(result) == 1
    assert result[0]["city"] == "new_york"


def test_simple_city_san_francisco():
    """Test: 'San Francisco' -> san_francisco, US"""
    result = extract_locations("San Francisco")

    assert len(result) == 1
    assert result[0]["city"] == "san_francisco"
    assert result[0]["country_code"] == "US"


def test_simple_city_sf():
    """Test: 'SF' -> san_francisco, US"""
    result = extract_locations("SF")

    assert len(result) == 1
    assert result[0]["city"] == "san_francisco"


def test_simple_city_bay_area():
    """Test: 'Bay Area' -> san_francisco, US"""
    result = extract_locations("Bay Area")

    assert len(result) == 1
    assert result[0]["city"] == "san_francisco"


def test_simple_city_singapore():
    """Test: 'Singapore' -> singapore, SG"""
    result = extract_locations("Singapore")

    assert len(result) == 1
    assert result[0]["city"] == "singapore"
    assert result[0]["country_code"] == "SG"


def test_simple_city_denver():
    """Test: 'Denver, CO' -> denver, US"""
    result = extract_locations("Denver, CO")

    assert len(result) == 1
    assert result[0]["city"] == "denver"
    assert result[0]["country_code"] == "US"


# =============================================================================
# Remote Pattern Tests
# =============================================================================

def test_remote_global():
    """Test: 'Remote' -> global remote"""
    result = extract_locations("Remote")

    assert len(result) == 1
    assert result[0] == {
        "type": "remote",
        "scope": "global"
    }


def test_remote_fully_remote():
    """Test: 'Fully Remote' -> global remote"""
    result = extract_locations("Fully Remote")

    assert len(result) == 1
    assert result[0]["scope"] == "global"


def test_remote_work_from_anywhere():
    """Test: 'Work from anywhere' -> global remote"""
    result = extract_locations("Work from anywhere")

    assert len(result) == 1
    assert result[0]["type"] == "remote"
    assert result[0]["scope"] == "global"


def test_remote_us():
    """Test: 'Remote - US' -> US remote"""
    result = extract_locations("Remote - US")

    assert len(result) == 1
    assert result[0] == {
        "type": "remote",
        "scope": "country",
        "country_code": "US"
    }


def test_remote_uk():
    """Test: 'Remote - UK' -> GB remote"""
    result = extract_locations("Remote - UK")

    assert len(result) == 1
    assert result[0]["country_code"] == "GB"
    assert result[0]["scope"] == "country"


def test_remote_emea():
    """Test: 'Remote - EMEA' -> EMEA remote"""
    result = extract_locations("Remote - EMEA")

    assert len(result) == 1
    assert result[0] == {
        "type": "remote",
        "scope": "region",
        "region": "EMEA"
    }


def test_remote_apac():
    """Test: 'Remote - APAC' -> APAC remote"""
    result = extract_locations("Remote - APAC")

    assert len(result) == 1
    assert result[0]["scope"] == "region"
    assert result[0]["region"] == "APAC"


# =============================================================================
# Multi-Location Tests
# =============================================================================

def test_multi_location_or_separator():
    """Test: 'London or Denver' -> two cities"""
    result = extract_locations("London or Denver")

    assert len(result) == 2

    cities = [loc["city"] for loc in result]
    assert "london" in cities
    assert "denver" in cities


def test_multi_location_nyc_or_remote():
    """Test: 'NYC or Remote' -> NYC city + US remote (inferred)"""
    result = extract_locations("NYC or Remote")

    assert len(result) == 2

    # Should have NYC city
    city_locs = [loc for loc in result if loc["type"] == "city"]
    assert len(city_locs) == 1
    assert city_locs[0]["city"] == "new_york"

    # Should have US remote (inferred from NYC)
    remote_locs = [loc for loc in result if loc["type"] == "remote"]
    assert len(remote_locs) == 1
    assert remote_locs[0]["scope"] == "country"
    assert remote_locs[0]["country_code"] == "US"


def test_multi_location_slash_separator():
    """Test: 'San Francisco / Remote' -> SF + US remote"""
    result = extract_locations("San Francisco / Remote")

    assert len(result) == 2

    cities = [loc.get("city") for loc in result if loc["type"] == "city"]
    assert "san_francisco" in cities

    remote_locs = [loc for loc in result if loc["type"] == "remote"]
    assert len(remote_locs) == 1
    assert remote_locs[0]["country_code"] == "US"


def test_multi_location_semicolon_separator():
    """Test: 'London; Singapore' -> two cities"""
    result = extract_locations("London; Singapore")

    assert len(result) == 2
    cities = {loc["city"] for loc in result}
    assert cities == {"london", "singapore"}


def test_multi_location_pipe_separator():
    """Test: 'NYC | Denver' -> two cities"""
    result = extract_locations("NYC | Denver")

    assert len(result) == 2
    cities = {loc["city"] for loc in result}
    assert cities == {"new_york", "denver"}


# =============================================================================
# Edge Cases and Unknown Locations
# =============================================================================

def test_empty_string():
    """Test: empty string -> unknown"""
    result = extract_locations("")

    assert len(result) == 1
    assert result[0] == {"type": "unknown"}


def test_whitespace_only():
    """Test: whitespace only -> unknown"""
    result = extract_locations("   ")

    assert len(result) == 1
    assert result[0]["type"] == "unknown"


def test_unknown_location():
    """Test: unrecognized location -> unknown"""
    result = extract_locations("Mars Colony 7")

    assert len(result) == 1
    assert result[0]["type"] == "unknown"


def test_none_input():
    """Test: None input -> unknown"""
    result = extract_locations(None)

    assert len(result) == 1
    assert result[0]["type"] == "unknown"


# =============================================================================
# Deduplication Tests
# =============================================================================

def test_deduplication_same_city_twice():
    """Test: 'London or London, UK' -> single london"""
    result = extract_locations("London or London, UK")

    # Should deduplicate to single london
    assert len(result) == 1
    assert result[0]["city"] == "london"


def test_deduplication_sf_and_bay_area():
    """Test: 'SF or Bay Area' -> single san_francisco (both match same city)"""
    result = extract_locations("SF or Bay Area")

    # Both patterns match san_francisco, should deduplicate
    assert len(result) == 1
    assert result[0]["city"] == "san_francisco"


# =============================================================================
# Case Insensitivity Tests
# =============================================================================

def test_case_insensitive_lowercase():
    """Test: 'london' -> london, GB"""
    result = extract_locations("london")

    assert result[0]["city"] == "london"


def test_case_insensitive_uppercase():
    """Test: 'LONDON' -> london, GB"""
    result = extract_locations("LONDON")

    assert result[0]["city"] == "london"


def test_case_insensitive_mixed():
    """Test: 'LoNdOn' -> london, GB"""
    result = extract_locations("LoNdOn")

    assert result[0]["city"] == "london"


# =============================================================================
# Specific Pattern Variations Tests
# =============================================================================

def test_nyc_variations():
    """Test various NYC pattern variations"""
    variations = [
        "NYC",
        "New York",
        "New York, NY",
        "New York City",
        "Manhattan",
        "Brooklyn",
    ]

    for variant in variations:
        result = extract_locations(variant)
        assert len(result) == 1
        assert result[0]["city"] == "new_york", f"Failed for: {variant}"
        assert result[0]["country_code"] == "US"


def test_sf_variations():
    """Test various San Francisco pattern variations"""
    variations = [
        "San Francisco",
        "SF",
        "Bay Area",
        "San Francisco, CA",
        "Palo Alto",
        "Mountain View",
    ]

    for variant in variations:
        result = extract_locations(variant)
        assert len(result) == 1
        assert result[0]["city"] == "san_francisco", f"Failed for: {variant}"


def test_remote_variations():
    """Test various remote pattern variations"""
    global_variations = [
        "Remote",
        "Fully Remote",
        "100% Remote",
        "Work from home",
        "WFH",
        "Anywhere",
    ]

    for variant in global_variations:
        result = extract_locations(variant)
        assert len(result) == 1
        assert result[0]["type"] == "remote", f"Failed for: {variant}"
        assert result[0]["scope"] == "global", f"Wrong scope for: {variant}"


# =============================================================================
# Utility Function Tests
# =============================================================================

def test_is_location_match_city():
    """Test is_location_match for specific city"""
    assert is_location_match("London", target_cities=["london"]) is True
    assert is_location_match("NYC", target_cities=["new_york"]) is True
    assert is_location_match("Denver", target_cities=["london"]) is False


def test_is_location_match_country():
    """Test is_location_match for country"""
    assert is_location_match("London", target_countries=["GB"]) is True
    assert is_location_match("NYC", target_countries=["US"]) is True
    assert is_location_match("London", target_countries=["US"]) is False


def test_is_location_match_remote():
    """Test is_location_match with remote jobs"""
    # Include remote by default
    assert is_location_match("Remote", target_countries=["US"], include_remote=True) is True

    # Exclude remote
    assert is_location_match("Remote", target_countries=["US"], include_remote=False) is False

    # US remote matches US country filter
    assert is_location_match("Remote - US", target_countries=["US"], include_remote=True) is True


def test_split_multi_location():
    """Test split_multi_location helper function"""
    assert split_multi_location("London or NYC") == ["London", "NYC"]
    assert split_multi_location("SF / Remote") == ["SF", "Remote"]
    assert split_multi_location("London; Singapore") == ["London", "Singapore"]
    assert split_multi_location("Denver | NYC") == ["Denver", "NYC"]
    assert split_multi_location("London") == ["London"]


# =============================================================================
# Pattern Matching Function Tests
# =============================================================================

def test_match_city_pattern():
    """Test match_city_pattern function"""
    config = load_location_config()

    result = match_city_pattern("london", config)
    assert result is not None
    assert result["city"] == "london"

    result = match_city_pattern("xyz123", config)
    assert result is None


def test_match_remote_pattern():
    """Test match_remote_pattern function"""
    config = load_location_config()

    # Specific remote should match before global
    result = match_remote_pattern("remote - us", config)
    assert result is not None
    assert result["scope"] == "country"
    assert result["country_code"] == "US"

    # Generic remote
    result = match_remote_pattern("remote", config)
    assert result is not None
    assert result["scope"] == "global"


def test_match_country_pattern():
    """Test match_country_pattern function"""
    config = load_location_config()

    result = match_country_pattern("united states", config)
    assert result is not None
    assert result["country_code"] == "US"

    result = match_country_pattern("uk", config)
    assert result is not None
    assert result["country_code"] == "GB"


def test_match_region_pattern():
    """Test match_region_pattern function"""
    config = load_location_config()

    result = match_region_pattern("emea", config)
    assert result is not None
    assert result["region"] == "EMEA"

    result = match_region_pattern("asia pacific", config)
    assert result is not None
    assert result["region"] == "APAC"


# =============================================================================
# Integration Tests (Real-World Examples)
# =============================================================================

def test_real_world_greenhouse_locations():
    """Test real-world Greenhouse location patterns"""
    test_cases = [
        ("London, United Kingdom", "london", "GB"),
        ("New York, NY", "new_york", "US"),
        ("Remote", None, None),  # Global remote
        ("San Francisco, California", "san_francisco", "US"),
        ("Singapore, Singapore", "singapore", "SG"),
    ]

    for raw_loc, expected_city, expected_country in test_cases:
        result = extract_locations(raw_loc)
        assert len(result) >= 1, f"Failed for: {raw_loc}"

        if expected_city:
            assert result[0]["type"] == "city"
            assert result[0]["city"] == expected_city
            assert result[0]["country_code"] == expected_country
        else:
            assert result[0]["type"] == "remote"


def test_real_world_lever_locations():
    """Test real-world Lever location patterns"""
    test_cases = [
        "London",
        "New York, New York, United States",
        "Remote",
        "United States",  # Country-level
        "San Francisco Bay Area",
    ]

    for raw_loc in test_cases:
        result = extract_locations(raw_loc)
        # Just verify it doesn't crash and returns something
        assert len(result) >= 1
        assert "type" in result[0]


# =============================================================================
# Description-based Country Restriction Tests
# =============================================================================

def test_description_us_only_based_in():
    """Test: Location 'Remote' + description 'based in the United States'"""
    result = extract_locations(
        "Remote",
        description_text="This role is remote and based in the United States."
    )
    assert len(result) == 1
    assert result[0]["type"] == "remote"
    assert result[0]["scope"] == "country"
    assert result[0]["country_code"] == "US"


def test_description_us_only_eligible():
    """Test: Location 'Remote' + description 'eligible to work in the US'"""
    result = extract_locations(
        "Remote",
        description_text="You must be eligible to work in the U.S. for this position."
    )
    assert len(result) == 1
    assert result[0]["type"] == "remote"
    assert result[0]["scope"] == "country"
    assert result[0]["country_code"] == "US"


def test_description_us_only_must_be_located():
    """Test: Location 'Remote' + description 'must be located in the US'"""
    result = extract_locations(
        "Remote",
        description_text="Candidates must be located in the United States."
    )
    assert len(result) == 1
    assert result[0]["type"] == "remote"
    assert result[0]["scope"] == "country"
    assert result[0]["country_code"] == "US"


def test_description_canada_based():
    """Test: Location 'Remote' + description 'based in Canada'"""
    result = extract_locations(
        "Remote",
        description_text="This role is remote and based in Canada."
    )
    assert len(result) == 1
    assert result[0]["type"] == "remote"
    assert result[0]["scope"] == "country"
    assert result[0]["country_code"] == "CA"


def test_description_canada_only():
    """Test: Location 'Remote' + description 'Canada only'"""
    result = extract_locations(
        "Remote",
        description_text="This is a remote position, Canada only."
    )
    assert len(result) == 1
    assert result[0]["type"] == "remote"
    assert result[0]["scope"] == "country"
    assert result[0]["country_code"] == "CA"


def test_description_uk_based():
    """Test: Location 'Remote' + description 'based in the UK'"""
    result = extract_locations(
        "Remote",
        description_text="This position is remote and based in the UK."
    )
    assert len(result) == 1
    assert result[0]["type"] == "remote"
    assert result[0]["scope"] == "country"
    assert result[0]["country_code"] == "GB"


def test_description_india_based():
    """Test: Location 'Remote' + description 'based in India'"""
    result = extract_locations(
        "Remote",
        description_text="This role is remote and based in India."
    )
    assert len(result) == 1
    assert result[0]["type"] == "remote"
    assert result[0]["scope"] == "country"
    assert result[0]["country_code"] == "IN"


def test_description_work_from_anywhere_stays_global():
    """Test: Location 'Remote' + description 'work from anywhere' -> stays global"""
    result = extract_locations(
        "Remote",
        description_text="Work from anywhere in the world! We're a fully distributed team."
    )
    assert len(result) == 1
    assert result[0]["type"] == "remote"
    assert result[0]["scope"] == "global"


def test_description_no_restriction_stays_global():
    """Test: Location 'Remote' + description without country mention -> stays global"""
    result = extract_locations(
        "Remote",
        description_text="Join our engineering team! We build amazing products."
    )
    assert len(result) == 1
    assert result[0]["type"] == "remote"
    assert result[0]["scope"] == "global"


def test_description_empty_stays_global():
    """Test: Location 'Remote' + empty description -> stays global"""
    result = extract_locations("Remote", description_text="")
    assert len(result) == 1
    assert result[0]["type"] == "remote"
    assert result[0]["scope"] == "global"


def test_description_none_stays_global():
    """Test: Location 'Remote' + None description -> stays global"""
    result = extract_locations("Remote", description_text=None)
    assert len(result) == 1
    assert result[0]["type"] == "remote"
    assert result[0]["scope"] == "global"


def test_description_city_plus_remote_still_infers():
    """Test: Location 'NYC or Remote' with US description -> Remote is US-scoped"""
    # This tests that city inference works AND description doesn't override it incorrectly
    result = extract_locations(
        "NYC or Remote",
        description_text="Join us in New York or work remotely within the US."
    )
    assert len(result) == 2
    # First should be NYC city
    assert result[0]["type"] == "city"
    assert result[0]["city"] == "new_york"
    # Second should be US-scoped remote (inferred from city)
    assert result[1]["type"] == "remote"
    assert result[1]["scope"] == "country"
    assert result[1]["country_code"] == "US"


def test_description_already_scoped_not_overridden():
    """Test: Location 'Remote - US' is already scoped, description shouldn't change it"""
    result = extract_locations(
        "Remote - US",
        description_text="This role is based in Canada."  # Conflicting info
    )
    # Should match the explicit "Remote - US" pattern, not description
    assert len(result) == 1
    assert result[0]["type"] == "remote"
    assert result[0]["scope"] == "country"
    assert result[0]["country_code"] == "US"


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
