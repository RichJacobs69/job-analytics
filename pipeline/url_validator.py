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
from typing import Tuple, Optional, List, Dict
from pipeline.db_connection import supabase

# Playwright is optional - only needed for blocked URL verification
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# ============================================
# Configuration
# ============================================

# HTTP request settings
REQUEST_TIMEOUT = 15  # seconds (increased from 10)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Concurrency settings
MAX_WORKERS = 10
BATCH_SIZE = 100

# Recheck interval (don't recheck URLs checked within this period)
RECHECK_DAYS = 3

# Soft 404 detection - patterns that indicate job is closed/gone even with 200 status
SOFT_404_PATTERNS = [
    "job not found",
    "position has been filled",
    "no longer available",
    "no longer accepting",
    "page not found",
    "this job is closed",
    "this position has been closed",
    "job has been removed",
    "listing has expired",
    "role has been filled",
    "opening has been filled",
    "job does not exist",
    "position is no longer available",
    "opportunity is no longer available",
]

# Bot protection detection - patterns that indicate we're blocked, not seeing real content
BOT_PROTECTION_PATTERNS = [
    "please complete a security check",
    "checking your browser",
    "please verify you are a human",
    "captcha",
    "access denied",
    "please wait while we verify",
    "just a moment",
    "ddos protection",
    "cloudflare",
    "enable javascript and cookies",
]


def check_url_playwright(url: str) -> Tuple[str, Optional[int], Optional[str]]:
    """
    Fallback URL check using Playwright for sites that block requests.
    Used for URLs that returned 403 (blocked) status.

    Returns:
        Tuple of (status, http_code, final_url):
        - ('active', 200, url) for valid URLs with live job
        - ('soft_404', 200, url) for pages showing "not found" content
        - ('unverifiable', None, None) if Playwright also fails or bot protection detected
    """
    if not PLAYWRIGHT_AVAILABLE:
        return ('unverifiable', None, None)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000, wait_until='domcontentloaded')

            content = page.content().lower()
            final_url = page.url

            browser.close()

            # Check for bot protection (Cloudflare, CAPTCHA, etc.)
            for pattern in BOT_PROTECTION_PATTERNS:
                if pattern in content:
                    return ('unverifiable', None, final_url)

            # Check for soft 404 patterns in rendered content
            for pattern in SOFT_404_PATTERNS:
                if pattern in content:
                    return ('soft_404', 200, final_url)

            return ('active', 200, final_url)
    except Exception:
        return ('unverifiable', None, None)


def check_url(url: str) -> Tuple[str, Optional[int], Optional[str]]:
    """
    Check a single URL and return its status.

    Returns:
        Tuple of (status, http_code, final_url):
        - ('active', 200, url) for valid URLs with live job
        - ('soft_404', 200, url) for pages that return 200 but show "not found" content
        - ('404', 404, url) for not found
        - ('blocked', 403, url) for bot-blocked sites
        - ('error', None, None) for network errors
    """
    try:
        # Use GET with redirect following to check final destination and content
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            headers={'User-Agent': USER_AGENT}
        )

        status_code = response.status_code
        final_url = response.url

        if status_code == 404:
            return ('404', status_code, final_url)
        elif status_code == 403:
            # Bot detection / access denied
            return ('blocked', status_code, final_url)
        elif status_code >= 500:
            return ('error', status_code, final_url)
        elif status_code == 200:
            # Check for URL-based error signals (e.g., ?error=true)
            if 'error=true' in final_url.lower() or 'notfound' in final_url.lower():
                return ('soft_404', status_code, final_url)

            # Check for soft 404 - page exists but content says job is gone
            content_lower = response.text.lower()
            for pattern in SOFT_404_PATTERNS:
                if pattern in content_lower:
                    return ('soft_404', status_code, final_url)
            return ('active', status_code, final_url)
        elif 300 <= status_code < 400:
            # Redirect not followed (shouldn't happen with allow_redirects=True)
            return ('redirect', status_code, final_url)
        else:
            # Other status codes (4xx besides 404)
            return ('error', status_code, final_url)

    except requests.exceptions.Timeout:
        return ('error', None, None)
    except requests.exceptions.ConnectionError:
        return ('error', None, None)
    except requests.exceptions.RequestException:
        return ('error', None, None)


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
            # Build query - skip confirmed dead jobs (404/soft_404 are terminal)
            query = supabase.table("enriched_jobs") \
                .select("id, raw_job_id") \
                .in_("data_source", ["greenhouse", "lever", "ashby"]) \
                .not_.in_("url_status", ["404", "soft_404"])

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
        'soft_404': 0,
        'blocked': 0,
        'unverifiable': 0,
        'redirect': 0,
        'error': 0
    }

    def process_job(job):
        """Process a single job URL check."""
        status, code, final_url = check_url(job['url'])
        return {
            'enriched_job_id': job['enriched_job_id'],
            'url': job['url'],
            'final_url': final_url,
            'status': status,
            'code': code
        }

    # Process in batches with thread pool
    processed = 0
    batch_num = 0
    blocked_jobs = []  # Track blocked URLs for Playwright fallback

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

                # Log 404s and soft_404s specifically
                if status == '404':
                    print(f"      [404] {result['url'][:60]}...")
                elif status == 'soft_404':
                    print(f"      [SOFT 404] {result['url'][:60]}...")
                elif status == 'blocked':
                    # Track for Playwright fallback
                    blocked_jobs.append(result)

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

    # Step 5: Playwright fallback for blocked URLs
    if blocked_jobs and PLAYWRIGHT_AVAILABLE:
        print(f"\n[PLAYWRIGHT] Verifying {len(blocked_jobs)} blocked URLs...")
        playwright_results = {'active': 0, 'soft_404': 0, 'unverifiable': 0}

        for i, job in enumerate(blocked_jobs):
            print(f"   [{i+1}/{len(blocked_jobs)}] {job['url'][:50]}...")
            status, code, final_url = check_url_playwright(job['url'])
            playwright_results[status] += 1

            # Update the results counter (subtract blocked, add new status)
            results['blocked'] -= 1
            if status not in results:
                results[status] = 0
            results[status] += 1

            # Update database with final status
            try:
                supabase.table("enriched_jobs") \
                    .update({
                        'url_status': status,
                        'url_checked_at': datetime.now().isoformat()
                    }) \
                    .eq("id", job['enriched_job_id']) \
                    .execute()
            except Exception as e:
                print(f"      [DB ERROR] {e}")

        print(f"   [PLAYWRIGHT] Results: {playwright_results}")
    elif blocked_jobs and not PLAYWRIGHT_AVAILABLE:
        print(f"\n[WARN] {len(blocked_jobs)} URLs blocked but Playwright not available")
        print("       Install with: pip install playwright && playwright install chromium")

    # Step 6: Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"URLs checked: {processed}")
    print(f"  Active (200): {results['active']}")
    print(f"  Not Found (404): {results['404']}")
    print(f"  Soft 404 (content says closed): {results['soft_404']}")
    print(f"  Blocked (403, unresolved): {results['blocked']}")
    print(f"  Unverifiable (Playwright failed): {results['unverifiable']}")
    print(f"  Redirect (3xx): {results['redirect']}")
    print(f"  Error (timeout/network): {results['error']}")

    dead_total = results['404'] + results['soft_404']
    if dead_total > 0:
        pct_dead = dead_total / processed * 100
        print(f"\n[WARN] {dead_total} dead links found ({pct_dead:.1f}%)")
        print(f"       ({results['404']} hard 404, {results['soft_404']} soft 404)")
        print("       These will be excluded from the job feed.")

    if results['blocked'] > 0:
        print(f"\n[INFO] {results['blocked']} URLs blocked by bot detection (403)")
        print("       These sites may require Playwright for accurate validation.")

    print("\n[DONE] URL validation complete!")


def verify_url_status():
    """Verify url_status distribution in enriched_jobs."""
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)

    try:
        # Get distribution of url_status with pagination (Supabase 1000-row limit)
        status_counts = {}
        offset = 0
        batch_size = 1000

        while True:
            result = supabase.table("enriched_jobs") \
                .select("url_status") \
                .in_("data_source", ["greenhouse", "lever", "ashby"]) \
                .range(offset, offset + batch_size - 1) \
                .execute()

            if not result.data:
                break

            for row in result.data:
                status = row.get('url_status') or 'unknown'
                status_counts[status] = status_counts.get(status, 0) + 1

            if len(result.data) < batch_size:
                break
            offset += batch_size

        total = sum(status_counts.values())

        print(f"\nURL status distribution (Greenhouse/Lever/Ashby):")
        print("-" * 40)

        for status in ['active', '404', 'soft_404', 'blocked', 'unverifiable', 'redirect', 'error', 'unknown']:
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
