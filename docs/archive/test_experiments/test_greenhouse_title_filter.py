"""
Greenhouse Title Filter Experiment

Tests whether title-based filtering can effectively reduce classification costs
by filtering out irrelevant jobs (Sales, Marketing, HR, Finance, etc.) before
passing to the Claude LLM classifier.

Purpose:
- Validate title extraction consistency across different Greenhouse sites
- Test regex pattern effectiveness for Data/Product role identification
- Identify false negatives (relevant jobs accidentally filtered out)
- Measure cost savings potential (% of jobs filtered out)
- Validate integration with existing classifier pipeline

Usage:
    python test_greenhouse_title_filter.py

Output:
    - Console: Summary statistics and sample job titles
    - File: output/title_filter_experiment.json (detailed results)
"""

import asyncio
import re
import json
from datetime import datetime
from scrapers.greenhouse.greenhouse_scraper import scrape_company_jobs

# Title patterns for Data and Product roles
# These match against job titles to identify relevant positions
RELEVANT_TITLE_PATTERNS = [
    r'data (analyst|engineer|scientist|architect)',
    r'analytics engineer',
    r'ml engineer|machine learning|ai engineer',
    r'product manager|product owner|tpm',
    r'growth (pm|product)',
]

def is_relevant_role(title: str) -> bool:
    """
    Check if job title matches Data/Product families.

    Args:
        title: Job title string to evaluate

    Returns:
        True if title matches any pattern in RELEVANT_TITLE_PATTERNS
    """
    title_lower = title.lower()
    return any(re.search(pattern, title_lower) for pattern in RELEVANT_TITLE_PATTERNS)


async def test_title_filtering():
    """
    Test title filtering across diverse Greenhouse companies.

    This experiment:
    1. Scrapes jobs from multiple companies (unfiltered)
    2. Applies title-based filtering
    3. Reports statistics and samples for manual review
    4. Saves detailed results for analysis
    """

    # Test across diverse company types
    # - Data-heavy companies (expect high % relevant): Databricks, OpenAI, Scale
    # - General tech companies (expect medium % relevant): Stripe, Notion, Figma
    test_companies = [
        {"name": "Stripe", "url": "https://stripe.com/jobs"},
        {"name": "Databricks", "url": "https://databricks.com/company/careers"},
        {"name": "Figma", "url": "https://figma.com/careers"},
        {"name": "Notion", "url": "https://notion.so/careers"},
        {"name": "OpenAI", "url": "https://openai.com/careers"},
    ]

    results = []
    total_across_all = 0
    relevant_across_all = 0

    for company in test_companies:
        print(f"\n{'='*70}")
        print(f"Testing: {company['name']}")
        print(f"{'='*70}")

        try:
            # Scrape all jobs (unfiltered)
            all_jobs = await scrape_company_jobs(company['url'])

            # Apply filter
            relevant_jobs = [j for j in all_jobs if is_relevant_role(j['title'])]
            filtered_out = [j for j in all_jobs if not is_relevant_role(j['title'])]

            # Calculate stats
            total = len(all_jobs)
            relevant_count = len(relevant_jobs)
            filtered_count = len(filtered_out)
            pct_relevant = (relevant_count / total * 100) if total > 0 else 0

            total_across_all += total
            relevant_across_all += relevant_count

            print(f"Total jobs scraped: {total}")
            print(f"Relevant jobs (match patterns): {relevant_count} ({pct_relevant:.1f}%)")
            print(f"Filtered out: {filtered_count} ({100-pct_relevant:.1f}%)")

            # Show sample relevant jobs
            print(f"\n✅ Sample RELEVANT jobs (first 5):")
            for job in relevant_jobs[:5]:
                print(f"  - {job['title']}")

            if relevant_count > 5:
                print(f"  ... and {relevant_count - 5} more")

            # Show sample filtered-out jobs (for false negative check)
            print(f"\n❌ Sample FILTERED OUT jobs (first 10):")
            for job in filtered_out[:10]:
                print(f"  - {job['title']}")

            if filtered_count > 10:
                print(f"  ... and {filtered_count - 10} more")

            # Store for analysis
            results.append({
                "company": company['name'],
                "url": company['url'],
                "total_jobs": total,
                "relevant_jobs": relevant_count,
                "filtered_out": filtered_count,
                "pct_relevant": round(pct_relevant, 1),
                "sample_relevant_titles": [j['title'] for j in relevant_jobs[:10]],
                "sample_filtered_titles": [j['title'] for j in filtered_out[:20]],
                "all_relevant_titles": [j['title'] for j in relevant_jobs],
                "all_filtered_titles": [j['title'] for j in filtered_out],
            })

        except Exception as e:
            print(f"❌ Error scraping {company['name']}: {str(e)}")
            results.append({
                "company": company['name'],
                "url": company['url'],
                "error": str(e),
            })

    # Overall summary
    print(f"\n{'='*70}")
    print("EXPERIMENT SUMMARY")
    print(f"{'='*70}")
    print(f"\n{'Company':<15} | {'Total':>5} | {'Relevant':>8} | {'Filtered':>8} | {'% Relevant':>11}")
    print(f"{'-'*70}")

    for r in results:
        if 'error' not in r:
            print(f"{r['company']:<15} | {r['total_jobs']:>5} | {r['relevant_jobs']:>8} | {r['filtered_out']:>8} | {r['pct_relevant']:>10.1f}%")

    # Calculate aggregate stats
    if total_across_all > 0:
        pct_overall = (relevant_across_all / total_across_all * 100)
        cost_savings_pct = 100 - pct_overall

        print(f"{'-'*70}")
        print(f"{'TOTAL':<15} | {total_across_all:>5} | {relevant_across_all:>8} | {total_across_all - relevant_across_all:>8} | {pct_overall:>10.1f}%")

        print(f"\n📊 COST IMPACT ANALYSIS:")
        print(f"  - Jobs we'd classify: {relevant_across_all} ({pct_overall:.1f}%)")
        print(f"  - Jobs we'd skip: {total_across_all - relevant_across_all} ({cost_savings_pct:.1f}%)")
        print(f"  - Estimated cost savings: {cost_savings_pct:.1f}% reduction in classification costs")
        print(f"  - Cost per filtered batch: {relevant_across_all} × $0.00388 = ${relevant_across_all * 0.00388:.2f}")
        print(f"  - Cost if unfiltered: {total_across_all} × $0.00388 = ${total_across_all * 0.00388:.2f}")
        print(f"  - Savings per batch: ${(total_across_all - relevant_across_all) * 0.00388:.2f}")

    # Save detailed results
    output_data = {
        "experiment_date": datetime.now().isoformat(),
        "title_patterns_tested": RELEVANT_TITLE_PATTERNS,
        "companies_tested": len(test_companies),
        "total_jobs_scraped": total_across_all,
        "relevant_jobs_found": relevant_across_all,
        "pct_relevant_overall": round(pct_overall, 1) if total_across_all > 0 else 0,
        "results_by_company": results,
    }

    output_file = 'output/title_filter_experiment.json'
    with open(output_file, 'w') as f:
        json.dump(output_data, indent=2, fp=f)

    print(f"\n📁 Detailed results saved to: {output_file}")
    print(f"\n🔍 NEXT STEPS:")
    print("1. Review 'sample_filtered_titles' in JSON - are we missing relevant jobs?")
    print("2. Check for edge cases in filtered data (e.g., 'Staff Data PM', 'Applied ML Scientist')")
    print("3. If false negatives found, refine RELEVANT_TITLE_PATTERNS")
    print("4. If patterns look good, proceed with integration into greenhouse_scraper.py")
    print("\nSee docs/testing/greenhouse_title_filter_experiment.md for interpretation guide.")


if __name__ == "__main__":
    asyncio.run(test_title_filtering())
