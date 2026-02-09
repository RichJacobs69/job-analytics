"""
API-Based Job Freshness Checker

PURPOSE:
Detect closed jobs on SPA-based ATS sources (Ashby, Lever, Workable, SmartRecruiters)
by checking whether tracked jobs still appear in each company's API listing.

Problem:
URL validator fails on SPA sources (especially Ashby) because they return HTTP 200
with a JS shell even for dead listings. The "job not found" message only renders
after JavaScript execution.

Solution:
Fetch each company's full job listing via API and check if our tracked jobs are
still present. Jobs absent for 2+ consecutive runs are escalated to Playwright
for final confirmation.

Key Principle: Absence != Closure
A job disappearing from an API listing could mean: filled/closed, API error,
slug change, temporarily paused, or reposted under new ID. Safeguards prevent
false positives.

USAGE:
    python pipeline/api_freshness_checker.py                    # Check all API sources
    python pipeline/api_freshness_checker.py --source ashby     # Single source
    python pipeline/api_freshness_checker.py --dry-run          # Preview without DB updates
    python pipeline/api_freshness_checker.py --stats            # Show api_last_seen_at distribution
"""

import sys
sys.path.insert(0, '.')

import json
import time
import argparse
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from pipeline.db_connection import supabase

# Playwright is optional - only needed for stale job confirmation
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# ============================================
# Configuration
# ============================================

API_SOURCES = ['ashby', 'lever', 'workable', 'smartrecruiters']

# Staleness threshold: jobs absent for this many days trigger escalation
# With Mon-Fri runs, 6 days ensures at least 2 consecutive absences
STALENESS_DAYS = 6

# Rate limits per source (seconds between requests)
RATE_LIMITS = {
    'ashby': 1.0,
    'lever': 1.0,
    'workable': 2.0,
    'smartrecruiters': 2.0,
}

# API endpoints
ASHBY_API_URL = "https://api.ashbyhq.com/posting-api/job-board"
LEVER_API_URLS = {
    "global": "https://api.lever.co/v0/postings",
    "eu": "https://api.eu.lever.co/v0/postings",
}
WORKABLE_API_URL = "https://www.workable.com/api/accounts"
SMARTRECRUITERS_API_URL = "https://api.smartrecruiters.com/v1/companies"

# HTTP settings
REQUEST_TIMEOUT = 30
USER_AGENT = "job-analytics-bot/1.0 (github.com/job-analytics)"

# Soft 404 detection patterns (shared with url_validator.py)
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
    "might have closed",
]

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


# ============================================
# API Fetchers (minimal, listing-only)
# ============================================

def fetch_ashby_job_ids(slug: str) -> Optional[Set[str]]:
    """Fetch all active job IDs from an Ashby company listing.

    Returns set of job IDs, or None on failure.
    """
    url = f"{ASHBY_API_URL}/{slug}"
    params = {'includeCompensation': 'false'}
    headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        jobs = data.get('jobs', [])
        if not isinstance(jobs, list):
            return None
        return {job.get('id', '') for job in jobs if job.get('id')}
    except Exception:
        return None


def fetch_lever_job_ids(slug: str, instance: str = 'global') -> Optional[Set[str]]:
    """Fetch all active job IDs from a Lever company listing.

    Returns set of posting IDs, or None on failure.
    """
    base_url = LEVER_API_URLS.get(instance, LEVER_API_URLS['global'])
    url = f"{base_url}/{slug}?mode=json"
    headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}

    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        jobs_data = response.json()
        if not isinstance(jobs_data, list):
            return None
        return {job.get('id', '') for job in jobs_data if job.get('id')}
    except Exception:
        return None


def fetch_workable_job_ids(slug: str) -> Optional[Set[str]]:
    """Fetch all active job shortcodes from a Workable company listing.

    Returns set of shortcodes, or None on failure.
    """
    url = f"{WORKABLE_API_URL}/{slug}"
    headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}

    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code in (404, 429):
            return None
        response.raise_for_status()
        data = response.json()
        jobs = data.get('jobs', [])
        if not isinstance(jobs, list):
            return None
        return {job.get('shortcode', '') for job in jobs if job.get('shortcode')}
    except Exception:
        return None


def fetch_smartrecruiters_job_ids(slug: str) -> Optional[Set[str]]:
    """Fetch all active job IDs from a SmartRecruiters company listing (paginated).

    Returns set of posting IDs, or None on failure.
    """
    headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}
    all_ids = set()
    offset = 0
    page_limit = 100

    try:
        while True:
            url = f"{SMARTRECRUITERS_API_URL}/{slug}/postings"
            params = {'offset': offset, 'limit': page_limit}
            response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)

            if response.status_code in (404, 429):
                return None
            response.raise_for_status()
            data = response.json()

            content = data.get('content', [])
            if not isinstance(content, list):
                return None

            for job in content:
                job_id = job.get('id', '')
                if job_id:
                    all_ids.add(job_id)

            total_found = data.get('totalFound', 0)
            if offset + page_limit >= total_found or not content:
                break
            offset += page_limit
            time.sleep(RATE_LIMITS['smartrecruiters'])

        return all_ids
    except Exception:
        return None


# Rate limit for per-job API calls (Lever/SmartRecruiters)
PER_JOB_DELAY = 0.3  # seconds between per-job API calls


def check_lever_job_exists(slug: str, job_id: str, instance: str = 'global') -> Optional[bool]:
    """Check if a single Lever posting still exists.

    Returns True (200 = active), False (404 = closed), None (error/unknown).
    """
    base_url = LEVER_API_URLS.get(instance, LEVER_API_URLS['global'])
    url = f"{base_url}/{slug}/{job_id}"
    headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}

    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            return True
        elif response.status_code == 404:
            return False
        else:
            return None
    except Exception:
        return None


def check_smartrecruiters_job_exists(slug: str, job_id: str) -> Optional[bool]:
    """Check if a single SmartRecruiters posting still exists.

    Returns True (200 = active), False (404 = closed), None (error/unknown).
    """
    url = f"{SMARTRECRUITERS_API_URL}/{slug}/postings/{job_id}"
    headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}

    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            return True
        elif response.status_code == 404:
            return False
        else:
            return None
    except Exception:
        return None


# Map source to fetcher function
API_FETCHERS = {
    'ashby': fetch_ashby_job_ids,
    'lever': fetch_lever_job_ids,
    'workable': fetch_workable_job_ids,
    'smartrecruiters': fetch_smartrecruiters_job_ids,
}


# ============================================
# DB Queries
# ============================================

def get_active_jobs_by_source(source: str) -> List[Dict]:
    """Get active enriched_jobs for a given API source, joined with raw_jobs metadata.

    Returns list of dicts with: enriched_job_id, source_job_id, company_slug,
    posting_url, api_last_seen_at, lever_instance.
    """
    all_jobs = []
    offset = 0
    page_size = 1000

    while True:
        result = supabase.table("enriched_jobs") \
            .select("id, raw_job_id, api_last_seen_at") \
            .eq("data_source", source) \
            .not_.in_("url_status", ["404", "410", "soft_404"]) \
            .range(offset, offset + page_size - 1) \
            .execute()

        if not result.data:
            break
        all_jobs.extend(result.data)
        if len(result.data) < page_size:
            break
        offset += page_size

    if not all_jobs:
        return []

    # Fetch raw_jobs metadata in batches
    raw_job_ids = [j['raw_job_id'] for j in all_jobs]
    raw_map = {}
    batch_size = 500

    for i in range(0, len(raw_job_ids), batch_size):
        batch = raw_job_ids[i:i + batch_size]
        result = supabase.table("raw_jobs") \
            .select("id, source_job_id, metadata") \
            .in_("id", batch) \
            .execute()
        for row in result.data:
            raw_map[row['id']] = row

    # Join and build result
    joined = []
    for job in all_jobs:
        raw = raw_map.get(job['raw_job_id'])
        if not raw or not raw.get('source_job_id'):
            continue

        metadata = raw.get('metadata') or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        company_slug = metadata.get('company_slug', '')
        if not company_slug:
            continue

        joined.append({
            'enriched_job_id': job['id'],
            'source_job_id': raw['source_job_id'],
            'company_slug': company_slug,
            'api_last_seen_at': job.get('api_last_seen_at'),
            'lever_instance': metadata.get('lever_instance', 'global'),
        })

    return joined


def group_by_company(jobs: List[Dict]) -> Dict[str, List[Dict]]:
    """Group jobs by company_slug."""
    groups = {}
    for job in jobs:
        slug = job['company_slug']
        if slug not in groups:
            groups[slug] = []
        groups[slug].append(job)
    return groups


# ============================================
# Playwright Confirmation
# ============================================

def check_url_playwright(url: str) -> str:
    """Render a job URL with Playwright and check for soft-404 patterns.

    Returns: 'soft_404', 'active', or 'unverifiable'.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return 'unverifiable'

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000, wait_until='domcontentloaded')
            content = page.content().lower()
            browser.close()

            for pattern in BOT_PROTECTION_PATTERNS:
                if pattern in content:
                    return 'unverifiable'

            for pattern in SOFT_404_PATTERNS:
                if pattern in content:
                    return 'soft_404'

            return 'active'
    except Exception:
        return 'unverifiable'


def get_posting_url(enriched_job_id: int) -> Optional[str]:
    """Get posting URL for an enriched job via its raw_job."""
    try:
        ej = supabase.table("enriched_jobs") \
            .select("raw_job_id") \
            .eq("id", enriched_job_id) \
            .execute()
        if not ej.data:
            return None
        raw_id = ej.data[0]['raw_job_id']

        rj = supabase.table("raw_jobs") \
            .select("posting_url") \
            .eq("id", raw_id) \
            .execute()
        if not rj.data:
            return None
        return rj.data[0].get('posting_url')
    except Exception:
        return None


# ============================================
# Main Logic
# ============================================

def run_freshness_check(
    sources: Optional[List[str]] = None,
    dry_run: bool = False
):
    """Run API freshness check for specified sources.

    Args:
        sources: List of ATS sources to check (default: all API sources)
        dry_run: If True, preview without DB updates
    """
    if sources is None:
        sources = API_SOURCES

    now = datetime.utcnow()
    staleness_threshold = now - timedelta(days=STALENESS_DAYS)

    print("=" * 70)
    print("API FRESHNESS CHECKER")
    print("=" * 70)
    print(f"Timestamp: {now.isoformat()}")
    print(f"Sources: {', '.join(sources)}")
    print(f"Staleness threshold: {STALENESS_DAYS} days ({staleness_threshold.date()})")
    print(f"Dry run: {dry_run}")
    print()

    # Aggregate stats
    total_stats = {
        'companies_checked': 0,
        'companies_skipped_error': 0,
        'companies_skipped_suspicious': 0,
        'jobs_confirmed_active': 0,
        'jobs_per_job_closed': 0,
        'jobs_first_absence': 0,
        'jobs_stale': 0,
        'jobs_closed_by_playwright': 0,
        'jobs_still_live': 0,
        'jobs_unverifiable': 0,
    }

    stale_jobs_for_playwright = []

    for source in sources:
        print(f"\n{'='*50}")
        print(f"SOURCE: {source.upper()}")
        print(f"{'='*50}")

        # Step 1: Get active jobs for this source
        jobs = get_active_jobs_by_source(source)
        if not jobs:
            print(f"  No active jobs found for {source}")
            continue

        print(f"  Active jobs tracked: {len(jobs)}")
        companies = group_by_company(jobs)
        print(f"  Companies with active jobs: {len(companies)}")

        # Step 2: For each company, fetch listing and compare
        for slug, company_jobs in companies.items():
            fetcher = API_FETCHERS.get(source)
            if not fetcher:
                continue

            # Fetch active job IDs from API
            if source == 'lever':
                # Lever needs instance (global/eu)
                instance = company_jobs[0].get('lever_instance', 'global')
                api_job_ids = fetcher(slug, instance)
            else:
                api_job_ids = fetcher(slug)

            # Rate limit between companies
            time.sleep(RATE_LIMITS.get(source, 1.0))

            # Safeguard 1: API failure
            if api_job_ids is None:
                total_stats['companies_skipped_error'] += 1
                print(f"  [SKIP] {slug}: API error or not found")
                continue

            # Safeguard 2: Empty API response when we have tracked jobs
            if len(api_job_ids) == 0 and len(company_jobs) > 0:
                total_stats['companies_skipped_error'] += 1
                print(f"  [SKIP] {slug}: API returned 0 jobs but we track {len(company_jobs)}")
                continue

            # Safeguard 3: ALL our tracked jobs absent (suspicious - slug change?)
            our_job_ids = {j['source_job_id'] for j in company_jobs}
            matches = our_job_ids & api_job_ids
            if len(matches) == 0 and len(company_jobs) > 1:
                total_stats['companies_skipped_suspicious'] += 1
                print(f"  [SUSPICIOUS] {slug}: 0/{len(company_jobs)} jobs found in API "
                      f"(API has {len(api_job_ids)} jobs) - possible slug change")
                continue

            total_stats['companies_checked'] += 1

            # Step 3: Per-job comparison
            confirmed = 0
            per_job_closed = 0
            absent_first = 0
            absent_stale = 0

            for job in company_jobs:
                job_id = job['source_job_id']
                ej_id = job['enriched_job_id']

                if job_id in api_job_ids:
                    # Job present in listing - verify with per-job endpoint if available
                    update_fields = {
                        "api_last_seen_at": now.isoformat(),
                        "url_checked_at": now.isoformat(),
                        "url_status": "active",
                    }

                    if source in ('lever', 'smartrecruiters'):
                        # Per-job verification (catches scenario 2: listed but actually closed)
                        time.sleep(PER_JOB_DELAY)
                        if source == 'lever':
                            instance = job.get('lever_instance', 'global')
                            per_job_result = check_lever_job_exists(slug, job_id, instance)
                        else:
                            per_job_result = check_smartrecruiters_job_exists(slug, job_id)

                        if per_job_result is False:
                            # Per-job endpoint says closed despite listing presence
                            per_job_closed += 1
                            update_fields = {
                                "url_status": "soft_404",
                                "url_checked_at": now.isoformat(),
                            }
                        else:
                            # per_job_result is True or None (error) -- trust listing
                            confirmed += 1
                    else:
                        # Ashby/Workable: no per-job endpoint, trust listing
                        confirmed += 1

                    if not dry_run:
                        try:
                            supabase.table("enriched_jobs") \
                                .update(update_fields) \
                                .eq("id", ej_id) \
                                .execute()
                        except Exception as e:
                            print(f"    [DB ERROR] {ej_id}: {e}")
                else:
                    # Job absent from API
                    last_seen = job.get('api_last_seen_at')

                    if last_seen is None:
                        # First absence, but never been API-checked before
                        # (backfill may not have run yet)
                        absent_first += 1
                    else:
                        # Parse last_seen timestamp
                        try:
                            last_seen_dt = datetime.fromisoformat(
                                last_seen.replace('Z', '+00:00').replace('+00:00', '')
                            )
                        except (ValueError, AttributeError):
                            last_seen_dt = now  # Treat parse errors as recent

                        if last_seen_dt > staleness_threshold:
                            # Recent absence - first miss
                            absent_first += 1
                        else:
                            # Stale - absent for 2+ consecutive runs
                            absent_stale += 1
                            stale_jobs_for_playwright.append({
                                'enriched_job_id': ej_id,
                                'source': source,
                                'slug': slug,
                                'source_job_id': job_id,
                            })

            total_stats['jobs_confirmed_active'] += confirmed
            total_stats['jobs_per_job_closed'] += per_job_closed
            total_stats['jobs_first_absence'] += absent_first
            total_stats['jobs_stale'] += absent_stale

            # Only log companies with notable findings
            if per_job_closed > 0:
                print(f"  {slug}: {confirmed} active, {per_job_closed} closed by per-job check, "
                      f"{absent_first} first-absence, {absent_stale} stale")
            elif absent_first > 0 or absent_stale > 0:
                print(f"  {slug}: {confirmed} active, {absent_first} first-absence, "
                      f"{absent_stale} stale (API has {len(api_job_ids)} total)")
            elif len(companies) <= 20:
                # Log all companies for small sources
                print(f"  {slug}: {confirmed} active [OK]")

    # Step 4: Playwright confirmation for stale jobs
    if stale_jobs_for_playwright:
        print(f"\n{'='*50}")
        print(f"PLAYWRIGHT CONFIRMATION ({len(stale_jobs_for_playwright)} stale jobs)")
        print(f"{'='*50}")

        if not PLAYWRIGHT_AVAILABLE:
            print("[WARN] Playwright not available - skipping confirmation")
            print("       Install with: pip install playwright && playwright install chromium")
            total_stats['jobs_unverifiable'] += len(stale_jobs_for_playwright)
        else:
            for i, stale_job in enumerate(stale_jobs_for_playwright):
                ej_id = stale_job['enriched_job_id']
                url = get_posting_url(ej_id)

                if not url:
                    print(f"  [{i+1}/{len(stale_jobs_for_playwright)}] "
                          f"Job {ej_id}: no URL found")
                    total_stats['jobs_unverifiable'] += 1
                    continue

                print(f"  [{i+1}/{len(stale_jobs_for_playwright)}] "
                      f"{stale_job['slug']}/{stale_job['source_job_id'][:12]}... ", end="")

                result = check_url_playwright(url)

                if result == 'soft_404':
                    print(f"-> CLOSED (soft 404)")
                    total_stats['jobs_closed_by_playwright'] += 1
                    if not dry_run:
                        try:
                            supabase.table("enriched_jobs") \
                                .update({
                                    "url_status": "soft_404",
                                    "url_checked_at": now.isoformat(),
                                }) \
                                .eq("id", ej_id) \
                                .execute()
                        except Exception as e:
                            print(f"    [DB ERROR] {ej_id}: {e}")

                elif result == 'active':
                    print(f"-> still live (false alarm)")
                    total_stats['jobs_still_live'] += 1
                    if not dry_run:
                        try:
                            supabase.table("enriched_jobs") \
                                .update({
                                    "api_last_seen_at": now.isoformat(),
                                    "url_status": "active",
                                    "url_checked_at": now.isoformat(),
                                }) \
                                .eq("id", ej_id) \
                                .execute()
                        except Exception as e:
                            print(f"    [DB ERROR] {ej_id}: {e}")

                else:
                    print(f"-> unverifiable")
                    total_stats['jobs_unverifiable'] += 1

                # Brief pause between Playwright checks
                time.sleep(2)

    # Step 5: Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print("=" * 70)
    print(f"  Companies checked:           {total_stats['companies_checked']}")
    print(f"  Companies skipped (error):   {total_stats['companies_skipped_error']}")
    print(f"  Companies skipped (suspicious): {total_stats['companies_skipped_suspicious']}")
    print()
    print(f"  Jobs confirmed active:       {total_stats['jobs_confirmed_active']}")
    print(f"  Jobs closed (per-job API):   {total_stats['jobs_per_job_closed']}")
    print(f"  Jobs first absence:          {total_stats['jobs_first_absence']}")
    print(f"  Jobs stale (2+ absences):    {total_stats['jobs_stale']}")
    if stale_jobs_for_playwright:
        print()
        print(f"  Playwright: closed (soft_404): {total_stats['jobs_closed_by_playwright']}")
        print(f"  Playwright: still live:        {total_stats['jobs_still_live']}")
        print(f"  Playwright: unverifiable:      {total_stats['jobs_unverifiable']}")

    if dry_run:
        print("\n  [DRY RUN] No database updates were made.")

    print(f"\n[DONE] API freshness check complete!")


def show_stats():
    """Show api_last_seen_at distribution for API-based sources."""
    print("=" * 70)
    print("API FRESHNESS STATS")
    print("=" * 70)

    now = datetime.utcnow()

    for source in API_SOURCES:
        print(f"\n--- {source.upper()} ---")

        # Count by api_last_seen_at status
        counts = {'never_checked': 0, 'fresh_3d': 0, 'stale_3_7d': 0, 'stale_7d_plus': 0}
        offset = 0
        page_size = 1000

        while True:
            result = supabase.table("enriched_jobs") \
                .select("api_last_seen_at, url_status") \
                .eq("data_source", source) \
                .not_.in_("url_status", ["404", "410", "soft_404"]) \
                .range(offset, offset + page_size - 1) \
                .execute()

            if not result.data:
                break

            for row in result.data:
                last_seen = row.get('api_last_seen_at')
                if not last_seen:
                    counts['never_checked'] += 1
                else:
                    try:
                        last_seen_dt = datetime.fromisoformat(
                            last_seen.replace('Z', '+00:00').replace('+00:00', '')
                        )
                        age_days = (now - last_seen_dt).days
                        if age_days <= 3:
                            counts['fresh_3d'] += 1
                        elif age_days <= 7:
                            counts['stale_3_7d'] += 1
                        else:
                            counts['stale_7d_plus'] += 1
                    except (ValueError, AttributeError):
                        counts['never_checked'] += 1

            if len(result.data) < page_size:
                break
            offset += page_size

        total = sum(counts.values())
        if total == 0:
            print(f"  No active jobs")
            continue

        print(f"  Total active: {total}")
        print(f"  Never checked:    {counts['never_checked']:>5} ({counts['never_checked']/total*100:>5.1f}%)")
        print(f"  Fresh (<=3 days): {counts['fresh_3d']:>5} ({counts['fresh_3d']/total*100:>5.1f}%)")
        print(f"  Stale (3-7 days): {counts['stale_3_7d']:>5} ({counts['stale_3_7d']/total*100:>5.1f}%)")
        print(f"  Stale (7+ days):  {counts['stale_7d_plus']:>5} ({counts['stale_7d_plus']/total*100:>5.1f}%)")

    print(f"\n[DONE] Stats complete!")


# ============================================
# CLI
# ============================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='API-based job freshness checker')
    parser.add_argument('--source', type=str, choices=API_SOURCES,
                        help='Check single source (default: all)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview without DB updates')
    parser.add_argument('--stats', action='store_true',
                        help='Show api_last_seen_at distribution')
    args = parser.parse_args()

    if args.stats:
        show_stats()
    else:
        sources = [args.source] if args.source else None
        run_freshness_check(sources=sources, dry_run=args.dry_run)

    print("\n" + "=" * 70)
    print("USAGE:")
    print("  python pipeline/api_freshness_checker.py                    # Check all API sources")
    print("  python pipeline/api_freshness_checker.py --source ashby     # Single source")
    print("  python pipeline/api_freshness_checker.py --dry-run          # Preview without DB updates")
    print("  python pipeline/api_freshness_checker.py --stats            # Show freshness distribution")
    print("=" * 70)
