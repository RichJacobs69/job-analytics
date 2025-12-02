"""
Quick test to validate DoubleVerify scraping fixes
"""
import asyncio
import sys
sys.path.insert(0, 'C:\\Cursor Projects\\job-analytics')

from scrapers.greenhouse.greenhouse_scraper import GreenhouseScraper

async def test_doubleverify():
    scraper = GreenhouseScraper(
        headless=True,
        filter_titles=True,
        filter_locations=True
    )

    try:
        await scraper.init()
        result = await scraper.scrape_company('doubleverify')

        jobs = result['jobs']
        stats = result['stats']

        print(f"\n{'='*70}")
        print(f"DOUBLEVERIFY TEST RESULTS")
        print(f"{'='*70}")
        print(f"Total scraped: {stats['jobs_scraped']}")
        print(f"Kept (relevant): {stats['jobs_kept']}")
        print(f"Filtered out: {stats['jobs_filtered']}")
        print(f"  - By title: {stats['filtered_by_title']}")
        print(f"  - By location: {stats['filtered_by_location']}")
        print(f"\nJobs kept:")
        for job in jobs:
            print(f"  - {job.title} ({job.location})")

        # Expected: Should find Product Manager jobs in NYC
        if stats['jobs_kept'] > 0:
            print(f"\n✅ SUCCESS: Found {stats['jobs_kept']} relevant jobs!")
        else:
            print(f"\n❌ FAILED: No jobs kept - bug not fixed")

    finally:
        await scraper.close()

if __name__ == '__main__':
    asyncio.run(test_doubleverify())
