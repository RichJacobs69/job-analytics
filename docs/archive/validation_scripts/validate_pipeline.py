"""
Pipeline Validation & Unit Economics Assessment

Purpose:
--------
Run the dual pipeline (Adzuna + Greenhouse) with comprehensive metrics tracking
to validate unit economics, deduplication logic, and classification quality.

Outputs:
--------
- validation_metrics.json: Detailed metrics for each step
- validation_sample_jobs.json: Sample of classified jobs for quality review
- PIPELINE_VALIDATION_REPORT.md: Comprehensive analysis and recommendations

Usage:
------
python validate_pipeline.py --cities lon,nyc --max-jobs 100 --output-file validation_metrics.json
"""

import sys
import asyncio
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from dataclasses import dataclass, asdict
import traceback

# Fix Windows charmap encoding issues
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ClassificationMetrics:
    """Metrics for a single classification"""
    job_id: str
    company: str
    title: str
    source: str  # 'adzuna' or 'greenhouse'
    description_length: int
    classification_time: float
    classification_success: bool
    classification_error: Optional[str] = None
    skills_extracted_count: Optional[int] = None
    remote_status_detected: Optional[bool] = None
    compensation_detected: Optional[bool] = None


@dataclass
class PipelineMetrics:
    """Overall pipeline metrics"""
    timestamp: str
    cities: List[str]
    max_jobs_per_city: int

    # Fetch phase
    adzuna_fetched: int
    adzuna_fetch_time: float
    greenhouse_fetched: int
    greenhouse_fetch_time: float

    # Merge phase
    merged_count: int
    adzuna_after_merge: int  # Adzuna jobs in final merged set
    greenhouse_after_merge: int  # Greenhouse jobs in final merged set
    duplicates_removed: int
    merge_time: float

    # Classification phase
    jobs_classified: int
    jobs_classified_time: float
    classification_failures: int
    avg_classification_time: float  # Per job

    # Cost analysis
    estimated_claude_calls: int
    estimated_claude_cost: float  # Based on Haiku pricing
    total_pipeline_cost: float
    cost_per_unique_job: float

    # Quality metrics
    skills_extraction_rate: float  # % of jobs with skills detected
    remote_status_detection_rate: float  # % of jobs with remote status detected
    compensation_detection_rate: float  # % of jobs with compensation detected

    # Storage phase
    jobs_stored: int
    storage_time: float
    storage_failures: int

    # Deduplication analysis
    greenhouse_preference_ratio: float  # % of merged jobs that preferred Greenhouse text


class PipelineValidator:
    """Validates the dual pipeline with comprehensive metrics"""

    def __init__(self):
        self.metrics = None
        self.classification_samples = []
        self.cost_model = {
            'haiku_per_1m_input_tokens': 0.80,  # $0.80 per 1M input tokens
            'haiku_per_1m_output_tokens': 2.40,  # $2.40 per 1M output tokens
            'avg_input_tokens_per_job': 1500,  # Rough estimate
            'avg_output_tokens_per_job': 200,  # Rough estimate
        }

    def estimate_classification_cost(self) -> float:
        """Estimate cost per classification based on token usage.

        Pricing:
        - Haiku input: $0.80 per 1M tokens
        - Haiku output: $2.40 per 1M tokens
        """
        input_cost = (self.cost_model['avg_input_tokens_per_job'] / 1_000_000) * self.cost_model['haiku_per_1m_input_tokens']
        output_cost = (self.cost_model['avg_output_tokens_per_job'] / 1_000_000) * self.cost_model['haiku_per_1m_output_tokens']
        return input_cost + output_cost

    async def run_validation(self, cities: List[str], max_jobs_per_city: int) -> Dict:
        """Run full validation pipeline"""

        logger.info("="*80)
        logger.info("PIPELINE VALIDATION & UNIT ECONOMICS ASSESSMENT")
        logger.info("="*80)
        logger.info(f"Cities: {cities}")
        logger.info(f"Max jobs per city: {max_jobs_per_city}")
        logger.info("="*80 + "\n")

        # Initialize metrics object
        self.metrics = PipelineMetrics(
            timestamp=datetime.now().isoformat(),
            cities=cities,
            max_jobs_per_city=max_jobs_per_city,
            adzuna_fetched=0,
            adzuna_fetch_time=0,
            greenhouse_fetched=0,
            greenhouse_fetch_time=0,
            merged_count=0,
            adzuna_after_merge=0,
            greenhouse_after_merge=0,
            duplicates_removed=0,
            merge_time=0,
            jobs_classified=0,
            jobs_classified_time=0,
            classification_failures=0,
            avg_classification_time=0,
            estimated_claude_calls=0,
            estimated_claude_cost=0,
            total_pipeline_cost=0,
            cost_per_unique_job=0,
            skills_extraction_rate=0,
            remote_status_detection_rate=0,
            compensation_detection_rate=0,
            jobs_stored=0,
            storage_time=0,
            storage_failures=0,
            greenhouse_preference_ratio=0,
        )

        all_adzuna_jobs = []
        all_greenhouse_jobs = []

        # Phase 1: Fetch from both sources
        logger.info("PHASE 1: FETCHING JOBS FROM SOURCES\n")

        for city in cities:
            # Adzuna fetch
            logger.info(f"Fetching from Adzuna ({city})...")
            start_time = time.time()
            try:
                from scrapers.adzuna.fetch_adzuna_jobs import fetch_adzuna_jobs as fetch_adzuna_api
                from scrapers.adzuna.fetch_adzuna_jobs import DEFAULT_SEARCH_QUERIES, LOCATION_QUERIES

                # Fetch jobs for each search query
                adzuna_jobs_for_city = []
                for search_query in DEFAULT_SEARCH_QUERIES[:3]:  # Limit to first 3 queries for speed
                    try:
                        jobs = fetch_adzuna_api(
                            city_code=city,
                            search_query=search_query,
                            results_per_page=max_jobs_per_city // 3
                        )
                        adzuna_jobs_for_city.extend(jobs)
                    except Exception as e:
                        logger.warning(f"Failed to fetch '{search_query}' for {city}: {str(e)}")
                        continue

                self.metrics.adzuna_fetched += len(adzuna_jobs_for_city)
                self.metrics.adzuna_fetch_time += time.time() - start_time

                # Convert Adzuna dicts to Job objects for ingester compatibility
                from scrapers.greenhouse.greenhouse_scraper import Job
                for adzuna_job in adzuna_jobs_for_city:
                    job_obj = Job(
                        company=adzuna_job.get("company", {}).get("display_name", "Unknown"),
                        title=adzuna_job.get("title", "Unknown"),
                        location=adzuna_job.get("location", {}).get("display_name", "Unknown"),
                        description=adzuna_job.get("description", ""),
                        job_type=adzuna_job.get("contract_type"),
                        url=adzuna_job.get("redirect_url", "")
                    )
                    all_adzuna_jobs.append(job_obj)

                logger.info(f"✓ Fetched {len(adzuna_jobs_for_city)} jobs from Adzuna\n")
            except Exception as e:
                logger.error(f"✗ Failed to fetch from Adzuna: {str(e)}\n")
                logger.error(traceback.format_exc())
                continue

        # Greenhouse fetch
        logger.info("Fetching from Greenhouse...")
        start_time = time.time()
        try:
            from scrapers.greenhouse.greenhouse_scraper import GreenhouseScraper
            scraper = GreenhouseScraper(headless=True, max_concurrent_pages=2)
            await scraper.init()
            try:
                # Load default companies
                mapping_file = Path(__file__).parent / 'config' / 'company_ats_mapping.json'
                if mapping_file.exists():
                    with open(mapping_file) as f:
                        mapping = json.load(f)
                    # Extract just the slugs (not full dict objects)
                    company_data = mapping.get('greenhouse', {})
                    # VALIDATION MODE: Use only Twilio and limit to 5 jobs for fast testing
                    # Tests: deduplication, classification, storage without long runtime
                    # Using Twilio instead of Stripe to avoid duplicate test data
                    company_slugs = ['twilio']
                    logger.info(f"Fetching from {len(company_slugs)} Greenhouse company: {', '.join(company_slugs)} (LIMITED TO 5 JOBS)")

                    # scrape_all returns dict of {slug: [jobs]}
                    greenhouse_results = await scraper.scrape_all(company_slugs)

                    # Flatten results into single list - LIMIT TO 5 JOBS TOTAL
                    job_limit = 5
                    jobs_added = 0
                    for company_slug, jobs in greenhouse_results.items():
                        for job in jobs:
                            if jobs_added >= job_limit:
                                break
                            all_greenhouse_jobs.append(job)
                            jobs_added += 1
                        if jobs_added >= job_limit:
                            break

                    self.metrics.greenhouse_fetched = len(all_greenhouse_jobs)
                    self.metrics.greenhouse_fetch_time = time.time() - start_time
                    logger.info(f"✓ Fetched {len(all_greenhouse_jobs)} jobs from Greenhouse\n")
                else:
                    logger.warning("✗ Mapping file not found\n")
            finally:
                await scraper.close()
        except Exception as e:
            logger.error(f"✗ Failed to fetch from Greenhouse: {str(e)}\n")
            logger.error(traceback.format_exc())

        # Phase 2: Merge with deduplication
        logger.info("PHASE 2: MERGING & DEDUPLICATION\n")
        start_time = time.time()

        try:
            from unified_job_ingester import UnifiedJobIngester
            ingester = UnifiedJobIngester(verbose=False)
            merged_jobs, merge_stats = await ingester.merge(
                adzuna_jobs=all_adzuna_jobs,
                greenhouse_jobs=all_greenhouse_jobs
            )

            self.metrics.merged_count = len(merged_jobs)
            self.metrics.duplicates_removed = self.metrics.adzuna_fetched + self.metrics.greenhouse_fetched - self.metrics.merged_count
            self.metrics.merge_time = time.time() - start_time

            # Count source distribution
            for job in merged_jobs:
                if hasattr(job, 'source'):
                    if job.source.value == 'adzuna':
                        self.metrics.adzuna_after_merge += 1
                    elif job.source.value == 'greenhouse':
                        self.metrics.greenhouse_after_merge += 1

            logger.info(f"✓ Merged {self.metrics.merged_count} unique jobs")
            logger.info(f"  - From Adzuna: {self.metrics.adzuna_after_merge}")
            logger.info(f"  - From Greenhouse: {self.metrics.greenhouse_after_merge}")
            logger.info(f"  - Duplicates removed: {self.metrics.duplicates_removed}")
            logger.info(f"  - Merge time: {self.metrics.merge_time:.2f}s\n")

        except Exception as e:
            logger.error(f"✗ Merge failed: {str(e)}\n")
            logger.error(traceback.format_exc())
            return asdict(self.metrics)

        # Phase 3: Classify with metrics
        logger.info("PHASE 3: CLASSIFICATION WITH METRICS\n")
        logger.info(f"Starting classification of {len(merged_jobs)} merged jobs\n")
        start_time = time.time()

        try:
            from classifier import classify_job_with_claude
            from agency_detection import detect_agency

            classified_jobs = []
            skills_count = 0
            remote_count = 0
            compensation_count = 0
            agencies_filtered = 0
            total_input_tokens = 0
            total_output_tokens = 0
            total_actual_cost = 0.0

            for i, job in enumerate(merged_jobs):
                if (i + 1) % 10 == 0:
                    logger.info(f"  Progress: {i+1}/{len(merged_jobs)}")

                # Skip agencies with detailed logging
                is_agency, agency_reason = detect_agency(job.company, job.description)
                if is_agency:
                    agencies_filtered += 1
                    if i < 10:  # Log first 10 filtered companies for visibility
                        logger.info(f"  [FILTERED AGENCY] {job.company} - {job.title[:40]} ({agency_reason})")
                    continue

                # DEBUG: Log description info for first few jobs
                if i < 5:
                    source_label = job.source.value if hasattr(job, 'source') else 'unknown'
                    logger.info(f"  [DEBUG {i+1}] {job.company} - {job.title[:40]}")
                    logger.info(f"    Source: {source_label} | Desc length: {len(job.description)} chars")

                # Classify with timing
                job_start = time.time()
                try:
                    classification = classify_job_with_claude(job.description)
                    classification_time = time.time() - job_start

                    # Extract actual cost data from classification
                    cost_data = classification.get('_cost_data', {})
                    if cost_data:
                        total_input_tokens += cost_data.get('input_tokens', 0)
                        total_output_tokens += cost_data.get('output_tokens', 0)
                        total_actual_cost += cost_data.get('total_cost', 0.0)

                    # Parse classification results
                    skills = classification.get('skills', [])
                    location = classification.get('location', {})
                    remote = location.get('working_arrangement') if location else None
                    compensation = classification.get('compensation', {})

                    if skills:
                        skills_count += 1
                    if remote:
                        remote_count += 1
                    if compensation and (compensation.get('base_salary_range') or compensation.get('currency')):
                        compensation_count += 1

                    job.classification = classification
                    classified_jobs.append(job)

                    # Store sample for quality review (first 5 of each source)
                    if len([s for s in self.classification_samples if s.source == (job.source.value if hasattr(job, 'source') else 'unknown')]) < 5:
                        self.classification_samples.append(ClassificationMetrics(
                            job_id=str(hash(job.company + job.title) % 10000),
                            company=job.company,
                            title=job.title,
                            source=job.source.value if hasattr(job, 'source') else 'unknown',
                            description_length=len(job.description),
                            classification_time=classification_time,
                            classification_success=True,
                            skills_extracted_count=len(skills),
                            remote_status_detected=bool(remote),
                            compensation_detected=bool(compensation),
                        ))

                except Exception as e:
                    # Detailed error logging for debugging
                    import traceback
                    self.metrics.classification_failures += 1
                    source_label = job.source.value if hasattr(job, 'source') else 'unknown'
                    logger.error(f"  [FAILED] {job.company} - {job.title[:40]}")
                    logger.error(f"    Source: {source_label}")
                    logger.error(f"    Description length: {len(job.description)} chars")
                    logger.error(f"    Error type: {type(e).__name__}")
                    logger.error(f"    Error message: {str(e)[:200]}")
                    logger.error(f"    Full traceback:")
                    for line in traceback.format_exc().split('\n'):
                        if line.strip():
                            logger.error(f"      {line}")
                    if len(job.description) > 0:
                        # Escape % symbols to prevent string formatting errors
                        preview = job.description[:100].replace('%', '%%')
                        logger.error(f"    Description preview: {preview}...")
                    continue

            self.metrics.jobs_classified = len(classified_jobs)
            self.metrics.jobs_classified_time = time.time() - start_time
            self.metrics.avg_classification_time = self.metrics.jobs_classified_time / max(self.metrics.jobs_classified, 1)

            # Calculate quality metrics
            self.metrics.skills_extraction_rate = (skills_count / max(self.metrics.jobs_classified, 1)) * 100
            self.metrics.remote_status_detection_rate = (remote_count / max(self.metrics.jobs_classified, 1)) * 100
            self.metrics.compensation_detection_rate = (compensation_count / max(self.metrics.jobs_classified, 1)) * 100

            logger.info(f"✓ Classified {self.metrics.jobs_classified} jobs")
            logger.info(f"  - Filtered as agencies: {agencies_filtered}")
            logger.info(f"  - Remaining after filtering: {len(merged_jobs) - agencies_filtered}")
            logger.info(f"  - Classification time: {self.metrics.jobs_classified_time:.2f}s")
            logger.info(f"  - Avg time per job: {self.metrics.avg_classification_time:.3f}s")
            logger.info(f"  - Failures: {self.metrics.classification_failures}")
            logger.info(f"  - Skills extraction rate: {self.metrics.skills_extraction_rate:.1f}%%")
            logger.info(f"  - Remote status detection: {self.metrics.remote_status_detection_rate:.1f}%%")
            logger.info(f"  - Compensation detection: {self.metrics.compensation_detection_rate:.1f}%%\n")

        except Exception as e:
            logger.error(f"✗ Classification failed: {str(e)}\n")
            logger.error(traceback.format_exc())
            return asdict(self.metrics)

        # Phase 4: Cost analysis
        logger.info("PHASE 4: COST ANALYSIS\n")

        # Use actual costs from API if available, otherwise fall back to estimates
        if total_actual_cost > 0:
            actual_cost_per_job = total_actual_cost / max(self.metrics.jobs_classified, 1)
            self.metrics.estimated_claude_calls = self.metrics.jobs_classified
            self.metrics.estimated_claude_cost = total_actual_cost
            self.metrics.cost_per_unique_job = total_actual_cost / max(self.metrics.merged_count, 1)

            logger.info(f"ACTUAL token usage from API:")
            logger.info(f"  - Total input tokens: {total_input_tokens:,}")
            logger.info(f"  - Total output tokens: {total_output_tokens:,}")
            logger.info(f"  - Avg input tokens per job: {total_input_tokens / max(self.metrics.jobs_classified, 1):.0f}")
            logger.info(f"  - Avg output tokens per job: {total_output_tokens / max(self.metrics.jobs_classified, 1):.0f}")
            logger.info(f"Cost per classification (actual): ${actual_cost_per_job:.6f}")
            logger.info(f"Total Claude cost for {self.metrics.jobs_classified} jobs: ${total_actual_cost:.4f}")
            logger.info(f"Cost per unique merged job: ${self.metrics.cost_per_unique_job:.6f}")
            logger.info(f"Estimated monthly cost (1,500 jobs): ${(1500 * self.metrics.cost_per_unique_job):.2f}\n")
        else:
            # Fall back to estimates if no actual data
            cost_per_job = self.estimate_classification_cost()
            self.metrics.estimated_claude_calls = self.metrics.jobs_classified
            self.metrics.estimated_claude_cost = self.metrics.jobs_classified * cost_per_job
            self.metrics.cost_per_unique_job = self.metrics.estimated_claude_cost / max(self.metrics.merged_count, 1)

            logger.info(f"Cost per classification (estimated): ${cost_per_job:.6f}")
            logger.info(f"Total Claude cost for {self.metrics.jobs_classified} jobs: ${self.metrics.estimated_claude_cost:.2f}")
            logger.info(f"Cost per unique merged job: ${self.metrics.cost_per_unique_job:.6f}")
            logger.info(f"Estimated monthly cost (1,500 jobs): ${(1500 * self.metrics.cost_per_unique_job):.2f}\n")

        # Phase 5: Storage (E2E validation)
        logger.info("PHASE 5: DATABASE STORAGE (E2E VALIDATION)\n")
        logger.info("Storing classified jobs in Supabase...\n")
        start_time = time.time()

        try:
            from db_connection import insert_raw_job, insert_enriched_job
            from datetime import date

            for job in classified_jobs:
                try:
                    # Store raw job
                    source_value = job.source.value if hasattr(job, 'source') else 'unknown'
                    raw_job_id = insert_raw_job(
                        source=source_value,
                        posting_url=job.url or '',
                        raw_text=job.description
                    )

                    # Store enriched job (with classification)
                    if raw_job_id and job.classification:
                        classification = job.classification
                        role = classification.get('role', {})
                        location = classification.get('location', {})
                        employer = classification.get('employer', {})
                        compensation = classification.get('compensation', {})

                        # Get city_code with fallback to 'unknown' if missing or None
                        city_code = location.get('city_code') or 'unknown'

                        enriched_job_id = insert_enriched_job(
                            raw_job_id=raw_job_id,
                            employer_name=employer.get('name', job.company),
                            title_display=role.get('title_display', job.title),
                            job_family=role.get('job_family', 'out_of_scope'),
                            city_code=city_code,
                            working_arrangement=location.get('working_arrangement', 'onsite'),
                            position_type=role.get('position_type', 'full_time'),
                            posted_date=date.today(),
                            last_seen_date=date.today(),
                            # Optional fields
                            job_subfamily=role.get('job_subfamily'),
                            track=role.get('track'),
                            seniority=role.get('seniority'),
                            experience_range=role.get('experience_range'),
                            employer_department=employer.get('department'),
                            employer_size=employer.get('company_size_estimate'),
                            is_agency=employer.get('is_agency'),
                            agency_confidence=employer.get('agency_confidence'),
                            currency=compensation.get('currency')
                        )
                        if enriched_job_id:
                            self.metrics.jobs_stored += 1

                except Exception as e:
                    logger.error(f"  Storage failed for {job.company} - {job.title[:40]}: {str(e)[:100]}")
                    self.metrics.storage_failures += 1
                    continue

            self.metrics.storage_time = time.time() - start_time

            logger.info(f"✓ Stored {self.metrics.jobs_stored} jobs in Supabase")
            logger.info(f"  - Storage time: {self.metrics.storage_time:.2f}s")
            logger.info(f"  - Storage failures: {self.metrics.storage_failures}\n")

        except Exception as e:
            logger.error(f"✗ Storage phase failed: {str(e)}\n")
            logger.error(traceback.format_exc())

        # Phase 6: Deduplication analysis
        logger.info("PHASE 6: DEDUPLICATION & SOURCE QUALITY ANALYSIS\n")

        greenhouse_preference = self.metrics.greenhouse_after_merge
        if self.metrics.merged_count > 0:
            self.metrics.greenhouse_preference_ratio = (greenhouse_preference / self.metrics.merged_count) * 100

        logger.info(f"Greenhouse jobs in final merged set: {self.metrics.greenhouse_after_merge} ({self.metrics.greenhouse_preference_ratio:.1f}%%)")
        logger.info(f"Adzuna jobs in final merged set: {self.metrics.adzuna_after_merge} ({100-self.metrics.greenhouse_preference_ratio:.1f}%%)")
        logger.info(f"Deduplication efficiency: {(self.metrics.duplicates_removed / max(self.metrics.adzuna_fetched + self.metrics.greenhouse_fetched, 1)) * 100:.1f}%%\n")

        logger.info("="*80)
        logger.info("VALIDATION COMPLETE")
        logger.info("="*80 + "\n")

        return asdict(self.metrics)

    def save_metrics(self, output_file: str = "validation_metrics.json"):
        """Save metrics to file"""
        data = {
            'metrics': asdict(self.metrics),
            'classification_samples': [asdict(s) for s in self.classification_samples],
        }

        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Metrics saved to {output_file}")


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Validate dual pipeline with comprehensive metrics'
    )
    parser.add_argument(
        '--cities',
        default='lon,nyc',
        help='Comma-separated cities to test. Default: lon,nyc'
    )
    parser.add_argument(
        '--max-jobs',
        type=int,
        default=100,
        help='Max jobs per city from Adzuna. Default: 100'
    )
    parser.add_argument(
        '--output-file',
        default='validation_metrics.json',
        help='Output file for metrics. Default: validation_metrics.json'
    )

    args = parser.parse_args()

    validator = PipelineValidator()
    cities = [c.strip() for c in args.cities.split(',')]

    await validator.run_validation(cities, args.max_jobs)
    validator.save_metrics(args.output_file)


if __name__ == "__main__":
    asyncio.run(main())
