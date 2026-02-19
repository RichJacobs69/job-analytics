"""
API-Based Job Freshness Checker

PURPOSE:
Detect closed jobs across all 5 ATS sources (Greenhouse, Ashby, Lever, Workable,
SmartRecruiters) by checking whether tracked jobs still appear in each company's
API listing.

All 5 sources use the same model: job present in API listing = active; job absent
= closed (soft_404). Company-level safeguards (API errors, empty responses, total
absence) prevent false positives from API glitches or slug changes.

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
from datetime import datetime
from typing import Dict, List, Optional, Set
from pipeline.db_connection import supabase

# ============================================
# Configuration
# ============================================

API_SOURCES = ['greenhouse', 'ashby', 'lever', 'workable', 'smartrecruiters']

# Rate limits per source (seconds between requests)
RATE_LIMITS = {
    'greenhouse': 0.5,
    'ashby': 1.0,
    'lever': 1.0,
    'workable': 2.0,
    'smartrecruiters': 2.0,
}

DB_BATCH_SIZE = 500  # Batch size for .in_() updates

# API endpoints
GREENHOUSE_API_URL = "https://boards-api.greenhouse.io/v1/boards"
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

# ============================================
# API Fetchers (minimal, listing-only)
# ============================================

def fetch_greenhouse_job_ids(slug: str) -> Optional[Set[str]]:
    """Fetch all active job IDs from a Greenhouse company listing."""
    url = f"{GREENHOUSE_API_URL}/{slug}/jobs"
    headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}
    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        jobs = data.get('jobs', [])
        if not isinstance(jobs, list):
            return None
        # str() cast required: Greenhouse API returns numeric IDs but
        # raw_jobs.source_job_id stores strings
        return {str(job.get('id', '')) for job in jobs if job.get('id')}
    except Exception:
        return None


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


# Map source to fetcher function
API_FETCHERS = {
    'greenhouse': fetch_greenhouse_job_ids,
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
# Batch DB Updates
# ============================================

def _batch_update(job_ids: list, fields: dict):
    """Update enriched_jobs in batches using .in_() filter."""
    for i in range(0, len(job_ids), DB_BATCH_SIZE):
        batch = job_ids[i:i + DB_BATCH_SIZE]
        try:
            supabase.table("enriched_jobs").update(fields).in_("id", batch).execute()
        except Exception as e:
            print(f"    [DB ERROR] batch update failed ({len(batch)} jobs): {e}")


# ============================================
# Main Logic
# ============================================

def run_freshness_check(
    sources: Optional[List[str]] = None,
    dry_run: bool = False
):
    """Run API freshness check for specified sources.

    For each source, fetches each company's job listing via API and compares
    against tracked jobs. Present = active, absent = closed (soft_404).

    Company-level safeguards prevent false positives:
    - API error/404 -> skip company
    - API returns 0 jobs -> skip company
    - ALL tracked jobs absent with >1 tracked -> skip company (slug change?)

    Args:
        sources: List of ATS sources to check (default: all API sources)
        dry_run: If True, preview without DB updates
    """
    if sources is None:
        sources = API_SOURCES

    now = datetime.utcnow()

    print("=" * 70)
    print("API FRESHNESS CHECKER")
    print("=" * 70)
    print(f"Timestamp: {now.isoformat()}")
    print(f"Sources: {', '.join(sources)}")
    print(f"Dry run: {dry_run}")
    print()

    # Aggregate stats
    total_stats = {
        'companies_checked': 0,
        'companies_skipped_error': 0,
        'companies_skipped_suspicious': 0,
        'jobs_confirmed_active': 0,
        'jobs_marked_closed': 0,
    }

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

            # Step 3: Per-job comparison - collect into lists for batch update
            active_ids = []
            closed_ids = []

            for job in company_jobs:
                job_id = job['source_job_id']
                ej_id = job['enriched_job_id']

                if job_id in api_job_ids:
                    active_ids.append(ej_id)
                else:
                    closed_ids.append(ej_id)

            # Batch update
            if not dry_run:
                if active_ids:
                    _batch_update(active_ids, {
                        "api_last_seen_at": now.isoformat(),
                        "url_checked_at": now.isoformat(),
                        "url_status": "active",
                    })
                if closed_ids:
                    _batch_update(closed_ids, {
                        "url_status": "soft_404",
                        "url_checked_at": now.isoformat(),
                    })

            total_stats['jobs_confirmed_active'] += len(active_ids)
            total_stats['jobs_marked_closed'] += len(closed_ids)

            # Only log companies with closures
            if closed_ids:
                print(f"  {slug}: {len(active_ids)} active, {len(closed_ids)} closed "
                      f"(API has {len(api_job_ids)} total)")
            elif len(companies) <= 20:
                print(f"  {slug}: {len(active_ids)} active [OK]")

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print("=" * 70)
    print(f"  Companies checked:           {total_stats['companies_checked']}")
    print(f"  Companies skipped (error):   {total_stats['companies_skipped_error']}")
    print(f"  Companies skipped (suspicious): {total_stats['companies_skipped_suspicious']}")
    print()
    print(f"  Jobs confirmed active:       {total_stats['jobs_confirmed_active']}")
    print(f"  Jobs marked closed:          {total_stats['jobs_marked_closed']}")

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
