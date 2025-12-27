"""
Backfill Script: Re-classify jobs using improved classifier

Purpose:
--------
Re-classifies jobs that may have been incorrectly classified due to:
- New job families added (e.g., delivery family)
- Improved classifier prompts
- Bug fixes in classification logic

This is useful when extending the taxonomy (adding new families/subfamilies)
and you want to re-evaluate previously classified jobs.

Usage:
------
# Dry run (no database changes):
python pipeline/utilities/backfill_reclassify.py --dry-run --limit 10

# Filter by title pattern (regex) to target specific roles:
python pipeline/utilities/backfill_reclassify.py --dry-run --title-pattern "project manager|scrum master"

# Filter by current job_family:
python pipeline/utilities/backfill_reclassify.py --dry-run --current-family out_of_scope

# Filter by classified_at window:
python pipeline/utilities/backfill_reclassify.py --dry-run --classified-after 2025-01-01 --classified-before 2025-01-08

# Process a specific raw_job_id:
python pipeline/utilities/backfill_reclassify.py --dry-run --raw-job-id 12345

# Full run with database updates:
python pipeline/utilities/backfill_reclassify.py --live

# Re-classify delivery roles that were marked out_of_scope (simple):
python pipeline/utilities/backfill_reclassify.py --live --current-family out_of_scope --delivery

# Or with custom title pattern:
python pipeline/utilities/backfill_reclassify.py --live --current-family out_of_scope --title-pattern "delivery (manager|lead)|project manager|scrum master"
"""

import os
import sys
import re
import argparse
import time
from datetime import datetime

sys.path.insert(0, '.')
from dotenv import load_dotenv
from supabase import create_client
from pipeline.classifier import classify_job_with_claude
from pipeline.location_extractor import extract_locations

# ============================================
# Predefined Title Patterns
# ============================================
# Use these with --title-pattern to target specific job families

DELIVERY_TITLE_PATTERN = (
    r"delivery (manager|lead|director)|"
    r"agile delivery|"
    r"project manager|"
    r"program(me)? manager|"
    r"technical program(me)? manager|"
    r"scrum master|"
    r"pmo|"
    r"agile (coach|lead)|"
    r"release manager|"
    r"iteration manager"
)

load_dotenv()
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))


def parse_iso_datetime(value: str) -> str:
    """Validate and normalize ISO-8601 datetime/date strings for queries."""
    try:
        return datetime.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Invalid date/datetime format. Use ISO-8601, e.g. 2025-01-01 or 2025-01-01T00:00:00"
        ) from exc


def get_jobs_to_reclassify(
    limit: int = None,
    classified_after: str = None,
    classified_before: str = None,
    raw_job_id: int = None,
    current_family: str = None,
    title_pattern: str = None,
):
    """
    Get jobs that need re-classification.

    Args:
        limit: Maximum number of jobs to process
        classified_after: Only jobs classified after this date
        classified_before: Only jobs classified before this date
        raw_job_id: Process only this specific raw_job_id
        current_family: Filter by current job_family (e.g., 'out_of_scope')
        title_pattern: Regex pattern to filter by title (case-insensitive)
    """
    filter_desc = []
    if current_family:
        filter_desc.append(f"job_family='{current_family}'")
    if title_pattern:
        filter_desc.append(f"title matches '{title_pattern}'")

    print(f"Fetching jobs to reclassify...")
    if filter_desc:
        print(f"  Filters: {', '.join(filter_desc)}")

    query = supabase.table('enriched_jobs').select(
        'id, raw_job_id, employer_name, title_display, job_family, job_subfamily, '
        'seniority, locations, working_arrangement, data_source'
    ).eq('is_agency', False)

    # Filter by current job_family if specified
    if current_family:
        query = query.eq('job_family', current_family)

    if raw_job_id is not None:
        query = query.eq('raw_job_id', raw_job_id)

    if classified_after:
        query = query.gte('classified_at', classified_after)
    if classified_before:
        query = query.lt('classified_at', classified_before)

    # Supabase defaults to 1K row limit; page through results to respect user limit.
    max_to_fetch = limit if limit is not None else 2000
    page_size = 1000
    offset = 0
    enriched_rows = []

    while True:
        remaining = max_to_fetch - len(enriched_rows)
        if remaining <= 0:
            break
        batch_size = min(page_size, remaining)
        batch = query.range(offset, offset + batch_size - 1).execute()
        batch_data = batch.data or []
        enriched_rows.extend(batch_data)
        offset += batch_size
        if len(batch_data) < batch_size:
            break

    # Apply title pattern filter (client-side regex)
    if title_pattern and enriched_rows:
        try:
            pattern = re.compile(title_pattern, re.IGNORECASE)
            before_count = len(enriched_rows)
            enriched_rows = [
                row for row in enriched_rows
                if row.get('title_display') and pattern.search(row['title_display'])
            ]
            print(f"  Title filter: {before_count} -> {len(enriched_rows)} jobs")
        except re.error as e:
            print(f"  [WARNING] Invalid regex pattern '{title_pattern}': {e}")
            print(f"  Continuing without title filter...")

    if not enriched_rows:
        return []

    family_desc = current_family or 'all families'
    print(f"Found {len(enriched_rows)} jobs ({family_desc})")
    
    # Get raw_job_ids
    raw_job_ids = [job['raw_job_id'] for job in enriched_rows]
    
    # Fetch raw_jobs
    print("Fetching raw job data...")
    raw_jobs_data = {}
    batch_size = 100
    
    for i in range(0, len(raw_job_ids), batch_size):
        batch_ids = raw_job_ids[i:i+batch_size]
        raw_result = supabase.table('raw_jobs').select(
            'id, title, company, raw_text, source'
        ).in_('id', batch_ids).execute()
        
        for raw in raw_result.data:
            raw_jobs_data[raw['id']] = raw
    
    # Combine enriched + raw data
    jobs_to_process = []
    for enriched in enriched_rows:
        raw_job_id = enriched['raw_job_id']
        if raw_job_id in raw_jobs_data:
            raw = raw_jobs_data[raw_job_id]
            jobs_to_process.append({
                'enriched_id': enriched['id'],
                'raw_job_id': raw_job_id,
                'title': raw.get('title') or enriched.get('title_display') or 'Unknown',
                'company': raw.get('company') or enriched.get('employer_name') or 'Unknown',
                'raw_text': raw.get('raw_text', ''),
                'source': raw.get('source', 'unknown'),
                'current_family': enriched['job_family'],
                'current_subfamily': enriched.get('job_subfamily'),
                'locations': enriched.get('locations', []),
            })

    print(f"Prepared {len(jobs_to_process)} jobs for re-classification")
    return jobs_to_process


def reclassify_job(job: dict):
    """Re-classify a single job using the improved classifier."""
    # Extract location string from locations JSONB for context
    locations = job.get('locations', [])
    location_str = None
    if locations and isinstance(locations, list) and len(locations) > 0:
        loc = locations[0]
        if loc.get('type') == 'city':
            location_str = f"{loc.get('city', 'unknown')}, {loc.get('country_code', '')}"
        elif loc.get('type') == 'remote':
            location_str = f"Remote ({loc.get('scope', 'unknown')})"

    structured_input = {
        'title': job['title'],
        'company': job['company'],
        'description': job['raw_text'],
        'location': location_str,
        'category': 'IT Jobs',
    }

    return classify_job_with_claude(
        job_text=job['raw_text'],
        structured_input=structured_input,
        verbose=False
    )


def update_enriched_job(enriched_id: int, classification: dict):
    """Update an enriched_job record with new classification."""
    role = classification.get('role', {})

    update_data = {
        'job_family': role.get('job_family') or 'out_of_scope',
        'job_subfamily': role.get('job_subfamily'),
        'seniority': role.get('seniority'),
        'track': role.get('track'),
        'classified_at': datetime.now().isoformat(),  # Update timestamp on reclassification
    }

    # Also update skills if present
    skills = classification.get('skills')
    if skills:
        update_data['skills'] = skills

    # Also update working_arrangement if present
    location = classification.get('location', {})
    if location.get('working_arrangement'):
        update_data['working_arrangement'] = location['working_arrangement']

    update_data = {k: v for k, v in update_data.items() if v is not None}

    supabase.table('enriched_jobs').update(update_data).eq('id', enriched_id).execute()


def run_backfill(
    dry_run: bool = True,
    limit: int = None,
    classified_after: str = None,
    classified_before: str = None,
    raw_job_id: int = None,
    current_family: str = None,
    title_pattern: str = None,
):
    """
    Main backfill function.

    Args:
        dry_run: If True, don't update database
        limit: Maximum number of jobs to process
        classified_after: Only process jobs classified after this date
        classified_before: Only process jobs classified before this date
        raw_job_id: Process only this specific raw_job_id
        current_family: Filter by current job_family (e.g., 'out_of_scope')
        title_pattern: Regex pattern to filter by title
    """
    start_time = time.time()

    print("="*80)
    print("BACKFILL: Re-classify jobs")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE (will update DB)'}")
    if current_family:
        print(f"Filter: job_family = '{current_family}'")
    if title_pattern:
        print(f"Filter: title matches '{title_pattern}'")
    if classified_after:
        print(f"Filter: classified_at >= {classified_after}")
    if classified_before:
        print(f"Filter: classified_at < {classified_before}")
    if raw_job_id is not None:
        print(f"Filter: raw_job_id = {raw_job_id}")
    print("="*80)

    jobs = get_jobs_to_reclassify(
        limit=limit,
        classified_after=classified_after,
        classified_before=classified_before,
        raw_job_id=raw_job_id,
        current_family=current_family,
        title_pattern=title_pattern,
    )

    if not jobs:
        print("\nNo jobs to process.")
        return

    stats = {
        'total': len(jobs),
        'processed': 0,
        'to_product': 0,
        'to_data': 0,
        'to_delivery': 0,
        'still_out_of_scope': 0,
        'unchanged': 0,
        'errors': 0,
        'cost': 0.0,
    }

    subfamily_counts = {'product': {}, 'data': {}, 'delivery': {}}
    
    print(f"\nProcessing {stats['total']} jobs...\n")

    for i, job in enumerate(jobs, 1):
        try:
            classification = reclassify_job(job)
            stats['processed'] += 1

            if '_cost_data' in classification:
                stats['cost'] += classification['_cost_data'].get('total_cost', 0)

            new_family = classification.get('role', {}).get('job_family', 'out_of_scope')
            new_subfamily = classification.get('role', {}).get('job_subfamily')
            old_family = job.get('current_family', 'unknown')

            # Determine what changed
            if new_family == old_family:
                stats['unchanged'] += 1
                symbol = f"= {new_family} (unchanged)"
            elif new_family == 'product':
                stats['to_product'] += 1
                subfamily_counts['product'][new_subfamily] = subfamily_counts['product'].get(new_subfamily, 0) + 1
                symbol = f"-> PRODUCT ({new_subfamily})"
            elif new_family == 'data':
                stats['to_data'] += 1
                subfamily_counts['data'][new_subfamily] = subfamily_counts['data'].get(new_subfamily, 0) + 1
                symbol = f"-> DATA ({new_subfamily})"
            elif new_family == 'delivery':
                stats['to_delivery'] += 1
                subfamily_counts['delivery'][new_subfamily] = subfamily_counts['delivery'].get(new_subfamily, 0) + 1
                symbol = f"-> DELIVERY ({new_subfamily})"
            else:
                stats['still_out_of_scope'] += 1
                symbol = "= out_of_scope"

            title_short = job['title'][:45] if job['title'] else 'Unknown'
            print(f"[{i}/{stats['total']}] {title_short}... {symbol}")

            # Update DB if live mode and family changed
            if not dry_run and new_family != old_family:
                update_enriched_job(job['enriched_id'], classification)

        except Exception as e:
            stats['errors'] += 1
            print(f"[{i}/{stats['total']}] ERROR: {str(e)[:60]}")
    
    # Report
    elapsed = time.time() - start_time
    total_reclassified = stats['to_product'] + stats['to_data'] + stats['to_delivery']

    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    print(f"Processed: {stats['processed']}/{stats['total']} | Errors: {stats['errors']}")
    print(f"Time: {elapsed:.1f}s | Cost: ${stats['cost']:.4f}")
    print(f"\n-> PRODUCT: {stats['to_product']} ({stats['to_product']/max(stats['processed'],1)*100:.1f}%)")
    print(f"-> DATA: {stats['to_data']} ({stats['to_data']/max(stats['processed'],1)*100:.1f}%)")
    print(f"-> DELIVERY: {stats['to_delivery']} ({stats['to_delivery']/max(stats['processed'],1)*100:.1f}%)")
    print(f"= UNCHANGED: {stats['unchanged']} ({stats['unchanged']/max(stats['processed'],1)*100:.1f}%)")
    print(f"= OUT_OF_SCOPE: {stats['still_out_of_scope']} ({stats['still_out_of_scope']/max(stats['processed'],1)*100:.1f}%)")

    if subfamily_counts['product']:
        print("\nProduct subfamilies:")
        for sf, cnt in sorted(subfamily_counts['product'].items(), key=lambda x: -x[1]):
            print(f"  {sf or 'None'}: {cnt}")

    if subfamily_counts['data']:
        print("\nData subfamilies:")
        for sf, cnt in sorted(subfamily_counts['data'].items(), key=lambda x: -x[1]):
            print(f"  {sf or 'None'}: {cnt}")

    if subfamily_counts['delivery']:
        print("\nDelivery subfamilies:")
        for sf, cnt in sorted(subfamily_counts['delivery'].items(), key=lambda x: -x[1]):
            print(f"  {sf or 'None'}: {cnt}")

    if dry_run:
        print("\n[DRY RUN] No DB changes. Use --live to apply.")
    else:
        print(f"\n[DONE] Updated {total_reclassified} jobs in DB")

    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Re-classify jobs using improved classifier',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run on out_of_scope jobs with delivery-like titles (using --delivery shortcut):
  python backfill_reclassify.py --dry-run --current-family out_of_scope --delivery

  # Same with custom pattern:
  python backfill_reclassify.py --dry-run --current-family out_of_scope --title-pattern "project manager|scrum master"

  # Re-classify all out_of_scope jobs:
  python backfill_reclassify.py --live --current-family out_of_scope

  # Re-classify specific job by ID:
  python backfill_reclassify.py --live --raw-job-id 12345

  # Limit to 10 jobs for testing:
  python backfill_reclassify.py --dry-run --limit 10
        """
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without making DB changes')
    parser.add_argument('--live', action='store_true',
                        help='Actually update the database (default is dry-run)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Maximum number of jobs to process')
    parser.add_argument('--current-family', type=str, default=None,
                        help='Filter by current job_family (e.g., out_of_scope, product, data)')
    parser.add_argument('--title-pattern', type=str, default=None,
                        help='Regex pattern to filter by title (case-insensitive)')
    parser.add_argument('--delivery', action='store_true',
                        help='Use predefined delivery role pattern (shortcut for --title-pattern)')
    parser.add_argument('--classified-after', type=parse_iso_datetime, default=None,
                        help='Only process jobs with classified_at >= this ISO date/datetime')
    parser.add_argument('--classified-before', type=parse_iso_datetime, default=None,
                        help='Only process jobs with classified_at < this ISO date/datetime')
    parser.add_argument('--raw-job-id', type=int, default=None,
                        help='Only process the job associated with this raw_job_id')

    args = parser.parse_args()
    dry_run = not args.live

    # Handle --delivery shortcut
    title_pattern = args.title_pattern
    if args.delivery:
        if title_pattern:
            print("[WARNING] Both --delivery and --title-pattern specified. Using --delivery pattern.")
        title_pattern = DELIVERY_TITLE_PATTERN
        print(f"[INFO] Using predefined delivery pattern: {title_pattern[:50]}...")

    run_backfill(
        dry_run=dry_run,
        limit=args.limit,
        classified_after=args.classified_after,
        classified_before=args.classified_before,
        raw_job_id=args.raw_job_id,
        current_family=args.current_family,
        title_pattern=title_pattern,
    )

