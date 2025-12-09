#!/usr/bin/env python3
"""
Delete jobs from raw_jobs and enriched_jobs that contain bot detection/challenge page text
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pipeline.db_connection import supabase

# Bot detection indicators
def is_bot_detection_page(raw_text: str) -> bool:
    """Check if text is a bot detection page (not a real job)"""
    if not raw_text:
        return False

    # More specific check: bot detection is typically short text with challenge keywords
    is_short = len(raw_text) < 500
    has_challenge = 'challenge-error' in raw_text.lower() or 'verify you are human' in raw_text.lower()
    has_js_warning = 'enable javascript and cookies' in raw_text.lower()

    return is_short and (has_challenge or has_js_warning)


def delete_bot_detection_jobs():
    """Delete bot detection jobs from both raw_jobs and enriched_jobs"""

    print("=" * 80)
    print("DELETING BOT DETECTION JOBS FROM DATABASE")
    print("=" * 80)
    print()

    # Step 1: Find all affected raw_job IDs
    print("Step 1: Finding affected jobs in raw_jobs...")

    all_jobs = []
    offset = 0
    page_size = 1000

    while True:
        result = supabase.table('raw_jobs') \
            .select('id,company,raw_text') \
            .eq('source', 'greenhouse') \
            .offset(offset) \
            .limit(page_size) \
            .execute()

        if not result.data:
            break

        all_jobs.extend(result.data)
        offset += page_size

        if len(result.data) < page_size:
            break

    print(f"  Total Greenhouse jobs in raw_jobs: {len(all_jobs)}")

    # Identify affected jobs
    affected_raw_ids = []
    affected_by_company = {}

    for job in all_jobs:
        if is_bot_detection_page(job.get('raw_text', '')):
            job_id = job['id']
            company = job.get('company', 'Unknown')

            affected_raw_ids.append(job_id)
            if company not in affected_by_company:
                affected_by_company[company] = 0
            affected_by_company[company] += 1

    print(f"  Found {len(affected_raw_ids)} bot detection jobs\n")

    if not affected_raw_ids:
        print("No bot detection jobs found - nothing to delete!")
        return

    print("Affected companies:")
    for company, count in sorted(affected_by_company.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {company}: {count} jobs")
    print()

    # Step 2: Delete from enriched_jobs first (foreign key constraint)
    print("Step 2: Deleting from enriched_jobs...")

    deleted_enriched = 0
    for raw_id in affected_raw_ids:
        try:
            result = supabase.table('enriched_jobs') \
                .delete() \
                .eq('raw_job_id', raw_id) \
                .execute()

            if result.data:
                deleted_enriched += len(result.data)
        except Exception as e:
            print(f"  Warning: Failed to delete enriched_jobs for raw_id {raw_id}: {e}")

    print(f"  Deleted {deleted_enriched} records from enriched_jobs\n")

    # Step 3: Delete from raw_jobs
    print("Step 3: Deleting from raw_jobs...")

    deleted_raw = 0
    for raw_id in affected_raw_ids:
        try:
            result = supabase.table('raw_jobs') \
                .delete() \
                .eq('id', raw_id) \
                .execute()

            if result.data:
                deleted_raw += len(result.data)
        except Exception as e:
            print(f"  Warning: Failed to delete raw_jobs id {raw_id}: {e}")

    print(f"  Deleted {deleted_raw} records from raw_jobs\n")

    # Summary
    print("=" * 80)
    print("DELETION COMPLETE")
    print("=" * 80)
    print(f"Total records deleted:")
    print(f"  - raw_jobs: {deleted_raw}")
    print(f"  - enriched_jobs: {deleted_enriched}")
    print()
    print("Companies affected:")
    for company, count in sorted(affected_by_company.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {company}: {count} jobs removed")
    print("=" * 80)


if __name__ == '__main__':
    import sys

    print("\nWARNING: This will permanently delete bot detection jobs from the database.")
    response = input("Are you sure you want to proceed? (yes/no): ")

    if response.lower() != 'yes':
        print("Aborted.")
        sys.exit(0)

    delete_bot_detection_jobs()
