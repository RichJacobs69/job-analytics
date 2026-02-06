"""
Database connection and helper functions for Supabase
"""
import os
import hashlib
import logging
from datetime import date, datetime
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

logger = logging.getLogger(__name__)

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
    last_seen_date: date,
    # Optional fields
    job_subfamily: Optional[str] = None,
    title_canonical: Optional[str] = None,
    track: Optional[str] = None,
    seniority: Optional[str] = None,
    experience_range: Optional[str] = None,
    employer_department: Optional[str] = None,
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
    locations: Optional[List[Dict]] = None,
    # AI-generated summary (inline from classifier)
    summary: Optional[str] = None,
    # URL validation status (defaults to active for freshly scraped jobs)
    url_status: str = 'active',
    # Display name hint for employer_metadata auto-creation (from ATS config key)
    display_name_hint: Optional[str] = None
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
        last_seen_date: Date job was last seen active
        locations: Array of location objects (Global Location Expansion)
        summary: AI-generated 2-3 sentence role summary (from classifier)
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

    # Normalize employer_name to lowercase for FK constraint
    employer_name_canonical = employer_name.lower().strip()

    # Ensure employer exists in employer_metadata (auto-create if needed for FK)
    # This maintains referential integrity while allowing new companies to be scraped
    # Use display_name_hint from config if provided, otherwise fall back to employer_name
    display_name = display_name_hint if display_name_hint else employer_name
    ensure_employer_metadata(employer_name_canonical, display_name=display_name)

    # Generate deduplication hash
    job_hash = generate_job_hash(employer_name_canonical, title_display, city_code)

    data = {
        "raw_job_id": raw_job_id,
        "job_hash": job_hash,

        # Employer (stored as canonical lowercase for FK to employer_metadata)
        "employer_name": employer_name_canonical,
        "employer_department": employer_department,
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

        # AI-generated summary
        "summary": summary,

        # Dates (posted_date omitted -- set by DB DEFAULT on first insert, preserved on upsert)
        "last_seen_date": last_seen_date.isoformat(),
        "classified_at": datetime.utcnow().isoformat(),  # Update on every classification

        # Dual pipeline source tracking (new fields)
        "data_source": data_source,
        "description_source": description_source,
        "deduplicated": deduplicated,
        "original_url_secondary": original_url_secondary,
        "merged_from_source": merged_from_source,

        # URL validation (default active for freshly scraped jobs)
        "url_status": url_status
    }

    # Validate/normalize constrained fields before insert
    VALID_CURRENCIES = {'usd', 'gbp', 'cad', 'eur', 'sgd'}
    VALID_WORKING_ARRANGEMENTS = {'onsite', 'hybrid', 'remote', 'flexible', 'unknown'}

    if data.get('currency'):
        currency_lower = data['currency'].lower()
        if currency_lower in VALID_CURRENCIES:
            data['currency'] = currency_lower
        else:
            data['currency'] = None

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
        logger.error(f"Error updating raw job {raw_job_id}: {e}")
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
        logger.error(f"Error retrieving raw job {raw_job_id}: {e}")
        return None


# ============================================
# Employer Metadata Functions
# ============================================

# In-memory cache for employer metadata (refreshed on script restart)
_employer_metadata_cache: Dict[str, Dict] = {}
_employer_metadata_loaded: bool = False


def _normalize_employer_name(name: str) -> str:
    """Normalize employer name for canonical lookup."""
    if not name:
        return ""
    return name.lower().strip()


def _load_employer_metadata_cache():
    """Load all employer metadata into memory cache."""
    global _employer_metadata_cache, _employer_metadata_loaded

    if _employer_metadata_loaded:
        return

    try:
        offset = 0
        page_size = 1000

        while True:
            result = supabase.table("employer_metadata") \
                .select("canonical_name, display_name, employer_size, working_arrangement_default, working_arrangement_source") \
                .range(offset, offset + page_size - 1) \
                .execute()

            if not result.data:
                break

            for row in result.data:
                _employer_metadata_cache[row['canonical_name']] = {
                    'display_name': row['display_name'],
                    'employer_size': row['employer_size'],
                    'working_arrangement_default': row['working_arrangement_default'],
                    'working_arrangement_source': row['working_arrangement_source']
                }

            if len(result.data) < page_size:
                break
            offset += page_size

        _employer_metadata_loaded = True
        if _employer_metadata_cache:
            logger.debug(f"Loaded {len(_employer_metadata_cache)} employer metadata entries into cache")

    except Exception as e:
        # Table may not exist yet - that's OK
        if 'does not exist' not in str(e).lower():
            logger.warning(f"Failed to load employer metadata cache: {e}")
        _employer_metadata_loaded = True  # Mark as loaded to avoid retry spam


def get_employer_metadata(employer_name: str) -> Optional[Dict]:
    """
    Get employer metadata by name (case-insensitive).

    Args:
        employer_name: Employer name as it appears in job posting

    Returns:
        Dict with display_name, employer_size, working_arrangement_default,
        working_arrangement_source - or None if not found
    """
    _load_employer_metadata_cache()

    canonical = _normalize_employer_name(employer_name)
    return _employer_metadata_cache.get(canonical)


def get_working_arrangement_fallback(employer_name: str) -> Optional[str]:
    """
    Get working arrangement fallback for an employer.

    Use this when the classifier returns 'unknown' for working_arrangement.
    Returns None if no fallback is configured for this employer.

    Args:
        employer_name: Employer name as it appears in job posting

    Returns:
        'hybrid', 'remote', 'onsite', 'flexible', or None
    """
    metadata = get_employer_metadata(employer_name)
    if metadata:
        return metadata.get('working_arrangement_default')
    return None


def upsert_employer_metadata(
    canonical_name: str,
    display_name: str,
    employer_size: Optional[str] = None,
    working_arrangement_default: Optional[str] = None,
    working_arrangement_source: str = 'manual'
) -> bool:
    """
    Insert or update employer metadata.

    Args:
        canonical_name: Lowercase normalized name (PK)
        display_name: Pretty name for UI
        employer_size: 'startup', 'scaleup', or 'enterprise'
        working_arrangement_default: Default working arrangement
        working_arrangement_source: 'manual', 'inferred', or 'scraped'

    Returns:
        True if successful
    """
    global _employer_metadata_loaded

    data = {
        'canonical_name': canonical_name.lower().strip(),
        'display_name': display_name,
    }

    # Add optional fields only if provided
    if employer_size is not None:
        data['employer_size'] = employer_size
    if working_arrangement_default is not None:
        data['working_arrangement_default'] = working_arrangement_default
        data['working_arrangement_source'] = working_arrangement_source

    try:
        supabase.table("employer_metadata").upsert(
            data, on_conflict='canonical_name'
        ).execute()

        # Invalidate cache so next lookup gets fresh data
        _employer_metadata_loaded = False
        return True

    except Exception as e:
        logger.error(f"Failed to upsert employer metadata: {e}")
        return False


def ensure_employer_metadata(employer_name: str, display_name: str = None) -> bool:
    """
    Create employer_metadata entry if not exists.

    Args:
        employer_name: The employer name (will be normalized to lowercase)
        display_name: Optional pretty name for UI (defaults to employer_name)

    Returns:
        True if new entry was created, False if already exists
    """
    canonical = employer_name.lower().strip()

    # Check if already exists
    existing = get_employer_metadata(canonical)
    if existing:
        return False  # Already exists

    # Create minimal entry (working_arrangement_default will be inferred later)
    return upsert_employer_metadata(
        canonical_name=canonical,
        display_name=display_name or employer_name
    )


def update_employer_working_arrangement_if_confident(
    employer_name: str,
    threshold: float = 0.7,
    min_jobs: int = 3
) -> bool:
    """
    Compute working_arrangement from classified jobs and update if confident.

    Only updates if:
    - working_arrangement_default is currently NULL
    - OR working_arrangement_source is 'inferred' (can be updated with more data)

    Never overwrites 'manual' or 'scraped' sources.

    Args:
        employer_name: The employer name to check
        threshold: Minimum agreement percentage (default: 70%)
        min_jobs: Minimum jobs with known arrangement (default: 3)

    Returns:
        True if metadata was updated
    """
    from collections import Counter

    canonical = employer_name.lower().strip()
    metadata = get_employer_metadata(canonical)

    if not metadata:
        return False  # Employer not in metadata table

    # Check source priority - never overwrite manual or scraped
    current_source = metadata.get('working_arrangement_source')
    if current_source in ('manual', 'scraped'):
        return False  # Higher priority source, don't overwrite

    # Query job counts by working_arrangement (exclude 'unknown')
    try:
        response = supabase.table("enriched_jobs").select(
            "working_arrangement"
        ).ilike(
            "employer_name", canonical
        ).neq(
            "working_arrangement", "unknown"
        ).execute()

        if not response.data:
            return False  # No jobs with known arrangement

        # Count arrangements
        counts = Counter(row["working_arrangement"] for row in response.data)
        total = sum(counts.values())

        if total < min_jobs:
            return False  # Not enough data

        # Get top value
        top_value, top_count = counts.most_common(1)[0]
        confidence = top_count / total

        if confidence < threshold:
            return False  # Threshold not met

        # Update metadata
        return upsert_employer_metadata(
            canonical_name=canonical,
            display_name=metadata.get('display_name', employer_name),
            working_arrangement_default=top_value,
            working_arrangement_source='inferred'
        )

    except Exception as e:
        logger.warning(f"Failed to compute working arrangement for '{employer_name}': {e}")
        return False


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