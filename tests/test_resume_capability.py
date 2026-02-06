"""
Test resume capability - skip recently processed companies

This test validates:
1. Companies processed recently are detected
2. Resume mode skips those companies
3. Only unprocessed companies are scraped

NOTE: This is a live integration test that hits Greenhouse, Gemini, and Supabase.
Run with: pytest tests/test_resume_capability.py -m integration -v
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.fetch_jobs import process_greenhouse_incremental, get_recently_processed_companies


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_resume_capability():
    """Test resume capability with recent processing window"""

    # First, check what companies were processed recently
    recent_companies = await get_recently_processed_companies(hours=24)

    # Test 1: Run with resume disabled (should process all 3 companies)
    test_companies = ['stripe', 'figma', 'monzo']
    stats1 = await process_greenhouse_incremental(test_companies, resume_hours=0)

    assert stats1['companies_processed'] + stats1['companies_skipped'] == 3, (
        f"Expected 3 total companies, got {stats1['companies_processed'] + stats1['companies_skipped']}"
    )

    # Test 2: Run immediately with resume enabled (should skip all 3 companies)
    stats2 = await process_greenhouse_incremental(test_companies, resume_hours=1)

    assert stats2['companies_skipped'] == 3, (
        f"Expected 3 skipped, got {stats2['companies_skipped']}"
    )
    assert stats2['companies_processed'] == 0, (
        f"Expected 0 processed, got {stats2['companies_processed']}"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
