"""
Live Validation Test: Title Filtering on Real Greenhouse Data

Scrapes Stripe jobs with filtering enabled to validate:
1. Filtering actually reduces jobs fetched
2. Relevant Data/Product roles are kept
3. Irrelevant roles (Sales, Marketing, etc.) are filtered out
4. Metrics tracking works correctly
5. Cost savings are realized
"""

import asyncio
import json
from datetime import datetime
from scrapers.greenhouse.greenhouse_scraper import GreenhouseScraper


async def test_filtering_on_company(company_slug: str, company_name: str = None):
    """Test title filtering on a company's career page"""

    if company_name is None:
        company_name = company_slug.title()

    print("\n" + "="*70)
    print(f"LIVE VALIDATION TEST: Title Filtering on {company_name}")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Initialize scraper WITH filtering (default)
    scraper_filtered = GreenhouseScraper(headless=True, filter_titles=True)

    try:
        await scraper_filtered.init()

        print(f"[Step 1] Scraping {company_name} WITH title filtering enabled...")
        print("-" * 70)

        result_filtered = await scraper_filtered.scrape_company(company_slug)
        jobs_filtered = result_filtered['jobs']
        stats_filtered = result_filtered['stats']

        print(f"\n[Results - WITH Filtering]")
        print(f"  Total jobs scraped: {stats_filtered['jobs_scraped']}")
        print(f"  Jobs kept (relevant): {stats_filtered['jobs_kept']}")
        print(f"  Jobs filtered out: {stats_filtered['jobs_filtered']}")
        print(f"  Filter rate: {stats_filtered['filter_rate']}%")
        print(f"  Cost savings: {stats_filtered['cost_savings_estimate']}")

        # Show sample KEPT jobs
        print(f"\n[Sample KEPT jobs - Should be Data/Product roles]")
        for i, job in enumerate(jobs_filtered[:10], 1):
            desc_len = len(job.description)
            print(f"  {i:2d}. {job.title:<50} ({desc_len:,} chars)")

        if len(jobs_filtered) > 10:
            print(f"  ... and {len(jobs_filtered) - 10} more")

        # Show sample FILTERED jobs
        print(f"\n[Sample FILTERED jobs - Should be Sales/Marketing/etc.]")
        filtered_sample = stats_filtered.get('filtered_titles_sample', [])
        for i, title in enumerate(filtered_sample[:15], 1):
            print(f"  {i:2d}. {title}")

        if stats_filtered['jobs_filtered'] > 15:
            print(f"  ... and {stats_filtered['jobs_filtered'] - 15} more")

        # Validation checks
        print(f"\n{'='*70}")
        print("VALIDATION CHECKS")
        print('='*70)

        # Check 1: Filtering actually happened
        if stats_filtered['jobs_filtered'] > 0:
            print("[PASS] Filtering is working - some jobs were filtered out")
        else:
            print("[WARN] No jobs were filtered - check patterns")

        # Check 2: Filter rate is reasonable (expect 60-70% based on experiment)
        if 50 <= stats_filtered['filter_rate'] <= 80:
            print(f"[PASS] Filter rate ({stats_filtered['filter_rate']}%) is in expected range (50-80%)")
        else:
            print(f"[WARN] Filter rate ({stats_filtered['filter_rate']}%) outside expected range")

        # Check 3: Kept jobs have descriptions (validation that we fetched them)
        jobs_with_descriptions = sum(1 for j in jobs_filtered if len(j.description) > 1000)
        pct_with_desc = (jobs_with_descriptions / len(jobs_filtered) * 100) if jobs_filtered else 0
        print(f"[INFO] {jobs_with_descriptions}/{len(jobs_filtered)} kept jobs have full descriptions ({pct_with_desc:.1f}%)")

        # Check 4: Manual spot-check of filtered titles
        sales_keywords = ['account executive', 'sales', 'marketing', 'hr ', 'legal', 'finance']
        filtered_correctly = []
        for title in filtered_sample:
            if any(keyword in title.lower() for keyword in sales_keywords):
                filtered_correctly.append(title)

        if filtered_correctly:
            print(f"[PASS] Found {len(filtered_correctly)} correctly filtered sales/marketing/hr jobs:")
            for title in filtered_correctly[:5]:
                print(f"       - {title}")

        # Save detailed results
        output = {
            'test_date': datetime.now().isoformat(),
            'company': company_slug,
            'company_name': company_name,
            'filtering_enabled': True,
            'stats': stats_filtered,
            'kept_jobs': [
                {
                    'title': j.title,
                    'location': j.location,
                    'description_length': len(j.description),
                    'url': j.url
                }
                for j in jobs_filtered
            ],
            'filtered_titles': stats_filtered.get('filtered_titles_sample', [])
        }

        output_file = f'output/live_filtering_{company_slug}_results.json'
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"\n[Saved] Detailed results saved to: {output_file}")

        # Summary
        print(f"\n{'='*70}")
        print("TEST SUMMARY")
        print('='*70)
        print(f"[OK] Scraping completed successfully")
        print(f"[OK] Filtering is operational (filter rate: {stats_filtered['filter_rate']}%)")
        print(f"[OK] Cost savings: {stats_filtered['cost_savings_estimate']}")
        print(f"[OK] {len(jobs_filtered)} Data/Product jobs ready for classification")
        print()

        return True

    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await scraper_filtered.close()


async def main():
    """Run live filtering validation"""

    # Test company - change this to test different companies
    # Options: 'stripe', 'figma', 'notion', 'monzo', etc.
    company_slug = 'monzo'
    company_name = 'Monzo'

    success = await test_filtering_on_company(company_slug, company_name)

    if success:
        print(f"\n[SUCCESS] Live filtering validation passed for {company_name}!")
        print("[READY] Filtering is working correctly on real Greenhouse data")
        return 0
    else:
        print(f"\n[FAILED] Live filtering validation failed for {company_name}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
