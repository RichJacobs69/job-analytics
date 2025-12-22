#!/usr/bin/env python3
"""
Greenhouse Slug Validator

Tests Greenhouse slugs that have zero jobs in the database using Playwright
to determine if they're valid (board exists) or invalid (404 error).

Simple approach: If page loads without 404, it's VALID.

Usage:
    python pipeline/utilities/validate_greenhouse_slugs.py [--batch-size 20] [--limit 100]

Options:
    --batch-size N      Number of slugs to test in parallel (default: 5)
    --limit N           Limit total slugs to test (default: all)
    --save-results      Save results to validate_greenhouse_results.json
"""

import json
import asyncio
from pathlib import Path
from supabase import create_client
import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright
import sys
import argparse
from datetime import datetime

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# Base URLs to try (EXACTLY same as discover_greenhouse_slugs.py)
BASE_URLS = [
    "https://job-boards.greenhouse.io",
    "https://job-boards.eu.greenhouse.io",
    "https://boards.greenhouse.io",
    "https://board.greenhouse.io",
    "https://boards.greenhouse.io/embed/job_board?for=",
]


def get_zero_job_slugs():
    """Get all Greenhouse slugs with zero jobs in database"""
    # Get all companies that have jobs in the database
    response = supabase.table("raw_jobs").select("company").eq("source", "greenhouse").execute()
    greenhouse_companies_in_db = set(job['company'] for job in response.data if job.get('company'))

    # Load all companies from mapping
    mapping_path = Path(__file__).parent.parent.parent / 'config' / 'greenhouse' / 'company_ats_mapping.json'
    with open(mapping_path) as f:
        mapping = json.load(f)

    # Find companies with zero jobs
    zero_job_companies = []
    for company, data in mapping.get('greenhouse', {}).items():
        slug = data.get('slug')
        if slug and company not in greenhouse_companies_in_db:
            zero_job_companies.append((company, slug))

    return zero_job_companies


async def test_slug_with_playwright(slug: str, timeout: int = 15000) -> tuple[bool, str | None]:
    """
    Test if a Greenhouse slug is valid using Playwright.

    Uses EXACT same validation logic as discover_greenhouse_slugs.py:
    - Try all URL patterns (including embed pattern)
    - If ANY pattern loads without 404 error, it's VALID
    - If ALL patterns return 404, it's INVALID

    Returns: (is_valid, working_url or None)
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            for base_url in BASE_URLS:
                # Handle embed URL pattern (ends with ?for=)
                if base_url.endswith('?for='):
                    url = f"{base_url}{slug}"
                else:
                    url = f"{base_url}/{slug}"

                page = None
                try:
                    page = await browser.new_page(
                        viewport={'width': 1280, 'height': 720}
                    )

                    try:
                        await page.goto(url, wait_until='networkidle', timeout=timeout)
                    except asyncio.TimeoutError:
                        # Timeout is not a 404 - still might be valid
                        if page:
                            await page.close()
                        continue

                    # Wait for page to fully load
                    await page.wait_for_timeout(1000)

                    # Get page content
                    content = await page.content()
                    content_lower = content.lower()

                    # Check for various Greenhouse error messages
                    error_messages = [
                        "sorry, but we can't find that page",
                        "the job board you were viewing is no longer active",
                        "page not found"
                    ]
                    is_error = any(msg in content_lower for msg in error_messages)

                    # Fallback: check for error page indicators
                    if not is_error:
                        # Genuine error pages are typically short; real job boards are large
                        if len(content) < 10000:  # Error pages usually < 10KB
                            is_error = True

                    if not is_error:
                        # Page loaded successfully without error message - it's valid!
                        await page.close()
                        await browser.close()
                        return True, url

                    await page.close()

                except Exception as e:
                    # Error on this URL, try next
                    if page:
                        try:
                            await page.close()
                        except:
                            pass
                    continue

            # All URLs either returned 404 or failed to load
            await browser.close()
            return False, None

    except Exception as e:
        return False, None


async def test_batch_concurrent(companies: list, batch_size: int = 5) -> dict:
    """
    Test multiple slugs concurrently in batches.

    Returns dict with 'valid' and 'invalid' lists
    """
    results = {'valid': [], 'invalid': []}
    total = len(companies)

    for i in range(0, total, batch_size):
        batch = companies[i:i+batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total + batch_size - 1) // batch_size

        print(f"\n[Batch {batch_num}/{total_batches}]")

        tasks = [
            test_slug_with_playwright(slug)
            for company, slug in batch
        ]
        batch_results = await asyncio.gather(*tasks)

        for (company, slug), (is_valid, url) in zip(batch, batch_results):
            if is_valid:
                status = "OK"
                results['valid'].append((company, slug, url))
            else:
                status = "XX"
                results['invalid'].append((company, slug))

            print(f"  [{status}] {company:40} -> {slug}")

        tested = min(i + batch_size, total)
        print(f"  Progress: {tested}/{total}")

    return results


def print_results(results: dict):
    """Print summary of validation results"""
    print("\n" + "=" * 80)
    print("VALIDATION RESULTS")
    print("=" * 80)

    total = len(results['valid']) + len(results['invalid'])
    print(f"\nTotal slugs tested: {total}")
    print(f"Valid boards (still active): {len(results['valid'])}")
    print(f"Invalid boards (404 or error): {len(results['invalid'])}")

    if results['valid']:
        print(f"\n{'=' * 40}")
        print("VALID SLUGS (still have job boards)")
        print("=" * 40)
        for company, slug, url in sorted(results['valid']):
            print(f"  {company:40} -> {slug}")

    if results['invalid']:
        print(f"\n{'=' * 40}")
        print("INVALID SLUGS (should be removed from mapping)")
        print("=" * 40)
        for company, slug in sorted(results['invalid']):
            print(f"  {company:40} -> {slug}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-size', type=int, default=5,
                        help='Number of slugs to test in parallel (default: 5)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit total slugs to test (default: all)')
    parser.add_argument('--save-results', action='store_true',
                        help='Save results to validate_greenhouse_results.json')

    args = parser.parse_args()

    print("=" * 80)
    print("GREENHOUSE SLUG VALIDATOR")
    print("=" * 80)
    print("\nQuerying database for companies with zero jobs...")

    # Get companies with zero jobs
    zero_job_companies = get_zero_job_slugs()

    if not zero_job_companies:
        print("\nNo companies with zero jobs found!")
        print("All Greenhouse companies in the mapping have jobs in the database.")
        return

    print(f"\nFound {len(zero_job_companies)} companies with zero jobs")

    if args.limit:
        zero_job_companies = zero_job_companies[:args.limit]
        print(f"Limited to: {len(zero_job_companies)} companies")

    print(f"\nTesting with batch size: {args.batch_size}")
    print("Status: [OK] = Valid board (still active), [XX] = Invalid (404 or error)")

    # Run validation
    results = asyncio.run(test_batch_concurrent(zero_job_companies, args.batch_size))

    # Print results
    print_results(results)

    # Save results if requested
    if args.save_results:
        output_path = Path(__file__).parent.parent.parent / 'output' / 'validate_greenhouse_results.json'
        output_path.parent.mkdir(exist_ok=True)

        save_data = {
            'timestamp': datetime.now().isoformat(),
            'total_tested': len(zero_job_companies),
            'valid': [(c, s, u) for c, s, u in results['valid']],
            'invalid': [(c, s) for c, s in results['invalid']]
        }

        with open(output_path, 'w') as f:
            json.dump(save_data, f, indent=2)

        print(f"\nResults saved to: {output_path}")

    # Recommendations
    if results['invalid']:
        print("\n" + "=" * 80)
        print("RECOMMENDATIONS")
        print("=" * 80)
        print(f"\n{len(results['invalid'])} companies have invalid boards and should be removed from:")
        print("  config/greenhouse/company_ats_mapping.json")
        print("\nThese companies either:")
        print("  - Migrated to a different ATS")
        print("  - Changed their Greenhouse slug")
        print("  - No longer use Greenhouse")


if __name__ == '__main__':
    main()
