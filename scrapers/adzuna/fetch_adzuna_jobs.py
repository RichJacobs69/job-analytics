"""
ADZUNA JOB FETCHER - WITH AGENCY DETECTION

PURPOSE:
This script fetches job postings from Adzuna API, classifies them using Claude,
and stores the results in Supabase. It includes both hard filtering (pre-classification)
and soft flagging (post-classification) of recruitment agencies.

AGENCY DETECTION:
1. Hard filter: Blocks known agencies BEFORE classification (saves API costs)
2. Soft detection: Flags agencies AFTER classification using pattern matching
"""

import yaml
import os
import time
import requests
from datetime import date, datetime
from dotenv import load_dotenv
from db_connection import insert_raw_job, insert_enriched_job, supabase
from classifier import classify_job_with_claude  # Uses v2 - no agency detection in prompt
from agency_detection import validate_agency_classification  # ← NEW IMPORT

# Load environment variables
load_dotenv()

# ============================================
# CONFIGURATION
# ============================================

ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_API_KEY = os.getenv("ADZUNA_API_KEY")

if not ADZUNA_APP_ID or not ADZUNA_API_KEY:
    raise ValueError("Missing ADZUNA_APP_ID or ADZUNA_API_KEY in .env file")

ADZUNA_BASE_URLS = {
    "lon": "https://api.adzuna.com/v1/api/jobs/gb/search",
    "nyc": "https://api.adzuna.com/v1/api/jobs/us/search",
    "den": "https://api.adzuna.com/v1/api/jobs/us/search",
}

LOCATION_QUERIES = {
    "lon": "London",
    "nyc": "New York",
    "den": "Denver"
}

DEFAULT_SEARCH_QUERIES = [
    # Data roles
    "Data Scientist",
    "Data Engineer", 
    "Machine Learning Engineer",
    "Analytics Engineer",
    "Data Analyst",
    "AI Engineer",
    "Data Architect",
    
    # Product roles
    "Product Manager",
    "Technical Product Manager",
    "Growth Product Manager",
    "AI Product Manager"
]

# Load agency config
with open('config/agency_blacklist.yaml') as f:
    AGENCY_CONFIG = yaml.safe_load(f)

# Normalize hard filter: lowercase + set for O(1) lookup
HARD_FILTER = set(agency.lower().strip() for agency in AGENCY_CONFIG['hard_filter'])

# Validation: print on startup
print(f"[PROTECT] Hard filter loaded: {len(HARD_FILTER)} agencies")
if len(HARD_FILTER) > 0:
    sample = list(HARD_FILTER)[:3]
    print(f"   Sample: {', '.join(sample)}")

# ============================================
# HELPER FUNCTIONS
# ============================================

def is_hard_filter_agency(employer_name: str) -> bool:
    """Check if employer is in hard filter blacklist"""
    if not employer_name:
        return False
    return employer_name.lower().strip() in HARD_FILTER


def fetch_adzuna_jobs(
    city_code: str,
    search_query: str,
    page: int = 1,
    results_per_page: int = 10,
    max_days_old: int = 30
) -> list:
    """Fetch jobs from Adzuna API"""
    base_url = ADZUNA_BASE_URLS[city_code]
    location = LOCATION_QUERIES[city_code]
    url = f"{base_url}/{page}"
    
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_API_KEY,
        "results_per_page": min(results_per_page, 50),
        "what": search_query,
        "where": location,
        "max_days_old": max_days_old
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Adzuna API error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response status: {e.response.status_code}")
        return []


def format_job_for_classification(adzuna_job: dict) -> str:
    """Convert Adzuna JSON to human-readable text for Claude"""
    title = adzuna_job.get("title", "")
    company = adzuna_job.get("company", {}).get("display_name", "Unknown Company")
    location = adzuna_job.get("location", {}).get("display_name", "")
    description = adzuna_job.get("description", "")
    
    salary_min = adzuna_job.get("salary_min")
    salary_max = adzuna_job.get("salary_max")
    salary_text = ""
    
    if salary_min and salary_max:
        salary_text = f"\nSalary: ${salary_min:,.0f} - ${salary_max:,.0f}"
    elif salary_min:
        salary_text = f"\nSalary: ${salary_min:,.0f}+"
    
    contract_type = adzuna_job.get("contract_type", "")
    contract_text = f"\n{contract_type}" if contract_type else ""
    
    job_text = f"""
{title}
{company} · {location}{contract_text}{salary_text}

{description}
    """.strip()
    
    return job_text


def check_if_job_exists(posting_url: str) -> bool:
    """Check if job already exists in database"""
    try:
        result = supabase.table("raw_jobs") \
            .select("id") \
            .eq("posting_url", posting_url) \
            .execute()
        return len(result.data) > 0
    except Exception as e:
        print(f"[WARNING] Error checking for duplicate: {e}")
        return False


# ============================================
# MAIN PIPELINE
# ============================================

def process_adzuna_jobs(
    city_code: str,
    search_queries: list = None,
    max_jobs_per_query: int = 10,
    skip_existing: bool = True
):
    """
    Main pipeline: Fetch, classify, and store jobs
    """
    if search_queries is None:
        search_queries = DEFAULT_SEARCH_QUERIES
    
    print("=" * 70)
    print(f"ADZUNA JOB FETCH - {LOCATION_QUERIES[city_code].upper()}")
    print("=" * 70)
    
    total_fetched = 0
    total_processed = 0
    total_skipped = 0
    total_errors = 0
    
    for query in search_queries:
        print(f"\n{'='*70}")
        print(f"SEARCHING: '{query}' in {LOCATION_QUERIES[city_code]}")
        print(f"{'='*70}")
        
        adzuna_jobs = fetch_adzuna_jobs(
            city_code=city_code,
            search_query=query,
            results_per_page=max_jobs_per_query
        )
        
        print(f"\n[OK] Fetched {len(adzuna_jobs)} jobs from Adzuna")
        total_fetched += len(adzuna_jobs)
        
        for i, adzuna_job in enumerate(adzuna_jobs, 1):
            job_title = adzuna_job.get("title", "Unknown")
            job_url = adzuna_job.get("redirect_url", f"adzuna-{adzuna_job.get('id')}")
            employer_name = adzuna_job.get("company", {}).get("display_name", "")
            
            # HARD FILTER: Block known agencies before classification
            if is_hard_filter_agency(employer_name):
                print(f"   [SKIP] Filtered agency (hard): {employer_name}")
                total_skipped += 1
                continue
            
            print(f"\n[{i}/{len(adzuna_jobs)}] Processing: {job_title[:60]}...")
            
            # Check for duplicates
            if skip_existing and check_if_job_exists(job_url):
                print(f"   [SKIP] Skipping (already in database)")
                total_skipped += 1
                continue
            
            try:
                # Format job text
                job_text = format_job_for_classification(adzuna_job)
                
                # Insert raw job
                raw_id = insert_raw_job(
                    source="adzuna",
                    posting_url=job_url,
                    raw_text=job_text,
                    source_job_id=str(adzuna_job.get("id")),
                    metadata={
                        "adzuna_created": adzuna_job.get("created"),
                        "adzuna_category": adzuna_job.get("category", {}).get("label"),
                        "adzuna_contract_type": adzuna_job.get("contract_type")
                    }
                )
                print(f"   [OK] Raw job inserted: ID {raw_id}")
                
                # Classify with Claude
                classification = classify_job_with_claude(job_text)
                print(f"   [OK] Classified: {classification['role']['job_family']} → {classification['role'].get('job_subfamily')}")
                
                # ========================================
                # SOFT DETECTION: Validate agency classification
                # ========================================
                # This overrides Claude's classification with pattern matching
                final_is_agency, final_confidence = validate_agency_classification(
                    employer_name=classification['employer']['name'],
                    claude_is_agency=classification['employer'].get('is_agency'),
                    claude_confidence=classification['employer'].get('agency_confidence'),
                    job_description=job_text
                )
                
                # Override with validated result
                classification['employer']['is_agency'] = final_is_agency
                classification['employer']['agency_confidence'] = final_confidence
                
                # Log if agency detected by soft filter
                if final_is_agency:
                    print(f"   [DETECT] Agency detected (soft): {employer_name} (confidence: {final_confidence})")
                
                # Extract salary
                salary_range = classification['compensation'].get('base_salary_range')
                salary_min = salary_range.get('min') if salary_range else None
                salary_max = salary_range.get('max') if salary_range else None
                
                # Parse posted date
                posted_date = date.today()
                if adzuna_job.get("created"):
                    try:
                        posted_date = datetime.fromisoformat(
                            adzuna_job["created"].replace("Z", "+00:00")
                        ).date()
                    except:
                        pass
                
                # Insert enriched job with validated agency flags
                enriched_id = insert_enriched_job(
                    raw_job_id=raw_id,
                    
                    # Employer info (with validated agency fields)
                    employer_name=classification['employer']['name'],
                    employer_department=classification['employer'].get('department'),
                    employer_size=classification['employer'].get('company_size_estimate'),
                    is_agency=classification['employer']['is_agency'],  # ← Validated
                    agency_confidence=classification['employer']['agency_confidence'],  # ← Validated
                    
                    # Role info
                    title_display=classification['role']['title_display'],
                    job_family=classification['role']['job_family'],
                    job_subfamily=classification['role'].get('job_subfamily'),
                    seniority=classification['role'].get('seniority'),
                    track=classification['role'].get('track'),
                    position_type=classification['role']['position_type'],
                    experience_range=classification['role'].get('experience_range'),
                    
                    # Location info
                    city_code=classification['location']['city_code'],
                    working_arrangement=classification['location']['working_arrangement'],
                    
                    # Compensation info
                    currency=classification['compensation'].get('currency'),
                    salary_min=salary_min,
                    salary_max=salary_max,
                    equity_eligible=classification['compensation'].get('equity_eligible'),
                    
                    # Skills
                    skills=classification.get('skills', []),
                    
                    # Dates
                    posted_date=posted_date,
                    last_seen_date=date.today()
                )
                print(f"   [OK] Enriched job inserted: ID {enriched_id}")
                
                total_processed += 1
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                print(f"   [ERROR] Error processing job: {e}")
                import traceback
                traceback.print_exc()
                total_errors += 1
                continue
    
    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Total fetched from Adzuna: {total_fetched}")
    print(f"Successfully processed: {total_processed}")
    print(f"Skipped (duplicates + agencies): {total_skipped}")
    print(f"Errors: {total_errors}")
    
    if total_processed > 0:
        print(f"\n[COST] Estimated cost: ~${total_processed * 0.004:.2f} (Claude API)")
        print(f"[TIME] Average time: ~3-4 seconds per job")


# ============================================
# COMMAND LINE INTERFACE
# ============================================

if __name__ == "__main__":
    import sys
    
    city = sys.argv[1] if len(sys.argv) > 1 else "lon"
    max_jobs = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    
    if city not in ["lon", "nyc", "den"]:
        print("[ERROR] Invalid city code. Use: lon, nyc, or den")
        sys.exit(1)
    
    print(f"\n[START] Starting Adzuna fetch for {LOCATION_QUERIES[city]}")
    print(f"   Target: {max_jobs} jobs per search query")
    print(f"   Search queries: {', '.join(DEFAULT_SEARCH_QUERIES)}\n")
    
    process_adzuna_jobs(
        city_code=city,
        max_jobs_per_query=max_jobs
    )