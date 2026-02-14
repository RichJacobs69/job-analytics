#!/usr/bin/env python3
"""
Greenhouse API Coverage Validation Script

Quick validation that the Greenhouse public Job Board API works for our
full company universe before migrating from Playwright to REST API.

Usage:
    python tests/test_greenhouse_api_coverage.py
    python tests/test_greenhouse_api_coverage.py --sample 20  # Quick test with 20 companies
"""

import json
import sys
import time
import requests
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

GREENHOUSE_API_URL = "https://boards-api.greenhouse.io/v1/boards"


def validate_api_coverage(sample_size: int = 0):
    """Validate Greenhouse API access for all companies in mapping."""

    # Load company mapping
    config_path = Path(__file__).parent.parent / 'config' / 'greenhouse' / 'company_ats_mapping.json'
    with open(config_path) as f:
        data = json.load(f)

    greenhouse = data.get('greenhouse', {})
    companies = list(greenhouse.items())

    if sample_size > 0:
        companies = companies[:sample_size]

    total = len(companies)
    print(f"Testing {total} companies against Greenhouse API...\n")

    results = {
        'success': 0,
        'failure': 0,
        'total_jobs': 0,
        'with_content': 0,
        'with_pay_ranges': 0,
        'embed_success': 0,
        'embed_total': 0,
        'eu_success': 0,
        'eu_total': 0,
        'failures': [],
    }

    for i, (name, info) in enumerate(companies, 1):
        slug = info['slug']
        url_type = info.get('url_type', 'standard')

        # Track embed/eu types
        if url_type == 'embed':
            results['embed_total'] += 1
        elif url_type == 'eu':
            results['eu_total'] += 1

        try:
            url = f"{GREENHOUSE_API_URL}/{slug}/jobs?content=true"
            response = requests.get(url, timeout=15, headers={
                'User-Agent': 'job-analytics-bot/1.0',
                'Accept': 'application/json'
            })

            if response.status_code == 200:
                data = response.json()
                jobs = data.get('jobs', [])
                job_count = len(jobs)

                results['success'] += 1
                results['total_jobs'] += job_count

                if url_type == 'embed':
                    results['embed_success'] += 1
                elif url_type == 'eu':
                    results['eu_success'] += 1

                # Check for content and pay_input_ranges
                has_content = any(j.get('content') for j in jobs[:3])
                has_pay = any(j.get('pay_input_ranges') for j in jobs[:3])

                if has_content:
                    results['with_content'] += 1
                if has_pay:
                    results['with_pay_ranges'] += 1

                status = "OK"
                extras = f"{job_count} jobs"
                if has_pay:
                    extras += " [PAY]"
            else:
                results['failure'] += 1
                results['failures'].append((slug, url_type, response.status_code))
                status = f"FAIL ({response.status_code})"
                extras = ""

        except Exception as e:
            results['failure'] += 1
            results['failures'].append((slug, url_type, str(e)[:50]))
            status = "ERROR"
            extras = str(e)[:40]

        print(f"  [{i}/{total}] {slug:40s} {status:15s} {extras}")

        # Light rate limiting
        time.sleep(0.3)

    # Summary
    success_rate = (results['success'] / total * 100) if total > 0 else 0

    print(f"\n{'='*60}")
    print(f"GREENHOUSE API COVERAGE SUMMARY")
    print(f"{'='*60}")
    print(f"Total companies tested:    {total}")
    print(f"Successful:                {results['success']} ({success_rate:.1f}%)")
    print(f"Failed:                    {results['failure']}")
    print(f"Total jobs accessible:     {results['total_jobs']}")
    print(f"With content field:        {results['with_content']}")
    print(f"With pay_input_ranges:     {results['with_pay_ranges']}")
    print(f"")
    print(f"Embed type ({results['embed_total']} total):    {results['embed_success']} success")
    print(f"EU type ({results['eu_total']} total):       {results['eu_success']} success")
    print(f"{'='*60}")

    if results['failures']:
        print(f"\nFailed companies ({len(results['failures'])}):")
        for slug, url_type, reason in results['failures']:
            print(f"  - {slug} (type={url_type}): {reason}")

    # Success criteria: >95%
    if success_rate >= 95:
        print(f"\n[DONE] Coverage validation PASSED ({success_rate:.1f}% >= 95%)")
    else:
        print(f"\n[WARNING] Coverage validation below threshold ({success_rate:.1f}% < 95%)")

    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Validate Greenhouse API coverage')
    parser.add_argument('--sample', type=int, default=0, help='Test only N companies (0 = all)')
    args = parser.parse_args()

    validate_api_coverage(sample_size=args.sample)
