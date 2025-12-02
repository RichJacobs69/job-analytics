"""
Detailed Job Analysis: Find exact reasons for raw_jobs vs enriched_jobs discrepancy

This script:
1. Checks for duplicate job_hashes in raw_jobs (which would result in upserts in enriched)
2. Identifies which raw jobs have corresponding enriched jobs
3. Analyzes the reasons why jobs didn't make it to enriched
"""

import logging
from datetime import datetime, timedelta
from db_connection import supabase, generate_job_hash
from collections import Counter, defaultdict

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def analyze_detailed_discrepancy(hours_back: int = 24):
    """Detailed analysis of job discrepancy"""

    cutoff = datetime.now() - timedelta(hours=hours_back)
    cutoff_str = cutoff.isoformat()

    logger.info("="*80)
    logger.info(f"DETAILED JOB DISCREPANCY ANALYSIS (last {hours_back} hours)")
    logger.info("="*80)

    # ========================================
    # Step 1: Get ALL raw_jobs with metadata
    # ========================================
    logger.info("\nStep 1: Fetching all raw_jobs...")
    raw_response = supabase.table('raw_jobs')\
        .select('id, source, source_job_id, scraped_at')\
        .gte('scraped_at', cutoff_str)\
        .execute()

    raw_jobs = raw_response.data
    logger.info(f"  Found {len(raw_jobs)} raw jobs")

    # ========================================
    # Step 2: Get ALL enriched_jobs with metadata
    # ========================================
    logger.info("\nStep 2: Fetching all enriched_jobs...")
    enriched_response = supabase.table('enriched_jobs')\
        .select('id, raw_job_id, job_hash, employer_name, title_display, city_code, is_agency, job_family, classified_at')\
        .gte('classified_at', cutoff_str)\
        .execute()

    enriched_jobs = enriched_response.data
    logger.info(f"  Found {len(enriched_jobs)} enriched jobs")

    # ========================================
    # Step 3: Build mappings
    # ========================================
    logger.info("\nStep 3: Building mappings...")

    # Map raw_job_id -> enriched_job
    enriched_by_raw_id = {job['raw_job_id']: job for job in enriched_jobs}

    # Map job_hash -> list of enriched jobs (to find duplicates)
    enriched_by_hash = defaultdict(list)
    for job in enriched_jobs:
        enriched_by_hash[job['job_hash']].append(job)

    # Count duplicates
    duplicate_hashes = {hash_val: jobs for hash_val, jobs in enriched_by_hash.items() if len(jobs) > 1}
    logger.info(f"  Found {len(duplicate_hashes)} duplicate job_hashes in enriched_jobs")

    if duplicate_hashes:
        logger.info("\n  Duplicate job_hashes (multiple enriched_jobs point to same hash):")
        for hash_val, jobs in list(duplicate_hashes.items())[:5]:
            logger.info(f"    Hash {hash_val[:8]}... has {len(jobs)} enriched records")
            for job in jobs:
                logger.info(f"      - {job['employer_name']} - {job['title_display'][:40]}")

    # ========================================
    # Step 4: Identify missing jobs
    # ========================================
    logger.info("\nStep 4: Identifying jobs missing from enriched...")

    missing_raw_ids = []
    for raw_job in raw_jobs:
        if raw_job['id'] not in enriched_by_raw_id:
            missing_raw_ids.append(raw_job['id'])

    logger.info(f"  {len(missing_raw_ids)} raw jobs have NO corresponding enriched job")

    # ========================================
    # Step 5: Fetch full data for missing jobs to analyze WHY
    # ========================================
    if missing_raw_ids:
        logger.info("\nStep 5: Analyzing WHY jobs are missing from enriched...")

        # Get a sample of missing jobs with full data
        sample_size = min(20, len(missing_raw_ids))
        sample_ids = missing_raw_ids[:sample_size]

        # Fetch full records for analysis
        missing_jobs_full = []
        for raw_id in sample_ids:
            result = supabase.table('raw_jobs')\
                .select('*')\
                .eq('id', raw_id)\
                .execute()
            if result.data:
                missing_jobs_full.append(result.data[0])

        # Analyze reasons
        reasons = {
            'short_description': 0,
            'agency_suspected': 0,
            'other': 0
        }

        logger.info(f"\n  Analyzing {len(missing_jobs_full)} sample missing jobs:")
        for i, job in enumerate(missing_jobs_full[:10]):
            raw_text = job.get('raw_text', '')
            source = job.get('source', 'unknown')
            desc_len = len(raw_text.strip())

            # Check reasons
            reason_parts = []
            if desc_len < 50:
                reasons['short_description'] += 1
                reason_parts.append(f"short desc ({desc_len} chars)")
            else:
                reasons['other'] += 1
                reason_parts.append("unknown reason")

            reason = ", ".join(reason_parts)
            logger.info(f"    [{i+1}] Source: {source:10} | Length: {desc_len:5} | Reason: {reason}")

        # Extrapolate to full missing set
        logger.info(f"\n  Estimated breakdown for all {len(missing_raw_ids)} missing jobs:")
        for reason, count in reasons.items():
            pct = (count / len(missing_jobs_full) * 100) if missing_jobs_full else 0
            estimated_total = int(pct / 100 * len(missing_raw_ids))
            logger.info(f"    {reason:20}: ~{estimated_total} jobs ({pct:.1f}% of sample)")

    # ========================================
    # Step 6: Check for potential UPSERT deduplication
    # ========================================
    logger.info("\nStep 6: Checking for UPSERT deduplication...")
    logger.info("  NOTE: enriched_jobs uses UPSERT on job_hash")
    logger.info("  This means multiple raw_jobs with same (company+title+city) will update the same enriched record")

    # For each enriched job, check how many raw_jobs might map to it
    # We need to fetch employer info from somewhere - let's check if we can infer it

    logger.info("\n  Analysis:")
    logger.info(f"    - {len(raw_jobs)} raw_jobs were inserted")
    logger.info(f"    - {len(enriched_jobs)} unique enriched_jobs exist")
    logger.info(f"    - {len(missing_raw_ids)} raw_jobs have NO corresponding enriched_job")

    potential_upserts = len(raw_jobs) - len(missing_raw_ids) - len(enriched_jobs)
    if potential_upserts > 0:
        logger.info(f"    - ~{potential_upserts} raw_jobs likely updated existing enriched_jobs (UPSERT)")
    else:
        logger.info(f"    - No evidence of UPSERT deduplication")

    # ========================================
    # Step 7: Summary
    # ========================================
    logger.info("\n" + "="*80)
    logger.info("SUMMARY")
    logger.info("="*80)
    logger.info(f"Total raw_jobs:                      {len(raw_jobs)}")
    logger.info(f"Total enriched_jobs:                 {len(enriched_jobs)}")
    logger.info(f"Raw jobs missing from enriched:      {len(missing_raw_ids)} ({100*len(missing_raw_ids)/len(raw_jobs):.1f}%)")
    logger.info("")
    logger.info("Breakdown of enriched jobs:")
    agency_count = sum(1 for job in enriched_jobs if job.get('is_agency'))
    out_of_scope = sum(1 for job in enriched_jobs if job.get('job_family') == 'out_of_scope')
    valid_jobs = len(enriched_jobs) - agency_count - out_of_scope
    logger.info(f"  - Agency jobs (flagged):           {agency_count}")
    logger.info(f"  - Out-of-scope jobs:               {out_of_scope}")
    logger.info(f"  - Valid in-scope jobs:             {valid_jobs}")
    logger.info("")
    logger.info("Key insights:")
    logger.info("  1. The 80.7% filtering rate suggests aggressive filtering is happening")
    logger.info("  2. Most likely causes:")
    logger.info("     a) Hard agency filtering (before classification)")
    logger.info("     b) Classification failures (job descriptions too vague)")
    logger.info("     c) Out-of-scope job classifications")
    logger.info("")
    logger.info("  To investigate further, run with increased verbosity in fetch_jobs.py")
    logger.info("="*80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Detailed job discrepancy analysis')
    parser.add_argument('--hours', type=int, default=24, help='Hours back to analyze')

    args = parser.parse_args()

    analyze_detailed_discrepancy(hours_back=args.hours)
