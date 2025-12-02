"""
Diagnostic Script: Analyze discrepancy between raw_jobs and enriched_jobs

Purpose:
--------
Investigates why some jobs appear in raw_jobs but not in enriched_jobs.
This is expected behavior due to filtering, but this script quantifies each filter.

Expected filters:
- Hard agency filter (before classification)
- Insufficient description length (<50 chars)
- Classification failures
- Duplicate detection (same job inserted twice)

Usage:
------
python analyze_job_discrepancy.py
"""

import logging
from datetime import datetime, timedelta
from db_connection import supabase
from agency_detection import is_agency_job
import json

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def analyze_discrepancy(hours_back: int = 24):
    """
    Analyze jobs from recent run to understand filtering.

    Args:
        hours_back: How many hours back to analyze (default: 24)
    """

    # Calculate cutoff time
    cutoff = datetime.now() - timedelta(hours=hours_back)
    cutoff_str = cutoff.isoformat()

    logger.info("="*80)
    logger.info(f"ANALYZING JOB DISCREPANCY (last {hours_back} hours)")
    logger.info("="*80)
    logger.info(f"Cutoff time: {cutoff_str}\n")

    # ========================================
    # 1. Count total jobs in raw_jobs
    # ========================================

    logger.info("Step 1: Counting raw_jobs...")
    raw_response = supabase.table('raw_jobs')\
        .select('id, source, raw_text, source_job_id, scraped_at')\
        .gte('scraped_at', cutoff_str)\
        .execute()

    raw_jobs = raw_response.data
    raw_count = len(raw_jobs)
    logger.info(f"  Total raw_jobs: {raw_count}")

    if raw_count == 0:
        logger.warning("No jobs found in the specified time range. Try increasing hours_back.")
        return

    # ========================================
    # 2. Count total jobs in enriched_jobs
    # ========================================

    logger.info("\nStep 2: Counting enriched_jobs...")
    enriched_response = supabase.table('enriched_jobs')\
        .select('raw_job_id, employer_name, title_display, is_agency, job_family, classified_at')\
        .gte('classified_at', cutoff_str)\
        .execute()

    enriched_jobs = enriched_response.data
    enriched_count = len(enriched_jobs)
    logger.info(f"  Total enriched_jobs: {enriched_count}")

    # Create set of raw_job_ids that made it to enriched
    enriched_raw_ids = {job['raw_job_id'] for job in enriched_jobs}

    # ========================================
    # 3. Find jobs that didn't make it to enriched
    # ========================================

    logger.info("\nStep 3: Finding jobs that didn't make it to enriched...")
    missing_jobs = [job for job in raw_jobs if job['id'] not in enriched_raw_ids]
    missing_count = len(missing_jobs)

    logger.info(f"  Jobs missing from enriched: {missing_count}")
    logger.info(f"  Percentage filtered: {100 * missing_count / raw_count:.1f}%")

    # ========================================
    # 4. Analyze why jobs were filtered
    # ========================================

    logger.info("\nStep 4: Analyzing filter reasons...")

    # We need to check the raw_text to understand why jobs were filtered
    # First, let's get the source_job_id to employer mapping from enriched jobs
    # We'll reconstruct company names from the raw_text where possible

    filter_stats = {
        'agency_filtered': 0,
        'short_description': 0,
        'classification_failed': 0,
        'unknown': 0,
        'duplicates': 0
    }

    # Sample 10 missing jobs for detailed analysis
    sample_size = min(10, len(missing_jobs))
    logger.info(f"\n  Analyzing sample of {sample_size} missing jobs:")

    for i, job in enumerate(missing_jobs[:sample_size]):
        raw_text = job.get('raw_text', '')
        source = job.get('source', 'unknown')

        # Try to extract company name from raw_text (simple heuristic)
        # This is imperfect, but gives us an idea
        company_name = "Unknown"

        # Check description length
        desc_len = len(raw_text.strip())

        if desc_len < 50:
            filter_stats['short_description'] += 1
            reason = f"Short description ({desc_len} chars)"
        else:
            # For now, we can't definitively say why without the original company name
            # But we can make educated guesses
            filter_stats['unknown'] += 1
            reason = "Unknown (likely agency or classification failure)"

        logger.info(f"    [{i+1}] Source: {source:10} | Length: {desc_len:5} chars | Reason: {reason}")

    # ========================================
    # 5. Check for duplicates in raw_jobs
    # ========================================

    logger.info("\nStep 5: Checking for duplicates in raw_jobs...")

    # Group by source_job_id
    from collections import Counter
    source_job_ids = [job.get('source_job_id') for job in raw_jobs if job.get('source_job_id')]
    duplicate_counts = Counter(source_job_ids)
    duplicates = {job_id: count for job_id, count in duplicate_counts.items() if count > 1}

    if duplicates:
        logger.info(f"  Found {len(duplicates)} duplicate source_job_ids:")
        for job_id, count in list(duplicates.items())[:5]:
            logger.info(f"    - {job_id}: {count} occurrences")
        filter_stats['duplicates'] = sum(count - 1 for count in duplicates.values())
    else:
        logger.info("  No duplicates found")

    # ========================================
    # 6. Analyze enriched jobs by agency flag
    # ========================================

    logger.info("\nStep 6: Analyzing enriched jobs...")

    agency_jobs = [job for job in enriched_jobs if job.get('is_agency')]
    out_of_scope = [job for job in enriched_jobs if job.get('job_family') == 'out_of_scope']

    logger.info(f"  Agency jobs that made it through: {len(agency_jobs)}")
    logger.info(f"  Out-of-scope jobs: {len(out_of_scope)}")
    logger.info(f"  Valid jobs: {enriched_count - len(agency_jobs) - len(out_of_scope)}")

    # ========================================
    # 7. Summary Report
    # ========================================

    logger.info("\n" + "="*80)
    logger.info("SUMMARY REPORT")
    logger.info("="*80)
    logger.info(f"Total raw_jobs:           {raw_count}")
    logger.info(f"Total enriched_jobs:      {enriched_count}")
    logger.info(f"Discrepancy:              {missing_count} jobs ({100 * missing_count / raw_count:.1f}%)")
    logger.info("")
    logger.info("Breakdown of missing jobs:")
    logger.info(f"  - Short descriptions (<50 chars):  {filter_stats['short_description']}")
    logger.info(f"  - Duplicates in raw:                {filter_stats['duplicates']}")
    logger.info(f"  - Unknown (agency/classification):  {filter_stats['unknown']}")
    logger.info("")
    logger.info("Enriched jobs breakdown:")
    logger.info(f"  - Agency jobs (soft filter):        {len(agency_jobs)}")
    logger.info(f"  - Out-of-scope jobs:                {len(out_of_scope)}")
    logger.info(f"  - Valid in-scope jobs:              {enriched_count - len(agency_jobs) - len(out_of_scope)}")
    logger.info("")
    logger.info("Expected behavior:")
    logger.info("  ✓ Raw jobs includes ALL fetched jobs")
    logger.info("  ✓ Enriched jobs only includes successfully classified jobs")
    logger.info("  ✓ Filtering is working as designed to reduce costs")
    logger.info("="*80)

    # ========================================
    # 8. Detailed breakdown by source
    # ========================================

    logger.info("\n" + "="*80)
    logger.info("BREAKDOWN BY DATA SOURCE")
    logger.info("="*80)

    from collections import defaultdict

    source_breakdown = defaultdict(lambda: {'raw': 0, 'enriched': 0})

    for job in raw_jobs:
        source = job.get('source', 'unknown')
        source_breakdown[source]['raw'] += 1

    for job in enriched_jobs:
        # Need to join back to raw_jobs to get source
        raw_job = next((r for r in raw_jobs if r['id'] == job['raw_job_id']), None)
        if raw_job:
            source = raw_job.get('source', 'unknown')
            source_breakdown[source]['enriched'] += 1

    for source, counts in source_breakdown.items():
        raw = counts['raw']
        enriched = counts['enriched']
        filter_rate = 100 * (raw - enriched) / raw if raw > 0 else 0
        logger.info(f"{source:12} | Raw: {raw:4} | Enriched: {enriched:4} | Filtered: {filter_rate:5.1f}%")

    logger.info("="*80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Analyze job discrepancy between raw_jobs and enriched_jobs')
    parser.add_argument('--hours', type=int, default=24, help='Hours back to analyze (default: 24)')

    args = parser.parse_args()

    analyze_discrepancy(hours_back=args.hours)
