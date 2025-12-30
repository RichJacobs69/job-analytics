# Ashby ATS Integration Guide

## Overview

Ashby is an ATS platform with a **public, unauthenticated API** for job postings. This slots directly into our existing multi-ATS scraper alongside Greenhouse and Lever.

**Endpoint Pattern:**
```
GET https://api.ashbyhq.com/posting-api/job-board/{company_slug}?includeCompensation=true
```

**No authentication required** — just need the company slug (e.g., `notion`, `anthropic`, `figma`).

---

## API Comparison: ATS Endpoints

| ATS | Endpoint | Auth | Compensation |
|-----|----------|------|--------------|
| Greenhouse | `api.greenhouse.io/v1/boards/{slug}/jobs?content=true` | None | Rarely included |
| Lever | `api.lever.co/v0/postings/{slug}` | None | Sometimes in text |
| **Ashby** | `api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true` | None | **Structured field** ✓ |

Ashby has the **best compensation data** of the three — they return it in a dedicated, parseable field.

---

## Response Schema

### Sample Response Structure

```json
{
  "apiVersion": "1",
  "jobs": [
    {
      "id": "job-uuid-here",
      "title": "Senior Data Engineer",
      "location": "London, UK",
      "secondaryLocations": [
        {
          "location": "Remote - Europe",
          "address": {
            "addressLocality": null,
            "addressRegion": null,
            "addressCountry": "Europe"
          }
        }
      ],
      "department": "Engineering",
      "team": "Data Platform",
      "isListed": true,
      "isRemote": true,
      "descriptionHtml": "<p>Full HTML job description...</p>",
      "descriptionPlain": "Plain text version of job description...",
      "publishedAt": "2025-01-15T10:30:00.000+00:00",
      "employmentType": "FullTime",
      "address": {
        "postalAddress": {
          "addressLocality": "London",
          "addressRegion": "England",
          "addressCountry": "UK"
        }
      },
      "jobUrl": "https://jobs.ashbyhq.com/company/job-uuid",
      "applyUrl": "https://jobs.ashbyhq.com/company/job-uuid/apply",
      "compensation": {
        "compensationTierSummary": "£80K – £120K • 0.1% – 0.5% • Offers Bonus",
        "scrapeableCompensationSalarySummary": "£80K - £120K",
        "compensationTiers": [
          {
            "id": "tier-uuid",
            "tierSummary": "£80K – £120K",
            "title": "Senior",
            "salaryRange": {
              "min": { "value": 80000, "currency": "GBP" },
              "max": { "value": 120000, "currency": "GBP" }
            }
          }
        ]
      }
    }
  ]
}
```

### Key Fields for Our Schema

| Ashby Field | Maps To | Notes |
|-------------|---------|-------|
| `title` | `role.title_display` | Direct map |
| `department` | `employer.department` | May need normalization |
| `team` | — | Optional enrichment |
| `location` | `location.city_code` | Needs parsing to our enum |
| `address.postalAddress` | `location.*` | Structured - prefer this |
| `isRemote` | `location.working_arrangement` | Boolean flag |
| `employmentType` | `role.position_type` | Map: FullTime→full_time, etc. |
| `descriptionPlain` | For classification | Feed to LLM |
| `descriptionHtml` | `posting.description_html` | Store raw |
| `publishedAt` | `posting.posted_date` | ISO 8601 format |
| `jobUrl` | `posting.posting_url` | Direct map |
| `compensation.scrapeableCompensationSalarySummary` | `compensation.base_salary_range` | Parse "£80K - £120K" |
| `compensation.compensationTiers[].salaryRange` | `compensation.base_salary_range` | **Best source** - already structured |

---

## Python Implementation

### Basic Scraper Class

```python
"""
Ashby ATS Scraper
Fetches job postings from Ashby's public API.
Follows same pattern as greenhouse_scraper.py and lever_scraper.py.
"""

import requests
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class AshbyScraper:
    """
    Scraper for Ashby ATS public job posting API.
    
    Usage:
        scraper = AshbyScraper()
        jobs = scraper.fetch_jobs("notion")
    """
    
    BASE_URL = "https://api.ashbyhq.com/posting-api/job-board"
    
    def __init__(self, include_compensation: bool = True):
        """
        Args:
            include_compensation: Include salary data in response (recommended True)
        """
        self.include_compensation = include_compensation
        self.session = requests.Session()
        # Be a good citizen - identify ourselves
        self.session.headers.update({
            "User-Agent": "JobMarketIntelligence/1.0 (contact@example.com)"
        })
    
    def fetch_jobs(self, company_slug: str) -> list[dict]:
        """
        Fetch all published jobs for a company.
        
        Args:
            company_slug: Company identifier (e.g., "notion", "anthropic")
                         Find this from jobs.ashbyhq.com/{slug}
        
        Returns:
            List of raw job dictionaries from Ashby API
        
        Raises:
            requests.HTTPError: If API returns error status
        """
        url = f"{self.BASE_URL}/{company_slug}"
        params = {}
        
        if self.include_compensation:
            params["includeCompensation"] = "true"
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            jobs = data.get("jobs", [])
            
            logger.info(f"Fetched {len(jobs)} jobs from Ashby/{company_slug}")
            return jobs
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Company not found on Ashby: {company_slug}")
                return []
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch Ashby/{company_slug}: {e}")
            raise
    
    def normalize_job(self, raw_job: dict, company_slug: str) -> dict:
        """
        Transform Ashby job data to our standard schema.
        
        Args:
            raw_job: Single job dict from Ashby API
            company_slug: Source company slug (for metadata)
        
        Returns:
            Normalized job dict matching our schema
        """
        # Extract structured location if available
        address = raw_job.get("address", {}).get("postalAddress", {})
        
        # Parse compensation - prefer structured tiers, fall back to summary
        compensation = self._parse_compensation(raw_job.get("compensation"))
        
        # Map employment type to our enum
        employment_type_map = {
            "FullTime": "full_time",
            "PartTime": "part_time",
            "Contract": "contract",
            "Intern": "internship",
            "Internship": "internship",
        }
        
        return {
            # Employer
            "employer_name": company_slug,  # Will need enrichment for display name
            "department": raw_job.get("department"),
            
            # Role
            "title_display": raw_job.get("title"),
            "position_type": employment_type_map.get(
                raw_job.get("employmentType"), 
                "full_time"
            ),
            
            # Location
            "location_raw": raw_job.get("location"),
            "city": address.get("addressLocality"),
            "region": address.get("addressRegion"),
            "country": address.get("addressCountry"),
            "is_remote": raw_job.get("isRemote", False),
            
            # Compensation
            "salary_min": compensation.get("min"),
            "salary_max": compensation.get("max"),
            "salary_currency": compensation.get("currency"),
            "compensation_summary": compensation.get("summary"),
            
            # Posting metadata
            "posting_url": raw_job.get("jobUrl"),
            "apply_url": raw_job.get("applyUrl"),
            "posted_date": self._parse_date(raw_job.get("publishedAt")),
            "description_html": raw_job.get("descriptionHtml"),
            "description_plain": raw_job.get("descriptionPlain"),
            
            # Source tracking
            "source": "ashby",
            "source_id": raw_job.get("id"),
            "source_company_slug": company_slug,
            "scraped_at": datetime.utcnow().isoformat(),
        }
    
    def _parse_compensation(self, comp_data: Optional[dict]) -> dict:
        """
        Extract structured compensation from Ashby's nested format.
        
        Ashby provides compensation in multiple formats - we prefer the
        structured salaryRange in compensationTiers when available.
        """
        if not comp_data:
            return {}
        
        result = {
            "summary": comp_data.get("compensationTierSummary")
        }
        
        # Try to get structured data from tiers
        tiers = comp_data.get("compensationTiers", [])
        if tiers:
            # Use first tier (usually the primary/only one)
            tier = tiers[0]
            salary_range = tier.get("salaryRange", {})
            
            min_data = salary_range.get("min", {})
            max_data = salary_range.get("max", {})
            
            if min_data.get("value"):
                result["min"] = min_data["value"]
                result["currency"] = min_data.get("currency")
            
            if max_data.get("value"):
                result["max"] = max_data["value"]
                result["currency"] = max_data.get("currency", result.get("currency"))
        
        # Fall back to parsing the summary string if no structured data
        if "min" not in result and comp_data.get("scrapeableCompensationSalarySummary"):
            parsed = self._parse_salary_string(
                comp_data["scrapeableCompensationSalarySummary"]
            )
            result.update(parsed)
        
        return result
    
    def _parse_salary_string(self, salary_str: str) -> dict:
        """
        Parse salary strings like "£80K - £120K" or "$150,000 - $200,000"
        
        Returns dict with min, max, currency keys.
        """
        import re
        
        result = {}
        
        # Detect currency
        if "£" in salary_str:
            result["currency"] = "GBP"
        elif "$" in salary_str:
            result["currency"] = "USD"
        elif "€" in salary_str:
            result["currency"] = "EUR"
        
        # Extract numbers - handles K notation and commas
        numbers = re.findall(r'[\d,]+(?:\.\d+)?[Kk]?', salary_str)
        
        parsed_numbers = []
        for n in numbers:
            # Remove commas
            n = n.replace(",", "")
            # Handle K notation
            if n.upper().endswith("K"):
                parsed_numbers.append(float(n[:-1]) * 1000)
            else:
                try:
                    parsed_numbers.append(float(n))
                except ValueError:
                    continue
        
        if len(parsed_numbers) >= 2:
            result["min"] = int(parsed_numbers[0])
            result["max"] = int(parsed_numbers[1])
        elif len(parsed_numbers) == 1:
            # Single number - could be min or exact
            result["min"] = int(parsed_numbers[0])
        
        return result
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[str]:
        """Parse Ashby ISO date to our standard format (YYYY-MM-DD)."""
        if not date_str:
            return None
        try:
            # Ashby uses ISO 8601 with timezone
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            return None
```

### Location Mapping Helper

```python
"""
Map Ashby location data to our city_code enum.
"""

# Our target cities with variations
CITY_MAPPINGS = {
    "lon": {
        "localities": ["london"],
        "regions": ["england", "greater london"],
        "countries": ["uk", "united kingdom", "gb"],
    },
    "nyc": {
        "localities": ["new york", "new york city", "manhattan", "brooklyn", "nyc"],
        "regions": ["new york", "ny"],
        "countries": ["usa", "us", "united states"],
    },
    "den": {
        "localities": ["denver", "boulder"],
        "regions": ["colorado", "co"],
        "countries": ["usa", "us", "united states"],
    },
    "sf": {
        "localities": ["san francisco", "sf", "palo alto", "mountain view", "menlo park"],
        "regions": ["california", "ca", "bay area"],
        "countries": ["usa", "us", "united states"],
    },
    "sin": {
        "localities": ["singapore"],
        "regions": ["singapore"],
        "countries": ["singapore", "sg"],
    },
}

def map_to_city_code(
    locality: Optional[str],
    region: Optional[str], 
    country: Optional[str],
    location_raw: Optional[str] = None
) -> Optional[str]:
    """
    Map Ashby's structured location to our city_code enum.
    
    Args:
        locality: addressLocality (e.g., "London")
        region: addressRegion (e.g., "England") 
        country: addressCountry (e.g., "UK")
        location_raw: Fallback location string (e.g., "London, UK")
    
    Returns:
        City code (lon/nyc/den/sf/sin) or None if not in scope
    """
    # Normalize inputs
    loc = (locality or "").lower().strip()
    reg = (region or "").lower().strip()
    cty = (country or "").lower().strip()
    raw = (location_raw or "").lower().strip()
    
    for city_code, patterns in CITY_MAPPINGS.items():
        # Check locality first (most specific)
        if loc and any(p in loc for p in patterns["localities"]):
            return city_code
        
        # Check if raw location string contains city name
        if raw and any(p in raw for p in patterns["localities"]):
            return city_code
        
        # For cities where locality might be missing, check region+country
        # This catches cases like "California, USA" for SF area
        if reg and cty:
            region_match = any(p in reg for p in patterns["regions"])
            country_match = any(p in cty for p in patterns["countries"])
            if region_match and country_match:
                # Be careful - "California, USA" could be LA or SF
                # Only return if we have a locality hint
                if loc and any(p in loc for p in patterns["localities"]):
                    return city_code
    
    return None  # Not in our target scope


def map_working_arrangement(is_remote: bool, location_raw: str) -> str:
    """
    Determine working arrangement from Ashby data.
    
    Ashby provides isRemote boolean but doesn't distinguish hybrid.
    We infer from location string when possible.
    """
    location_lower = (location_raw or "").lower()
    
    # Check for explicit hybrid mentions
    if "hybrid" in location_lower:
        return "hybrid"
    
    # Check for explicit remote mentions
    if is_remote or "remote" in location_lower:
        # Could be fully remote or remote-first hybrid
        if any(word in location_lower for word in ["only", "fully", "100%"]):
            return "remote"
        # Default remote flag to remote (conservative)
        return "remote"
    
    # Default to onsite
    return "onsite"
```

### Batch Processing for Multiple Companies

```python
"""
Batch processor for scraping multiple Ashby companies.
"""

import time
from typing import Generator

# Sample companies using Ashby (tech companies in our scope)
# You'll want to expand this list - see Discovery section below
ASHBY_COMPANIES = [
    # Company slug -> Display name
    ("notion", "Notion"),
    ("figma", "Figma"),
    ("ramp", "Ramp"),
    ("anthropic", "Anthropic"),
    ("perplexityai", "Perplexity"),
    ("linear", "Linear"),
    ("openai", "OpenAI"),
    ("stability", "Stability AI"),
    ("replit", "Replit"),
    ("vercel", "Vercel"),
    ("supabase", "Supabase"),
    ("posthog", "PostHog"),
    ("retool", "Retool"),
    ("airtable", "Airtable"),
    ("plaid", "Plaid"),
]

def scrape_all_ashby_companies(
    companies: list[tuple[str, str]] = ASHBY_COMPANIES,
    delay_seconds: float = 1.0
) -> Generator[dict, None, None]:
    """
    Iterate through all Ashby companies, yielding normalized jobs.
    
    Args:
        companies: List of (slug, display_name) tuples
        delay_seconds: Polite delay between API calls
    
    Yields:
        Normalized job dicts ready for database insertion
    """
    scraper = AshbyScraper()
    
    for slug, display_name in companies:
        try:
            raw_jobs = scraper.fetch_jobs(slug)
            
            for raw_job in raw_jobs:
                normalized = scraper.normalize_job(raw_job, slug)
                # Enrich with display name
                normalized["employer_name_display"] = display_name
                
                # Filter to our target cities
                city_code = map_to_city_code(
                    normalized.get("city"),
                    normalized.get("region"),
                    normalized.get("country"),
                    normalized.get("location_raw")
                )
                
                if city_code:
                    normalized["city_code"] = city_code
                    yield normalized
                else:
                    # Log but skip - not in our geographic scope
                    logger.debug(
                        f"Skipping job outside scope: {normalized['title_display']} "
                        f"at {normalized['location_raw']}"
                    )
            
            # Be polite to the API
            time.sleep(delay_seconds)
            
        except Exception as e:
            logger.error(f"Failed to scrape {slug}: {e}")
            continue
```

---

## Company Discovery

### How to Find the Company Slug

The slug is the final path component of their Ashby jobs page:
- `https://jobs.ashbyhq.com/notion` → slug is `notion`
- `https://jobs.ashbyhq.com/anthropic` → slug is `anthropic`

### Finding Companies That Use Ashby

**Option 1: Manual Curation (Recommended for MVP)**
- Check career pages of target companies
- Look for `jobs.ashbyhq.com` URLs
- Build list of 50-100 high-value targets

**Option 2: Check via API**
```python
def check_company_on_ashby(slug: str) -> bool:
    """Quick check if a company uses Ashby."""
    try:
        response = requests.get(
            f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
            timeout=10
        )
        return response.status_code == 200
    except:
        return False
```

**Option 3: Third-Party Data**
- Services like TheirStack or BuiltWith track which companies use which ATS
- May require paid subscription

---

## Integration with Existing Pipeline

### Database Schema Additions

No schema changes needed if you're already storing Greenhouse/Lever jobs. The `source` field differentiates:
- `source = 'greenhouse'`
- `source = 'lever'`
- `source = 'ashby'` ← new

### Suggested File Structure

```
scrapers/
├── __init__.py
├── base_scraper.py          # Shared utilities
├── greenhouse_scraper.py    # Existing
├── lever_scraper.py         # Existing  
├── ashby_scraper.py         # New - copy from above
├── company_lists/
│   ├── greenhouse_companies.json
│   ├── lever_companies.json
│   └── ashby_companies.json  # New
└── orchestrator.py          # Runs all scrapers
```

### Orchestrator Integration

```python
# In orchestrator.py

from scrapers.ashby_scraper import scrape_all_ashby_companies

def run_daily_scrape():
    """Run all ATS scrapers and store results."""
    
    all_jobs = []
    
    # Existing scrapers
    all_jobs.extend(scrape_greenhouse())
    all_jobs.extend(scrape_lever())
    
    # Add Ashby
    all_jobs.extend(scrape_all_ashby_companies())
    
    # Dedupe and store
    store_jobs(all_jobs)
```

---

## Testing

### Quick Validation Script

```python
"""
Quick test to validate Ashby scraper works.
Run: python -m scrapers.test_ashby
"""

from ashby_scraper import AshbyScraper, map_to_city_code

def test_ashby():
    scraper = AshbyScraper()
    
    # Test with a known company
    jobs = scraper.fetch_jobs("notion")
    print(f"✓ Fetched {len(jobs)} jobs from Notion")
    
    if jobs:
        # Test normalization
        normalized = scraper.normalize_job(jobs[0], "notion")
        print(f"✓ Normalized job: {normalized['title_display']}")
        print(f"  Location: {normalized['location_raw']}")
        print(f"  Salary: {normalized.get('salary_min')} - {normalized.get('salary_max')} {normalized.get('salary_currency')}")
        
        # Test location mapping
        city_code = map_to_city_code(
            normalized.get("city"),
            normalized.get("region"),
            normalized.get("country"),
            normalized.get("location_raw")
        )
        print(f"  City code: {city_code or 'OUT OF SCOPE'}")

if __name__ == "__main__":
    test_ashby()
```

---

## Key Advantages of Ashby Data

1. **Structured Compensation** — Unlike Greenhouse/Lever where salary is buried in description text, Ashby provides `compensationTiers` with actual min/max/currency values.

2. **Explicit Remote Flag** — `isRemote` boolean, no parsing needed.

3. **Structured Location** — `postalAddress` with separate city/region/country fields.

4. **Clean Description** — Both HTML and plain text provided, no scraping needed.

5. **Published Date** — Proper ISO timestamp, not "2 days ago" text.

---

## Rate Limiting & Politeness

Ashby doesn't document rate limits, but best practices:
- **1 second delay** between company requests
- **Identify yourself** in User-Agent header
- **Cache responses** - don't re-fetch same company multiple times per day
- **Handle 429s gracefully** - exponential backoff if rate limited

---

## Common Issues

| Issue | Solution |
|-------|----------|
| 404 on company slug | Company doesn't use Ashby or slug is wrong |
| Empty jobs array | Company has no public listings (all confidential) |
| Missing compensation | Not all companies enable salary transparency |
| Location parsing fails | Fall back to `location_raw` string matching |

---

## Next Steps

1. [ ] Add `ashby_scraper.py` to scrapers directory
2. [ ] Create `ashby_companies.json` with initial target list
3. [ ] Test with 5-10 companies before full rollout
4. [ ] Add to daily orchestrator run
5. [ ] Verify deduplication works across sources
