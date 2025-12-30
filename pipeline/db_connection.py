"""
Database connection and helper functions for Supabase
"""
import os
import hashlib
from datetime import date
from typing import Optional, Dict, List
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# ============================================
# Configuration
# ============================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in .env file")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================
# Helper Functions
# ============================================

def generate_job_hash(employer_name: str, title: str, city_code: str) -> str:
    """
    Generate MD5 hash for deduplication.
    
    Uses employer + title + city as unique identifier.
    Handles None values gracefully.
    
    Args:
        employer_name: Company name
        title: Job title
        city_code: City code (lon/nyc/den)
    
    Returns:
        MD5 hash string
    """
    # Handle None values defensively
    employer = (employer_name or "unknown").lower().strip()
    job_title = (title or "unknown").lower().strip()
    city = (city_code or "unknown").lower().strip()
    
    # Create unique key
    key = f"{employer}|{job_title}|{city}"
    
    # Generate MD5 hash
    return hashlib.md5(key.encode()).hexdigest()


def insert_raw_job(
    source: str,
    posting_url: str,
    raw_text: str,
    source_job_id: Optional[str] = None,
    title: Optional[str] = None,
    company: Optional[str] = None,
    metadata: Optional[Dict] = None,
    full_text: Optional[str] = None,
    text_source: Optional[str] = None
) -> int:
    """
    Insert a raw job posting into the database.

    Args:
        source: Source identifier (e.g., 'adzuna', 'linkedin_rss', 'manual')
        posting_url: Full URL to job posting
        raw_text: Complete job description text/HTML
        source_job_id: Optional external ID from source
        title: Optional job title from source (before classification)
        company: Optional company name from source (before classification)
        metadata: Optional additional metadata (dict)
        full_text: Optional full job description (for enrichment from ATS scraping)
        text_source: Source of full_text ('adzuna_api', 'ats_scrape', 'company_website', etc.)

    Returns:
        ID of inserted raw job
    """
    data = {
        "source": source,
        "posting_url": posting_url,
        "raw_text": raw_text,
        "source_job_id": source_job_id,
        "metadata": metadata or {},
    }

    # Add optional metadata fields if provided
    if title is not None:
        data["title"] = title
    if company is not None:
        data["company"] = company
    if full_text is not None:
        data["full_text"] = full_text
    if text_source is not None:
        data["text_source"] = text_source

    result = supabase.table("raw_jobs").insert(data).execute()
    return result.data[0]["id"]


def insert_raw_job_upsert(
    source: str,
    posting_url: str,
    title: str,
    company: str,
    raw_text: str,
    city_code: str = 'unk',
    source_job_id: Optional[str] = None,
    metadata: Optional[Dict] = None,
    full_text: Optional[str] = None,
    text_source: Optional[str] = None
) -> Dict:
    """
    Insert or update a raw job posting using UPSERT (incremental pipeline mode).

    Uses (source, source_job_id) as the unique identifier for upserts when source_job_id
    is provided. This correctly handles Adzuna URLs that contain session tracking 
    parameters (same job appears with different URLs but same source_job_id).
    
    Also stores a hash (company+title+city) for potential cross-source deduplication.

    Args:
        source: Source identifier ('adzuna', 'greenhouse', 'manual')
        posting_url: Full URL to job posting (stored but not used for deduplication)
        title: Job title
        company: Company name
        raw_text: Job description text
        city_code: City code ('lon', 'nyc', 'den', or 'unk')
        source_job_id: External ID from source (REQUIRED for deduplication)
        metadata: Optional additional metadata (dict)
        full_text: Optional full job description (for enrichment)
        text_source: Source of full_text ('adzuna_api', 'greenhouse', etc.)

    Returns:
        Dict with:
            - 'id': raw_job_id (existing or newly created)
            - 'action': 'inserted' or 'updated'
            - 'was_duplicate': boolean
    """
    # Generate hash for cross-source deduplication (stored but not used for upsert)
    job_hash = generate_job_hash(company, title, city_code)

    from datetime import datetime

    data = {
        "source": source,
        "posting_url": posting_url,
        "raw_text": raw_text,
        "hash": job_hash,
        "title": title,
        "company": company,
        "source_job_id": source_job_id,
        "metadata": metadata or {},
        "last_seen": datetime.utcnow().isoformat(),  # Update on every encounter
    }

    # Add optional enrichment fields
    if full_text is not None:
        data["full_text"] = full_text
    if text_source is not None:
        data["text_source"] = text_source

    try:
        # Check if job already exists by (source, source_job_id)
        # This handles Adzuna URLs that change session parameters
        if source_job_id:
            existing = supabase.table("raw_jobs").select("id, scraped_at").eq(
                "source", source
            ).eq("source_job_id", source_job_id).execute()
            
            if existing.data:
                # Job exists - update it
                raw_job_id = existing.data[0]["id"]
                supabase.table("raw_jobs").update({
                    "last_seen": datetime.utcnow().isoformat(),
                    "posting_url": posting_url,  # Update URL in case it changed
                    "raw_text": raw_text,
                    "title": title,
                    "company": company,
                    "metadata": metadata or {},
                }).eq("id", raw_job_id).execute()
                
                return {
                    "id": raw_job_id,
                    "action": "updated",
                    "was_duplicate": True
                }
        
        # No existing job found or no source_job_id - insert new
        result = supabase.table("raw_jobs").insert(data).execute()
        raw_job_id = result.data[0]["id"]

        # If we got here, the job is NEW (we checked for existing above)
        # No need for timestamp comparison which can fail due to clock skew
        return {
            'id': raw_job_id,
            'action': 'inserted',
            'was_duplicate': False
        }

    except Exception as e:
        # If error is NOT about unique constraint, re-raise
        error_str = str(e).lower()
        if 'duplicate key' not in error_str and 'unique constraint' not in error_str and '23505' not in str(e):
            raise

        # Unique constraint conflict - try to find existing job by source_job_id first
        if source_job_id:
            existing = supabase.table('raw_jobs').select('id').eq(
                'source', source
            ).eq('source_job_id', source_job_id).execute()
            if existing.data:
                return {
                    'id': existing.data[0]['id'],
                    'action': 'skipped',
                    'was_duplicate': True
                }
        
        raise  # Unexpected error


def insert_enriched_job(
    raw_job_id: int,
    employer_name: str,
    title_display: str,
    job_family: str,
    city_code: str,
    working_arrangement: str,
    position_type: str,
    posted_date: date,
    last_seen_date: date,
    # Optional fields
    job_subfamily: Optional[str] = None,
    title_canonical: Optional[str] = None,
    track: Optional[str] = None,
    seniority: Optional[str] = None,
    experience_range: Optional[str] = None,
    employer_department: Optional[str] = None,
    employer_size: Optional[str] = None,
    is_agency: Optional[bool] = None,
    agency_confidence: Optional[str] = None,
    currency: Optional[str] = None,
    salary_min: Optional[float] = None,
    salary_max: Optional[float] = None,
    equity_eligible: Optional[bool] = None,
    skills: Optional[List[Dict]] = None,
    # Dual pipeline tracking (new fields)
    data_source: Optional[str] = "adzuna",
    description_source: Optional[str] = "adzuna",
    deduplicated: Optional[bool] = False,
    original_url_secondary: Optional[str] = None,
    merged_from_source: Optional[str] = None,
    # Location expansion (Global Location Expansion Epic)
    locations: Optional[List[Dict]] = None
) -> int:
    """
    Insert a classified/enriched job into the database.
    Uses upsert to handle duplicates based on job_hash.

    Args:
        raw_job_id: Foreign key to raw_jobs table
        employer_name: Company name
        title_display: Original job title from posting
        job_family: 'product', 'data', or 'out_of_scope'
        city_code: 'lon', 'nyc', or 'den' (legacy, being replaced by locations)
        working_arrangement: 'onsite', 'hybrid', 'remote', or 'flexible'
        position_type: 'full_time', 'part_time', 'contract', or 'internship'
        posted_date: Date job was posted
        last_seen_date: Date job was last seen active
        locations: Array of location objects (Global Location Expansion)
        ... (other optional fields)

    Returns:
        ID of inserted/updated enriched job

    Skills format: [
        {"name": "Python", "family_code": "programming"},
        {"name": "PyTorch", "family_code": "deep_learning"}
    ]

    Locations format: [
        {"type": "city", "country_code": "GB", "city": "london"},
        {"type": "remote", "scope": "country", "country_code": "US"}
    ]
    """
    # VALIDATION: Check required fields
    if not city_code:
        raise ValueError(f"Missing city_code for job: {title_display} at {employer_name}")
    
    if not employer_name:
        raise ValueError(f"Missing employer_name for job ID: {raw_job_id}")
    
    if not title_display:
        raise ValueError(f"Missing title_display for job ID: {raw_job_id}")
    
    # Generate deduplication hash
    job_hash = generate_job_hash(employer_name, title_display, city_code)
    
    data = {
        "raw_job_id": raw_job_id,
        "job_hash": job_hash,

        # Employer
        "employer_name": employer_name,
        "employer_department": employer_department,
        "employer_size": employer_size,
        "is_agency": is_agency,
        "agency_confidence": agency_confidence,

        # Role
        "title_display": title_display,
        "title_canonical": title_canonical,
        "job_family": job_family,
        "job_subfamily": job_subfamily,
        "track": track,
        "seniority": seniority,
        "position_type": position_type,
        "experience_range": experience_range,

        # Location
        "city_code": city_code,
        "working_arrangement": working_arrangement,
        "locations": locations or [],

        # Compensation
        "currency": currency,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "equity_eligible": equity_eligible,

        # Skills
        "skills": skills or [],

        # Dates
        "posted_date": posted_date.isoformat(),
        "last_seen_date": last_seen_date.isoformat(),

        # Dual pipeline source tracking (new fields)
        "data_source": data_source,
        "description_source": description_source,
        "deduplicated": deduplicated,
        "original_url_secondary": original_url_secondary,
        "merged_from_source": merged_from_source
    }

    # Validate/normalize constrained fields before insert
    VALID_CURRENCIES = {'usd', 'gbp', 'cad', 'eur', 'sgd'}
    VALID_EMPLOYER_SIZES = {'startup', 'scaleup', 'enterprise'}
    VALID_WORKING_ARRANGEMENTS = {'onsite', 'hybrid', 'remote', 'flexible', 'unknown'}

    if data.get('currency'):
        currency_lower = data['currency'].lower()
        if currency_lower in VALID_CURRENCIES:
            data['currency'] = currency_lower
        else:
            data['currency'] = None

    if data.get('employer_size'):
        size_lower = data['employer_size'].lower()
        if size_lower in VALID_EMPLOYER_SIZES:
            data['employer_size'] = size_lower
        else:
            data['employer_size'] = None  # LLM returned invalid value (e.g., prompt text)

    if data.get('working_arrangement'):
        wa_lower = data['working_arrangement'].lower()
        if wa_lower in VALID_WORKING_ARRANGEMENTS:
            data['working_arrangement'] = wa_lower
        else:
            # LLM returned invalid value (e.g., 'remote-flexible', 'work from home')
            # Map common variants, otherwise default to 'unknown'
            wa_mapping = {
                'remote-flexible': 'flexible',
                'remote-first': 'remote',
                'work from home': 'remote',
                'wfh': 'remote',
                'in-office': 'onsite',
                'on-site': 'onsite',
            }
            data['working_arrangement'] = wa_mapping.get(wa_lower, 'unknown')

    # Remove None values - Postgres CHECK constraints don't allow explicit NULL
    # Let Postgres use column defaults instead
    data = {k: v for k, v in data.items() if v is not None}

    # Use upsert to handle duplicates (same job_hash)
    result = supabase.table("enriched_jobs").upsert(
        data,
        on_conflict="job_hash"  # Update if hash already exists
    ).execute()
    
    return result.data[0]["id"]


def update_raw_job_full_text(
    raw_job_id: int,
    full_text: str,
    text_source: str
) -> bool:
    """
    Update full_text and text_source on an existing raw job record.

    Used for enriching Adzuna records with full job descriptions from ATS scraping.

    Args:
        raw_job_id: ID of the raw_job record to update
        full_text: Full job description text
        text_source: Source of the full text ('ats_scrape', 'company_website', etc.)

    Returns:
        True if update successful, False otherwise
    """
    try:
        data = {
            "full_text": full_text,
            "text_source": text_source
        }

        result = supabase.table("raw_jobs").update(data).eq("id", raw_job_id).execute()
        return len(result.data) > 0
    except Exception as e:
        print(f"Error updating raw job {raw_job_id}: {e}")
        return False


def get_raw_job_by_id(raw_job_id: int) -> Optional[Dict]:
    """
    Retrieve a raw job record by ID.

    Args:
        raw_job_id: ID of the raw job

    Returns:
        Job record dict or None if not found
    """
    try:
        result = supabase.table("raw_jobs").select("*").eq("id", raw_job_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error retrieving raw job {raw_job_id}: {e}")
        return None


def test_connection():
    """Test that we can connect to Supabase"""
    try:
        result = supabase.table("raw_jobs").select("count").execute()
        print(f"[OK] Connected to Supabase successfully")
        print(f"   Current raw jobs count: {result.count}")
        return True
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        return False


# ============================================
# Test Connection on Import
# ============================================
if __name__ == "__main__":
    print("Testing Supabase connection...")
    test_connection()