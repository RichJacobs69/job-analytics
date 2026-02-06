"""
Backfill Greenhouse Job Descriptions

Re-scrapes job descriptions for companies that previously failed due to
custom career pages redirecting away from Greenhouse. Uses the embed URL
pattern to fetch clean descriptions directly from Greenhouse.

Usage:
    python pipeline/utilities/backfill_greenhouse_descriptions.py --dry-run
    python pipeline/utilities/backfill_greenhouse_descriptions.py --company stabilityai
    python pipeline/utilities/backfill_greenhouse_descriptions.py --all
"""

import asyncio
import argparse
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pipeline.db_connection import supabase

# Companies that need re-scraping (custom career pages that redirect)
AFFECTED_COMPANIES = [
    'block', 'nuro', 'quantifind', 'agilityrobotics', 'foratravel',
    'netskope', 'skydio', 'stabilityai', 'tifin', 'lattice',
    'watchmakergenomics', 'hextechnologies', 'motive', 'duolingo',
    'capellaspace', 'pleo', 'feverup'
]


def extract_job_id(url: str) -> str:
    """Extract job ID from various URL formats."""
    # Pattern 1: gh_jid query parameter
    match = re.search(r'[?&]gh_jid=(\d+)', url)
    if match:
        return match.group(1)

    # Pattern 2: /jobs/ID
    match = re.search(r'/jobs/(\d+)', url)
    if match:
        return match.group(1)

    # Pattern 3: trailing numeric ID
    match = re.search(r'/(\d{6,})(?:\?|$)', url)
    if match:
        return match.group(1)

    return None


def is_valid_job_content(text: str) -> bool:
    """Check if text contains valid job description content."""
    if not text or len(text.strip()) < 200:
        return False

    text_lower = text.lower()

    # Check for job content indicators
    job_patterns = [
        'responsib', 'requirement', 'qualif', 'experience',
        'you will', 'the role', 'about us', 'the team',
        'skills', 'benefits', 'salary', 'compensation',
    ]
    has_job_content = sum(1 for p in job_patterns if p in text_lower) >= 2

    return has_job_content


async def fetch_description_from_embed(company_slug: str, job_id: str) -> str:
    """Fetch job description using Greenhouse embed URL."""
    from playwright.async_api import async_playwright

    embed_url = f"https://boards.greenhouse.io/embed/job_app?for={company_slug}&token={job_id}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )

        try:
            page = await context.new_page()
            await page.goto(embed_url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(2)

            # Check we stayed on greenhouse
            if 'greenhouse.io' not in page.url:
                return None

            body = await page.query_selector('body')
            if body:
                text = await body.text_content()
                if text and is_valid_job_content(text):
                    return ' '.join(text.split())  # Normalize whitespace

            return None

        finally:
            await browser.close()


async def backfill_company(company: str, dry_run: bool = True) -> dict:
    """Re-scrape all jobs for a company."""
    stats = {'total': 0, 'success': 0, 'failed': 0, 'skipped': 0}

    # Get all jobs for this company
    offset = 0
    jobs = []
    while True:
        batch = supabase.table('raw_jobs').select(
            'id, posting_url, raw_text, company'
        ).eq('source', 'greenhouse').ilike('company', company).range(offset, offset + 999).execute()

        if not batch.data:
            break
        jobs.extend(batch.data)
        offset += 1000
        if len(batch.data) < 1000:
            break

    stats['total'] = len(jobs)
    print(f"\n  Found {len(jobs)} jobs for {company}")

    for job in jobs:
        job_id = extract_job_id(job['posting_url'])

        if not job_id:
            print(f"    [SKIP] ID {job['id']}: Could not extract job_id from {job['posting_url']}")
            stats['skipped'] += 1
            continue

        # Check if already has valid content
        if is_valid_job_content(job.get('raw_text', '')):
            print(f"    [SKIP] ID {job['id']}: Already has valid content ({len(job['raw_text'])} chars)")
            stats['skipped'] += 1
            continue

        if dry_run:
            print(f"    [DRY-RUN] ID {job['id']}: Would re-scrape with embed URL (job_id={job_id})")
            stats['success'] += 1
            continue

        # Fetch new description
        try:
            description = await fetch_description_from_embed(company.lower(), job_id)

            if description and is_valid_job_content(description):
                # Update in database
                supabase.table('raw_jobs').update({
                    'raw_text': description,
                    'scraped_at': datetime.now(timezone.utc).isoformat()
                }).eq('id', job['id']).execute()

                print(f"    [OK] ID {job['id']}: Updated with {len(description)} chars")
                stats['success'] += 1
            else:
                print(f"    [FAIL] ID {job['id']}: Embed URL returned invalid content")
                stats['failed'] += 1

        except Exception as e:
            print(f"    [ERROR] ID {job['id']}: {str(e)[:80]}")
            stats['failed'] += 1

    return stats


async def main():
    parser = argparse.ArgumentParser(description='Backfill Greenhouse job descriptions')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--company', type=str, help='Re-scrape specific company only')
    parser.add_argument('--all', action='store_true', help='Re-scrape all affected companies')
    args = parser.parse_args()

    if not args.company and not args.all:
        parser.print_help()
        print("\nAffected companies:", ', '.join(AFFECTED_COMPANIES))
        return

    companies = [args.company] if args.company else AFFECTED_COMPANIES

    print(f"Backfill Greenhouse Descriptions")
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'LIVE'}")
    print(f"Companies: {', '.join(companies)}")
    print("=" * 60)

    total_stats = {'total': 0, 'success': 0, 'failed': 0, 'skipped': 0}

    for company in companies:
        if company.lower() not in [c.lower() for c in AFFECTED_COMPANIES]:
            print(f"\n[WARN] {company} not in affected companies list, skipping")
            continue

        print(f"\nProcessing: {company}")
        stats = await backfill_company(company, dry_run=args.dry_run)

        for key in total_stats:
            total_stats[key] += stats[key]

    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Total jobs: {total_stats['total']}")
    print(f"  Success: {total_stats['success']}")
    print(f"  Failed: {total_stats['failed']}")
    print(f"  Skipped: {total_stats['skipped']}")


if __name__ == '__main__':
    asyncio.run(main())
