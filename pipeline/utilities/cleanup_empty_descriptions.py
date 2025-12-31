"""
Cleanup jobs with empty descriptions.

These jobs were scraped from companies that redirect to custom career sites,
causing the scraper to miss the job descriptions. After cleanup, re-running
the scraper will fetch them properly (config has been updated with url_type=embed).

Usage:
    python pipeline/utilities/cleanup_empty_descriptions.py --dry-run   # Preview
    python pipeline/utilities/cleanup_empty_descriptions.py             # Execute
"""
import sys
sys.path.insert(0, '.')

from pipeline.db_connection import supabase

def cleanup_empty_descriptions(dry_run: bool = True):
    """Delete jobs with empty raw_text descriptions."""

    print("=" * 70)
    print("CLEANUP: Jobs with Empty Descriptions")
    print("=" * 70)
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'EXECUTE (will delete)'}")
    print()

    # Companies known to have empty description issues
    companies_to_fix = [
        'roblox', 'skydio', 'beaconsoftware', 'block',
        'abnormalsecurity', 'veriff', 'drweng', 'elastic'
    ]

    jobs_to_delete = []

    # Find all jobs with empty descriptions
    for company in companies_to_fix:
        enriched = supabase.table('enriched_jobs').select(
            'id, raw_job_id, title_display'
        ).eq('employer_name', company).execute()

        for job in enriched.data:
            raw = supabase.table('raw_jobs').select(
                'id, raw_text'
            ).eq('id', job['raw_job_id']).execute()

            if raw.data:
                raw_text = raw.data[0].get('raw_text') or ''
                if len(raw_text) == 0:
                    jobs_to_delete.append({
                        'enriched_id': job['id'],
                        'raw_job_id': job['raw_job_id'],
                        'company': company,
                        'title': job['title_display']
                    })

    if not jobs_to_delete:
        print("[OK] No jobs with empty descriptions found!")
        return

    print(f"Found {len(jobs_to_delete)} jobs with empty descriptions:")
    print()

    # Group by company for display
    by_company = {}
    for job in jobs_to_delete:
        company = job['company']
        if company not in by_company:
            by_company[company] = []
        by_company[company].append(job)

    for company, jobs in sorted(by_company.items(), key=lambda x: -len(x[1])):
        print(f"  {company}: {len(jobs)} jobs")

    print()

    if dry_run:
        print("[DRY RUN] Would delete:")
        print(f"  - {len(jobs_to_delete)} enriched_jobs records")
        print(f"  - {len(jobs_to_delete)} raw_jobs records")
        print()
        print("Run without --dry-run to execute deletion.")
        return

    # Execute deletion
    print("Deleting...")

    enriched_ids = [j['enriched_id'] for j in jobs_to_delete]
    raw_job_ids = [j['raw_job_id'] for j in jobs_to_delete]

    # Step 1: Delete from enriched_jobs (child table)
    print(f"  [1/2] Deleting {len(enriched_ids)} enriched_jobs records...")
    for i in range(0, len(enriched_ids), 100):
        batch = enriched_ids[i:i+100]
        supabase.table('enriched_jobs').delete().in_('id', batch).execute()
    print(f"  [OK] Deleted from enriched_jobs")

    # Step 2: Delete from raw_jobs (parent table)
    print(f"  [2/2] Deleting {len(raw_job_ids)} raw_jobs records...")
    for i in range(0, len(raw_job_ids), 100):
        batch = raw_job_ids[i:i+100]
        supabase.table('raw_jobs').delete().in_('id', batch).execute()
    print(f"  [OK] Deleted from raw_jobs")

    print()
    print("=" * 70)
    print(f"[DONE] Deleted {len(jobs_to_delete)} jobs with empty descriptions")
    print()
    print("Next steps:")
    print("  1. Re-scrape affected companies:")
    print("     python wrappers/fetch_jobs.py --sources greenhouse --companies roblox,beaconsoftware")
    print("  2. Or wait for next scheduled GHA run")
    print("=" * 70)


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv or "-d" in sys.argv
    cleanup_empty_descriptions(dry_run=dry_run)
