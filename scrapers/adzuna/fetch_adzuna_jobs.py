"""
ADZUNA API CLIENT MODULE

PURPOSE:
Reusable module for fetching job postings from Adzuna API.
Provides low-level API functions and configuration constants.

Used by fetch_jobs.py (dual-pipeline orchestrator) for integration with Greenhouse scraper.

RATE LIMITING:
- Enforces minimum delay between API calls (default: 1.2 seconds)
- Automatic retry with exponential backoff on 429 errors
- Thread-safe for parallel execution
"""

import os
import time
import threading
import requests
from dotenv import load_dotenv

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

# All role types to fetch from Adzuna
# Import this in fetch_jobs.py to maintain single source of truth
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

# ============================================
# RATE LIMITING
# ============================================

# Minimum seconds between API calls (Adzuna allows ~50 requests/minute)
MIN_REQUEST_INTERVAL = 1.2  # ~50 requests/minute with safety margin

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF = 5  # seconds to wait after first 429

# Thread-safe rate limiter
_rate_lock = threading.Lock()
_last_request_time = 0.0


def _wait_for_rate_limit():
    """Ensure minimum interval between API calls (thread-safe)."""
    global _last_request_time
    with _rate_lock:
        now = time.time()
        elapsed = now - _last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            sleep_time = MIN_REQUEST_INTERVAL - elapsed
            time.sleep(sleep_time)
        _last_request_time = time.time()


# ============================================
# API CLIENT FUNCTIONS
# ============================================

def fetch_adzuna_jobs(
    city_code: str,
    search_query: str,
    page: int = 1,
    results_per_page: int = 10,
    max_days_old: int = 30
) -> list:
    """
    Fetch jobs from Adzuna API for a single search query.
    
    Includes automatic rate limiting and retry logic for 429 errors.

    Args:
        city_code: City code (lon, nyc, den)
        search_query: Job role to search for (e.g., "Data Scientist")
        page: Page number for pagination (default: 1)
        results_per_page: Number of results per page (max 50, default: 10)
        max_days_old: Filter jobs posted within N days (default: 30)

    Returns:
        List of job dictionaries from Adzuna API
    """
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

    # Retry loop with exponential backoff for 429 errors
    for attempt in range(MAX_RETRIES + 1):
        # Rate limit: wait if needed
        _wait_for_rate_limit()
        
        try:
            response = requests.get(url, params=params, headers=headers)
            
            # Handle rate limit (429)
            if response.status_code == 429:
                if attempt < MAX_RETRIES:
                    backoff = INITIAL_BACKOFF * (2 ** attempt)
                    print(f"[RATE LIMIT] 429 received for '{search_query}' in {city_code}. "
                          f"Waiting {backoff}s before retry {attempt + 1}/{MAX_RETRIES}...")
                    time.sleep(backoff)
                    continue
                else:
                    print(f"[ERROR] Max retries exceeded for '{search_query}' in {city_code} after 429 errors")
                    return []
            
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
            
        except requests.exceptions.RequestException as e:
            # Don't retry other errors
            print(f"[ERROR] Adzuna API error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Response status: {e.response.status_code}")
            return []
    
    return []
