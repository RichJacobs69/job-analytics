"""
URL Validator
Checks posting URLs for 404s and updates enriched_jobs.url_status.

Part of: EPIC-008 Curated Job Feed
Runs: Nightly via GitHub Actions (after scraping completes)

Purpose:
- Identify dead job postings (404s) before users click through
- Prevent poor UX in curated job feed
- Mark jobs as closed when URL returns 404
"""

import sys
sys.path.insert(0, '.')

import time
import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, Optional
from pipeline.db_connection import supabase


# ============================================
# Configuration
# ============================================

# HTTP request settings
REQUEST_TIMEOUT = 10  # seconds
USER_AGENT = "Mozilla/5.0 (compatible; JobFeedBot/1.0; +https://richjacobs.me)"

# Concurrency settings
MAX_WORKERS = 10
BATCH_SIZE = 100

# Recheck interval (don't recheck URLs checked within this period)
RECHECK_DAYS = 3


def check_url(url: str) -> Tuple[str, Optional[int]]:
    """
    Check a single URL and return its status.

    Returns:
        Tuple of (status, http_code):
        - ('active', 200) for valid URLs
        - ('404', 404) for not found
        - ('redirect', 3xx) for redirects
        - ('error', None) for network errors
    """
    try:
        # Use HEAD request first (faster)
        response = requests.head(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=False,
            headers={'User-Agent': USER_AGENT}
        )

        status_code = response.status_code

        if status_code == 200:
            return ('active', status_code)
        elif status_code == 404:
            return ('404', status_code)
        elif 300 <= status_code < 400:
            return ('redirect', status_code)
        elif status_code == 405:
            # Method not allowed - try GET instead
            response = requests.get(
                url,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=False,
                headers={'User-Agent': USER_AGENT}
            )
            if response.status_code == 200:
                return ('active', response.status_code)
            elif response.status_code == 404:
                return ('404', response.status_code)
            else:
                return ('redirect', response.status_code)
        else:
            # Other status codes (5xx, etc.)
            return ('error', status_code)

    except requests.exceptions.Timeout:
        return ('error', None)
    except requests.exceptions.ConnectionError:
        return ('error', None)
    except requests.exceptions.RequestException:
        return ('error', None)


def validate_urls(limit: int = None, force: bool = False, dry_run: bool = False):
    """
    Validate posting URLs for Greenhouse/Lever jobs.

    Args:
        limit: Maximum jobs to check (None = all needing check)
        force: If True, recheck all URLs regardless of url_checked_at
        dry_run: If True, show what would be checked without updating database
    """
    print("=" * 70)
    print("URL VALIDATOR")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Limit: {limit or 'None (check all)'}")
    print(f"Force recheck: {force}")
    print(f"Dry run: {dry_run}")
    print()

    # Step 1: Find jobs needing URL validation
    print("[DATA] Finding jobs needing URL validation...")

    try:
        # Calculate recheck threshold
        recheck_threshold = (datetime.now() - timedelta(days=RECHECK_DAYS)).isoformat()

        jobs_to_check = []
        offset = 0
        page_size = 1000

        while True:
            # Build query
            query = supabase.table("enriched_jobs") \
                .select("id, raw_job_id") \
                .in_("data_source", ["greenhouse", "lever"])

            if not force:
                # Only check jobs not recently validated
                # url_checked_at is NULL or older than threshold
                query = query.or_(
                    f"url_checked_at.is.null,url_checked_at.lt.{recheck_threshold}"
                )

            result = query.range(offset, offset + page_size - 1).execute()

            if not result.data:
                break

            jobs_to_check.extend(result.data)

            if len(result.data) < page_size:
                break
            offset += page_size

        print(f"[OK] Found {len(jobs_to_check)} jobs needing validation")

        if not jobs_to_check:
            print("\n[DONE] All URLs recently validated!")
            return

        # Apply limit if specified
        if limit:
            jobs_to_check = jobs_to_check[:limit]
            print(f"[LIMIT] Checking first {limit} jobs")

    except Exception as e:
        print(f"[ERROR] Failed to find jobs: {e}")
        return

    # Step 2: Fetch posting URLs from raw_jobs
    print("\n[DATA] Fetching posting URLs...")

    raw_job_ids = [job['raw_job_id'] for job in jobs_to_check]
    url_map = {}  # raw_job_id -> posting_url

    try:
        batch_fetch_size = 500
        for i in range(0, len(raw_job_ids), batch_fetch_size):
            batch_ids = raw_job_ids[i:i + batch_fetch_size]
            result = supabase.table("raw_jobs") \
                .select("id, posting_url") \
                .in_("id", batch_ids) \
                .execute()

            for row in result.data:
                url_map[row['id']] = row['posting_url']

        print(f"[OK] Retrieved {len(url_map)} URLs")

    except Exception as e:
        print(f"[ERROR] Failed to fetch URLs: {e}")
        return

    # Step 3: Build job list with URLs
    jobs_with_urls = []
    for job in jobs_to_check:
        url = url_map.get(job['raw_job_id'])
        if url:
            jobs_with_urls.append({
                'enriched_job_id': job['id'],
                'url': url
            })

    print(f"[OK] {len(jobs_with_urls)} jobs have valid URLs")

    if dry_run:
        print(f"\n[DRY RUN] Would check {len(jobs_with_urls)} URLs")
        print("\nSample URLs:")
        for job in jobs_with_urls[:10]:
            print(f"   {job['url'][:70]}...")
        return

    # Step 4: Check URLs in parallel
    print(f"\n[CHECK] Validating {len(jobs_with_urls)} URLs (max {MAX_WORKERS} workers)...")

    results = {
        'active': 0,
        '404': 0,
        'redirect': 0,
        'error': 0
    }

    def process_job(job):
        """Process a single job URL check."""
        status, code = check_url(job['url'])
        return {
            'enriched_job_id': job['enriched_job_id'],
            'url': job['url'],
            'status': status,
            'code': code
        }

    # Process in batches with thread pool
    processed = 0
    batch_num = 0

    for batch_start in range(0, len(jobs_with_urls), BATCH_SIZE):
        batch = jobs_with_urls[batch_start:batch_start + BATCH_SIZE]
        batch_num += 1

        print(f"\n   [BATCH {batch_num}] Checking {len(batch)} URLs...")

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_job, job): job for job in batch}

            for future in as_completed(futures):
                result = future.result()
                status = result['status']
                results[status] += 1
                processed += 1

                # Log 404s specifically
                if status == '404':
                    print(f"      [404] {result['url'][:60]}...")

                # Update database
                try:
                    supabase.table("enriched_jobs") \
                        .update({
                            'url_status': status,
                            'url_checked_at': datetime.now().isoformat()
                        }) \
                        .eq("id", result['enriched_job_id']) \
                        .execute()
                except Exception as e:
                    print(f"      [DB ERROR] {e}")

        print(f"   [BATCH {batch_num}] Complete: {results}")

        # Brief pause between batches
        if batch_start + BATCH_SIZE < len(jobs_with_urls):
            time.sleep(1)

    # Step 5: Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"URLs checked: {processed}")
    print(f"  Active (200): {results['active']}")
    print(f"  Not Found (404): {results['404']}")
    print(f"  Redirect (3xx): {results['redirect']}")
    print(f"  Error (timeout/network): {results['error']}")

    if results['404'] > 0:
        pct_404 = results['404'] / processed * 100
        print(f"\n[WARN] {results['404']} dead links found ({pct_404:.1f}%)")
        print("       These will be excluded from the job feed.")

    print("\n[DONE] URL validation complete!")


def verify_url_status():
    """Verify url_status distribution in enriched_jobs."""
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)

    try:
        # Get distribution of url_status
        result = supabase.table("enriched_jobs") \
            .select("url_status") \
            .in_("data_source", ["greenhouse", "lever"]) \
            .execute()

        status_counts = {}
        for row in result.data:
            status = row.get('url_status') or 'unknown'
            status_counts[status] = status_counts.get(status, 0) + 1

        total = sum(status_counts.values())

        print(f"\nURL status distribution (Greenhouse/Lever only):")
        print("-" * 40)

        for status in ['active', '404', 'redirect', 'error', 'unknown']:
            count = status_counts.get(status, 0)
            pct = count / total * 100 if total > 0 else 0
            bar = '#' * int(pct / 2)  # Use # instead of █ for Windows compatibility
            print(f"  {status:12} {count:>6} ({pct:>5.1f}%) {bar}")

        print(f"\nTotal: {total}")

        # Show sample 404s
        sample_404 = supabase.table("enriched_jobs") \
            .select("id, title_display, employer_name") \
            .eq("url_status", "404") \
            .limit(5) \
            .execute()

        if sample_404.data:
            print("\nSample 404 jobs (will be excluded from feed):")
            for row in sample_404.data:
                print(f"   - {row['title_display'][:40]} @ {row['employer_name']}")

    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")


if __name__ == "__main__":
    import sys

    dry_run = "--dry-run" in sys.argv or "-d" in sys.argv
    verify_only = "--verify" in sys.argv or "-v" in sys.argv
    force = "--force" in sys.argv or "-f" in sys.argv

    # Parse limit argument
    limit = None
    for arg in sys.argv:
        if arg.startswith("--limit="):
            limit = int(arg.split("=")[1])

    if verify_only:
        verify_url_status()
    else:
        validate_urls(limit=limit, force=force, dry_run=dry_run)
        verify_url_status()

    print("\n" + "=" * 70)
    print("USAGE:")
    print("  python pipeline/url_validator.py                  # Check URLs needing validation")
    print("  python pipeline/url_validator.py --limit=100      # Check first 100")
    print("  python pipeline/url_validator.py --force          # Recheck all URLs")
    print("  python pipeline/url_validator.py --dry-run        # Preview without updating")
    print("  python pipeline/url_validator.py --verify         # Just check current state")
    print("=" * 70)
