"""
Test the ATS scraper orchestrator on sample companies
"""

import asyncio
import sys
import io

# Windows UTF-8 fix
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from ats_scraper_orchestrator import ATSScraperOrchestrator


async def test_orchestrator():
    """Test scraping on 5 companies"""

    test_companies = [
        'Stripe',
        'Figma',
        'GitHub',
        'Coinbase',
        'MongoDB',
    ]

    print("="*70)
    print("ORCHESTRATOR TEST")
    print("="*70)

    orchestrator = ATSScraperOrchestrator()

    print(f"\nLoaded mapping for {len(orchestrator.mapping)} companies\n")

    # Show which ATS each test company uses
    print("Test companies and their ATS:")
    print("-"*70)
    for company in test_companies:
        ats_info = orchestrator.get_ats_for_company(company)
        if ats_info:
            ats_type, ats_slug = ats_info
            print(f"  {company:20} -> {ats_type:15} ({ats_slug})")
        else:
            print(f"  {company:20} -> NOT FOUND")

    try:
        print("\n" + "="*70)
        print("Initializing browser...")
        print("="*70)
        await orchestrator.init()

        print("\n" + "="*70)
        print("Scraping companies...")
        print("="*70)

        results = await orchestrator.scrape_and_format(test_companies)

        # Print summary
        print("\n" + "="*70)
        print("RESULTS SUMMARY")
        print("="*70)

        total_jobs = 0
        for company_name, jobs in results.items():
            job_count = len(jobs)
            total_jobs += job_count
            status = "[OK]" if job_count > 0 else "[FAIL]"
            print(f"{status} {company_name:20} {job_count:3d} jobs")

        print("-"*70)
        print(f"TOTAL: {total_jobs} jobs")

        # Show sample jobs
        if total_jobs > 0:
            print("\n" + "="*70)
            print("SAMPLE JOBS (first job from each company)")
            print("="*70)

            for company_name, jobs in results.items():
                if jobs:
                    job = jobs[0]
                    print(f"\n[{company_name}]")
                    print(f"  Title: {job['title']}")
                    print(f"  Location: {job['location']}")
                    print(f"  Department: {job['department']}")
                    print(f"  Description (first 250 chars): {job['description'][:250]}...")
                    print(f"  URL: {job['url']}")
                    print(f"  Text Source: {job['text_source']}")

    finally:
        print("\n" + "="*70)
        print("Closing browser...")
        print("="*70)
        await orchestrator.close()
        print("Done!")


if __name__ == '__main__':
    asyncio.run(test_orchestrator())
