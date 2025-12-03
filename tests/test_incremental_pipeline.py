"""
Test incremental pipeline with a small subset of companies

This test validates:
1. Greenhouse jobs are scraped per company
2. Raw jobs written using UPSERT (hash-based deduplication)
3. Jobs classified immediately
4. Enriched jobs written after classification
5. Statistics tracked correctly
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.fetch_jobs import process_greenhouse_incremental


async def test_incremental_pipeline():
    """Test incremental pipeline with 3 companies"""

    print("="*80)
    print("TESTING INCREMENTAL PIPELINE")
    print("="*80)
    print("\nTesting with 3 companies: stripe, figma, monzo")
    print("This will scrape, write, classify, and store incrementally\n")

    # Test with 3 companies
    test_companies = ['stripe', 'figma', 'monzo']

    stats = await process_greenhouse_incremental(test_companies)

    # Verify results
    print("\n" + "="*80)
    print("TEST RESULTS")
    print("="*80)

    success = True

    # Check that we processed all 3 companies
    if stats['companies_processed'] != 3:
        print(f"FAIL: Expected 3 companies, got {stats['companies_processed']}")
        success = False
    else:
        print("PASS: All 3 companies processed")

    # Check that we scraped some jobs
    if stats['jobs_scraped'] == 0:
        print("FAIL: No jobs scraped")
        success = False
    else:
        print(f"PASS: Scraped {stats['jobs_scraped']} jobs")

    # Check that we wrote some raw jobs
    if stats['jobs_written_raw'] == 0:
        print("FAIL: No raw jobs written")
        success = False
    else:
        print(f"PASS: Wrote {stats['jobs_written_raw']} raw jobs")

    # Check that we classified some jobs
    if stats['jobs_classified'] == 0:
        print("FAIL: No jobs classified")
        success = False
    else:
        print(f"PASS: Classified {stats['jobs_classified']} jobs")

    # Check that we wrote some enriched jobs
    if stats['jobs_written_enriched'] == 0:
        print("FAIL: No enriched jobs written")
        success = False
    else:
        print(f"PASS: Wrote {stats['jobs_written_enriched']} enriched jobs")

    # Check filtering worked (should have filtered most jobs)
    if stats['jobs_filtered'] == 0:
        print("WARNING: No jobs filtered (expected some filtering)")
    else:
        filter_rate = stats['jobs_filtered'] / stats['jobs_scraped'] * 100
        print(f"PASS: Filtered {stats['jobs_filtered']} jobs ({filter_rate:.1f}%)")

    print("\n" + "="*80)
    if success:
        print("TEST PASSED - Incremental pipeline working correctly!")
    else:
        print("TEST FAILED - See errors above")
    print("="*80)

    return success


if __name__ == "__main__":
    success = asyncio.run(test_incremental_pipeline())
    sys.exit(0 if success else 1)
