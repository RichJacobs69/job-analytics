"""
Unified Job Fetcher: Adzuna + Greenhouse + Lever Triple Pipeline Orchestrator

Purpose:
--------
Main entry point for fetching jobs from multiple sources (Adzuna API, Greenhouse scraper, Lever API).
Orchestrates the full pipeline: fetch -> merge -> classify -> store.

Supports:
- Single, dual, or triple source fetching (--sources adzuna,greenhouse,lever)
- Multiple cities (lon, nyc, den)
- Agency filtering (hard + soft detection)
- Classification via Claude 3.5 Haiku
- Storage in Supabase PostgreSQL

Data Sources:
- Adzuna: REST API, mass market jobs, 100-200 char descriptions
- Greenhouse: Browser scraping, premium companies, 9,000-15,000+ char descriptions
- Lever: REST API (no auth), full descriptions like Greenhouse

Usage:
------
# Triple pipeline (all sources):
python fetch_jobs.py lon 100 --sources adzuna,greenhouse,lever

# Adzuna only:
python fetch_jobs.py lon 100 --sources adzuna

# Greenhouse only (browser scraping):
python fetch_jobs.py --sources greenhouse

# Lever only (simple HTTP API):
python fetch_jobs.py --sources lever

# NYC with more jobs:
python fetch_jobs.py nyc 200 --sources adzuna,greenhouse,lever

# With filtering:
python fetch_jobs.py lon 100 --sources adzuna,greenhouse,lever --min-description-length 500

# With companies filter (applies to Greenhouse and Lever):
python fetch_jobs.py lon 100 --sources greenhouse,lever --companies "spotify,plaid,figma"

# With resume hours (Greenhouse only):
python fetch_jobs.py lon 100 --sources adzuna,greenhouse --resume-hours 24

# With adzuna max days old:
python fetch_jobs.py lon 100 --sources adzuna --adzuna-max-days-old 30

Author: Claude Code
"""

import asyncio
import argparse
import logging
import sys
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

# Add project root to path so we can import scrapers module
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import location extraction for the new locations JSONB column
from pipeline.location_extractor import extract_locations

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def fetch_from_adzuna(city: str, max_jobs_per_query: int, max_days_old: int = 30) -> List:
    """Fetch jobs from Adzuna API for ALL role types and convert to UnifiedJob objects
    
    Now supports pagination with rate limiting to fetch more than 50 jobs per query.
    Rate limited to ~24 calls/minute to stay within Adzuna's 25 calls/minute limit.
    """
    try:
        from scrapers.adzuna.fetch_adzuna_jobs import (
            fetch_adzuna_jobs_paginated, 
            DEFAULT_SEARCH_QUERIES,
            calculate_api_calls
        )
        from pipeline.unified_job_ingester import UnifiedJob, DataSource

        logger.info(f"Fetching jobs from Adzuna API for {city}")
        logger.info(f"Will search {len(DEFAULT_SEARCH_QUERIES)} role types with up to {max_jobs_per_query} jobs per query")
        logger.info(f"Filtering Adzuna results to jobs posted in last {max_days_old} days")
        
        # Show API call estimate
        estimate = calculate_api_calls(
            num_queries=len(DEFAULT_SEARCH_QUERIES),
            num_cities=1,  # This function handles one city at a time
            results_per_query=max_jobs_per_query
        )
        logger.info(f"  API calls needed: {estimate['total_api_calls']} (ETA: ~{estimate['estimated_time_minutes']} min)")

        all_unified_jobs = []

        # Loop through all role queries (Data Scientist, Data Engineer, ML Engineer, etc.)
        for query in DEFAULT_SEARCH_QUERIES:
            logger.info(f"  Searching: '{query}' in {city}")

            # Fetch raw dicts from Adzuna with pagination and rate limiting
            raw_jobs = fetch_adzuna_jobs_paginated(
                city_code=city,
                search_query=query,
                max_results=max_jobs_per_query,
                max_days_old=max_days_old,
                verbose=True
            )

            logger.info(f"    Found {len(raw_jobs)} jobs for '{query}'")

            # Convert dicts to UnifiedJob objects
            for job_dict in raw_jobs:
                try:
                    # Extract Adzuna-specific metadata for classifier context
                    category_info = job_dict.get("category", {})
                    category_label = category_info.get("label") if isinstance(category_info, dict) else None
                    
                    salary_min = job_dict.get("salary_min")
                    salary_max = job_dict.get("salary_max")
                    salary_predicted = job_dict.get("salary_is_predicted") == "1"
                    
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
                        adzuna_description=job_dict.get("description", ""),
                        # New: Adzuna metadata for classifier
                        adzuna_category=category_label,
                        adzuna_salary_min=salary_min,
                        adzuna_salary_max=salary_max,
                        adzuna_salary_predicted=salary_predicted
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
    """Fetch jobs from Greenhouse-hosted career pages (LEGACY BATCH MODE)

    NOTE: This function is kept for backwards compatibility.
    For incremental processing, use process_greenhouse_incremental() instead.
    """
    try:
        from scrapers.greenhouse.greenhouse_scraper import GreenhouseScraper

        scraper = GreenhouseScraper(headless=True, max_concurrent_pages=2, company_timeout_seconds=600)
        await scraper.init()

        try:
            if companies:
                logger.info(f"Scraping {len(companies)} Greenhouse companies")
                jobs_dict = await scraper.scrape_all(companies)
            else:
                # Load default companies from mapping
                import json
                # Look for mapping file at project root config directory
                mapping_file = Path(__file__).parent.parent / 'config' / 'greenhouse' / 'company_ats_mapping.json'

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


async def fetch_from_lever(companies: Optional[List[str]] = None) -> List:
    """Fetch jobs from Lever API and convert to UnifiedJob objects

    Args:
        companies: Optional list of company slugs to fetch. If None, uses mapping.

    Returns:
        List of UnifiedJob objects from Lever
    """
    try:
        from scrapers.lever.lever_fetcher import fetch_all_lever_companies, LeverJob
        from pipeline.unified_job_ingester import UnifiedJob, DataSource

        logger.info("Fetching jobs from Lever API...")

        # Fetch jobs from Lever (filtering enabled by default)
        lever_jobs, stats = fetch_all_lever_companies(
            companies=companies,
            filter_titles=True,
            filter_locations=True
        )

        logger.info(f"Lever API Stats:")
        logger.info(f"  - Companies processed: {stats['companies_processed']}")
        logger.info(f"  - Total jobs fetched: {stats['total_jobs_fetched']}")
        logger.info(f"  - Filtered by title: {stats['total_filtered_by_title']}")
        logger.info(f"  - Filtered by location: {stats['total_filtered_by_location']}")
        logger.info(f"  - Jobs kept: {stats['total_jobs_kept']}")

        # Convert LeverJob objects to UnifiedJob objects
        unified_jobs = []
        for job in lever_jobs:
            try:
                unified_job = UnifiedJob(
                    company=job.company_slug.replace('-', ' ').title(),
                    title=job.title,
                    location=job.location,
                    description=job.description,
                    url=job.url,
                    job_id=job.id,
                    department=job.department,
                    source=DataSource.LEVER,
                    description_source=DataSource.LEVER,
                    lever_id=job.id,
                    lever_team=job.team,
                    lever_department=job.department,
                    lever_commitment=job.commitment,
                    lever_description=job.description
                )
                unified_jobs.append(unified_job)
            except Exception as e:
                logger.warning(f"Failed to convert Lever job: {str(e)}")
                continue

        logger.info(f"Successfully converted {len(unified_jobs)} Lever jobs to UnifiedJob format")
        return unified_jobs

    except Exception as e:
        logger.error(f"Failed to fetch from Lever: {str(e)}")
        return []


async def get_recently_processed_companies(hours: int = 24) -> List[str]:
    """Get list of companies processed in the last N hours

    Args:
        hours: Look back window in hours (default: 24)

    Returns:
        List of company slugs that have been processed recently
    """
    from pipeline.db_connection import supabase
    from datetime import datetime, timedelta

    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    cutoff_str = cutoff_time.isoformat()

    try:
        # Query raw_jobs for Greenhouse jobs last seen after cutoff
        # Uses 'last_seen' (updated on every scrape) instead of 'scraped_at' (first discovery)
        result = supabase.table('raw_jobs') \
            .select('metadata') \
            .eq('source', 'greenhouse') \
            .gte('last_seen', cutoff_str) \
            .execute()

        # Extract company slugs from metadata
        company_slugs = set()
        for row in result.data:
            metadata = row.get('metadata', {})
            if isinstance(metadata, dict):
                company_slug = metadata.get('company_slug')
                if company_slug:
                    company_slugs.add(company_slug)

        return list(company_slugs)

    except Exception as e:
        logger.warning(f"Failed to query recently processed companies: {str(e)}")
        return []


async def process_greenhouse_incremental(companies: Optional[List[str]] = None, resume_hours: int = 0) -> Dict:
    """Process Greenhouse jobs incrementally with per-company database writes

    This function implements the incremental architecture:
    1. Scrape company jobs
    2. Write to raw_jobs using insert_raw_job_upsert()
    3. Classify jobs immediately
    4. Write to enriched_jobs
    5. Log progress clearly per company

    Args:
        companies: Optional list of company slugs to process. If None, processes all from mapping.
        resume_hours: If > 0, skip companies processed within last N hours (resume capability)

    Returns:
        Dict with processing statistics:
            - companies_processed: int
            - companies_skipped: int
            - jobs_scraped: int
            - jobs_kept: int (after filtering)
            - jobs_written_raw: int
            - jobs_classified: int
            - jobs_written_enriched: int
    """
    from scrapers.greenhouse.greenhouse_scraper import GreenhouseScraper
    from pipeline.db_connection import (
        insert_raw_job_upsert, insert_enriched_job, get_working_arrangement_fallback,
        ensure_employer_metadata
    )
    from pipeline.classifier import classify_job
    from pipeline.agency_detection import is_agency_job, validate_agency_classification
    from pipeline.unified_job_ingester import UnifiedJob, DataSource
    from datetime import date
    import json
    from pathlib import Path

    # Load greenhouse config to create slug -> display_name mapping
    project_root = Path(__file__).parent.parent
    config_path = project_root / 'config' / 'greenhouse' / 'company_ats_mapping.json'
    slug_to_display_name = {}
    if config_path.exists():
        with open(config_path) as f:
            gh_config = json.load(f)
            # Config structure: {"DisplayName": {"slug": "company-slug"}, ...}
            for display_name, info in gh_config.items():
                if isinstance(info, dict) and 'slug' in info:
                    slug_to_display_name[info['slug']] = display_name

    from datetime import datetime
    import time

    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    logger.info("="*80)
    logger.info("GREENHOUSE INCREMENTAL PROCESSING")
    logger.info(f"Started: {start_timestamp}")
    logger.info("="*80)

    # Time tracking
    pipeline_start_time = time.time()
    company_start_times = {}

    # Statistics tracking
    stats = {
        'companies_processed': 0,
        'companies_skipped': 0,
        'companies_total': 0,
        'companies_total_effective': 0,
        'jobs_scraped': 0,
        'jobs_kept': 0,
        'jobs_filtered': 0,
        'jobs_written_raw': 0,
        'jobs_duplicate': 0,
        'jobs_classified': 0,
        'jobs_agency_filtered': 0,
        'jobs_written_enriched': 0,
        'cost_saved_filtering': 0.0,
        'cost_classification': 0.0,
        'start_time': pipeline_start_time,
        'resume_hours': resume_hours,
        'zero_job_companies': []
    }

    # Callback function to process each company's jobs incrementally
    def process_company_jobs(company_slug: str, result: Dict):
        """Process jobs from one company: write raw, classify, write enriched"""

        company_start = time.time()
        company_stats = result['stats']
        jobs = result['jobs']

        # Header with company info
        logger.info(f"\n{'='*80}")
        logger.info(f"COMPANY: {company_slug.upper()}")
        logger.info(f"{'='*80}")
        logger.info(f"Scraping Summary:")
        logger.info(f"  - Total jobs scraped: {company_stats['jobs_scraped']}")
        logger.info(f"  - Filtered (title): {company_stats.get('jobs_filtered_title', 0)}")
        logger.info(f"  - Filtered (location): {company_stats.get('jobs_filtered_location', 0)}")
        logger.info(f"  - Jobs to process: {len(jobs)}")
        logger.info(f"  - Filter rate: {company_stats.get('filter_rate', 0):.1f}%")
        logger.info(f"  - Cost saved: ${company_stats['jobs_filtered'] * 0.00388:.2f}")
        logger.info(f"{'-'*80}")

        # Track companies where nothing was kept to process
        if len(jobs) == 0:
            stats['zero_job_companies'].append(company_slug)

        # Update global stats
        stats['companies_processed'] += 1
        stats['jobs_scraped'] += company_stats['jobs_scraped']
        stats['jobs_filtered'] += company_stats['jobs_filtered']
        stats['jobs_kept'] += len(jobs)
        stats['cost_saved_filtering'] += company_stats['jobs_filtered'] * 0.00388

        # Track company-specific metrics
        company_jobs_written = 0
        company_jobs_duplicate = 0
        agencies_blocked = 0
        company_jobs_classified = 0
        company_jobs_enriched = 0

        # Process each job
        for i, job in enumerate(jobs, 1):
            try:
                # Step 1: Write to raw_jobs using UPSERT
                upsert_result = insert_raw_job_upsert(
                    source='greenhouse',
                    posting_url=job.url,
                    title=job.title,
                    company=job.company,
                    raw_text=job.description,
                    city_code='unk',  # Greenhouse doesn't specify city in listings
                    source_job_id=job.job_id,
                    metadata={
                        'company_slug': company_slug,
                        'greenhouse_location': job.location if job.location and job.location != 'Unspecified' else None
                    }
                )

                raw_job_id = upsert_result['id']
                action = upsert_result['action']
                was_duplicate = upsert_result['was_duplicate']

                if was_duplicate:
                    stats['jobs_duplicate'] += 1
                    company_jobs_duplicate += 1
                    logger.info(f"  [{i}/{len(jobs)}] DUPLICATE: {job.title[:60]}... (skipped)")
                    # Skip classification for duplicates (already done previously)
                    continue

                stats['jobs_written_raw'] += 1
                company_jobs_written += 1
                logger.info(f"  [{i}/{len(jobs)}] NEW JOB: {job.title[:60]}... (classifying...)")

                # Step 2: Hard filter - check if agency before classification
                if is_agency_job(job.company):
                    stats['jobs_agency_filtered'] += 1
                    logger.info(f"  [{i}/{len(jobs)}] AGENCY (hard filter): Skipped")
                    continue

                # Step 3: Classify the job with structured input (including title)
                try:
                    structured_input = {
                        'title': job.title,
                        'company': job.company,
                        'description': job.description,
                        'location': None,
                        'category': None,
                        'salary_min': None,
                        'salary_max': None,
                    }
                    classification = classify_job(
                        job_text=job.description,
                        structured_input=structured_input
                    )
                    stats['jobs_classified'] += 1
                    company_jobs_classified += 1

                    # Track classification cost (if available)
                    if '_cost_data' in classification and 'total_cost' in classification['_cost_data']:
                        cost = classification['_cost_data']['total_cost']
                        stats['cost_classification'] += cost
                        logger.info(f"  [{i}/{len(jobs)}] Classified (${cost:.4f})")
                    else:
                        logger.info(f"  [{i}/{len(jobs)}] Classified")

                except Exception as e:
                    logger.warning(f"  [{i}/{len(jobs)}] Classification FAILED: {str(e)[:100]}")
                    continue

                # Step 4: Soft agency detection
                is_agency, agency_conf = validate_agency_classification(
                    employer_name=job.company,
                    claude_is_agency=None,
                    claude_confidence=None,
                    job_description=job.description
                )

                if is_agency:
                    stats['jobs_agency_filtered'] += 1
                    logger.info(f"  [{i}/{len(jobs)}] AGENCY (soft detection): Flagged")
                    # Continue anyway to store the job, but flag it as agency

                # Inject agency flags
                if 'employer' not in classification:
                    classification['employer'] = {}
                classification['employer']['is_agency'] = is_agency
                classification['employer']['agency_confidence'] = agency_conf

                # Step 5: Write to enriched_jobs
                logger.info(f"  [{i}/{len(jobs)}] Writing to enriched_jobs...")
                role = classification.get('role', {})
                location = classification.get('location', {})
                compensation = classification.get('compensation', {})
                employer = classification.get('employer', {})

                # Extract locations from Greenhouse job.location field (Global Location Expansion Epic)
                greenhouse_location = job.location if job.location and job.location != 'Unspecified' else None
                extracted_locations = extract_locations(greenhouse_location) if greenhouse_location else [{"type": "unknown"}]

                # Derive legacy city_code from locations for backward compatibility (DEPRECATED)
                legacy_city_code = 'unk'
                if extracted_locations and extracted_locations[0].get('type') == 'city':
                    city_name = extracted_locations[0].get('city', '')
                    city_to_code = {'london': 'lon', 'new_york': 'nyc', 'denver': 'den', 'san_francisco': 'sfo', 'singapore': 'sgp'}
                    legacy_city_code = city_to_code.get(city_name, 'unk')
                elif extracted_locations and extracted_locations[0].get('type') == 'remote':
                    legacy_city_code = 'remote'

                # Determine working arrangement with employer metadata fallback
                wa_from_classifier = location.get('working_arrangement') or 'unknown'
                if wa_from_classifier == 'unknown':
                    wa_fallback = get_working_arrangement_fallback(job.company)
                    working_arrangement = wa_fallback if wa_fallback else 'unknown'
                else:
                    working_arrangement = wa_from_classifier

                # Get display name from config (e.g., "Rightmove" instead of "rightmovecareers")
                employer_display_name = slug_to_display_name.get(company_slug, job.company)

                enriched_job_id = insert_enriched_job(
                    raw_job_id=raw_job_id,
                    employer_name=job.company,
                    title_display=job.title,
                    job_family=role.get('job_family') or 'out_of_scope',
                    city_code=legacy_city_code,  # DEPRECATED - use locations instead
                    working_arrangement=working_arrangement,
                    position_type=role.get('position_type') or 'full_time',
                    posted_date=date.today(),
                    last_seen_date=date.today(),
                    job_subfamily=role.get('job_subfamily'),
                    seniority=role.get('seniority'),
                    track=role.get('track'),
                    experience_range=role.get('experience_range'),
                    employer_department=employer.get('department'),
                    is_agency=employer.get('is_agency'),
                    agency_confidence=employer.get('agency_confidence'),
                    currency=compensation.get('currency'),
                    salary_min=compensation.get('base_salary_range', {}).get('min'),
                    salary_max=compensation.get('base_salary_range', {}).get('max'),
                    equity_eligible=compensation.get('equity_eligible'),
                    skills=classification.get('skills', []),
                    summary=classification.get('summary'),
                    data_source='greenhouse',
                    description_source='greenhouse',
                    deduplicated=False,
                    locations=extracted_locations,  # Structured location data
                    display_name_hint=employer_display_name  # From config key
                )

                stats['jobs_written_enriched'] += 1
                company_jobs_enriched += 1

                logger.info(f"  [{i}/{len(jobs)}] SUCCESS: Stored (raw_id={raw_job_id}, enriched_id={enriched_job_id})")

            except Exception as e:
                logger.error(f"  [{i}/{len(jobs)}] ERROR: {str(e)[:100]}")
                continue

        # Company completion time
        company_elapsed = time.time() - company_start

        # Company summary
        logger.info(f"{'-'*80}")
        logger.info(f"Company Summary:")
        logger.info(f"  - New jobs written: {company_jobs_written}")
        logger.info(f"  - Duplicates skipped: {company_jobs_duplicate}")
        logger.info(f"  - Agencies blocked: {agencies_blocked}")
        logger.info(f"  - Jobs classified: {company_jobs_classified}")
        logger.info(f"  - Jobs enriched: {company_jobs_enriched}")
        logger.info(f"  - Processing time: {company_elapsed:.1f}s")
        logger.info(f"{'='*80}")

        # Pipeline progress
        elapsed = time.time() - stats['start_time']
        avg_time_per_company = elapsed / stats['companies_processed'] if stats['companies_processed'] > 0 else 0
        effective_total_companies = (
            stats.get('companies_total_effective')
            or max(stats['companies_total'] - stats.get('companies_skipped', 0), 0)
        )
        remaining_companies = max(effective_total_companies - stats['companies_processed'], 0)
        eta_seconds = avg_time_per_company * remaining_companies

        logger.info(f"Pipeline Progress: {stats['companies_processed']}/{effective_total_companies} companies")
        logger.info(f"  - Elapsed: {elapsed/60:.1f} min")
        logger.info(f"  - Avg per company: {avg_time_per_company:.1f}s")
        logger.info(f"  - ETA: {eta_seconds/60:.1f} min")
        logger.info(f"  - Total jobs: {stats['jobs_written_enriched']} enriched, {stats['jobs_duplicate']} duplicates")
        logger.info(f"{'='*80}")

    # Initialize scraper
    try:
        scraper = GreenhouseScraper(headless=True, max_concurrent_pages=2, company_timeout_seconds=600)
        await scraper.init()

        try:
            # Determine companies to process
            if companies:
                logger.info(f"Processing {len(companies)} specified Greenhouse companies")
                original_count = len(companies)
            else:
                # Load default companies from mapping
                mapping_file = Path(__file__).parent.parent / 'config' / 'greenhouse' / 'company_ats_mapping.json'

                if mapping_file.exists():
                    with open(mapping_file) as f:
                        mapping = json.load(f)
                    companies = [company_data['slug'] for company_data in mapping.get('greenhouse', {}).values()]
                    logger.info(f"Loaded {len(companies)} Greenhouse companies from mapping")
                    original_count = len(companies)
                else:
                    logger.warning("No companies specified and mapping file not found")
                    return stats

            # Resume capability: Skip recently processed companies
            if resume_hours > 0:
                logger.info(f"\n{'='*80}")
                logger.info(f"RESUME MODE: Checking for companies processed in last {resume_hours} hours")
                logger.info(f"{'='*80}")

                recently_processed = await get_recently_processed_companies(resume_hours)

                if recently_processed:
                    logger.info(f"Found {len(recently_processed)} recently processed companies:")
                    for company_slug in sorted(recently_processed):
                        logger.info(f"  - {company_slug}")

                    # Filter out recently processed companies
                    companies_to_skip = [c for c in companies if c in recently_processed]
                    companies = [c for c in companies if c not in recently_processed]

                    stats['companies_skipped'] = len(companies_to_skip)

                    logger.info(f"\nResume Summary:")
                    logger.info(f"  - Total companies: {original_count}")
                    logger.info(f"  - Already processed: {len(companies_to_skip)}")
                    logger.info(f"  - Remaining to process: {len(companies)}")
                    logger.info(f"{'='*80}\n")

                    if not companies:
                        logger.info("All companies already processed - nothing to do!")
                        stats['companies_total'] = original_count
                        stats['companies_total_effective'] = len(companies)
                        return stats
                else:
                    logger.info(f"No companies found processed in last {resume_hours} hours")
                    logger.info(f"Will process all {len(companies)} companies")
                    logger.info(f"{'='*80}\n")

            stats['companies_total'] = original_count
            stats['companies_total_effective'] = len(companies)

            # Scrape with incremental callback
            logger.info(f"Starting incremental scrape of {len(companies)} companies...")
            logger.info("Jobs will be written to database after each company completes\n")

            await scraper.scrape_all(companies, on_company_complete=process_company_jobs)

        finally:
            await scraper.close()

    except Exception as e:
        logger.error(f"Greenhouse incremental processing failed: {str(e)}")
        import traceback
        logger.debug(traceback.format_exc())

    # Final summary
    total_elapsed = time.time() - stats['start_time']
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    logger.info("\n" + "="*80)
    logger.info("GREENHOUSE INCREMENTAL PROCESSING COMPLETE")
    logger.info(f"Started: {start_timestamp}")
    logger.info(f"Ended: {end_timestamp}")
    logger.info(f"Total time: {total_elapsed/60:.1f} min ({total_elapsed:.1f}s)")
    logger.info("="*80)

    logger.info(f"\nCompany Processing:")
    logger.info(f"  - Companies total (after resume filter): {stats.get('companies_total_effective', stats['companies_total'])}")
    logger.info(f"  - Companies processed: {stats['companies_processed']}")
    logger.info(f"  - Companies skipped (resume): {stats['companies_skipped']}")
    logger.info(f"  - Companies in original list: {stats['companies_total']}")
    logger.info(f"  - Avg time per company: {total_elapsed/stats['companies_processed'] if stats['companies_processed'] > 0 else 0:.1f}s")

    logger.info(f"\nJob Scraping & Filtering:")
    logger.info(f"  - Jobs scraped: {stats['jobs_scraped']}")
    logger.info(f"  - Jobs filtered: {stats['jobs_filtered']} ({stats['jobs_filtered']/stats['jobs_scraped']*100 if stats['jobs_scraped'] > 0 else 0:.1f}%)")
    logger.info(f"  - Jobs kept: {stats['jobs_kept']}")

    logger.info(f"\nDatabase Writes:")
    logger.info(f"  - New raw jobs: {stats['jobs_written_raw']}")
    logger.info(f"  - Duplicates skipped: {stats['jobs_duplicate']}")
    logger.info(f"  - Jobs classified: {stats['jobs_classified']}")
    logger.info(f"  - Enriched jobs: {stats['jobs_written_enriched']}")
    logger.info(f"  - Agency flags: {stats['jobs_agency_filtered']}")

    logger.info(f"\nCost Analysis:")
    logger.info(f"  - Saved from filtering: ${stats['cost_saved_filtering']:.2f}")
    logger.info(f"  - Classification cost: ${stats['cost_classification']:.2f}")
    logger.info(f"  - Net cost: ${stats['cost_classification']:.2f}")
    logger.info(f"  - Cost per job enriched: ${stats['cost_classification']/stats['jobs_written_enriched'] if stats['jobs_written_enriched'] > 0 else 0:.4f}")

    logger.info(f"\nCompanies with 0 jobs kept:")
    if stats['zero_job_companies']:
        for slug in stats['zero_job_companies']:
            logger.info(f"  - {slug}")
    else:
        logger.info("  - none")

    logger.info("="*80)

    return stats


async def process_adzuna_incremental(city_code: str, max_jobs: int = 100, max_days_old: int = 30) -> Dict:
    """
    Process Adzuna jobs incrementally with upsert pattern.
    
    Follows the same pattern as process_greenhouse_incremental():
    1. Fetch jobs from Adzuna API
    2. For each job: upsert to raw_jobs (updates last_seen for existing)
    3. If new job: classify with Claude
    4. Write to enriched_jobs
    
    This avoids paying for classification of jobs that already exist in the database.
    
    Args:
        city_code: City to fetch jobs for (lon, nyc, den)
        max_jobs: Maximum jobs to fetch
        
    Returns:
        Stats dictionary with processing metrics
    """
    from pipeline.db_connection import (
        insert_raw_job_upsert, insert_enriched_job, get_working_arrangement_fallback,
        ensure_employer_metadata
    )
    from pipeline.classifier import classify_job
    from pipeline.agency_detection import is_agency_job, validate_agency_classification
    from pipeline.unified_job_ingester import UnifiedJob, DataSource
    from datetime import date
    import time

    logger.info(f"\n{'='*80}")
    logger.info(f"ADZUNA INCREMENTAL PIPELINE - {city_code.upper()}")
    logger.info(f"{'='*80}\n")
    
    # Initialize stats
    stats = {
        'start_time': time.time(),
        'jobs_fetched': 0,
        'jobs_written_raw': 0,
        'jobs_duplicate': 0,
        'jobs_classified': 0,
        'jobs_written_enriched': 0,
        'jobs_agency_filtered': 0,
        'cost_classification': 0.0,
        'cost_saved_duplicates': 0.0,
    }
    
    # Fetch jobs from Adzuna
    jobs = await fetch_from_adzuna(city_code, max_jobs, max_days_old=max_days_old)
    
    if not jobs:
        logger.warning(f"No Adzuna jobs fetched for {city_code}")
        return stats
    
    stats['jobs_fetched'] = len(jobs)
    logger.info(f"Fetched {len(jobs)} jobs from Adzuna for {city_code.upper()}")
    logger.info(f"{'-'*80}")
    
    # Process each job incrementally
    for i, job in enumerate(jobs, 1):
        try:
            # Extract job data
            company = job.company
            title = job.title
            description = job.description
            url = job.url
            job_id = job.job_id
            source = job.source.value if isinstance(job.source, DataSource) else str(job.source)
            
            # Step 1: Upsert to raw_jobs (updates last_seen for existing jobs)
            # Store both the search city code AND the actual location from Adzuna API
            adzuna_location = job.location if hasattr(job, 'location') else None
            upsert_result = insert_raw_job_upsert(
                source='adzuna',
                posting_url=url,
                title=title,
                company=company,
                raw_text=description,
                city_code=city_code,
                source_job_id=job_id,
                metadata={
                    'adzuna_city': city_code,
                    'adzuna_location': adzuna_location  # Actual location from API for accurate extraction
                }
            )
            
            raw_job_id = upsert_result['id']
            action = upsert_result['action']
            was_duplicate = upsert_result['was_duplicate']
            
            if was_duplicate:
                stats['jobs_duplicate'] += 1
                stats['cost_saved_duplicates'] += 0.00388  # Cost of one classification
                logger.info(f"  [{i}/{len(jobs)}] DUPLICATE: {title[:50]}... (skipped)")
                continue
            
            stats['jobs_written_raw'] += 1
            logger.info(f"  [{i}/{len(jobs)}] NEW: {title[:50]}... (classifying...)")
            
            # Step 2: Hard filter - check if agency before classification
            if is_agency_job(company):
                stats['jobs_agency_filtered'] += 1
                logger.info(f"  [{i}/{len(jobs)}] AGENCY (hard filter): Skipped")
                continue
            
            # Step 3: Check description length (relaxed - we now have structured input)
            if not description or len(description.strip()) < 20:
                logger.warning(f"  [{i}/{len(jobs)}] Skipping - insufficient description (<20 chars)")
                continue
            
            # Step 4: Classify the job with STRUCTURED INPUT
            # Pass title, company, category, and other metadata to help the classifier
            try:
                # Build structured input for classifier
                structured_input = {
                    'title': title,
                    'company': company,
                    'description': description,
                    'location': None,  # Location extracted deterministically via extract_locations()
                    'category': job.adzuna_category if hasattr(job, 'adzuna_category') else None,
                    'salary_min': job.adzuna_salary_min if hasattr(job, 'adzuna_salary_min') else None,
                    'salary_max': job.adzuna_salary_max if hasattr(job, 'adzuna_salary_max') else None,
                }
                
                classification = classify_job(
                    job_text=description,  # Fallback
                    structured_input=structured_input
                )
                stats['jobs_classified'] += 1
                
                # Track classification cost
                if '_cost_data' in classification and 'total_cost' in classification['_cost_data']:
                    cost = classification['_cost_data']['total_cost']
                    stats['cost_classification'] += cost
                    
            except Exception as e:
                logger.warning(f"  [{i}/{len(jobs)}] Classification FAILED: {str(e)[:100]}")
                continue
            
            # Step 5: Soft agency detection
            is_agency, agency_conf = validate_agency_classification(
                employer_name=company,
                claude_is_agency=None,
                claude_confidence=None,
                job_description=description
            )
            
            if is_agency:
                stats['jobs_agency_filtered'] += 1
                logger.info(f"  [{i}/{len(jobs)}] AGENCY (soft detection): Flagged")
            
            # Inject agency flags
            if 'employer' not in classification:
                classification['employer'] = {}
            classification['employer']['is_agency'] = is_agency
            classification['employer']['agency_confidence'] = agency_conf
            
            # Step 6: Write to enriched_jobs
            role = classification.get('role', {})
            location = classification.get('location', {})
            compensation = classification.get('compensation', {})
            employer = classification.get('employer', {})

            # Extract locations from Adzuna API location field (Global Location Expansion Epic)
            # This replaces the legacy city_code approach
            extracted_locations = extract_locations(adzuna_location) if adzuna_location else [{"type": "unknown"}]

            # Derive legacy city_code from locations for backward compatibility (DEPRECATED)
            # This will be removed once all queries use the locations JSONB column
            legacy_city_code = 'unk'
            if extracted_locations and extracted_locations[0].get('type') == 'city':
                city_name = extracted_locations[0].get('city', '')
                city_to_code = {'london': 'lon', 'new_york': 'nyc', 'denver': 'den', 'san_francisco': 'sfo', 'singapore': 'sgp'}
                legacy_city_code = city_to_code.get(city_name, 'unk')
            elif extracted_locations and extracted_locations[0].get('type') == 'remote':
                legacy_city_code = 'remote'

            # Determine working arrangement with employer metadata fallback
            wa_from_classifier = location.get('working_arrangement')
            if not wa_from_classifier or wa_from_classifier == 'unknown':
                wa_fallback = get_working_arrangement_fallback(company)
                working_arrangement = wa_fallback if wa_fallback else 'onsite'  # Adzuna defaults to onsite
            else:
                working_arrangement = wa_from_classifier

            enriched_job_id = insert_enriched_job(
                raw_job_id=raw_job_id,
                employer_name=company,
                title_display=title,
                job_family=role.get('job_family') or 'out_of_scope',
                city_code=legacy_city_code,  # DEPRECATED - use locations instead
                working_arrangement=working_arrangement,
                position_type=role.get('position_type') or 'full_time',
                posted_date=date.today(),
                last_seen_date=date.today(),
                job_subfamily=role.get('job_subfamily'),
                seniority=role.get('seniority'),
                track=role.get('track'),
                experience_range=role.get('experience_range'),
                employer_department=employer.get('department'),
                is_agency=employer.get('is_agency'),
                agency_confidence=employer.get('agency_confidence'),
                currency=compensation.get('currency'),
                salary_min=compensation.get('base_salary_range', {}).get('min'),
                salary_max=compensation.get('base_salary_range', {}).get('max'),
                equity_eligible=compensation.get('equity_eligible'),
                skills=classification.get('skills', []),
                summary=classification.get('summary'),
                data_source='adzuna',
                description_source='adzuna',
                deduplicated=False,
                locations=extracted_locations  # NEW: Structured location data
            )

            # Ensure employer exists in metadata table (for working_arrangement fallback)
            ensure_employer_metadata(company, display_name=company)

            stats['jobs_written_enriched'] += 1
            logger.info(f"  [{i}/{len(jobs)}] SUCCESS: Stored (raw_id={raw_job_id}, enriched_id={enriched_job_id})")
            
        except Exception as e:
            logger.error(f"  [{i}/{len(jobs)}] ERROR: {str(e)[:100]}")
            continue
    
    # Final summary
    elapsed = time.time() - stats['start_time']
    
    logger.info(f"\n{'='*80}")
    logger.info(f"ADZUNA {city_code.upper()} COMPLETE - {elapsed:.1f}s")
    logger.info(f"{'='*80}")
    
    logger.info(f"\nJobs:")
    logger.info(f"  - Fetched: {stats['jobs_fetched']}")
    logger.info(f"  - New (written to raw): {stats['jobs_written_raw']}")
    logger.info(f"  - Duplicates (last_seen updated): {stats['jobs_duplicate']}")
    logger.info(f"  - Classified: {stats['jobs_classified']}")
    logger.info(f"  - Enriched: {stats['jobs_written_enriched']}")
    logger.info(f"  - Agency flags: {stats['jobs_agency_filtered']}")
    
    logger.info(f"\nCost Analysis:")
    logger.info(f"  - Classification cost: ${stats['cost_classification']:.2f}")
    logger.info(f"  - Saved (duplicates skipped): ${stats['cost_saved_duplicates']:.2f}")
    logger.info(f"  - Cost per new job: ${stats['cost_classification']/stats['jobs_written_enriched'] if stats['jobs_written_enriched'] > 0 else 0:.4f}")
    
    logger.info("="*80)
    
    return stats


async def process_lever_incremental(companies: Optional[List[str]] = None) -> Dict:
    """Process Lever jobs incrementally with per-company database writes

    This function implements the incremental architecture (same as Greenhouse):
    1. Fetch jobs from Lever API (with filtering)
    2. Write to raw_jobs using insert_raw_job_upsert()
    3. Classify jobs immediately
    4. Write to enriched_jobs
    5. Log progress clearly per company

    Args:
        companies: Optional list of company slugs to process. If None, processes all from mapping.

    Returns:
        Dict with processing statistics
    """
    from scrapers.lever.lever_fetcher import fetch_lever_jobs, load_company_mapping
    from pipeline.db_connection import (
        insert_raw_job_upsert, insert_enriched_job, get_working_arrangement_fallback,
        ensure_employer_metadata
    )
    from pipeline.classifier import classify_job
    from pipeline.agency_detection import is_agency_job, validate_agency_classification
    from pipeline.unified_job_ingester import DataSource
    from datetime import date
    import json
    import time

    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    logger.info("="*80)
    logger.info("LEVER INCREMENTAL PROCESSING")
    logger.info(f"Started: {start_timestamp}")
    logger.info("="*80)

    # Time tracking
    pipeline_start_time = time.time()

    # Statistics tracking
    stats = {
        'companies_processed': 0,
        'companies_with_jobs': 0,
        'total_jobs_fetched': 0,
        'total_jobs_kept': 0,
        'total_filtered_by_title': 0,
        'total_filtered_by_location': 0,
        'jobs_written_raw': 0,
        'jobs_duplicate': 0,
        'jobs_classified': 0,
        'jobs_agency_filtered': 0,
        'jobs_written_enriched': 0,
        'cost_saved_filtering': 0.0,
        'cost_classification': 0.0,
        'errors': []
    }

    # Load company mapping
    mapping = load_company_mapping()
    lever_companies = mapping.get('lever', {})

    # Create slug -> display_name mapping for proper employer names
    slug_to_display_name = {}
    for display_name, info in lever_companies.items():
        if isinstance(info, dict) and 'slug' in info:
            slug_to_display_name[info['slug']] = display_name

    if not lever_companies:
        logger.warning("No companies in Lever mapping")
        return stats

    # Filter to specified companies if provided
    if companies:
        companies_to_process = {
            name: data for name, data in lever_companies.items()
            if data['slug'] in companies
        }
    else:
        companies_to_process = lever_companies

    logger.info(f"Processing {len(companies_to_process)} Lever companies...\n")

    # Load filter patterns once (for cost savings calculation)
    cost_per_classification = 0.00388  # Haiku cost per job

    for company_name, company_data in companies_to_process.items():
        slug = company_data['slug']
        instance = company_data.get('instance', 'global')
        company_start_time = time.time()

        logger.info(f"\n{'='*80}")
        logger.info(f"COMPANY: {company_name.upper()} ({slug})")
        logger.info(f"{'='*80}")

        # Fetch jobs for this company
        jobs, fetch_stats = fetch_lever_jobs(
            site_slug=slug,
            instance=instance,
            filter_titles=True,
            filter_locations=True
        )

        # Update stats
        stats['companies_processed'] += 1
        stats['total_jobs_fetched'] += fetch_stats['jobs_fetched']
        stats['total_jobs_kept'] += fetch_stats['jobs_kept']
        stats['total_filtered_by_title'] += fetch_stats['filtered_by_title']
        stats['total_filtered_by_location'] += fetch_stats['filtered_by_location']

        # Calculate cost savings from filtering
        filtered_count = fetch_stats['filtered_by_title'] + fetch_stats['filtered_by_location']
        stats['cost_saved_filtering'] += filtered_count * cost_per_classification

        logger.info(f"Fetch Summary:")
        logger.info(f"  - Jobs fetched: {fetch_stats['jobs_fetched']}")
        logger.info(f"  - Filtered (title): {fetch_stats['filtered_by_title']}")
        logger.info(f"  - Filtered (location): {fetch_stats['filtered_by_location']}")
        logger.info(f"  - Jobs to process: {len(jobs)}")
        logger.info(f"  - Cost saved: ${filtered_count * cost_per_classification:.2f}")

        if fetch_stats['error']:
            stats['errors'].append(f"{slug}: {fetch_stats['error']}")
            logger.warning(f"  Error: {fetch_stats['error']}")
            continue

        if not jobs:
            logger.info(f"  No jobs to process for {company_name}")
            continue

        stats['companies_with_jobs'] += 1
        logger.info(f"{'-'*80}")

        # Process each job
        company_jobs_written = 0
        company_jobs_duplicate = 0
        company_jobs_classified = 0
        company_jobs_enriched = 0
        company_agencies_blocked = 0

        for i, job in enumerate(jobs, 1):
            try:
                # Step 1: Write to raw_jobs using UPSERT
                upsert_result = insert_raw_job_upsert(
                    source='lever',
                    posting_url=job.url,
                    title=job.title,
                    company=job.company_slug.replace('-', ' ').title(),
                    raw_text=job.description,
                    city_code='unk',  # Lever doesn't use city codes - location is in metadata
                    source_job_id=job.id,
                    metadata={
                        'company_slug': job.company_slug,
                        'lever_instance': job.instance,
                        'lever_location': job.location,  # Lever's location field from API
                        'lever_team': job.team,
                        'lever_department': job.department,
                        'lever_commitment': job.commitment
                    }
                )

                raw_job_id = upsert_result['id']
                was_duplicate = upsert_result['was_duplicate']

                if was_duplicate:
                    stats['jobs_duplicate'] += 1
                    company_jobs_duplicate += 1
                    logger.info(f"  [{i}/{len(jobs)}] DUPLICATE: {job.title[:50]}... (skipped)")
                    continue

                stats['jobs_written_raw'] += 1
                company_jobs_written += 1
                logger.info(f"  [{i}/{len(jobs)}] NEW JOB: {job.title[:50]}... (classifying...)")

                # Step 2: Hard filter - check if agency before classification
                # Get proper display name from config (e.g., "Figma" instead of "Figma Inc")
                company_display = slug_to_display_name.get(job.company_slug, job.company_slug.replace('-', ' ').title())
                if is_agency_job(company_display):
                    stats['jobs_agency_filtered'] += 1
                    company_agencies_blocked += 1
                    logger.info(f"  [{i}/{len(jobs)}] AGENCY (hard filter): Skipped")
                    continue

                # Step 3: Classify the job
                try:
                    structured_input = {
                        'title': job.title,
                        'company': company_display,
                        'description': job.description,
                        'location': None,  # Location extracted deterministically via extract_locations()
                        'category': None,
                        'salary_min': None,
                        'salary_max': None,
                    }
                    classification = classify_job(
                        job_text=job.description,
                        structured_input=structured_input
                    )
                    stats['jobs_classified'] += 1
                    company_jobs_classified += 1

                    # Track classification cost
                    if '_cost_data' in classification and 'total_cost' in classification['_cost_data']:
                        cost = classification['_cost_data']['total_cost']
                        stats['cost_classification'] += cost
                        logger.info(f"  [{i}/{len(jobs)}] Classified (${cost:.4f})")
                    else:
                        logger.info(f"  [{i}/{len(jobs)}] Classified")

                except Exception as e:
                    logger.warning(f"  [{i}/{len(jobs)}] Classification FAILED: {str(e)[:100]}")
                    continue

                # Step 4: Soft agency detection
                is_agency, agency_conf = validate_agency_classification(
                    employer_name=company_display,
                    claude_is_agency=None,
                    claude_confidence=None,
                    job_description=job.description
                )

                if is_agency:
                    stats['jobs_agency_filtered'] += 1
                    logger.info(f"  [{i}/{len(jobs)}] AGENCY (soft detection): Flagged")

                # Inject agency flags
                if 'employer' not in classification:
                    classification['employer'] = {}
                classification['employer']['is_agency'] = is_agency
                classification['employer']['agency_confidence'] = agency_conf

                # Step 5: Write to enriched_jobs
                role = classification.get('role', {})
                location = classification.get('location', {})
                compensation = classification.get('compensation', {})
                employer = classification.get('employer', {})

                # Extract locations from Lever job.location field (Global Location Expansion Epic)
                # Note: job.location now contains allLocations joined with " / " (fixed in lever_fetcher.py)
                lever_location = job.location if job.location else None
                extracted_locations = extract_locations(lever_location) if lever_location else [{"type": "unknown"}]

                # Derive legacy city_code from locations for backward compatibility (DEPRECATED)
                legacy_city_code = 'unk'
                if extracted_locations and extracted_locations[0].get('type') == 'city':
                    city_name = extracted_locations[0].get('city', '')
                    city_to_code = {'london': 'lon', 'new_york': 'nyc', 'denver': 'den', 'san_francisco': 'sfo', 'singapore': 'sgp'}
                    legacy_city_code = city_to_code.get(city_name, 'unk')
                elif extracted_locations and extracted_locations[0].get('type') == 'remote':
                    legacy_city_code = 'remote'

                # Determine working arrangement with employer metadata fallback
                wa_from_classifier = location.get('working_arrangement') or 'unknown'
                if wa_from_classifier == 'unknown':
                    wa_fallback = get_working_arrangement_fallback(company_display)
                    working_arrangement = wa_fallback if wa_fallback else 'unknown'
                else:
                    working_arrangement = wa_from_classifier

                enriched_job_id = insert_enriched_job(
                    raw_job_id=raw_job_id,
                    employer_name=company_display,
                    title_display=job.title,
                    job_family=role.get('job_family') or 'out_of_scope',
                    city_code=legacy_city_code,  # DEPRECATED - use locations instead
                    working_arrangement=working_arrangement,
                    position_type=role.get('position_type') or 'full_time',
                    posted_date=date.today(),
                    last_seen_date=date.today(),
                    job_subfamily=role.get('job_subfamily'),
                    seniority=role.get('seniority'),
                    track=role.get('track'),
                    experience_range=role.get('experience_range'),
                    employer_department=employer.get('department'),
                    is_agency=employer.get('is_agency'),
                    agency_confidence=employer.get('agency_confidence'),
                    currency=compensation.get('currency'),
                    salary_min=compensation.get('base_salary_range', {}).get('min'),
                    salary_max=compensation.get('base_salary_range', {}).get('max'),
                    equity_eligible=compensation.get('equity_eligible'),
                    skills=classification.get('skills', []),
                    summary=classification.get('summary'),
                    data_source='lever',
                    description_source='lever',
                    locations=extracted_locations,
                    deduplicated=False,
                    display_name_hint=company_display  # From config key
                )

                stats['jobs_written_enriched'] += 1
                company_jobs_enriched += 1
                logger.info(f"  [{i}/{len(jobs)}] SUCCESS: Stored (raw_id={raw_job_id}, enriched_id={enriched_job_id})")

            except Exception as e:
                logger.error(f"  [{i}/{len(jobs)}] ERROR: {str(e)[:100]}")
                continue

        # Company summary
        company_elapsed = time.time() - company_start_time
        logger.info(f"{'-'*80}")
        logger.info(f"Company Summary:")
        logger.info(f"  - New jobs written: {company_jobs_written}")
        logger.info(f"  - Duplicates skipped: {company_jobs_duplicate}")
        logger.info(f"  - Agencies blocked: {company_agencies_blocked}")
        logger.info(f"  - Jobs classified: {company_jobs_classified}")
        logger.info(f"  - Jobs enriched: {company_jobs_enriched}")
        logger.info(f"  - Processing time: {company_elapsed:.1f}s")
        logger.info(f"{'='*80}")

    # Final summary
    total_elapsed = time.time() - pipeline_start_time
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    logger.info("\n" + "="*80)
    logger.info("LEVER INCREMENTAL PROCESSING COMPLETE")
    logger.info(f"Started: {start_timestamp}")
    logger.info(f"Ended: {end_timestamp}")
    logger.info(f"Total time: {total_elapsed/60:.1f} min ({total_elapsed:.1f}s)")
    logger.info("="*80)

    logger.info(f"\nCompany Processing:")
    logger.info(f"  - Companies processed: {stats['companies_processed']}")
    logger.info(f"  - Companies with jobs: {stats['companies_with_jobs']}")

    logger.info(f"\nJob Fetching & Filtering:")
    logger.info(f"  - Jobs fetched: {stats['total_jobs_fetched']}")
    logger.info(f"  - Filtered (title): {stats['total_filtered_by_title']}")
    logger.info(f"  - Filtered (location): {stats['total_filtered_by_location']}")
    logger.info(f"  - Jobs kept: {stats['total_jobs_kept']}")

    logger.info(f"\nDatabase Writes:")
    logger.info(f"  - New raw jobs: {stats['jobs_written_raw']}")
    logger.info(f"  - Duplicates skipped: {stats['jobs_duplicate']}")
    logger.info(f"  - Jobs classified: {stats['jobs_classified']}")
    logger.info(f"  - Enriched jobs: {stats['jobs_written_enriched']}")
    logger.info(f"  - Agency flags: {stats['jobs_agency_filtered']}")

    logger.info(f"\nCost Analysis:")
    logger.info(f"  - Saved from filtering: ${stats['cost_saved_filtering']:.2f}")
    logger.info(f"  - Classification cost: ${stats['cost_classification']:.2f}")
    logger.info(f"  - Net cost: ${stats['cost_classification']:.2f}")

    if stats['errors']:
        logger.info(f"\nErrors:")
        for error in stats['errors']:
            logger.info(f"  - {error}")

    logger.info("="*80)

    return stats


async def process_ashby_incremental(companies: Optional[List[str]] = None) -> Dict:
    """Process Ashby jobs incrementally with per-company database writes

    This function implements the incremental architecture (same as Lever):
    1. Fetch jobs from Ashby API (with filtering)
    2. Write to raw_jobs using insert_raw_job_upsert()
    3. Classify jobs immediately
    4. Write to enriched_jobs
    5. Log progress clearly per company

    Ashby Advantages:
    - Structured compensation data (salary_min/max/currency already parsed)
    - Explicit isRemote boolean flag
    - Structured postalAddress for location extraction
    - Both HTML and plain text descriptions provided

    Args:
        companies: Optional list of company slugs to process. If None, processes all from mapping.

    Returns:
        Dict with processing statistics
    """
    from scrapers.ashby.ashby_fetcher import fetch_ashby_jobs, load_company_mapping
    from pipeline.db_connection import (
        insert_raw_job_upsert, insert_enriched_job, get_working_arrangement_fallback,
        ensure_employer_metadata
    )
    from pipeline.classifier import classify_job
    from pipeline.agency_detection import is_agency_job, validate_agency_classification
    from pipeline.unified_job_ingester import DataSource
    from datetime import date
    import json
    import time

    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    logger.info("="*80)
    logger.info("ASHBY INCREMENTAL PROCESSING")
    logger.info(f"Started: {start_timestamp}")
    logger.info("="*80)

    # Time tracking
    pipeline_start_time = time.time()

    # Statistics tracking
    stats = {
        'companies_processed': 0,
        'companies_with_jobs': 0,
        'total_jobs_fetched': 0,
        'total_jobs_kept': 0,
        'total_filtered_by_title': 0,
        'total_filtered_by_location': 0,
        'jobs_written_raw': 0,
        'jobs_duplicate': 0,
        'jobs_classified': 0,
        'jobs_agency_filtered': 0,
        'jobs_written_enriched': 0,
        'jobs_with_salary': 0,  # Track Ashby's structured compensation
        'cost_saved_filtering': 0.0,
        'cost_classification': 0.0,
        'errors': []
    }

    # Load company mapping
    mapping = load_company_mapping()
    ashby_companies = mapping.get('ashby', {})

    # Create slug -> display_name mapping for proper employer names
    slug_to_display_name = {}
    for display_name, info in ashby_companies.items():
        if isinstance(info, dict) and 'slug' in info:
            slug_to_display_name[info['slug']] = display_name

    if not ashby_companies:
        logger.warning("No companies in Ashby mapping")
        return stats

    # Filter to specified companies if provided
    if companies:
        companies_to_process = {
            name: data for name, data in ashby_companies.items()
            if data['slug'] in companies
        }
    else:
        companies_to_process = ashby_companies

    logger.info(f"Processing {len(companies_to_process)} Ashby companies...\n")

    # Cost per classification
    cost_per_classification = 0.00388  # Haiku cost per job

    for company_name, company_data in companies_to_process.items():
        slug = company_data['slug']
        company_start_time = time.time()

        logger.info(f"\n{'='*80}")
        logger.info(f"COMPANY: {company_name.upper()} ({slug})")
        logger.info(f"{'='*80}")

        # Fetch jobs for this company
        jobs, fetch_stats = fetch_ashby_jobs(
            company_slug=slug,
            filter_titles=True,
            filter_locations=True
        )

        # Update stats
        stats['companies_processed'] += 1
        stats['total_jobs_fetched'] += fetch_stats['jobs_fetched']
        stats['total_jobs_kept'] += fetch_stats['jobs_kept']
        stats['total_filtered_by_title'] += fetch_stats['filtered_by_title']
        stats['total_filtered_by_location'] += fetch_stats['filtered_by_location']

        # Calculate cost savings from filtering
        filtered_count = fetch_stats['filtered_by_title'] + fetch_stats['filtered_by_location']
        stats['cost_saved_filtering'] += filtered_count * cost_per_classification

        logger.info(f"Fetch Summary:")
        logger.info(f"  - Jobs fetched: {fetch_stats['jobs_fetched']}")
        logger.info(f"  - Filtered (title): {fetch_stats['filtered_by_title']}")
        logger.info(f"  - Filtered (location): {fetch_stats['filtered_by_location']}")
        logger.info(f"  - Jobs to process: {len(jobs)}")
        logger.info(f"  - Cost saved: ${filtered_count * cost_per_classification:.2f}")

        if fetch_stats['error']:
            stats['errors'].append(f"{slug}: {fetch_stats['error']}")
            logger.warning(f"  Error: {fetch_stats['error']}")
            continue

        if not jobs:
            logger.info(f"  No jobs to process for {company_name}")
            continue

        stats['companies_with_jobs'] += 1
        logger.info(f"{'-'*80}")

        # Process each job
        company_jobs_written = 0
        company_jobs_duplicate = 0
        company_jobs_classified = 0
        company_jobs_enriched = 0
        company_agencies_blocked = 0
        company_with_salary = 0

        for i, job in enumerate(jobs, 1):
            try:
                # Step 1: Write to raw_jobs using UPSERT
                # Build location string from Ashby's structured data
                ashby_location = job.location  # Already combined in fetcher

                upsert_result = insert_raw_job_upsert(
                    source='ashby',
                    posting_url=job.url,
                    title=job.title,
                    company=company_name,
                    raw_text=job.description,
                    city_code='unk',  # Ashby doesn't use city codes - location is in metadata
                    source_job_id=job.id,
                    metadata={
                        'company_slug': job.company_slug,
                        'ashby_location': ashby_location,
                        'ashby_city': job.city,
                        'ashby_region': job.region,
                        'ashby_country': job.country,
                        'ashby_is_remote': job.is_remote,
                        'ashby_department': job.department,
                        'ashby_team': job.team,
                        'ashby_employment_type': job.employment_type,
                        'ashby_salary_min': job.salary_min,
                        'ashby_salary_max': job.salary_max,
                        'ashby_salary_currency': job.salary_currency,
                        'ashby_published_at': job.published_at
                    }
                )

                raw_job_id = upsert_result['id']
                was_duplicate = upsert_result['was_duplicate']

                if was_duplicate:
                    stats['jobs_duplicate'] += 1
                    company_jobs_duplicate += 1
                    logger.info(f"  [{i}/{len(jobs)}] DUPLICATE: {job.title[:50]}... (skipped)")
                    continue

                stats['jobs_written_raw'] += 1
                company_jobs_written += 1

                # Track jobs with structured salary data
                if job.salary_min or job.salary_max:
                    stats['jobs_with_salary'] += 1
                    company_with_salary += 1

                logger.info(f"  [{i}/{len(jobs)}] NEW JOB: {job.title[:50]}... (classifying...)")

                # Step 2: Hard filter - check if agency before classification
                if is_agency_job(company_name):
                    stats['jobs_agency_filtered'] += 1
                    company_agencies_blocked += 1
                    logger.info(f"  [{i}/{len(jobs)}] AGENCY (hard filter): Skipped")
                    continue

                # Step 3: Classify the job
                try:
                    structured_input = {
                        'title': job.title,
                        'company': company_name,
                        'description': job.description,
                        'location': None,  # Location extracted deterministically via extract_locations()
                        'category': None,
                        # Pass Ashby's structured salary to classifier for validation
                        'salary_min': job.salary_min,
                        'salary_max': job.salary_max,
                    }
                    classification = classify_job(
                        job_text=job.description,
                        structured_input=structured_input
                    )
                    stats['jobs_classified'] += 1
                    company_jobs_classified += 1

                    # Track classification cost
                    if '_cost_data' in classification and 'total_cost' in classification['_cost_data']:
                        cost = classification['_cost_data']['total_cost']
                        stats['cost_classification'] += cost
                        logger.info(f"  [{i}/{len(jobs)}] Classified (${cost:.4f})")
                    else:
                        logger.info(f"  [{i}/{len(jobs)}] Classified")

                except Exception as e:
                    logger.warning(f"  [{i}/{len(jobs)}] Classification FAILED: {str(e)[:100]}")
                    continue

                # Step 4: Soft agency detection
                is_agency, agency_conf = validate_agency_classification(
                    employer_name=company_name,
                    claude_is_agency=None,
                    claude_confidence=None,
                    job_description=job.description
                )

                if is_agency:
                    stats['jobs_agency_filtered'] += 1
                    logger.info(f"  [{i}/{len(jobs)}] AGENCY (soft detection): Flagged")

                # Inject agency flags
                if 'employer' not in classification:
                    classification['employer'] = {}
                classification['employer']['is_agency'] = is_agency
                classification['employer']['agency_confidence'] = agency_conf

                # Step 5: Write to enriched_jobs
                role = classification.get('role', {})
                location = classification.get('location', {})
                compensation = classification.get('compensation', {})
                employer = classification.get('employer', {})

                # Extract locations from Ashby job.location field
                extracted_locations = extract_locations(ashby_location) if ashby_location else [{"type": "unknown"}]

                # Derive legacy city_code from locations for backward compatibility (DEPRECATED)
                legacy_city_code = 'unk'
                if extracted_locations and extracted_locations[0].get('type') == 'city':
                    city_name = extracted_locations[0].get('city', '')
                    city_to_code = {'london': 'lon', 'new_york': 'nyc', 'denver': 'den', 'san_francisco': 'sfo', 'singapore': 'sgp'}
                    legacy_city_code = city_to_code.get(city_name, 'unk')
                elif extracted_locations and extracted_locations[0].get('type') == 'remote':
                    legacy_city_code = 'remote'
                # Override with Ashby's explicit isRemote flag
                elif job.is_remote:
                    legacy_city_code = 'remote'

                # Use Ashby's structured salary data if available, fall back to classifier
                final_salary_min = job.salary_min or compensation.get('base_salary_range', {}).get('min')
                final_salary_max = job.salary_max or compensation.get('base_salary_range', {}).get('max')
                final_currency = job.salary_currency or compensation.get('currency')

                # Derive working arrangement: classifier > is_remote flag > employer metadata > unknown
                working_arrangement = location.get('working_arrangement') or 'unknown'
                if job.is_remote and working_arrangement == 'unknown':
                    working_arrangement = 'remote'
                elif working_arrangement == 'unknown':
                    wa_fallback = get_working_arrangement_fallback(company_name)
                    working_arrangement = wa_fallback if wa_fallback else 'unknown'

                enriched_job_id = insert_enriched_job(
                    raw_job_id=raw_job_id,
                    employer_name=company_name,
                    title_display=job.title,
                    job_family=role.get('job_family') or 'out_of_scope',
                    city_code=legacy_city_code,  # DEPRECATED - use locations instead
                    working_arrangement=working_arrangement,
                    position_type=role.get('position_type') or 'full_time',
                    posted_date=date.today(),
                    last_seen_date=date.today(),
                    job_subfamily=role.get('job_subfamily'),
                    seniority=role.get('seniority'),
                    track=role.get('track'),
                    experience_range=role.get('experience_range'),
                    employer_department=employer.get('department'),
                    is_agency=employer.get('is_agency'),
                    agency_confidence=employer.get('agency_confidence'),
                    currency=final_currency,
                    salary_min=final_salary_min,
                    salary_max=final_salary_max,
                    equity_eligible=compensation.get('equity_eligible'),
                    skills=classification.get('skills', []),
                    summary=classification.get('summary'),
                    data_source='ashby',
                    description_source='ashby',
                    locations=extracted_locations,
                    deduplicated=False,
                    display_name_hint=company_name  # From config key
                )

                stats['jobs_written_enriched'] += 1
                company_jobs_enriched += 1
                logger.info(f"  [{i}/{len(jobs)}] SUCCESS: Stored (raw_id={raw_job_id}, enriched_id={enriched_job_id})")

            except Exception as e:
                logger.error(f"  [{i}/{len(jobs)}] ERROR: {str(e)[:100]}")
                continue

        # Company summary
        company_elapsed = time.time() - company_start_time
        logger.info(f"{'-'*80}")
        logger.info(f"Company Summary:")
        logger.info(f"  - New jobs written: {company_jobs_written}")
        logger.info(f"  - Duplicates skipped: {company_jobs_duplicate}")
        logger.info(f"  - Agencies blocked: {company_agencies_blocked}")
        logger.info(f"  - Jobs classified: {company_jobs_classified}")
        logger.info(f"  - Jobs enriched: {company_jobs_enriched}")
        logger.info(f"  - Jobs with salary data: {company_with_salary}")
        logger.info(f"  - Processing time: {company_elapsed:.1f}s")
        logger.info(f"{'='*80}")

    # Final summary
    total_elapsed = time.time() - pipeline_start_time
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    logger.info("\n" + "="*80)
    logger.info("ASHBY INCREMENTAL PROCESSING COMPLETE")
    logger.info(f"Started: {start_timestamp}")
    logger.info(f"Ended: {end_timestamp}")
    logger.info(f"Total time: {total_elapsed/60:.1f} min ({total_elapsed:.1f}s)")
    logger.info("="*80)

    logger.info(f"\nCompany Processing:")
    logger.info(f"  - Companies processed: {stats['companies_processed']}")
    logger.info(f"  - Companies with jobs: {stats['companies_with_jobs']}")

    logger.info(f"\nJob Fetching & Filtering:")
    logger.info(f"  - Jobs fetched: {stats['total_jobs_fetched']}")
    logger.info(f"  - Filtered (title): {stats['total_filtered_by_title']}")
    logger.info(f"  - Filtered (location): {stats['total_filtered_by_location']}")
    logger.info(f"  - Jobs kept: {stats['total_jobs_kept']}")

    logger.info(f"\nDatabase Writes:")
    logger.info(f"  - New raw jobs: {stats['jobs_written_raw']}")
    logger.info(f"  - Duplicates skipped: {stats['jobs_duplicate']}")
    logger.info(f"  - Jobs classified: {stats['jobs_classified']}")
    logger.info(f"  - Enriched jobs: {stats['jobs_written_enriched']}")
    logger.info(f"  - Agency flags: {stats['jobs_agency_filtered']}")

    logger.info(f"\nAshby Data Quality:")
    logger.info(f"  - Jobs with structured salary: {stats['jobs_with_salary']}")
    if stats['jobs_written_enriched'] > 0:
        salary_rate = (stats['jobs_with_salary'] / stats['jobs_written_enriched'] * 100)
        logger.info(f"  - Salary data rate: {salary_rate:.1f}%")

    logger.info(f"\nCost Analysis:")
    logger.info(f"  - Saved from filtering: ${stats['cost_saved_filtering']:.2f}")
    logger.info(f"  - Classification cost: ${stats['cost_classification']:.2f}")
    logger.info(f"  - Net cost: ${stats['cost_classification']:.2f}")

    if stats['errors']:
        logger.info(f"\nErrors:")
        for error in stats['errors']:
            logger.info(f"  - {error}")

    logger.info("="*80)

    return stats


async def merge_jobs(
    adzuna_jobs: List,
    greenhouse_jobs: List,
    min_description_length: int = 0
) -> Dict:
    """Merge jobs from multiple sources with deduplication"""

    from pipeline.unified_job_ingester import UnifiedJobIngester

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
        from pipeline.classifier import classify_job
        from pipeline.agency_detection import is_agency_job

        logger.info(f"Classifying {len(jobs)} jobs")

        classified = []
        agencies_blocked = 0
        for i, job in enumerate(jobs):
            if (i + 1) % 10 == 0:
                logger.info(f"  Progress: {i+1}/{len(jobs)}")

            # Hard filter: check if it's a known agency
            company_name = job.company
            if is_agency_job(company_name):
                logger.info(f"[BLOCKED AGENCY] {company_name}")
                agencies_blocked += 1
                continue

            # Classify the job
            try:
                # Check for empty or insufficient descriptions
                description = job.description
                if not description or len(description.strip()) < 50:
                    logger.warning(f"Skipping job with insufficient description (<50 chars): {job.title}")
                    continue

                # classify_job is synchronous, not async
                structured_input = {
                    'title': job.title,
                    'company': job.company,
                    'description': description,
                    'location': None,
                    'category': None,
                    'salary_min': None,
                    'salary_max': None,
                }
                classification = classify_job(
                    job_text=description,
                    structured_input=structured_input
                )

                # Add agency detection via pattern matching (soft detection)
                # This populates is_agency and agency_confidence fields that Claude no longer returns
                from pipeline.agency_detection import validate_agency_classification

                is_agency, agency_conf = validate_agency_classification(
                    employer_name=job.company,
                    claude_is_agency=None,  # Claude no longer returns this field
                    claude_confidence=None,
                    job_description=description
                )

                # Inject agency flags into classification result
                if 'employer' not in classification:
                    classification['employer'] = {}
                classification['employer']['is_agency'] = is_agency
                classification['employer']['agency_confidence'] = agency_conf

                # Add classification to job (now a proper dataclass field)
                job.classification = classification

                classified.append(job)
            except Exception as e:
                logger.warning(f"Failed to classify job {job.title}: {str(e)}")
                continue

        logger.info(f"Classified {len(classified)} jobs successfully")
        logger.info(f"  - Agencies blocked: {agencies_blocked}")
        logger.info(f"  - Other filters: {len(jobs) - len(classified) - agencies_blocked}")

        return classified

    except Exception as e:
        logger.error(f"Classification failed: {str(e)}")
        return jobs  # Return original jobs if classification fails


async def store_jobs(jobs: List, source_city: str = 'unk', table: str = "enriched_jobs") -> bool:
    """Store jobs in Supabase database

    Expects jobs to be UnifiedJob objects with classification data attached.

    Args:
        jobs: List of UnifiedJob objects with classification data
        source_city: City code where jobs were fetched from (lon, nyc, den). Fallback if classification fails to extract.
        table: Database table to store in (default: enriched_jobs)
    """

    try:
        from pipeline.db_connection import (
            insert_raw_job, insert_enriched_job, get_working_arrangement_fallback,
            ensure_employer_metadata
        )
        from datetime import date
        from pipeline.unified_job_ingester import UnifiedJob, DataSource

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
                    title=title,
                    company=company,
                    raw_text=description,
                    source_job_id=job_id
                )

                # Step 2: Extract classification data
                role = classification.get('role', {})
                location = classification.get('location', {})
                compensation = classification.get('compensation', {})
                employer = classification.get('employer', {})

                # Determine working arrangement with employer metadata fallback
                wa_from_classifier = location.get('working_arrangement') or 'unknown'
                if wa_from_classifier == 'unknown':
                    wa_fallback = get_working_arrangement_fallback(company)
                    working_arrangement = wa_fallback if wa_fallback else 'unknown'
                else:
                    working_arrangement = wa_from_classifier

                # Step 3: Insert enriched job
                # Use extracted location > source city > 'unk' (unknown)
                # This way: Adzuna jobs use source_city if extraction fails, Greenhouse jobs use 'unk'
                enriched_job_id = insert_enriched_job(
                    raw_job_id=raw_job_id,
                    employer_name=company,
                    title_display=title,
                    job_family=role.get('job_family') or 'out_of_scope',
                    city_code=location.get('city_code') or source_city or 'unk',
                    working_arrangement=working_arrangement,
                    position_type=role.get('position_type') or 'full_time',
                    posted_date=date.today(),
                    last_seen_date=date.today(),
                    # Optional fields
                    job_subfamily=role.get('job_subfamily'),
                    seniority=role.get('seniority'),
                    track=role.get('track'),
                    experience_range=role.get('experience_range'),
                    employer_department=employer.get('department'),
                    is_agency=employer.get('is_agency'),
                    agency_confidence=employer.get('agency_confidence'),
                    currency=compensation.get('currency'),
                    salary_min=compensation.get('base_salary_range', {}).get('min'),
                    salary_max=compensation.get('base_salary_range', {}).get('max'),
                    equity_eligible=compensation.get('equity_eligible'),
                    skills=classification.get('skills', []),
                    summary=classification.get('summary'),
                    # Dual pipeline source tracking
                    data_source=source,
                    description_source=description_source,
                    deduplicated=deduplicated,
                    display_name_hint=company  # From Adzuna API
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
        description='Unified job fetcher: Adzuna + Greenhouse + Lever + Ashby multi-source pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # All sources
  python fetch_jobs.py lon 100 --sources adzuna,greenhouse,lever,ashby

  # Adzuna only
  python fetch_jobs.py lon 100 --sources adzuna

  # Greenhouse only (browser scraping)
  python fetch_jobs.py --sources greenhouse

  # Lever only (simple HTTP API)
  python fetch_jobs.py --sources lever

  # Ashby only (simple HTTP API, best compensation data)
  python fetch_jobs.py --sources ashby

  # NYC with more jobs
  python fetch_jobs.py nyc 200 --sources adzuna,greenhouse,lever,ashby
        """
    )

    parser.add_argument(
        'city',
        nargs='?',
        default='lon',
        help='City code: lon (London), nyc (New York), den (Denver), sfo (San Francisco), sgp (Singapore). Default: lon'
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
        required=True,
        help='Comma-separated sources: adzuna, greenhouse, lever, ashby (required). Example: --sources adzuna,greenhouse,ashby'
    )

    parser.add_argument(
        '--companies',
        help='Comma-separated list of company slugs (applies to Greenhouse, Lever, and Ashby sources)'
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

    parser.add_argument(
        '--resume-hours',
        type=int,
        default=0,
        help='Resume mode: Skip companies processed within last N hours (0 = disabled). Example: --resume-hours 24'
    )

    parser.add_argument(
        '--adzuna-max-days-old',
        type=int,
        default=30,
        help='Adzuna only: filter to jobs posted within last N days (max_days_old). Default: 30'
    )

    args = parser.parse_args()

    # Parse sources first
    sources = [s.strip().lower() for s in args.sources.split(',')]

    logger.info("="*80)
    logger.info("JOB FETCHER PIPELINE")
    logger.info("="*80)
    logger.info(f"Sources: {args.sources}")
    logger.info(f"Min description length: {args.min_description_length}")

    # Only show Adzuna-specific options if Adzuna is being used
    if 'adzuna' in sources:
        logger.info(f"Adzuna city: {args.city}")
        logger.info(f"Adzuna max jobs per role query: {args.max_jobs}")
        from scrapers.adzuna.fetch_adzuna_jobs import DEFAULT_SEARCH_QUERIES
        logger.info(f"Adzuna will search {len(DEFAULT_SEARCH_QUERIES)} role types")
        logger.info(f"Adzuna max_days_old filter: {args.adzuna_max_days_old} days")

    # Only show Greenhouse-specific options if Greenhouse is being used
    if 'greenhouse' in sources:
        logger.info(f"Greenhouse: Resume mode {args.resume_hours}h window" if args.resume_hours > 0 else "Greenhouse: No resume mode")

    # Show companies if specified
    if args.companies:
        logger.info(f"Companies (Greenhouse/Lever): {args.companies}")

    logger.info("="*80 + "\n")

    # Track total statistics
    total_stats = {
        'greenhouse': None,
        'adzuna': None,
        'lever': None,
        'ashby': None
    }

    # GREENHOUSE PIPELINE: Incremental processing (scrape → write raw → classify → write enriched)
    if 'greenhouse' in sources:
        companies = None
        if args.companies:
            companies = [c.strip() for c in args.companies.split(',')]

        logger.info("\n" + "="*80)
        logger.info("STARTING GREENHOUSE INCREMENTAL PIPELINE")
        if args.resume_hours > 0:
            logger.info(f"Resume Mode: Enabled ({args.resume_hours} hour window)")
        logger.info("="*80 + "\n")

        greenhouse_stats = await process_greenhouse_incremental(companies, resume_hours=args.resume_hours)
        total_stats['greenhouse'] = greenhouse_stats

    # ADZUNA PIPELINE: Incremental processing (same pattern as Greenhouse)
    # Upserts to raw_jobs first, only classifies NEW jobs to save API costs
    if 'adzuna' in sources:
        adzuna_stats = await process_adzuna_incremental(
            args.city,
            args.max_jobs,
            max_days_old=args.adzuna_max_days_old
        )
        total_stats['adzuna'] = adzuna_stats

    # LEVER PIPELINE: Incremental processing (same pattern as Greenhouse)
    # Simple HTTP API (no browser automation), full job descriptions like Greenhouse
    if 'lever' in sources:
        lever_companies = None
        if args.companies:
            lever_companies = [c.strip() for c in args.companies.split(',')]

        logger.info("\n" + "="*80)
        logger.info("STARTING LEVER INCREMENTAL PIPELINE")
        logger.info("="*80 + "\n")

        lever_stats = await process_lever_incremental(lever_companies)
        total_stats['lever'] = lever_stats

    # ASHBY PIPELINE: Incremental processing (same pattern as Lever)
    # Simple HTTP API with best structured compensation data
    if 'ashby' in sources:
        ashby_companies = None
        if args.companies:
            ashby_companies = [c.strip() for c in args.companies.split(',')]

        logger.info("\n" + "="*80)
        logger.info("STARTING ASHBY INCREMENTAL PIPELINE")
        logger.info("="*80 + "\n")

        ashby_stats = await process_ashby_incremental(ashby_companies)
        total_stats['ashby'] = ashby_stats

    # FINAL SUMMARY
    logger.info("\n" + "="*80)
    logger.info("MULTI-SOURCE PIPELINE COMPLETE")
    logger.info("="*80)

    if total_stats['greenhouse']:
        logger.info("\nGreenhouse Pipeline:")
        gh_effective_total = total_stats['greenhouse'].get(
            'companies_total_effective',
            total_stats['greenhouse']['companies_total']
        )
        logger.info(f"  Companies processed: {total_stats['greenhouse']['companies_processed']}/{gh_effective_total}")
        logger.info(f"  Companies skipped (resume): {total_stats['greenhouse']['companies_skipped']}")
        if total_stats['greenhouse'].get('companies_total') != gh_effective_total:
            logger.info(f"  Companies in original list: {total_stats['greenhouse']['companies_total']}")
        logger.info(f"  Jobs scraped: {total_stats['greenhouse']['jobs_scraped']}")
        logger.info(f"  Jobs kept after filtering: {total_stats['greenhouse']['jobs_kept']}")
        logger.info(f"  Jobs written to raw_jobs: {total_stats['greenhouse']['jobs_written_raw']}")
        logger.info(f"  Jobs classified: {total_stats['greenhouse']['jobs_classified']}")
        logger.info(f"  Jobs written to enriched_jobs: {total_stats['greenhouse']['jobs_written_enriched']}")
        logger.info(f"  Duplicates skipped: {total_stats['greenhouse']['jobs_duplicate']}")
        logger.info(f"  Cost saved from filtering: ${total_stats['greenhouse']['cost_saved_filtering']:.2f}")
        logger.info(f"  Cost of classification: ${total_stats['greenhouse']['cost_classification']:.2f}")

    if total_stats['adzuna']:
        logger.info("\nAdzuna Pipeline:")
        logger.info(f"  Jobs fetched: {total_stats['adzuna']['jobs_fetched']}")
        logger.info(f"  New jobs (written to raw): {total_stats['adzuna']['jobs_written_raw']}")
        logger.info(f"  Duplicates (last_seen updated): {total_stats['adzuna']['jobs_duplicate']}")
        logger.info(f"  Jobs classified: {total_stats['adzuna']['jobs_classified']}")
        logger.info(f"  Jobs written to enriched_jobs: {total_stats['adzuna']['jobs_written_enriched']}")
        logger.info(f"  Cost of classification: ${total_stats['adzuna']['cost_classification']:.2f}")
        logger.info(f"  Cost saved (duplicates): ${total_stats['adzuna']['cost_saved_duplicates']:.2f}")

    if total_stats['lever']:
        logger.info("\nLever Pipeline:")
        logger.info(f"  Companies processed: {total_stats['lever']['companies_processed']}")
        logger.info(f"  Companies with jobs: {total_stats['lever']['companies_with_jobs']}")
        logger.info(f"  Jobs fetched: {total_stats['lever']['total_jobs_fetched']}")
        logger.info(f"  Filtered (title): {total_stats['lever']['total_filtered_by_title']}")
        logger.info(f"  Filtered (location): {total_stats['lever']['total_filtered_by_location']}")
        logger.info(f"  Jobs kept: {total_stats['lever']['total_jobs_kept']}")
        logger.info(f"  New jobs (written to raw): {total_stats['lever']['jobs_written_raw']}")
        logger.info(f"  Duplicates skipped: {total_stats['lever']['jobs_duplicate']}")
        logger.info(f"  Jobs classified: {total_stats['lever']['jobs_classified']}")
        logger.info(f"  Jobs written to enriched_jobs: {total_stats['lever']['jobs_written_enriched']}")
        logger.info(f"  Cost saved from filtering: ${total_stats['lever']['cost_saved_filtering']:.2f}")
        logger.info(f"  Cost of classification: ${total_stats['lever']['cost_classification']:.2f}")

    if total_stats['ashby']:
        logger.info("\nAshby Pipeline:")
        logger.info(f"  Companies processed: {total_stats['ashby']['companies_processed']}")
        logger.info(f"  Companies with jobs: {total_stats['ashby']['companies_with_jobs']}")
        logger.info(f"  Jobs fetched: {total_stats['ashby']['total_jobs_fetched']}")
        logger.info(f"  Filtered (title): {total_stats['ashby']['total_filtered_by_title']}")
        logger.info(f"  Filtered (location): {total_stats['ashby']['total_filtered_by_location']}")
        logger.info(f"  Jobs kept: {total_stats['ashby']['total_jobs_kept']}")
        logger.info(f"  New jobs (written to raw): {total_stats['ashby']['jobs_written_raw']}")
        logger.info(f"  Duplicates skipped: {total_stats['ashby']['jobs_duplicate']}")
        logger.info(f"  Jobs classified: {total_stats['ashby']['jobs_classified']}")
        logger.info(f"  Jobs written to enriched_jobs: {total_stats['ashby']['jobs_written_enriched']}")
        logger.info(f"  Jobs with structured salary: {total_stats['ashby']['jobs_with_salary']}")
        logger.info(f"  Cost saved from filtering: ${total_stats['ashby']['cost_saved_filtering']:.2f}")
        logger.info(f"  Cost of classification: ${total_stats['ashby']['cost_classification']:.2f}")

    total_jobs = 0
    if total_stats['greenhouse']:
        total_jobs += total_stats['greenhouse']['jobs_written_enriched']
    if total_stats['adzuna']:
        total_jobs += total_stats['adzuna']['jobs_written_enriched']
    if total_stats['lever']:
        total_jobs += total_stats['lever']['jobs_written_enriched']
    if total_stats['ashby']:
        total_jobs += total_stats['ashby']['jobs_written_enriched']

    logger.info(f"\nTotal jobs processed: {total_jobs}")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
