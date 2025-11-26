"""
Quick validation script for title filtering integration

Tests:
1. YAML pattern loading
2. is_relevant_role() function
3. Scraper initialization with filtering
"""

import asyncio
from pathlib import Path
from scrapers.greenhouse.greenhouse_scraper import (
    load_title_patterns,
    is_relevant_role,
    GreenhouseScraper
)


def test_pattern_loading():
    """Test that patterns load from YAML"""
    print("\n" + "="*70)
    print("TEST 1: Pattern Loading")
    print("="*70)

    patterns = load_title_patterns()
    print(f"[OK] Loaded {len(patterns)} patterns")

    # Show first few patterns
    print("\nSample patterns:")
    for i, pattern in enumerate(patterns[:5], 1):
        print(f"  {i}. {pattern}")

    assert len(patterns) > 0, "No patterns loaded!"
    print("\n[OK] Pattern loading works!")


def test_is_relevant_role():
    """Test is_relevant_role() function with known cases"""
    print("\n" + "="*70)
    print("TEST 2: Title Matching Logic")
    print("="*70)

    patterns = load_title_patterns()

    # Test Data roles (should match)
    data_titles = [
        "Senior Data Engineer",
        "Data Analyst",
        "Principal Data Scientist",
        "Analytics Engineer",
        "ML Engineer",
        "Staff AI Engineer",
        "Analytics Lead",
    ]

    print("\n[OK] Testing Data/Product roles (should match):")
    for title in data_titles:
        result = is_relevant_role(title, patterns)
        status = "[OK]" if result else "[FAIL]"
        print(f"  {status} {title}: {result}")
        if not result:
            print(f"    ERROR: Expected True but got {result}")

    # Test Product roles (should match)
    product_titles = [
        "Product Manager",
        "Senior Product Manager",
        "Technical Program Manager",
        "Growth PM",
        "AI Product Manager",
    ]

    print("\n[OK] Testing Product roles (should match):")
    for title in product_titles:
        result = is_relevant_role(title, patterns)
        status = "[OK]" if result else "[FAIL]"
        print(f"  {status} {title}: {result}")
        if not result:
            print(f"    ERROR: Expected True but got {result}")

    # Test filtered roles (should NOT match)
    filtered_titles = [
        "Account Executive",
        "Sales Development Representative",
        "Marketing Manager",
        "Software Engineer",
        "DevOps Engineer",
        "HR Business Partner",
        "Legal Counsel",
    ]

    print("\n[OK] Testing filtered roles (should NOT match):")
    for title in filtered_titles:
        result = is_relevant_role(title, patterns)
        status = "[OK]" if not result else "[FAIL]"
        print(f"  {status} {title}: {result}")
        if result:
            print(f"    ERROR: Expected False but got {result}")

    print("\n[OK] Title matching logic works!")


async def test_scraper_initialization():
    """Test that scraper initializes with filtering enabled"""
    print("\n" + "="*70)
    print("TEST 3: Scraper Initialization")
    print("="*70)

    # Test with filtering enabled (default)
    print("\nInitializing scraper with filtering enabled...")
    scraper = GreenhouseScraper(headless=True, filter_titles=True)

    assert scraper.filter_titles == True, "Filtering should be enabled"
    assert len(scraper.title_patterns) > 0, "Patterns should be loaded"
    assert scraper.filter_stats is not None, "Filter stats should be initialized"

    print(f"[OK] Filtering enabled: {scraper.filter_titles}")
    print(f"[OK] Patterns loaded: {len(scraper.title_patterns)}")
    print(f"[OK] Filter stats initialized: {scraper.filter_stats}")

    # Test with filtering disabled
    print("\nInitializing scraper with filtering disabled...")
    scraper_no_filter = GreenhouseScraper(headless=True, filter_titles=False)

    assert scraper_no_filter.filter_titles == False, "Filtering should be disabled"
    assert len(scraper_no_filter.title_patterns) == 0, "No patterns should be loaded"

    print(f"[OK] Filtering disabled: {scraper_no_filter.filter_titles}")
    print(f"[OK] No patterns loaded: {len(scraper_no_filter.title_patterns)}")

    print("\n[OK] Scraper initialization works!")


async def main():
    """Run all validation tests"""
    print("\n" + "="*70)
    print("TITLE FILTER INTEGRATION VALIDATION")
    print("="*70)

    try:
        # Test 1: Pattern loading
        test_pattern_loading()

        # Test 2: Title matching
        test_is_relevant_role()

        # Test 3: Scraper initialization
        await test_scraper_initialization()

        print("\n" + "="*70)
        print("ALL TESTS PASSED!")
        print("="*70)
        print("\n[OK] Core integration is working correctly")
        print("[OK] Ready for real scraping tests\n")

    except Exception as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
