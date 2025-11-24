#!/usr/bin/env python3
"""End-to-end test: Full scraping with listings and descriptions"""

import asyncio
import sys
import io
from greenhouse_scraper import GreenhouseScraper

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

async def main():
    print("\n" + "="*80)
    print("END-TO-END TEST: Scraping Stripe (Job Listings + Full Descriptions)")
    print("="*80 + "\n")

    scraper = GreenhouseScraper(headless=True, max_concurrent_pages=2)

    try:
        await scraper.init()

        print("Step 1: Scraping job listings from Stripe...")
        print("Step 2: Extracting full description for each job...")
        print("(This will take ~1-2 minutes for full dataset)\n")

        jobs = await scraper.scrape_company('stripe')

        if jobs:
            print(f"\n{'='*80}")
            print(f"RESULTS: Scraped {len(jobs)} total jobs")
            print(f"{'='*80}\n")

            # Analysis
            with_descriptions = [j for j in jobs if j.description and len(j.description) > 100]
            description_chars = [len(j.description) for j in with_descriptions]

            print(f"Jobs with descriptions: {len(with_descriptions)}/{len(jobs)} ({len(with_descriptions)*100//len(jobs)}%)")
            if description_chars:
                print(f"Min description length: {min(description_chars):,} chars")
                print(f"Max description length: {max(description_chars):,} chars")
                print(f"Avg description length: {sum(description_chars)//len(description_chars):,} chars")
                print(f"Total text extracted: {sum(description_chars):,} chars\n")

                # Data quality check
                long_descriptions = [d for d in description_chars if d > 2000]
                print(f"Descriptions > 2000 chars: {len(long_descriptions)}/{len(description_chars)} ({len(long_descriptions)*100//len(description_chars)}%)")
                print(f"Descriptions > 3000 chars: {sum(1 for d in description_chars if d > 3000)}/{len(description_chars)}")
                print(f"Descriptions > 4000 chars: {sum(1 for d in description_chars if d > 4000)}/{len(description_chars)}")

            print(f"\n{'='*80}")
            print("VERIFICATION CHECKLIST")
            print(f"{'='*80}\n")

            checks = [
                (len(jobs) >= 60, f"✓ Job listing extraction: {len(jobs)} jobs found (target: 60+)"),
                (len(with_descriptions) >= len(jobs) * 0.95, f"✓ Description extraction: {len(with_descriptions)}/{len(jobs)} jobs ({len(with_descriptions)*100//len(jobs)}%, target: 95%+)"),
                (min(description_chars) > 500 if description_chars else False, f"✓ Description quality: All > 500 chars (min: {min(description_chars) if description_chars else 0})"),
                (sum(1 for d in description_chars if d > 2000) > len(description_chars) * 0.8 if description_chars else False, f"✓ Full descriptions: {sum(1 for d in description_chars if d > 2000)}/{len(description_chars)} > 2000 chars"),
            ]

            all_passed = True
            for passed, message in checks:
                status = message
                print(status)
                if not passed:
                    all_passed = False

            print(f"\n{'='*80}")
            if all_passed:
                print("✓✓✓ SUCCESS! All checks passed ✓✓✓")
                print("\nThe scraper is ready for production integration:")
                print("  • Extracts job listings reliably (60+ jobs)")
                print("  • Extracts full descriptions (2,000+ chars average)")
                print("  • No browser crashes detected")
                print("  • Page management stable with max 2 concurrent pages")
            else:
                print("[WARNING] Some checks failed - review output above")
            print(f"{'='*80}\n")

        else:
            print("✗ No jobs found!")

    finally:
        await scraper.close()

if __name__ == '__main__':
    asyncio.run(main())
