"""
Test Figma location filtering - shows how filters work in stages.

This test demonstrates the production filtering pipeline:
1. Title filtering only (no location filter)
2. Both title + location filtering
3. Shows what gets filtered at each stage
"""

import asyncio
from collections import Counter
from scrapers.greenhouse.greenhouse_scraper import GreenhouseScraper

async def test_figma():
    """Test filtering stages on Figma jobs."""

    print("=" * 80)
    print("FIGMA FILTERING TEST (PRODUCTION PIPELINE)")
    print("=" * 80)
    print()

    # STEP 1: Title filtering only
    print("STEP 1: Title filtering only (no location filter)")
    print("-" * 80)
    scraper_title_only = GreenhouseScraper(
        headless=True,
        filter_titles=True,  # Enable title filter
        filter_locations=False  # Disable location filter
    )
    await scraper_title_only.init()

    try:
        result_title = await scraper_title_only.scrape_company('figma')
        title_filtered_jobs = result_title['jobs']
        stats_title = result_title['stats']

        print(f"Total jobs scraped: {stats_title['jobs_scraped']}")
        print(f"Filtered by title: {stats_title['filtered_by_title']}")
        print(f"Jobs kept: {stats_title['jobs_kept']}")
        print()

        # Show location distribution of jobs that passed title filter
        location_counter = Counter(job.location for job in title_filtered_jobs)
        print("LOCATION DISTRIBUTION (Data/Product roles that passed title filter):")
        print("-" * 80)
        for location, count in location_counter.most_common():
            is_target = any(target in location.lower() for target in
                          ['london', 'uk', 'new york', 'nyc', 'denver', 'colorado', 'england'])
            target_flag = " [TARGET]" if is_target else ""
            print(f"  {location}: {count} jobs{target_flag}")

        target_count = sum(count for loc, count in location_counter.items()
                          if any(target in loc.lower() for target in
                                ['london', 'uk', 'new york', 'nyc', 'denver', 'colorado', 'england']))
        non_target_count = len(title_filtered_jobs) - target_count

        print()
        print(f"Summary: {target_count} in target locations, {non_target_count} outside target ({non_target_count/len(title_filtered_jobs)*100:.1f}% waste without location filtering)")
        print()

    finally:
        await scraper_title_only.close()

    # STEP 2: Both title + location filtering
    print()
    print("STEP 2: Both title + location filtering (production pipeline)")
    print("-" * 80)
    scraper_both = GreenhouseScraper(
        headless=True,
        filter_titles=True,  # Enable title filter
        filter_locations=True  # Enable location filter
    )
    await scraper_both.init()

    try:
        result_both = await scraper_both.scrape_company('figma')
        both_filtered_jobs = result_both['jobs']
        stats_both = result_both['stats']

        print(f"Total jobs scraped: {stats_both['jobs_scraped']}")
        print(f"Filtered by title: {stats_both['filtered_by_title']}")
        print(f"Filtered by location: {stats_both['filtered_by_location']}")
        print(f"Final jobs kept: {stats_both['jobs_kept']}")
        print(f"Total filtered: {stats_both['jobs_filtered']} ({stats_both['filter_rate']}%)")
        print(f"Cost savings: {stats_both['cost_savings_estimate']}")
        print()

        # Show final location distribution
        if both_filtered_jobs:
            location_counter_final = Counter(job.location for job in both_filtered_jobs)
            print("FINAL LOCATION DISTRIBUTION (Target cities only):")
            print("-" * 80)
            for location, count in location_counter_final.most_common():
                print(f"  {location}: {count} jobs")
        else:
            print("No jobs passed both filters")

        print()

        # Show sample filtered locations
        if stats_both.get('filtered_locations_sample'):
            unique_filtered_locs = list(set(stats_both['filtered_locations_sample'][:20]))
            print("SAMPLE FILTERED LOCATIONS (First 20 unique):")
            print("-" * 80)
            for location in unique_filtered_locs:
                print(f"  - {location}")

        print()
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Stage 1 (title filter): {stats_title['jobs_scraped']} -> {stats_title['jobs_kept']} jobs")
        print(f"Stage 2 (location filter): {stats_title['jobs_kept']} -> {stats_both['jobs_kept']} jobs")
        print(f"Overall reduction: {stats_title['jobs_scraped']} -> {stats_both['jobs_kept']} ({stats_both['filter_rate']}%)")
        print()

    finally:
        await scraper_both.close()


if __name__ == "__main__":
    asyncio.run(test_figma())
