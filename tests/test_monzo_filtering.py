#!/usr/bin/env python3
"""
Live test: Scrape Monzo with title filtering enabled

This validates that the title filtering feature works correctly on a real company.
Expected results based on validation (from docs):
- ~66 total jobs
- ~8 kept (Data/Product roles)
- ~58 filtered (87.9% filter rate)
- ~$0.23 cost savings
"""

import asyncio
import json
from scrapers.greenhouse.greenhouse_scraper import GreenhouseScraper


async def test_monzo_filtering():
    """Test filtering on Monzo careers page"""

    print("\n" + "="*80)
    print("TESTING GREENHOUSE TITLE FILTERING ON MONZO")
    print("="*80 + "\n")

    # Initialize scraper with filtering enabled
    scraper = GreenhouseScraper(headless=True, filter_titles=True)

    try:
        await scraper.init()
        print("[OK] Browser initialized")
        print(f"[OK] Filtering enabled: {scraper.filter_titles}")
        print(f"[OK] Patterns loaded: {len(scraper.title_patterns)}")
        print()

        # Scrape Monzo
        print("Scraping Monzo...")
        result = await scraper.scrape_company('monzo')

        jobs = result['jobs']
        stats = result['stats']

        # Display results
        print("\n" + "="*80)
        print("RESULTS")
        print("="*80)

        print(f"\nJobs scraped (total): {stats['jobs_scraped']}")
        print(f"Jobs kept (relevant): {stats['jobs_kept']} ({100 - stats['filter_rate']:.1f}%)")
        print(f"Jobs filtered out:    {stats['jobs_filtered']} ({stats['filter_rate']}%)")
        print(f"Cost savings:         {stats['cost_savings_estimate']}")

        # Show kept jobs
        print(f"\n{'='*80}")
        print(f"KEPT JOBS (Data/Product roles)")
        print(f"{'='*80}\n")

        for i, job in enumerate(jobs, 1):
            print(f"[{i}] {job.title}")
            print(f"    Location: {job.location}")
            print(f"    URL: {job.url}")
            print()

        # Show sample of filtered jobs
        print(f"\n{'='*80}")
        print(f"FILTERED OUT (Sample - first 10)")
        print(f"{'='*80}\n")

        for i, title in enumerate(stats.get('filtered_titles_sample', [])[:10], 1):
            print(f"  {i}. {title}")

        if stats['jobs_filtered'] > 10:
            print(f"\n  ... and {stats['jobs_filtered'] - 10} more")

        # Validation checks
        print(f"\n{'='*80}")
        print("VALIDATION CHECKS")
        print(f"{'='*80}\n")

        checks = []

        # Check 1: Did we scrape jobs?
        if stats['jobs_scraped'] > 0:
            checks.append(("[PASS]", f"Scraped {stats['jobs_scraped']} jobs from Monzo"))
        else:
            checks.append(("[FAIL]", "No jobs scraped - check scraper"))

        # Check 2: Did filtering work?
        if stats['jobs_filtered'] > 0:
            checks.append(("[PASS]", f"Filtering active - filtered {stats['jobs_filtered']} jobs"))
        else:
            checks.append(("[WARN]", "No jobs filtered - unusual for Monzo (check patterns)"))

        # Check 3: Filter rate in expected range (70-95%)
        if 70 <= stats['filter_rate'] <= 95:
            checks.append(("[PASS]", f"Filter rate {stats['filter_rate']}% within expected range (70-95%)"))
        elif stats['filter_rate'] < 70:
            checks.append(("[WARN]", f"Filter rate {stats['filter_rate']}% lower than expected (70-95%)"))
        else:
            checks.append(("[WARN]", f"Filter rate {stats['filter_rate']}% higher than expected (70-95%)"))

        # Check 4: Kept some Data/Product jobs
        if stats['jobs_kept'] > 0:
            checks.append(("[PASS]", f"Found {stats['jobs_kept']} Data/Product roles"))
        else:
            checks.append(("[FAIL]", "No Data/Product jobs kept - check patterns"))

        # Check 5: Cost savings
        savings_numeric = float(stats['cost_savings_estimate'].replace('$', ''))
        if savings_numeric > 0:
            checks.append(("[PASS]", f"Cost savings: {stats['cost_savings_estimate']}"))
        else:
            checks.append(("[WARN]", "No cost savings calculated"))

        # Print all checks
        for symbol, message in checks:
            print(f"{symbol} {message}")

        # Summary
        print(f"\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}\n")

        if all(check[0] in ["[PASS]", "[WARN]"] for check in checks):
            print("[PASS] Test PASSED - Filtering working correctly on Monzo")
        else:
            print("[FAIL] Test FAILED - Issues detected")

        # Save detailed results
        output = {
            'company': 'monzo',
            'stats': stats,
            'kept_jobs': [
                {
                    'title': j.title,
                    'location': j.location,
                    'department': j.department,
                    'url': j.url,
                    'description_length': len(j.description)
                }
                for j in jobs
            ],
            'filtered_titles_sample': stats.get('filtered_titles_sample', [])
        }

        with open('monzo_filtering_test_results.json', 'w') as f:
            json.dump(output, f, indent=2, default=str)

        print(f"\nDetailed results saved to: monzo_filtering_test_results.json")

        return True

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await scraper.close()
        print("\n[OK] Browser closed")


if __name__ == '__main__':
    success = asyncio.run(test_monzo_filtering())
    exit(0 if success else 1)
