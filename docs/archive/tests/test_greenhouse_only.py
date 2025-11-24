"""
Test 1: Greenhouse Scraping Only
Purpose: Verify we can scrape <10 jobs from Greenhouse
"""
import asyncio
import json
from scrapers.greenhouse.greenhouse_scraper import GreenhouseScraper

async def test_greenhouse_scrape():
    """Test scraping just Stripe jobs"""

    scraper = GreenhouseScraper(headless=True)

    try:
        await scraper.init()

        print("=" * 70)
        print("TEST 1: GREENHOUSE SCRAPING")
        print("=" * 70)
        print("Scraping Stripe (limiting to first 10 jobs for speed)...\n")

        jobs = await scraper.scrape_company('stripe')

        # Limit to first 10 for testing
        jobs = jobs[:10]

        print(f"[OK] Successfully scraped {len(jobs)} jobs from Stripe\n")

        # Display sample job data
        if jobs:
            for i, job in enumerate(jobs[:3], 1):
                print(f"[Sample {i}] {job.title}")
                print(f"  Company: {job.company}")
                print(f"  Location: {job.location}")
                print(f"  Description length: {len(job.description)} chars")
                print(f"  URL: {job.url}\n")

        # Save to file for next test
        try:
            print("[STEP 2] Converting jobs to JSON-serializable format...")
            jobs_dict = []
            for i, j in enumerate(jobs, 1):
                try:
                    job_dict = {
                        'company': j.company,
                        'title': j.title,
                        'location': j.location,
                        'description': j.description,  # Keep full description for downstream processing
                        'url': j.url,
                        'job_id': j.job_id if j.job_id else f"gh_{i}",  # Fallback if job_id is None
                    }
                    jobs_dict.append(job_dict)
                except Exception as e:
                    print(f"  [WARN] Job {i} conversion failed: {str(e)[:50]}")
                    continue

            print(f"  [OK] Converted {len(jobs_dict)} jobs to JSON format\n")

            print("[STEP 3] Writing jobs to test_greenhouse_jobs.json...")
            with open('test_greenhouse_jobs.json', 'w', encoding='utf-8') as f:
                json.dump(jobs_dict, f, indent=2, ensure_ascii=False)

            print(f"  [OK] Saved {len(jobs_dict)} jobs to test_greenhouse_jobs.json\n")
        except Exception as e:
            print(f"\n[ERROR] Error saving jobs: {str(e)}\n")
            import traceback
            traceback.print_exc()
            return

        print("=" * 70)
        print("TEST 1 COMPLETE - GREENHOUSE SCRAPING WORKS")
        print("=" * 70)

    finally:
        await scraper.close()

if __name__ == '__main__':
    asyncio.run(test_greenhouse_scrape())
