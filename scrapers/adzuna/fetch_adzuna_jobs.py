"""
ADZUNA API CLIENT MODULE

PURPOSE:
Reusable module for fetching job postings from Adzuna API.
Provides low-level API functions and configuration constants.

Used by fetch_jobs.py (dual-pipeline orchestrator) for integration with Greenhouse scraper.

RATE LIMITS (from Adzuna ToS):
- 25 hits per minute
- 250 hits per day
- 1000 hits per week
- 2500 hits per month

See: https://developer.adzuna.com/docs/terms_of_service
"""

import os
import time
import requests
from dotenv import load_dotenv
from typing import List, Dict, Optional

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

# Rate limiting configuration
# Adzuna allows 25 hits/minute, so ~2.5 seconds between calls is safe
RATE_LIMIT_DELAY = 2.5  # seconds between API calls
MAX_RESULTS_PER_PAGE = 50  # Adzuna hard limit

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
    "AI Product Manager",
    "Product Owner"
]

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


def fetch_adzuna_jobs_paginated(
    city_code: str,
    search_query: str,
    max_results: int = 50,
    max_days_old: int = 30,
    rate_limit_delay: float = RATE_LIMIT_DELAY,
    verbose: bool = True
) -> List[Dict]:
    """
    Fetch jobs from Adzuna API with pagination support and rate limiting.
    
    Handles Adzuna's 50 results/page limit by fetching multiple pages.
    Includes rate limiting to stay within 25 calls/minute API limit.
    
    Args:
        city_code: City code (lon, nyc, den)
        search_query: Job role to search for (e.g., "Data Scientist")
        max_results: Maximum total results to fetch (will paginate if > 50)
        max_days_old: Filter jobs posted within N days (default: 30)
        rate_limit_delay: Seconds to wait between API calls (default: 2.5)
        verbose: Print progress messages (default: True)
    
    Returns:
        List of job dictionaries from Adzuna API
    
    Example:
        # Fetch up to 150 Data Scientist jobs in London (3 pages)
        jobs = fetch_adzuna_jobs_paginated("lon", "Data Scientist", max_results=150)
    """
    all_jobs = []
    page = 1
    pages_needed = (max_results + MAX_RESULTS_PER_PAGE - 1) // MAX_RESULTS_PER_PAGE  # Ceiling division
    
    if verbose:
        print(f"    Fetching up to {max_results} jobs ({pages_needed} pages)...")
    
    while len(all_jobs) < max_results:
        # Rate limiting: wait before each call (except the first)
        if page > 1:
            if verbose:
                print(f"      Rate limit: waiting {rate_limit_delay}s...")
            time.sleep(rate_limit_delay)
        
        # Fetch one page
        jobs = fetch_adzuna_jobs(
            city_code=city_code,
            search_query=search_query,
            page=page,
            results_per_page=MAX_RESULTS_PER_PAGE,
            max_days_old=max_days_old
        )
        
        if not jobs:
            # No more results available
            if verbose:
                print(f"      Page {page}: No more results")
            break
        
        all_jobs.extend(jobs)
        
        if verbose:
            print(f"      Page {page}: Got {len(jobs)} jobs (total: {len(all_jobs)})")
        
        # Check if we got fewer results than requested (last page)
        if len(jobs) < MAX_RESULTS_PER_PAGE:
            break
        
        page += 1
        
        # Safety check: don't exceed reasonable page count
        if page > 20:
            print(f"    Warning: Stopping at page 20 to avoid excessive API calls")
            break
    
    # Trim to exact max_results if we fetched more
    if len(all_jobs) > max_results:
        all_jobs = all_jobs[:max_results]
    
    if verbose:
        print(f"    Total fetched: {len(all_jobs)} jobs")
    
    return all_jobs


def calculate_api_calls(
    num_queries: int = len(DEFAULT_SEARCH_QUERIES),
    num_cities: int = 3,
    results_per_query: int = 50
) -> Dict:
    """
    Calculate API calls needed and check against rate limits.
    
    Args:
        num_queries: Number of search queries (default: 11)
        num_cities: Number of cities (default: 3)
        results_per_query: Results per query (determines pages needed)
    
    Returns:
        Dict with call counts and limit status
    """
    pages_per_query = (results_per_query + MAX_RESULTS_PER_PAGE - 1) // MAX_RESULTS_PER_PAGE
    total_calls = num_queries * num_cities * pages_per_query
    
    # Time estimate with rate limiting
    time_seconds = total_calls * RATE_LIMIT_DELAY
    time_minutes = time_seconds / 60
    
    return {
        "total_api_calls": total_calls,
        "pages_per_query": pages_per_query,
        "estimated_time_minutes": round(time_minutes, 1),
        "within_daily_limit": total_calls <= 250,
        "within_weekly_limit": total_calls <= 1000,
        "within_monthly_limit": total_calls <= 2500,
        "calls_per_minute": 60 / RATE_LIMIT_DELAY,  # With rate limiting
    }