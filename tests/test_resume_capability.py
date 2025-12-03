"""
Test resume capability - skip recently processed companies

This test validates:
1. Companies processed recently are detected
2. Resume mode skips those companies
3. Only unprocessed companies are scraped
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.fetch_jobs import process_greenhouse_incremental, get_recently_processed_companies


async def test_resume_capability():
    """Test resume capability with recent processing window"""

    print("="*80)
    print("TESTING RESUME CAPABILITY")
    print("="*80)

    # First, check what companies were processed recently
    print("\n[Step 1] Checking recently processed companies (24 hour window)...")
    recent_companies = await get_recently_processed_companies(hours=24)

    if recent_companies:
        print(f"Found {len(recent_companies)} companies processed in last 24 hours:")
        for company in sorted(recent_companies):
            print(f"  - {company}")
    else:
        print("No companies processed in last 24 hours")

    # Test 1: Run with resume disabled (should process all 3 companies)
    print("\n" + "="*80)
    print("[TEST 1] Resume DISABLED - Process all companies")
    print("="*80)
    test_companies = ['stripe', 'figma', 'monzo']
    stats1 = await process_greenhouse_incremental(test_companies, resume_hours=0)

    print("\n[Test 1] Results:")
    print(f"  - Companies processed: {stats1['companies_processed']}")
    print(f"  - Companies skipped: {stats1['companies_skipped']}")

    # Test 2: Run immediately with resume enabled (should skip all 3 companies)
    print("\n" + "="*80)
    print("[TEST 2] Resume ENABLED (1 hour window) - Should skip all")
    print("="*80)
    stats2 = await process_greenhouse_incremental(test_companies, resume_hours=1)

    print("\n[Test 2] Results:")
    print(f"  - Companies processed: {stats2['companies_processed']}")
    print(f"  - Companies skipped: {stats2['companies_skipped']}")

    # Validation
    print("\n" + "="*80)
    print("VALIDATION")
    print("="*80)

    success = True

    # Test 1: Should process all companies (unless already in DB from previous tests)
    if stats1['companies_processed'] + stats1['companies_skipped'] != 3:
        print(f"FAIL [Test 1]: Expected 3 total companies, got {stats1['companies_processed'] + stats1['companies_skipped']}")
        success = False
    else:
        print(f"PASS [Test 1]: Handled all 3 companies")

    # Test 2: Should skip all companies (just processed in Test 1)
    if stats2['companies_skipped'] != 3:
        print(f"FAIL [Test 2]: Expected 3 skipped, got {stats2['companies_skipped']}")
        success = False
    else:
        print(f"PASS [Test 2]: Skipped all 3 recently processed companies")

    if stats2['companies_processed'] != 0:
        print(f"FAIL [Test 2]: Expected 0 processed, got {stats2['companies_processed']}")
        success = False
    else:
        print(f"PASS [Test 2]: Did not re-process recent companies")

    print("\n" + "="*80)
    if success:
        print("ALL TESTS PASSED - Resume capability working!")
    else:
        print("TESTS FAILED - See errors above")
    print("="*80)

    return success


if __name__ == "__main__":
    success = asyncio.run(test_resume_capability())
    sys.exit(0 if success else 1)
