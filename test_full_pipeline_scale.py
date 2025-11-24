"""
Full-Scale Pipeline Test: Dual Source (Adzuna + Greenhouse)
==============================================================

Tests the complete pipeline at meaningful scale with fast-mode error handling:
- Fetches: 50-75 Adzuna jobs + 2-3 Greenhouse companies (~50-100 jobs)
- Merges: Deduplicates by (company + title + location)
- Classifies: Using Claude 3.5 Haiku
- Stores: Inserts into raw_jobs and enriched_jobs tables
- Error Handling: Fast-mode (fail fast per job, keep pipeline running)
- Metrics: Comprehensive collection for pipeline validation

Expected Duration: 30-45 minutes
Expected Cost: $0.15-0.25 (100-150 classifications)
"""

import json
import time
from datetime import date, datetime
from typing import Dict, List, Tuple
import traceback

# Import pipeline components
import asyncio
from scrapers.adzuna.fetch_adzuna_jobs import fetch_adzuna_jobs
from scrapers.greenhouse.greenhouse_scraper import GreenhouseScraper, Job as GreenhouseJob
from unified_job_ingester import UnifiedJobIngester
from classifier import classify_job_with_claude
from db_connection import insert_raw_job, insert_enriched_job, test_connection


# ============================================
# Configuration
# ============================================

ADZUNA_CONFIG = {
    'city': 'lon',
    'max_jobs': 75,
    'description': 'London market data'
}

GREENHOUSE_CONFIG = {
    'companies': ['stripe', 'figma'],  # 2 verified companies, ~200 jobs total
    'description': 'Premium tech companies (verified Greenhouse users)'
}

# ============================================
# Helper Functions
# ============================================

def convert_adzuna_to_job(adzuna_dict: Dict) -> GreenhouseJob:
    """Convert Adzuna unified format dict to GreenhouseJob dataclass"""
    return GreenhouseJob(
        company=adzuna_dict.get('company', 'Unknown'),
        title=adzuna_dict.get('title', 'Unknown'),
        location=adzuna_dict.get('location', 'Unknown'),
        description=adzuna_dict.get('description', ''),
        url=adzuna_dict.get('url', ''),
        job_id=adzuna_dict.get('job_id'),
        department=None,
        job_type=None
    )


# ============================================
# Error Tracking (Fast Mode)
# ============================================

class ErrorTracker:
    """Track errors by stage and category for detailed reporting"""

    def __init__(self):
        self.errors = {
            'adzuna_fetch': [],
            'greenhouse_scrape': [],
            'merge': [],
            'classification': [],
            'database_insert': []
        }
        self.job_errors = {}  # job_id -> [list of errors]

    def add_error(self, stage: str, error_obj: Dict):
        """Add error with stage and details"""
        self.errors[stage].append(error_obj)

    def add_job_error(self, job_id: str, stage: str, error_msg: str):
        """Track error for specific job"""
        if job_id not in self.job_errors:
            self.job_errors[job_id] = []
        self.job_errors[job_id].append({
            'stage': stage,
            'error': error_msg[:200]  # Truncate long errors
        })

    def summary(self) -> Dict:
        """Return error summary for reporting"""
        total_errors = sum(len(v) for v in self.errors.values())
        return {
            'total_errors': total_errors,
            'by_stage': {k: len(v) for k, v in self.errors.items()},
            'affected_jobs': len(self.job_errors),
            'jobs_with_errors': list(self.job_errors.keys())[:10]  # First 10
        }


# ============================================
# Phase 1: Fetch from Adzuna API
# ============================================

def fetch_adzuna_phase(tracker: ErrorTracker) -> Tuple[List[Dict], float]:
    """Fetch Adzuna jobs with error handling - uses multiple search queries"""

    print("\n" + "=" * 80)
    print("[PHASE 1] FETCHING FROM ADZUNA API")
    print("=" * 80)

    start_time = time.time()
    adzuna_jobs_all = []

    # Search queries to get reasonable coverage
    search_queries = [
        "Data Engineer",
        "Data Scientist",
        "Machine Learning Engineer"
    ]

    try:
        print(f"\n[INFO] Fetching from {ADZUNA_CONFIG['city'].upper()} via {len(search_queries)} queries")
        print(f"[INFO] Queries: {', '.join(search_queries)}")
        print(f"[INFO] Expected: ~9-18 jobs per query (varies by market)")

        for query in search_queries:
            print(f"\n  [QUERY] Fetching: '{query}'...")

            # Fetch Adzuna API result (returns raw format from API)
            adzuna_raw = fetch_adzuna_jobs(
                city_code=ADZUNA_CONFIG['city'],
                search_query=query,
                results_per_page=10
            )

            # Convert Adzuna format to unified format
            for job_data in adzuna_raw:
                unified_job = {
                    'company': job_data.get('company', {}).get('display_name', 'Unknown'),
                    'title': job_data.get('title', 'Unknown'),
                    'location': job_data.get('location', {}).get('display_name', 'Unknown'),
                    'description': job_data.get('description', ''),
                    'url': job_data.get('redirect_url', ''),
                    'job_id': str(job_data.get('id', '')),
                    'source': 'adzuna',
                    'metadata': job_data
                }
                adzuna_jobs_all.append(unified_job)

            print(f"    [OK] Got {len(adzuna_raw)} jobs from this query")

        elapsed = time.time() - start_time
        print(f"\n[SUMMARY] Total Adzuna jobs: {len(adzuna_jobs_all)} in {elapsed:.2f}s")

        # Show sample
        if adzuna_jobs_all:
            sample = adzuna_jobs_all[0]
            print(f"\n[SAMPLE] First Adzuna job:")
            print(f"  Company: {sample.get('company', 'N/A')}")
            print(f"  Title: {sample.get('title', 'N/A')[:50]}...")
            print(f"  Description length: {len(sample.get('description', ''))} chars")

        return adzuna_jobs_all, elapsed

    except Exception as e:
        elapsed = time.time() - start_time
        error_msg = f"Adzuna fetch failed: {str(e)}"
        print(f"[ERROR] {error_msg}")
        tracker.add_error('adzuna_fetch', {
            'error': str(e)[:200],
            'elapsed': elapsed
        })
        traceback.print_exc()
        return [], elapsed


# ============================================
# Phase 2: Scrape from Greenhouse
# ============================================

async def fetch_greenhouse_phase_async(tracker: ErrorTracker) -> Tuple[List[Dict], float]:
    """Scrape Greenhouse jobs with per-company error handling (fast mode)"""

    print("\n" + "=" * 80)
    print("[PHASE 2] SCRAPING FROM GREENHOUSE")
    print("=" * 80)

    start_time = time.time()
    greenhouse_jobs = []

    companies = GREENHOUSE_CONFIG['companies']
    print(f"\n[INFO] Scraping {len(companies)} companies: {', '.join(companies)}")
    print(f"[INFO] Expected: ~15-35 jobs per company (varies by company size)")

    try:
        scraper = GreenhouseScraper(headless=True, max_concurrent_pages=2)

        print(f"\n[COMPANY] Initializing scraper...")
        await scraper.init()

        print(f"[COMPANY] Scraping {len(companies)} companies: {', '.join(companies)}")

        # Scrape all companies at once using asyncio
        # NOTE: scrape_all returns Dict[company_slug -> List[Job]], not flat list
        company_jobs_dict = await scraper.scrape_all(companies)

        await scraper.close()

        company_elapsed = time.time() - start_time

        # Flatten dict to single list and report per-company results
        total_jobs_found = 0
        for company, jobs in company_jobs_dict.items():
            job_count = len(jobs) if jobs else 0
            total_jobs_found += job_count
            status = "[OK]" if job_count > 0 else "[EMPTY]"
            print(f"  {status} {company.upper()}: {job_count} jobs")

            # Keep Job objects as-is for merge phase (convert to dicts later)
            if jobs:
                greenhouse_jobs.extend(jobs)

        print(f"\n  [OK] Total scraped: {total_jobs_found} jobs in {company_elapsed:.2f}s")

        if greenhouse_jobs:
            sample = greenhouse_jobs[0]
            desc_len = len(sample.get('description', '') if isinstance(sample, dict) else '')
            title = sample.get('title', 'N/A') if isinstance(sample, dict) else 'N/A'
            print(f"  [SAMPLE] First job: {title[:40]}... ({desc_len} chars)")

    except Exception as e:
        elapsed = time.time() - start_time
        error_msg = f"Greenhouse scrape failed: {str(e)[:100]}"
        print(f"  [ERROR] {error_msg}")
        tracker.add_error('greenhouse_scrape', {
            'error': str(e)[:200],
            'elapsed': elapsed
        })
        traceback.print_exc()
        return [], elapsed

    elapsed = time.time() - start_time
    print(f"\n[SUMMARY] Total Greenhouse jobs: {len(greenhouse_jobs)} in {elapsed:.2f}s")

    return greenhouse_jobs, elapsed


# ============================================
# Phase 3: Merge and Deduplicate
# ============================================

async def merge_phase(adzuna_jobs: List[Dict], greenhouse_jobs: List[Dict], tracker: ErrorTracker) -> Tuple[List[Dict], Dict, float]:
    """Merge both sources and deduplicate"""

    print("\n" + "=" * 80)
    print("[PHASE 3] MERGE & DEDUPLICATION")
    print("=" * 80)

    start_time = time.time()

    try:
        print(f"\n[INFO] Merging {len(adzuna_jobs)} Adzuna + {len(greenhouse_jobs)} Greenhouse jobs")

        # Convert Adzuna dicts to Job objects for merge compatibility
        adzuna_job_objects = [convert_adzuna_to_job(job) for job in adzuna_jobs]

        # Ensure greenhouse_jobs are Job objects (not dicts or other types)
        greenhouse_job_objects = []
        for job in greenhouse_jobs:
            if isinstance(job, dict):
                # If somehow we have a dict, convert it to Job object
                greenhouse_job_objects.append(convert_adzuna_to_job(job))
            else:
                # Already a Job object
                greenhouse_job_objects.append(job)

        print(f"  [DEBUG] Adzuna: {len(adzuna_job_objects)} objects, Greenhouse: {len(greenhouse_job_objects)} objects")

        ingester = UnifiedJobIngester(verbose=False)
        merged_jobs, merge_stats = await ingester.merge(adzuna_job_objects, greenhouse_job_objects)

        elapsed = time.time() - start_time

        # Convert UnifiedJob objects to dicts for downstream processing
        merged_dicts = []
        for job in merged_jobs:
            if hasattr(job, 'to_dict'):
                # UnifiedJob objects have to_dict() method
                job_dict = job.to_dict()
            else:
                # Fallback for other types
                job_dict = {
                    'company': getattr(job, 'company', ''),
                    'title': getattr(job, 'title', ''),
                    'location': getattr(job, 'location', ''),
                    'description': getattr(job, 'description', ''),
                    'url': getattr(job, 'url', ''),
                    'job_id': getattr(job, 'job_id', ''),
                    'source': 'unknown'
                }
            merged_dicts.append(job_dict)

        # Create dedup stats
        duplicates_found = len(adzuna_jobs) + len(greenhouse_jobs) - len(merged_jobs)
        greenhouse_count = sum(1 for j in merged_jobs if hasattr(j, 'description_source') and hasattr(j.description_source, 'value') and j.description_source.value == 'greenhouse')

        dedup_stats = {
            'duplicates_found': duplicates_found,
            'greenhouse_preference': greenhouse_count,
            'merge_stats': merge_stats
        }

        print(f"\n[OK] Merge complete in {elapsed:.2f}s")
        print(f"  Total before dedup: {len(adzuna_jobs) + len(greenhouse_jobs)}")
        print(f"  Total after dedup: {len(merged_jobs)}")
        print(f"  Duplicates found: {duplicates_found}")
        print(f"  Greenhouse-sourced: {greenhouse_count} jobs")

        return merged_dicts, dedup_stats, elapsed

    except Exception as e:
        elapsed = time.time() - start_time
        error_msg = f"Merge failed: {str(e)}"
        print(f"[ERROR] {error_msg}")
        tracker.add_error('merge', {
            'error': str(e)[:200],
            'elapsed': elapsed
        })
        traceback.print_exc()
        return [], {}, elapsed


# ============================================
# Phase 4: Classification (with per-job error handling)
# ============================================

def classify_phase(jobs: List[Dict], tracker: ErrorTracker) -> Tuple[List[Dict], float]:
    """Classify jobs with fast-mode error handling (fail fast per job)"""

    print("\n" + "=" * 80)
    print("[PHASE 4] JOB CLASSIFICATION")
    print("=" * 80)

    start_time = time.time()
    classified_jobs = []

    print(f"\n[INFO] Classifying {len(jobs)} jobs (expecting ~3.3s per job)")
    print(f"[INFO] Estimated time: {len(jobs) * 3.3 / 60:.1f} minutes")
    print(f"[INFO] Fast-mode: Skipping failed jobs, continuing with rest\n")

    for i, job in enumerate(jobs, 1):
        job_start = time.time()
        job_id = f"{job.get('employer', 'unknown')}_{job.get('title', 'unknown')}_{i}"

        try:
            # Show progress
            if i % 5 == 1:
                print(f"[Progress] Classifying job {i}/{len(jobs)}...")

            classification = classify_job_with_claude(job.get('description', ''))

            job_elapsed = time.time() - job_start

            # Combine original job data with classification
            enriched = {
                **job,
                'classification': classification,
                'classification_time': job_elapsed,
                'source': job.get('source', 'unknown')
            }

            classified_jobs.append(enriched)

        except Exception as e:
            job_elapsed = time.time() - job_start
            error_msg = f"Classification failed: {str(e)[:100]}"
            print(f"  [JOB {i}] [ERROR] {job.get('title', 'Unknown')[:40]}... ({error_msg})")

            tracker.add_job_error(job_id, 'classification', str(e)[:150])
            tracker.add_error('classification', {
                'job': job_id,
                'error': str(e)[:200],
                'elapsed': job_elapsed
            })
            # Fast mode: continue with next job
            continue

    elapsed = time.time() - start_time

    print(f"\n[SUMMARY] Classification complete")
    print(f"  Successfully classified: {len(classified_jobs)}/{len(jobs)}")
    print(f"  Failed: {len(jobs) - len(classified_jobs)}")
    print(f"  Total time: {elapsed:.2f}s ({elapsed/60:.1f} minutes)")
    print(f"  Avg per job: {elapsed/len(classified_jobs):.2f}s" if classified_jobs else "  Avg per job: N/A")

    return classified_jobs, elapsed


# ============================================
# Phase 5: Database Insertion (with per-job error handling)
# ============================================

def insert_phase(classified_jobs: List[Dict], tracker: ErrorTracker) -> Tuple[int, int, float]:
    """Insert jobs into database with fast-mode error handling"""

    print("\n" + "=" * 80)
    print("[PHASE 5] DATABASE INSERTION")
    print("=" * 80)

    start_time = time.time()

    inserted_raw = 0
    inserted_enriched = 0

    print(f"\n[INFO] Inserting {len(classified_jobs)} jobs into Supabase")
    print(f"[INFO] Fast-mode: Skipping failed jobs, continuing with rest\n")

    for i, job in enumerate(classified_jobs, 1):
        job_id = f"{job.get('company', 'unknown')}_{job.get('title', 'unknown')}"

        try:
            # Step 1: Insert raw job
            raw_job_id = insert_raw_job(
                source=job.get('source', 'unknown'),
                posting_url=job.get('url', ''),
                raw_text=job.get('description', ''),
                source_job_id=job.get('job_id'),
                metadata=job.get('metadata', {})
            )
            inserted_raw += 1

            # Step 2: Extract classification data
            classification = job.get('classification', {})
            role = classification.get('role', {})
            location = classification.get('location', {})
            compensation = classification.get('compensation', {})

            # Step 3: Insert enriched job
            enriched_job_id = insert_enriched_job(
                raw_job_id=raw_job_id,
                employer_name=job.get('company', 'Unknown'),
                title_display=job.get('title', 'Unknown'),
                job_family=role.get('job_family') or 'out_of_scope',
                city_code=location.get('city_code') or 'lon',
                working_arrangement=location.get('working_arrangement') or 'onsite',
                position_type=role.get('position_type') or 'full_time',
                posted_date=date.today(),
                last_seen_date=date.today(),
                # Optional fields
                job_subfamily=role.get('job_subfamily'),
                title_canonical=role.get('title_canonical'),
                track=role.get('track'),
                seniority=role.get('seniority'),
                experience_range=role.get('experience_range'),
                currency=compensation.get('currency'),
                salary_min=compensation.get('base_salary_range', {}).get('min'),
                salary_max=compensation.get('base_salary_range', {}).get('max'),
                equity_eligible=compensation.get('equity_eligible'),
                skills=classification.get('skills', []),
                # Dual pipeline tracking
                data_source=job.get('source', 'unknown'),
                description_source=f"{job.get('source', 'unknown')}_scraper",
                deduplicated=job.get('deduplicated', False)
            )
            inserted_enriched += 1

            if i % 5 == 1 or i == 1:
                print(f"  [Job {i}/{len(classified_jobs)}] [OK] {job.get('title', 'Unknown')[:40]}... (raw_id: {raw_job_id}, enriched_id: {enriched_job_id})")

        except Exception as e:
            error_msg = f"Database insert failed: {str(e)[:100]}"
            print(f"  [Job {i}] [ERROR] {job.get('title', 'Unknown')[:40]}... ({error_msg})")

            tracker.add_job_error(job_id, 'database_insert', str(e)[:150])
            tracker.add_error('database_insert', {
                'job': job_id,
                'error': str(e)[:200]
            })
            # Fast mode: continue with next job
            continue

    elapsed = time.time() - start_time

    print(f"\n[SUMMARY] Database insertion complete")
    print(f"  Raw jobs inserted: {inserted_raw}/{len(classified_jobs)}")
    print(f"  Enriched jobs inserted: {inserted_enriched}/{len(classified_jobs)}")
    print(f"  Total time: {elapsed:.2f}s")

    return inserted_raw, inserted_enriched, elapsed


# ============================================
# Metrics Calculation
# ============================================

def calculate_metrics(
    adzuna_jobs: List[Dict],
    greenhouse_jobs: List[Dict],
    merged_jobs: List[Dict],
    classified_jobs: List[Dict],
    inserted_raw: int,
    inserted_enriched: int,
    dedup_stats: Dict,
    phase_times: Dict,
    tracker: ErrorTracker
) -> Dict:
    """Calculate comprehensive metrics for pipeline validation"""

    total_fetched = len(adzuna_jobs) + len(greenhouse_jobs)

    # Skills extraction analysis
    skills_found = 0
    for job in classified_jobs:
        if job.get('classification', {}).get('skills'):
            skills_found += 1

    # Seniority detection analysis
    seniority_found = 0
    for job in classified_jobs:
        if job.get('classification', {}).get('role', {}).get('seniority'):
            seniority_found += 1

    # Calculate average description lengths by source
    adzuna_desc_lens = [len(j.get('description', '')) for j in adzuna_jobs]
    greenhouse_desc_lens = [len(j.get('description', '')) for j in greenhouse_jobs]

    avg_adzuna_len = sum(adzuna_desc_lens) / len(adzuna_desc_lens) if adzuna_desc_lens else 0
    avg_greenhouse_len = sum(greenhouse_desc_lens) / len(greenhouse_desc_lens) if greenhouse_desc_lens else 0

    # Cost calculation (Claude 3.5 Haiku: $0.80/1M input tokens, ~300 tokens per job)
    estimated_cost = len(classified_jobs) * 0.00168  # Empirically measured cost per job

    # Total pipeline time
    total_time = sum(phase_times.values())

    metrics = {
        'timestamp': datetime.now().isoformat(),
        'test_config': {
            'adzuna': ADZUNA_CONFIG,
            'greenhouse': GREENHOUSE_CONFIG
        },
        'data_volume': {
            'adzuna_fetched': len(adzuna_jobs),
            'greenhouse_fetched': len(greenhouse_jobs),
            'total_fetched': total_fetched,
            'merged_count': len(merged_jobs),
            'after_dedup': len(merged_jobs),
            'classified': len(classified_jobs),
            'inserted_raw': inserted_raw,
            'inserted_enriched': inserted_enriched
        },
        'deduplication': {
            'duplicates_found': dedup_stats.get('duplicates_found', 0),
            'greenhouse_preferred': dedup_stats.get('greenhouse_preference', 0),
            'dedup_efficiency': (dedup_stats.get('duplicates_found', 0) / total_fetched * 100) if total_fetched > 0 else 0
        },
        'description_quality': {
            'adzuna_avg_length': round(avg_adzuna_len, 0),
            'greenhouse_avg_length': round(avg_greenhouse_len, 0),
            'length_improvement_ratio': round(avg_greenhouse_len / avg_adzuna_len, 1) if avg_adzuna_len > 0 else 0
        },
        'extraction_quality': {
            'skills_extraction_rate': (skills_found / len(classified_jobs) * 100) if classified_jobs else 0,
            'seniority_detection_rate': (seniority_found / len(classified_jobs) * 100) if classified_jobs else 0,
            'jobs_with_skills': skills_found,
            'jobs_with_seniority': seniority_found
        },
        'performance': {
            'phase_times': phase_times,
            'total_time_seconds': total_time,
            'total_time_minutes': round(total_time / 60, 2),
            'avg_classification_time': (sum(j.get('classification_time', 0) for j in classified_jobs) / len(classified_jobs)) if classified_jobs else 0
        },
        'economics': {
            'estimated_claude_calls': len(classified_jobs),
            'estimated_cost': round(estimated_cost, 4),
            'cost_per_unique_job': round(estimated_cost / max(len(merged_jobs), 1), 6)
        },
        'reliability': {
            'classification_success_rate': (len(classified_jobs) / total_fetched * 100) if total_fetched > 0 else 0,
            'insertion_success_rate': (inserted_enriched / len(classified_jobs) * 100) if classified_jobs else 0,
            'errors': tracker.summary()
        }
    }

    return metrics


# ============================================
# Main Test Orchestration
# ============================================

async def run_full_pipeline_test():
    """Execute full pipeline test with all phases"""

    print("\n")
    print("=" * 80)
    print("FULL-SCALE PIPELINE TEST: ADZUNA + GREENHOUSE")
    print("=" * 80)
    print(f"\nStarted: {datetime.now().isoformat()}")
    print(f"Scope: {ADZUNA_CONFIG['max_jobs']} Adzuna + {len(GREENHOUSE_CONFIG['companies'])} Greenhouse companies")
    print(f"Expected: ~100-175 total jobs, 30-45 min duration, $0.15-0.25 cost")
    print(f"Error Handling: Fast-mode (fail fast per job, keep pipeline running)")

    # Initialize tracking
    tracker = ErrorTracker()
    phase_times = {}

    # Test database connection first
    print("\n[PRE-CHECK] Testing Supabase connection...")
    if not test_connection():
        print("[ERROR] Cannot connect to Supabase. Check .env credentials.")
        return

    # Phase 1: Fetch Adzuna
    adzuna_jobs, phase_times['fetch_adzuna'] = fetch_adzuna_phase(tracker)

    # Phase 2: Scrape Greenhouse
    greenhouse_jobs, phase_times['scrape_greenhouse'] = await fetch_greenhouse_phase_async(tracker)

    # Phase 3: Merge & Deduplicate
    merged_jobs, dedup_stats, phase_times['merge'] = await merge_phase(adzuna_jobs, greenhouse_jobs, tracker)

    # Stop if nothing to process
    if not merged_jobs:
        print("\n[ERROR] No jobs to process after merge. Check fetch phases.")
        return

    # Phase 4: Classify
    classified_jobs, phase_times['classify'] = classify_phase(merged_jobs, tracker)

    # Stop if nothing classified
    if not classified_jobs:
        print("\n[ERROR] No jobs classified. Check classification phase.")
        return

    # Phase 5: Insert to Database
    inserted_raw, inserted_enriched, phase_times['insert'] = insert_phase(classified_jobs, tracker)

    # Calculate metrics
    metrics = calculate_metrics(
        adzuna_jobs, greenhouse_jobs, merged_jobs, classified_jobs,
        inserted_raw, inserted_enriched, dedup_stats, phase_times, tracker
    )

    # ============================================
    # Final Report
    # ============================================

    print("\n" + "=" * 80)
    print("FINAL REPORT")
    print("=" * 80)

    print(f"\n[DATA VOLUME]")
    print(f"  Adzuna fetched: {metrics['data_volume']['adzuna_fetched']}")
    print(f"  Greenhouse fetched: {metrics['data_volume']['greenhouse_fetched']}")
    print(f"  Total before merge: {metrics['data_volume']['total_fetched']}")
    print(f"  After dedup: {metrics['data_volume']['merged_count']}")
    print(f"  Successfully classified: {metrics['data_volume']['classified']}")
    print(f"  Inserted (raw): {metrics['data_volume']['inserted_raw']}")
    print(f"  Inserted (enriched): {metrics['data_volume']['inserted_enriched']}")

    print(f"\n[DEDUPLICATION]")
    print(f"  Duplicates found: {metrics['deduplication']['duplicates_found']}")
    print(f"  Efficiency: {metrics['deduplication']['dedup_efficiency']:.1f}%")
    print(f"  Greenhouse preferred: {metrics['deduplication']['greenhouse_preferred']}")

    print(f"\n[TEXT QUALITY]")
    print(f"  Adzuna avg: {metrics['description_quality']['adzuna_avg_length']:.0f} chars")
    print(f"  Greenhouse avg: {metrics['description_quality']['greenhouse_avg_length']:.0f} chars")
    print(f"  Improvement ratio: {metrics['description_quality']['length_improvement_ratio']:.1f}x")

    print(f"\n[EXTRACTION QUALITY]")
    print(f"  Skills extraction: {metrics['extraction_quality']['skills_extraction_rate']:.1f}%")
    print(f"  Seniority detection: {metrics['extraction_quality']['seniority_detection_rate']:.1f}%")

    print(f"\n[PERFORMANCE]")
    print(f"  Adzuna fetch: {phase_times['fetch_adzuna']:.2f}s")
    print(f"  Greenhouse scrape: {phase_times['scrape_greenhouse']:.2f}s")
    print(f"  Merge: {phase_times['merge']:.2f}s")
    print(f"  Classification: {phase_times['classify']:.2f}s ({metrics['performance']['avg_classification_time']:.2f}s/job)")
    print(f"  Database insert: {phase_times['insert']:.2f}s")
    print(f"  TOTAL: {metrics['performance']['total_time_minutes']:.1f} minutes")

    print(f"\n[ECONOMICS]")
    print(f"  Claude calls: {metrics['economics']['estimated_claude_calls']}")
    print(f"  Estimated cost: ${metrics['economics']['estimated_cost']:.4f}")
    print(f"  Cost per unique job: ${metrics['economics']['cost_per_unique_job']:.6f}")

    print(f"\n[RELIABILITY]")
    print(f"  Classification success: {metrics['reliability']['classification_success_rate']:.1f}%")
    print(f"  Insertion success: {metrics['reliability']['insertion_success_rate']:.1f}%")
    error_summary = metrics['reliability']['errors']
    print(f"  Total errors: {error_summary['total_errors']}")
    if error_summary['total_errors'] > 0:
        print(f"  Errors by stage: {error_summary['by_stage']}")
        print(f"  Jobs affected: {error_summary['affected_jobs']}")

    # Save detailed metrics
    metrics_file = 'validation_metrics_full_pipeline.json'
    with open(metrics_file, 'w') as f:
        json.dump(metrics, f, indent=2)

    print(f"\n[OK] Detailed metrics saved to: {metrics_file}")

    print("\n" + "=" * 80)
    print(f"Completed: {datetime.now().isoformat()}")
    print("=" * 80 + "\n")

    return metrics


# ============================================
# Entry Point
# ============================================

if __name__ == "__main__":
    try:
        metrics = asyncio.run(run_full_pipeline_test())
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Pipeline test cancelled by user")
    except Exception as e:
        print(f"\n[FATAL ERROR] Pipeline test failed: {e}")
        traceback.print_exc()
