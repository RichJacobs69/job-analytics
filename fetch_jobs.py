"""
Unified Job Fetcher: Adzuna + Greenhouse Dual Pipeline Orchestrator

Purpose:
--------
Main entry point for fetching jobs from multiple sources (Adzuna API + Greenhouse scraper).
Orchestrates the full pipeline: fetch -> merge -> classify -> store.

Supports:
- Single or dual source fetching (--sources adzuna,greenhouse)
- Multiple cities (lon, nyc, den)
- Agency filtering (hard + soft detection)
- Classification via Claude 3.5 Haiku
- Storage in Supabase PostgreSQL

Usage:
------
# Dual pipeline (default):
python fetch_jobs.py lon 100 --sources adzuna,greenhouse

# Adzuna only:
python fetch_jobs.py lon 100 --sources adzuna

# Greenhouse only (premium companies):
python fetch_jobs.py --sources greenhouse

# NYC with more jobs:
python fetch_jobs.py nyc 200 --sources adzuna,greenhouse

# With filtering:
python fetch_jobs.py lon 100 --sources adzuna,greenhouse --min-description-length 500

Author: Claude Code
"""

import asyncio
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def fetch_from_adzuna(city: str, max_jobs_per_query: int) -> List:
    """Fetch jobs from Adzuna API for ALL role types and convert to UnifiedJob objects"""
    try:
        from scrapers.adzuna.fetch_adzuna_jobs import fetch_adzuna_jobs, DEFAULT_SEARCH_QUERIES
        from unified_job_ingester import UnifiedJob, DataSource

        logger.info(f"Fetching jobs from Adzuna API for {city}")
        logger.info(f"Will search {len(DEFAULT_SEARCH_QUERIES)} role types with {max_jobs_per_query} jobs per query")

        all_unified_jobs = []

        # Loop through all role queries (Data Scientist, Data Engineer, ML Engineer, etc.)
        for query in DEFAULT_SEARCH_QUERIES:
            logger.info(f"  Searching: '{query}' in {city}")

            # Fetch raw dicts from Adzuna for this query
            raw_jobs = fetch_adzuna_jobs(
                city_code=city,
                search_query=query,
                results_per_page=max_jobs_per_query
            )

            logger.info(f"    Found {len(raw_jobs)} jobs for '{query}'")

            # Convert dicts to UnifiedJob objects
            for job_dict in raw_jobs:
                try:
                    unified_job = UnifiedJob(
                        company=job_dict.get("company", {}).get("display_name", "Unknown Company"),
                        title=job_dict.get("title", "Unknown Title"),
                        location=job_dict.get("location", {}).get("display_name", city),
                        description=job_dict.get("description", ""),
                        url=job_dict.get("redirect_url", f"adzuna-{job_dict.get('id')}"),
                        job_id=str(job_dict.get("id", "")),
                        job_type=job_dict.get("contract_type"),
                        source=DataSource.ADZUNA,
                        description_source=DataSource.ADZUNA,
                        adzuna_description=job_dict.get("description", "")
                    )
                    all_unified_jobs.append(unified_job)
                except Exception as e:
                    logger.warning(f"Failed to convert Adzuna job: {str(e)}")
                    continue

        logger.info(f"Successfully fetched {len(all_unified_jobs)} total jobs from Adzuna across all role types")
        return all_unified_jobs

    except Exception as e:
        logger.error(f"Failed to fetch from Adzuna: {str(e)}")
        return []


async def fetch_from_greenhouse(companies: Optional[List[str]] = None) -> List:
    """Fetch jobs from Greenhouse-hosted career pages"""
    try:
        from scrapers.greenhouse.greenhouse_scraper import GreenhouseScraper

        scraper = GreenhouseScraper(headless=True, max_concurrent_pages=2)
        await scraper.init()

        try:
            if companies:
                logger.info(f"Scraping {len(companies)} Greenhouse companies")
                jobs_dict = await scraper.scrape_all(companies)
            else:
                # Load default companies from mapping
                import json
                mapping_file = Path(__file__).parent / 'config' / 'company_ats_mapping.json'

                if mapping_file.exists():
                    with open(mapping_file) as f:
                        mapping = json.load(f)
                    # Extract slug field from each company dict
                    companies = [company_data['slug'] for company_data in mapping.get('greenhouse', {}).values()]
                    logger.info(f"Scraping all {len(companies)} Greenhouse companies from mapping")
                    jobs_dict = await scraper.scrape_all(companies)
                else:
                    logger.warning("No companies specified and mapping file not found")
                    return []

            # Flatten dict result into a single list of jobs
            # scrape_all returns Dict[str, Dict] with 'jobs' and 'stats' - we need to flatten it
            all_jobs = []
            total_scraped = 0
            total_filtered = 0
            for company_slug, result in jobs_dict.items():
                all_jobs.extend(result['jobs'])
                total_scraped += result['stats']['jobs_scraped']
                total_filtered += result['stats']['jobs_filtered']

            logger.info(f"Successfully scraped {len(all_jobs)} jobs from {len(jobs_dict)} Greenhouse companies")
            if total_scraped > 0:
                filter_rate = (total_filtered / total_scraped * 100)
                logger.info(f"Greenhouse filtering: {total_scraped} total, {len(all_jobs)} kept, {total_filtered} filtered ({filter_rate:.1f}%)")
                logger.info(f"Cost savings from filtering: ${total_filtered * 0.00388:.2f}")
            return all_jobs

        finally:
            await scraper.close()

    except Exception as e:
        logger.error(f"Failed to fetch from Greenhouse: {str(e)}")
        return []


async def merge_jobs(
    adzuna_jobs: List,
    greenhouse_jobs: List,
    min_description_length: int = 0
) -> Dict:
    """Merge jobs from multiple sources with deduplication"""

    from unified_job_ingester import UnifiedJobIngester

    logger.info("Merging jobs from all sources")

    ingester = UnifiedJobIngester(verbose=True)
    merged_jobs, stats = await ingester.merge(
        adzuna_jobs=adzuna_jobs,
        greenhouse_jobs=greenhouse_jobs
    )

    # Filter by minimum description length if specified
    if min_description_length > 0:
        original_count = len(merged_jobs)
        merged_jobs = [j for j in merged_jobs if len(j.description) >= min_description_length]
        logger.info(f"Filtered to {len(merged_jobs)} jobs with >={min_description_length} chars (removed {original_count - len(merged_jobs)})")

    stats['filtered_count'] = len(merged_jobs)

    return {
        'jobs': merged_jobs,
        'stats': stats
    }


async def classify_jobs(jobs: List) -> List:
    """Classify jobs using Claude 3.5 Haiku"""

    try:
        from classifier import classify_job_with_claude
        from agency_detection import is_agency_job

        logger.info(f"Classifying {len(jobs)} jobs")

        classified = []
        for i, job in enumerate(jobs):
            if (i + 1) % 10 == 0:
                logger.info(f"  Progress: {i+1}/{len(jobs)}")

            # Hard filter: check if it's a known agency
            company_name = job.company
            if is_agency_job(company_name):
                logger.debug(f"Skipping agency: {company_name}")
                continue

            # Classify the job
            try:
                # Check for empty or insufficient descriptions
                description = job.description
                if not description or len(description.strip()) < 50:
                    logger.warning(f"Skipping job with insufficient description (<50 chars): {job.title}")
                    continue

                # classify_job_with_claude is synchronous, not async
                classification = classify_job_with_claude(description)

                # Add classification to job (now a proper dataclass field)
                job.classification = classification

                classified.append(job)
            except Exception as e:
                logger.warning(f"Failed to classify job {job.title}: {str(e)}")
                continue

        logger.info(f"Classified {len(classified)} jobs (filtered {len(jobs) - len(classified)} agencies)")

        return classified

    except Exception as e:
        logger.error(f"Classification failed: {str(e)}")
        return jobs  # Return original jobs if classification fails


async def store_jobs(jobs: List, table: str = "enriched_jobs") -> bool:
    """Store jobs in Supabase database
    
    Expects jobs to be UnifiedJob objects with classification data attached.
    """

    try:
        from db_connection import insert_raw_job, insert_enriched_job
        from datetime import date
        from unified_job_ingester import UnifiedJob, DataSource

        logger.info(f"Storing {len(jobs)} jobs to {table}")

        stored_count = 0
        for job in jobs:
            try:
                # Validate job type
                if not isinstance(job, UnifiedJob):
                    logger.error(f"Expected UnifiedJob, got {type(job).__name__}. Skipping.")
                    continue

                # Extract job data from UnifiedJob
                company = job.company
                title = job.title
                description = job.description
                url = job.url
                job_id = job.job_id
                source = job.source.value if isinstance(job.source, DataSource) else str(job.source)
                description_source = job.description_source.value if isinstance(job.description_source, DataSource) else str(job.description_source)
                deduplicated = job.deduplicated
                classification = job.classification

                # Skip jobs without classification
                if not classification:
                    logger.warning(f"Skipping job without classification: {title}")
                    continue

                # Step 1: Insert raw job
                raw_job_id = insert_raw_job(
                    source=source,
                    posting_url=url,
                    raw_text=description,
                    source_job_id=job_id
                )

                # Step 2: Extract classification data
                role = classification.get('role', {})
                location = classification.get('location', {})
                compensation = classification.get('compensation', {})
                employer = classification.get('employer', {})

                # Step 3: Insert enriched job
                enriched_job_id = insert_enriched_job(
                    raw_job_id=raw_job_id,
                    employer_name=company,
                    title_display=title,
                    job_family=role.get('job_family', 'out_of_scope'),
                    city_code=location.get('city_code') or 'lon',  # Default to London
                    working_arrangement=location.get('working_arrangement') or 'onsite',
                    position_type=role.get('position_type') or 'full_time',
                    posted_date=date.today(),
                    last_seen_date=date.today(),
                    # Optional fields
                    job_subfamily=role.get('job_subfamily'),
                    seniority=role.get('seniority'),
                    track=role.get('track'),
                    experience_range=role.get('experience_range'),
                    employer_department=employer.get('department'),
                    employer_size=employer.get('company_size_estimate'),
                    is_agency=employer.get('is_agency'),
                    agency_confidence=employer.get('agency_confidence'),
                    currency=compensation.get('currency'),
                    salary_min=compensation.get('base_salary_range', {}).get('min'),
                    salary_max=compensation.get('base_salary_range', {}).get('max'),
                    equity_eligible=compensation.get('equity_eligible'),
                    skills=classification.get('skills', []),
                    # Dual pipeline source tracking
                    data_source=source,
                    description_source=description_source,
                    deduplicated=deduplicated
                )

                stored_count += 1
                if stored_count % 10 == 0:
                    logger.info(f"  Progress: {stored_count}/{len(jobs)}")

            except Exception as e:
                job_title = title if 'title' in locals() else 'unknown'
                logger.warning(f"Failed to store job {job_title}: {str(e)}")
                import traceback
                logger.debug(traceback.format_exc())
                continue

        logger.info(f"Successfully stored {stored_count} jobs")
        return True

    except Exception as e:
        logger.error(f"Failed to store jobs: {str(e)}")
        import traceback
        logger.debug(traceback.format_exc())
        return False


async def main():
    """Main orchestration function"""

    parser = argparse.ArgumentParser(
        description='Unified job fetcher: Adzuna + Greenhouse dual pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dual pipeline (default)
  python fetch_jobs.py lon 100 --sources adzuna,greenhouse

  # Adzuna only
  python fetch_jobs.py lon 100 --sources adzuna

  # Greenhouse only
  python fetch_jobs.py --sources greenhouse

  # NYC with more jobs
  python fetch_jobs.py nyc 200 --sources adzuna,greenhouse
        """
    )

    parser.add_argument(
        'city',
        nargs='?',
        default='lon',
        help='City code: lon (London), nyc (New York), den (Denver). Default: lon'
    )

    parser.add_argument(
        'max_jobs',
        nargs='?',
        type=int,
        default=100,
        help='Max jobs to fetch per role query from Adzuna (11 role types total). Default: 100'
    )

    parser.add_argument(
        '--sources',
        default='adzuna,greenhouse',
        help='Comma-separated sources: adzuna, greenhouse. Default: adzuna,greenhouse'
    )

    parser.add_argument(
        '--companies',
        help='Comma-separated list of Greenhouse companies (if --sources includes greenhouse)'
    )

    parser.add_argument(
        '--min-description-length',
        type=int,
        default=0,
        help='Minimum description length in characters. Default: 0'
    )

    parser.add_argument(
        '--skip-classification',
        action='store_true',
        help='Skip classification step (just fetch and merge)'
    )

    parser.add_argument(
        '--skip-storage',
        action='store_true',
        help='Skip storage step (just fetch and classify)'
    )

    args = parser.parse_args()

    logger.info("="*80)
    logger.info("DUAL PIPELINE JOB FETCHER")
    logger.info("="*80)
    logger.info(f"City: {args.city}")
    logger.info(f"Max jobs per role query (Adzuna): {args.max_jobs}")
    logger.info(f"Sources: {args.sources}")
    logger.info(f"Min description length: {args.min_description_length}")
    if 'adzuna' in [s.strip().lower() for s in args.sources.split(',')]:
        from scrapers.adzuna.fetch_adzuna_jobs import DEFAULT_SEARCH_QUERIES
        logger.info(f"Adzuna will search {len(DEFAULT_SEARCH_QUERIES)} role types: {', '.join(DEFAULT_SEARCH_QUERIES[:3])}...")
    logger.info("="*80 + "\n")

    # Parse sources
    sources = [s.strip().lower() for s in args.sources.split(',')]

    # Fetch from sources
    adzuna_jobs = []
    greenhouse_jobs = []

    if 'adzuna' in sources:
        adzuna_jobs = await fetch_from_adzuna(args.city, args.max_jobs)

    if 'greenhouse' in sources:
        companies = None
        if args.companies:
            companies = [c.strip() for c in args.companies.split(',')]

        greenhouse_jobs = await fetch_from_greenhouse(companies)

    # Merge
    merged_result = await merge_jobs(
        adzuna_jobs,
        greenhouse_jobs,
        min_description_length=args.min_description_length
    )

    merged_jobs = merged_result['jobs']
    stats = merged_result['stats']

    logger.info("\n" + "="*80)
    logger.info("MERGE STATISTICS")
    logger.info("="*80)
    for key, value in stats.items():
        logger.info(f"{key}: {value}")
    logger.info("="*80 + "\n")

    if not merged_jobs:
        logger.error("No jobs to process after merging")
        return

    # Classification (optional)
    if not args.skip_classification:
        merged_jobs = await classify_jobs(merged_jobs)

    # Storage (optional)
    if not args.skip_storage:
        await store_jobs(merged_jobs)

    logger.info("\nPipeline complete!")
    logger.info(f"Final result: {len(merged_jobs)} jobs ready for analysis")


if __name__ == "__main__":
    asyncio.run(main())
