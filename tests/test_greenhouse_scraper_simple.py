#!/usr/bin/env python3
"""
Simple test harness for Greenhouse scraper.

Tests the browser automation scraper with a few known Greenhouse companies.
"""

import asyncio
import json
import logging
from scrapers.greenhouse.greenhouse_scraper import GreenhouseScraper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Test Greenhouse scraper with a few companies"""

    # Companies to test - mix of sizes
    test_companies = [
        'openai',      # OpenAI (large, famous)
        'stripe',      # Stripe (large, famous)
        'figma',       # Figma (medium, growing)
    ]

    scraper = GreenhouseScraper(headless=True)
    results = {}

    print("\n" + "="*80)
    print("GREENHOUSE SCRAPER TEST")
    print("="*80)

    try:
        await scraper.init()

        for company_slug in test_companies:
            print(f"\n{'='*80}")
            print(f"Scraping: {company_slug.upper()}")
            print(f"{'='*80}")

            try:
                result = await scraper.scrape_company(company_slug)
                jobs = result['jobs']
                stats = result['stats']

                results[company_slug] = {
                    'status': 'success',
                    'job_count': len(jobs),
                    'stats': stats,
                    'jobs': [
                        {
                            'title': j.title,
                            'location': j.location,
                            'description_length': len(j.description),
                            'url': j.url,
                        }
                        for j in jobs[:3]  # Show first 3
                    ]
                }

                print(f"\n✓ SUCCESS: Found {len(jobs)} jobs")

                # Print filtering stats if filtering was enabled
                if stats['jobs_scraped'] > 0:
                    print(f"   Filtering stats:")
                    print(f"     - Total scraped: {stats['jobs_scraped']}")
                    print(f"     - Kept (relevant): {stats['jobs_kept']} ({100 - stats['filter_rate']:.1f}%)")
                    print(f"     - Filtered out: {stats['jobs_filtered']} ({stats['filter_rate']}%)")
                    print(f"     - Cost savings: {stats['cost_savings_estimate']}")

                for i, job in enumerate(jobs[:3], 1):
                    print(f"\n  [{i}] {job.title}")
                    print(f"      Location: {job.location}")
                    print(f"      Description: {len(job.description)} characters")
                    print(f"      URL: {job.url}")

                if len(jobs) > 3:
                    print(f"\n  ... and {len(jobs) - 3} more jobs")

            except Exception as e:
                logger.error(f"Failed to scrape {company_slug}: {e}")
                results[company_slug] = {
                    'status': 'failed',
                    'error': str(e)
                }

    finally:
        await scraper.close()

    # Save results
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")

    for company, result in results.items():
        status = result['status']
        if status == 'success':
            print(f"✓ {company:20} {result['job_count']:3d} jobs")
        else:
            print(f"✗ {company:20} FAILED")

    # Save full results to JSON
    with open('greenhouse_test_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nDetailed results saved to greenhouse_test_results.json")


if __name__ == '__main__':
    asyncio.run(main())
