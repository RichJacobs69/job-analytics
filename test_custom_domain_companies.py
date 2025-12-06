"""
Test script to check if custom domain companies have standard Greenhouse boards.

Tests companies that use custom career pages but may also have standard GH boards.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from scrapers.greenhouse.greenhouse_scraper import GreenhouseScraper


async def test_company(scraper, company_name, slug, max_jobs=5):
    """Test if a company's Greenhouse board is accessible."""
    print(f"\n{'='*70}")
    print(f"Testing: {company_name} (slug: {slug})")
    print('='*70)

    try:
        result = await scraper.scrape_company(slug, max_jobs=max_jobs)
        jobs = result['jobs']
        stats = result['stats']

        if jobs:
            print(f"[SUCCESS] Found {len(jobs)} jobs")
            print(f"   Total scraped: {stats['jobs_scraped']}")
            print(f"   Kept after filters: {stats['jobs_kept']}")
            print(f"   Filter rate: {stats.get('filter_rate', 0)}%")
            print("\n   Sample jobs:")
            for i, job in enumerate(jobs[:3], 1):
                print(f"   {i}. {job.title}")
                print(f"      Location: {job.location}")
                print(f"      URL: {job.url[:80]}...")
            return True
        else:
            print(f"[FAIL] NO JOBS FOUND - Board may not exist or has no listings")
            return False

    except Exception as e:
        print(f"[ERROR] {str(e)[:100]}")
        return False


async def main():
    """Test multiple custom domain companies."""

    # Companies to test (from custom domain list)
    test_companies = [
        ('Brex', 'brex'),
        ('Vanta', 'vanta'),
        ('Unity', 'unity'),
        ('Axonius', 'axonius'),
    ]

    print("="*70)
    print("TESTING CUSTOM DOMAIN COMPANIES")
    print("="*70)
    print("\nChecking if these companies have standard Greenhouse boards...")
    print("(They use custom career pages but may also have standard boards)")

    # Initialize scraper
    scraper = GreenhouseScraper(
        headless=True,
        filter_titles=True,
        filter_locations=True,
        max_concurrent_pages=2
    )

    try:
        await scraper.init()

        results = {}
        for company_name, slug in test_companies:
            success = await test_company(scraper, company_name, slug, max_jobs=5)
            results[company_name] = success
            await asyncio.sleep(2)  # Rate limiting between companies

        # Summary
        print(f"\n{'='*70}")
        print("SUMMARY")
        print('='*70)

        working = [name for name, success in results.items() if success]
        not_working = [name for name, success in results.items() if not success]

        print(f"\n[SUCCESS] Companies with standard Greenhouse boards ({len(working)}):")
        for name in working:
            print(f"   - {name}")

        print(f"\n[FAIL] Companies without standard boards ({len(not_working)}):")
        for name in not_working:
            print(f"   - {name}")

        if working:
            print("\nRecommendation: Add working companies to config if not already there")
        if not_working:
            print("\nRecommendation: Skip non-working companies or implement custom scraping")

    finally:
        await scraper.close()


if __name__ == '__main__':
    asyncio.run(main())
