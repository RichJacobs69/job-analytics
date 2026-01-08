"""
Employer Metadata Enrichment
=============================
Enriches employer metadata by scraping career pages and using LLM inference.

Part of: Epic - Employer Metadata Enrichment (Phase 2)

Combines:
- Career page scraping for logo_url, website
- LLM inference for description, headquarters, ownership, founding_year, working_arrangement

Usage:
    python -m pipeline.utilities.enrich_employer_metadata --dry-run
    python -m pipeline.utilities.enrich_employer_metadata --limit=10 --apply
    python -m pipeline.utilities.enrich_employer_metadata --employer stripe,figma --apply
    python -m pipeline.utilities.enrich_employer_metadata --source greenhouse --apply
    python -m pipeline.utilities.enrich_employer_metadata --model pro --apply  # Higher quality

Options:
    --dry-run       Preview enrichment without updating database
    --apply         Apply changes to database
    --limit N       Only enrich first N employers (default: all)
    --source        Filter by ATS source: greenhouse, lever, ashby (default: all)
    --employer      Comma-separated canonical names to enrich
    --force         Re-enrich even if recently enriched
    --model         LLM model: flash (default) or pro
    --export        Export results to CSV path
    --min-days N    Skip employers enriched within N days (default: 180)
"""

import sys
sys.path.insert(0, '.')

import os
import re
import json
import time
import argparse
import requests
from datetime import date, datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

from pipeline.db_connection import supabase

# ============================================
# Gemini Configuration
# ============================================

import google.generativeai as genai

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("Missing GOOGLE_API_KEY in .env file")

genai.configure(api_key=GOOGLE_API_KEY)

# Model configurations
GEMINI_MODELS = {
    "flash": "gemini-3-flash-preview",  # Best accuracy for niche companies
    "pro": "gemini-2.5-flash",          # Stable fallback
    "lite": "gemini-2.5-flash-lite",    # Cost-effective but less accurate
}

# Track model fallbacks for reporting
_model_fallback_count = 0

def get_gemini_model(model_tier: str = "flash"):
    """Get Gemini model based on tier selection."""
    model_name = GEMINI_MODELS.get(model_tier, GEMINI_MODELS["flash"])
    return genai.GenerativeModel(
        model_name=model_name,
        generation_config={
            "temperature": 0.3,
            "max_output_tokens": 2000,  # Increased for longer descriptions
            "response_mime_type": "application/json"
        }
    )

# ============================================
# ATS URL Templates
# ============================================

ATS_URL_TEMPLATES = {
    'greenhouse': {
        'standard': 'https://job-boards.greenhouse.io/{slug}',
        'embed': 'https://boards.greenhouse.io/embed/job_board?for={slug}',
        'eu': 'https://job-boards.eu.greenhouse.io/{slug}',
        'legacy': 'https://boards.greenhouse.io/{slug}',
    },
    'lever': {
        'global': 'https://jobs.lever.co/{slug}',
        'eu': 'https://jobs.eu.lever.co/{slug}',
    },
    'ashby': {
        'default': 'https://jobs.ashbyhq.com/{slug}',
    },
    'workable': {
        'default': 'https://apply.workable.com/{slug}',
    },
}

CONFIG_PATHS = {
    'greenhouse': 'config/greenhouse/company_ats_mapping.json',
    'lever': 'config/lever/company_mapping.json',
    'ashby': 'config/ashby/company_mapping.json',
    'workable': 'config/workable/company_mapping.json',
    'adzuna': 'config/adzuna/all_employers.json',
}

# ============================================
# Industry Taxonomy (from docs/schema_taxonomy.yaml)
# ============================================

VALID_INDUSTRIES = [
    "fintech",
    "financial_services",
    "healthtech",
    "ecommerce",
    "ai_ml",
    "consumer",
    "mobility",
    "proptech",
    "edtech",
    "climate",
    "crypto",
    "devtools",
    "data_infra",
    "cybersecurity",
    "hr_tech",
    "martech",
    "professional_services",
    "productivity",
    "hardware",
    "other"
]

INDUSTRY_DESCRIPTIONS = """
- fintech: Tech-first financial disruptors - payments, neobanks, lending platforms, insurtech
- financial_services: Traditional banks, insurers, asset managers, VC/PE firms, investment firms
- healthtech: Digital health, biotech, pharma, medical devices, healthcare platforms
- ecommerce: Online retail, marketplaces, delivery platforms, consumer commerce
- ai_ml: Companies whose PRIMARY PRODUCT is AI/ML - foundation models, AI tools, ML platforms
- consumer: Consumer apps, social media, entertainment, gaming, content, media
- mobility: Transportation, autonomous vehicles, logistics, fleet management
- proptech: Real estate technology, property management, home services
- edtech: Education technology, learning platforms, training, upskilling
- climate: Clean energy, sustainability, carbon tracking, environmental tech
- crypto: Blockchain, cryptocurrency, DeFi, NFTs, web3 infrastructure
- devtools: Developer productivity, IDEs, CI/CD, code collaboration, infra tools
- data_infra: Data platforms, analytics tools, data pipelines, BI
- cybersecurity: Security software, identity management, compliance, threat detection
- hr_tech: HR software, payroll, workforce management, recruiting platforms
- martech: Marketing automation, analytics, CRM, customer data platforms
- professional_services: Consulting, staffing, recruiting, legal tech, accounting, agencies
- productivity: Work management, team collaboration, scheduling, business productivity tools (NOT developer tools)
- hardware: Hardware products, robotics, semiconductors, IoT devices
- other: Diversified or industries not fitting other categories
"""

# ============================================
# Rule-Based Pre-Classification
# ============================================

STAFFING_KEYWORDS = [
    "staffing", "recruiting", "recruitment", "talent acquisition",
    "consultancy", "consulting group", "associates", "partners llp",
    "solutions ltd", "resources", "personnel", "headhunter",
    "executive search", "employment agency"
]

VC_PE_KEYWORDS = [
    "ventures", "venture capital", "capital partners", "investment partners",
    "private equity", "growth equity", "venture fund", "capital management"
]

BANK_KEYWORDS = [
    "bank", "banking", "credit union", "savings", "trust company"
]


def pre_classify_industry(company_name: str, website: str = None) -> Optional[str]:
    """
    Rule-based pre-classification for obvious cases.
    Returns industry code or None to fall through to LLM.
    """
    name_lower = company_name.lower()

    # Staffing/recruiting agencies -> professional_services
    if any(kw in name_lower for kw in STAFFING_KEYWORDS):
        return "professional_services"

    # VC/PE firms -> financial_services
    if any(kw in name_lower for kw in VC_PE_KEYWORDS):
        return "financial_services"

    # Traditional banks -> financial_services
    if any(kw in name_lower for kw in BANK_KEYWORDS):
        return "financial_services"

    return None  # Fall through to LLM


# ============================================
# Enrichment Prompt
# ============================================

ENRICHMENT_PROMPT = """You are enriching employer metadata for a job market intelligence platform.

COMPANY: {company_name}
ATS CAREER PAGE URL: {ats_url}
(Note: This is the ATS-hosted career page, NOT necessarily the company's main website)

CAREER PAGE TEXT (excerpt):
{career_text}

---

INDUSTRY CATEGORIES (choose exactly one for field 1):
{industry_list}

CRITICAL CLASSIFICATION RULES:
- Classify based on the company's CORE PRODUCT/SERVICE, not who they hire
- ai_ml is ONLY for companies whose PRIMARY PRODUCT IS AI/ML (e.g., OpenAI, Anthropic)
- Companies that USE AI but sell something else go in their primary category
- VC/PE firms = financial_services (even if investing in tech)
- Banks with ML teams = financial_services
- Staffing/recruiting agencies = professional_services
- E-commerce with recommendation engines = ecommerce

---

Generate a JSON response with the following fields. Be accurate - use null if you don't know.

1. "industry": One of the industry codes above. Classify based on WHAT THE COMPANY SELLS, not their tech stack or hiring.

2. "website": The company's PRIMARY website domain (e.g., "stripe.com", "figma.com").
   Do NOT use the ATS URL (greenhouse.io, lever.co, ashbyhq.com).
   Use your knowledge of the company to provide their actual website.

3. "careers_url": The company's careers/jobs page URL if known (e.g., "https://stripe.com/jobs").
   This will possibly be different from the ATS URL provided above. Use null if unknown, do not just use the ATS URL.

4. "description": A rich 2-3 paragraph narrative (200-400 words) aimed at job seekers researching this company. Cover:
   - Company mission and what problem they solve
   - Core products/services and who their customers are
   - Brief founding story and key milestones if known
   - Industry position, notable achievements, funding stage if relevant
   - Company culture signals, growth trajectory, or recent news
   - Approximate company size (startup/scaleup/enterprise) if known
   Write in third person, professional but engaging tone. Be specific with product names,
   customer types, and concrete details. Avoid generic corporate filler like "innovative solutions"
   or "cutting-edge technology" - instead describe what they actually do.

5. "working_arrangement": Based on the career page text, what is the company's work policy?
   - "remote" = fully remote, remote-first, distributed
   - "hybrid" = mix of office and remote, X days in office
   - "onsite" = office-based, in-person required
   - "flexible" = employee choice, varies by role
   - null = cannot determine from available text

6. "headquarters_city": Primary HQ city, normalized as lowercase with underscores (e.g., "san_francisco", "new_york", "london", "madrid"). Use null if unknown.

7. "headquarters_state": ISO 3166-2 subdivision code for state/province/region (e.g., "CA" for California, "NY" for New York, "ENG" for England, "MD" for Madrid). Use null if unknown or not applicable.

8. "headquarters_country": ISO 3166-1 alpha-2 country code (e.g., "US", "GB", "ES"). Use null if unknown.

9. "ownership_type": One of:
   - "public" = publicly traded company
   - "private" = privately held
   - "subsidiary" = owned by another company
   - "acquired" = recently acquired
   - null = unknown

10. "parent_company": If ownership_type is "subsidiary" or "acquired", the parent company name. Otherwise null.

11. "founding_year": 4-digit year the company was founded. Use null if unknown.

Example response:
{{
  "industry": "fintech",
  "website": "stripe.com",
  "careers_url": "https://stripe.com/jobs",
  "description": "Stripe is a financial infrastructure platform that powers online payments for millions of businesses worldwide, from startups to Fortune 500 companies. Founded in 2010 by Irish brothers Patrick and John Collison, the company set out to simplify the complex world of online payments by providing developers with elegant APIs that handle everything from payment processing to fraud prevention.\n\nStripe's core products include Stripe Payments for accepting credit cards and digital wallets, Stripe Connect for marketplace and platform payments, Stripe Billing for subscriptions, and Stripe Atlas for company incorporation. The company has expanded into banking-as-a-service with Treasury and corporate cards, and financial reporting with Revenue Recognition. Valued at over $50 billion, Stripe processes hundreds of billions of dollars annually and employs thousands globally.\n\nHeadquartered in San Francisco with major offices in Dublin, Stripe is known for its engineering-driven culture and has been a pioneer in remote work. The company continues to expand its financial operating system vision, recently launching features for AI companies and crypto businesses.",
  "working_arrangement": "hybrid",
  "headquarters_city": "san_francisco",
  "headquarters_state": "CA",
  "headquarters_country": "US",
  "ownership_type": "private",
  "parent_company": null,
  "founding_year": 2010
}}

IMPORTANT: Return valid JSON only. Escape special characters in strings properly.
"""

# ============================================
# Career Page Scraping
# ============================================

def load_ats_companies(sources: List[str] = None) -> List[Dict]:
    """
    Load all companies from ATS config files.

    Returns list of dicts with: canonical_name, display_name, ats_source, slug, url_type/instance
    For Adzuna sources, slug will be None (no career page URL available).
    """
    if sources is None:
        sources = ['greenhouse', 'lever', 'ashby', 'workable', 'adzuna']

    repo_root = Path(__file__).parent.parent.parent
    companies = []

    for source in sources:
        if source not in CONFIG_PATHS:
            print(f"  [WARN] Unknown source: {source}")
            continue

        config_path = repo_root / CONFIG_PATHS[source]

        if not config_path.exists():
            print(f"  [WARN] Config not found: {config_path}")
            continue

        with open(config_path, encoding='utf-8') as f:
            data = json.load(f)

        source_data = data.get(source, {})

        for display_name, info in source_data.items():
            if source == 'adzuna':
                # Adzuna config format: {"display_name": {"canonical": "...", "job_count": N}}
                # No career page URL - LLM-only enrichment
                # Use display_name.lower() to match how seed_employer_metadata creates entries
                canonical_name = display_name.lower()
                companies.append({
                    'canonical_name': canonical_name,
                    'display_name': display_name,
                    'ats_source': source,
                    'slug': None,  # No career page
                    'url_type': None,
                    'instance': None,
                })
            else:
                # ATS config format: {"slug": "...", "url_type": "..."}
                if isinstance(info, dict):
                    slug = info.get('slug', '')
                    url_type = info.get('url_type', 'standard')
                    instance = info.get('instance', 'global')
                else:
                    slug = str(info)
                    url_type = 'standard'
                    instance = 'global'

                # Use display_name lowercased as canonical_name (matches job ingestion)
                canonical_name = display_name.lower()

                companies.append({
                    'canonical_name': canonical_name,
                    'display_name': display_name,
                    'ats_source': source,
                    'slug': slug,
                    'url_type': url_type,
                    'instance': instance,
                })

    return companies


def build_career_page_url(slug: str, ats_source: str, url_type: str = None, instance: str = None) -> str:
    """Build career page URL from slug and ATS source."""
    templates = ATS_URL_TEMPLATES.get(ats_source, {})

    if ats_source == 'greenhouse':
        template_key = url_type or 'standard'
        template = templates.get(template_key, templates.get('standard'))
    elif ats_source == 'lever':
        template_key = instance or 'global'
        template = templates.get(template_key, templates.get('global'))
    else:  # ashby, workable
        template = templates.get('default')

    return template.format(slug=slug) if template else None


def fetch_page(url: str, timeout: int = 15, retries: int = 2) -> Tuple[Optional[str], int]:
    """
    Fetch HTML from URL with retry logic.

    Returns: (html_content, status_code) or (None, error_code)
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    retry_delays = [2, 5]

    for attempt in range(retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)

            if response.status_code == 200:
                return response.text, 200
            elif response.status_code in [403, 429]:
                # Rate limited or blocked
                if attempt < retries:
                    time.sleep(retry_delays[min(attempt, len(retry_delays) - 1)])
                    continue
                return None, response.status_code
            elif response.status_code == 404:
                return None, 404
            else:
                return None, response.status_code

        except requests.exceptions.Timeout:
            if attempt < retries:
                time.sleep(retry_delays[min(attempt, len(retry_delays) - 1)])
                continue
            return None, -1  # Timeout
        except requests.exceptions.RequestException as e:
            return None, -2  # Connection error

    return None, -3  # Max retries exceeded


def extract_scraped_fields(html: str, url: str) -> Dict:
    """
    Extract metadata from HTML using BeautifulSoup.

    Returns dict with: logo_url, website, page_text
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = {
        'logo_url': None,
        'website': None,
        'page_text': '',
    }

    # Extract logo from og:image
    og_image = soup.find('meta', property='og:image')
    if og_image and og_image.get('content'):
        result['logo_url'] = og_image['content']

    # Fallback: look for apple-touch-icon or favicon
    if not result['logo_url']:
        icon = soup.find('link', rel=lambda x: x and 'icon' in x.lower() if x else False)
        if icon and icon.get('href'):
            href = icon['href']
            # Make absolute URL if relative
            if href.startswith('/'):
                parsed = urlparse(url)
                href = f"{parsed.scheme}://{parsed.netloc}{href}"
            result['logo_url'] = href

    # Extract website from og:url
    og_url = soup.find('meta', property='og:url')
    if og_url and og_url.get('content'):
        parsed = urlparse(og_url['content'])
        if parsed.netloc:
            # Clean up the domain
            domain = parsed.netloc.replace('www.', '')
            result['website'] = domain

    # Fallback: derive website from career page URL
    if not result['website']:
        parsed = urlparse(url)
        # For ATS URLs, try to extract company domain
        if 'greenhouse.io' in parsed.netloc or 'lever.co' in parsed.netloc or 'ashbyhq.com' in parsed.netloc:
            # Can't derive company website from ATS URL reliably
            pass
        else:
            result['website'] = parsed.netloc.replace('www.', '')

    # Extract page text for LLM analysis
    # Remove script and style elements
    for element in soup(['script', 'style', 'nav', 'footer', 'header']):
        element.decompose()

    # Get text content
    text = soup.get_text(separator=' ', strip=True)

    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text)

    # Truncate to reasonable size for LLM
    result['page_text'] = text[:8000]  # ~2000 tokens

    return result


# ============================================
# LLM Enrichment
# ============================================

def call_gemini_enrichment(
    company_name: str,
    ats_url: str,
    career_text: str,
    model_tier: str = "flash",
    max_retries: int = 3
) -> Optional[Dict]:
    """
    Call Gemini to enrich employer metadata including industry classification.

    Returns dict with: industry, website, careers_url, description, working_arrangement,
                       headquarters_city, headquarters_country, ownership_type,
                       parent_company, founding_year
    """
    # Check rule-based pre-classification first
    pre_classified_industry = pre_classify_industry(company_name)

    # Truncate career text if too long
    if career_text and len(career_text) > 6000:
        career_text = career_text[:6000] + "..."

    prompt = ENRICHMENT_PROMPT.format(
        company_name=company_name,
        ats_url=ats_url or "unknown",
        career_text=career_text or "No career page text available",
        industry_list=INDUSTRY_DESCRIPTIONS
    )

    model = get_gemini_model(model_tier)

    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            result = json.loads(response.text)

            # Handle case where Gemini returns array instead of object
            if isinstance(result, list):
                if len(result) > 0 and isinstance(result[0], dict):
                    result = result[0]  # Extract first element
                else:
                    raise ValueError(f"Unexpected array response: {result}")

            if not isinstance(result, dict):
                raise ValueError(f"Expected dict, got {type(result).__name__}")

            # Validate and clean response
            cleaned = {}

            # Industry classification
            industry = result.get('industry', '').lower()
            if industry in VALID_INDUSTRIES:
                # Use pre-classified if available (rule-based has priority)
                cleaned['industry'] = pre_classified_industry or industry
            else:
                cleaned['industry'] = pre_classified_industry or 'other'

            # Website (LLM-inferred, not from scraping)
            website = result.get('website')
            if website:
                # Clean up the website - remove protocol, trailing slashes
                website = website.lower().strip()
                website = website.replace('https://', '').replace('http://', '')
                website = website.rstrip('/')
                # Reject if it's an ATS domain
                if any(ats in website for ats in ['greenhouse.io', 'lever.co', 'ashbyhq.com']):
                    website = None
            cleaned['website'] = website

            # Careers URL - direct link to company careers/jobs page
            cleaned['careers_url'] = result.get('careers_url')

            # Description (required)
            cleaned['description'] = result.get('description')
            if cleaned['description'] and len(cleaned['description']) < 50:
                cleaned['description'] = None  # Too short, likely garbage

            # Working arrangement (validate enum)
            wa = result.get('working_arrangement')
            if wa in ['remote', 'hybrid', 'onsite', 'flexible']:
                cleaned['working_arrangement'] = wa
            else:
                cleaned['working_arrangement'] = None

            # Headquarters - normalize to standards
            # City: lowercase with underscores
            city = result.get('headquarters_city')
            if city:
                city = str(city).lower().strip()
                city = re.sub(r'[\s-]+', '_', city)  # spaces/hyphens to underscores
                city = re.sub(r'[^a-z_]', '', city)  # remove non-alpha
                cleaned['headquarters_city'] = city if city else None
            else:
                cleaned['headquarters_city'] = None

            # State: ISO 3166-2 subdivision (2-3 letter code, uppercase)
            state = result.get('headquarters_state')
            if state:
                state = str(state).upper().strip()
                # Valid subdivision codes are 1-3 alphanumeric chars
                if re.match(r'^[A-Z0-9]{1,3}$', state):
                    cleaned['headquarters_state'] = state
                else:
                    cleaned['headquarters_state'] = None
            else:
                cleaned['headquarters_state'] = None

            # Country: ISO 3166-1 alpha-2 (2 letters, uppercase)
            country = result.get('headquarters_country')
            if country:
                country = str(country).upper().strip()
                if re.match(r'^[A-Z]{2}$', country):
                    cleaned['headquarters_country'] = country
                else:
                    cleaned['headquarters_country'] = None
            else:
                cleaned['headquarters_country'] = None

            # Ownership
            ownership = result.get('ownership_type')
            if ownership in ['public', 'private', 'subsidiary', 'acquired']:
                cleaned['ownership_type'] = ownership
            else:
                cleaned['ownership_type'] = None

            cleaned['parent_company'] = result.get('parent_company')

            # Founding year (validate range)
            year = result.get('founding_year')
            if year and isinstance(year, int) and 1800 <= year <= date.today().year:
                cleaned['founding_year'] = year
            else:
                cleaned['founding_year'] = None

            return cleaned

        except json.JSONDecodeError as e:
            print(f"    [WARN] JSON parse error (attempt {attempt + 1}): {e}")
            # Try to repair common JSON issues
            if attempt < max_retries - 1:
                try:
                    # Attempt to fix unterminated strings by finding last valid JSON
                    raw_text = response.text if 'response' in dir() else ""
                    # Try truncating at last complete field
                    for end_pattern in ['}\n}', '"}', 'null}', '}']:
                        idx = raw_text.rfind(end_pattern)
                        if idx > 0:
                            fixed = raw_text[:idx + len(end_pattern)]
                            result = json.loads(fixed)
                            print(f"    [INFO] Recovered partial JSON")
                            # Continue with partial result (will be validated above)
                            break
                except:
                    pass
            time.sleep(1)
        except Exception as e:
            print(f"    [ERROR] API error (attempt {attempt + 1}): {e}")
            time.sleep(2 ** attempt)  # Exponential backoff

    # If all retries failed with flash (gemini-3-preview), try fallback to stable model
    if model_tier == "flash":
        global _model_fallback_count
        _model_fallback_count += 1
        print(f"    [INFO] Falling back to stable model (gemini-2.5-flash)...")
        return call_gemini_enrichment(
            company_name=company_name,
            ats_url=ats_url,
            career_text=career_text,
            model_tier="pro",  # Fallback to gemini-2.5-flash
            max_retries=2
        )

    return None


def get_model_fallback_count() -> int:
    """Get the number of times the model fell back from flash to pro."""
    return _model_fallback_count


def reset_model_fallback_count():
    """Reset the fallback counter (for testing)."""
    global _model_fallback_count
    _model_fallback_count = 0


# ============================================
# Database Operations
# ============================================

def get_employers_to_enrich(
    ats_companies: List[Dict],
    employer_filter: List[str] = None,
    min_days: int = 180,
    force: bool = False
) -> List[Dict]:
    """
    Get employers that need enrichment.

    Filters by:
    - Employer exists in employer_metadata
    - enrichment_date is NULL or > min_days ago
    - OR force=True
    """
    # Get canonical names from ATS companies
    ats_canonical_names = {c['canonical_name']: c for c in ats_companies}

    # Apply employer filter if specified
    if employer_filter:
        filter_lower = [e.lower() for e in employer_filter]
        ats_canonical_names = {
            k: v for k, v in ats_canonical_names.items()
            if k in filter_lower or v['display_name'].lower() in filter_lower
        }

    # Get current enrichment status from database
    offset = 0
    batch_size = 1000
    db_employers = {}

    while True:
        batch = supabase.table("employer_metadata").select(
            "canonical_name, display_name, enrichment_date, working_arrangement_source, description"
        ).range(offset, offset + batch_size - 1).execute()

        if not batch.data:
            break

        for emp in batch.data:
            db_employers[emp['canonical_name']] = emp
        offset += batch_size

    # Filter to employers that need enrichment
    cutoff_date = date.today().replace(day=1)  # First of current month as rough cutoff

    result = []
    for canonical_name, ats_info in ats_canonical_names.items():
        db_info = db_employers.get(canonical_name)

        if not db_info:
            # Not in database yet - skip (should be seeded first)
            continue

        # Check if needs enrichment
        needs_enrichment = False

        if force:
            needs_enrichment = True
        elif not db_info.get('description'):
            # No description yet
            needs_enrichment = True
        elif not db_info.get('enrichment_date'):
            # Never enriched
            needs_enrichment = True
        else:
            # Check age
            try:
                enrichment_date = datetime.strptime(db_info['enrichment_date'], '%Y-%m-%d').date()
                days_since = (date.today() - enrichment_date).days
                if days_since > min_days:
                    needs_enrichment = True
            except:
                needs_enrichment = True

        if needs_enrichment:
            result.append({
                **ats_info,
                'db_display_name': db_info.get('display_name', ats_info['display_name']),
                'working_arrangement_source': db_info.get('working_arrangement_source'),
                'has_description': bool(db_info.get('description')),
            })

    return result


def update_employer_metadata(
    canonical_name: str,
    scraped: Dict,
    llm_enrichment: Dict,
    dry_run: bool = False
) -> bool:
    """
    Update employer_metadata with enrichment data.

    Source priority: manual > scraped > inferred
    """
    if dry_run:
        return True

    try:
        # Get current record to check source priorities
        current = supabase.table("employer_metadata").select(
            "working_arrangement_source, logo_url, website, careers_url, description"
        ).eq("canonical_name", canonical_name).single().execute()

        if not current.data:
            return False

        updates = {
            'enrichment_source': 'scraped',
            'enrichment_date': str(date.today()),
        }

        # Scraped fields (logo only - website comes from LLM now)
        if scraped.get('logo_url') and not current.data.get('logo_url'):
            updates['logo_url'] = scraped['logo_url']

        # LLM enrichment fields
        if llm_enrichment:
            # Industry - always update (new classification is better than old)
            if llm_enrichment.get('industry'):
                updates['industry'] = llm_enrichment['industry']

            # Website - from LLM inference (not scraped ATS URL)
            if llm_enrichment.get('website') and not current.data.get('website'):
                updates['website'] = llm_enrichment['website']

            # Careers URL - direct link to careers/jobs page
            if llm_enrichment.get('careers_url') and not current.data.get('careers_url'):
                updates['careers_url'] = llm_enrichment['careers_url']

            # Description - always update if we have one
            if llm_enrichment.get('description'):
                updates['description'] = llm_enrichment['description']

            # Working arrangement - respect source priority
            current_source = current.data.get('working_arrangement_source')
            if llm_enrichment.get('working_arrangement'):
                if current_source != 'manual':  # scraped can override inferred
                    updates['working_arrangement_default'] = llm_enrichment['working_arrangement']
                    updates['working_arrangement_source'] = 'scraped'

            # Other LLM fields - update if we have them
            if llm_enrichment.get('headquarters_city'):
                updates['headquarters_city'] = llm_enrichment['headquarters_city']
            if llm_enrichment.get('headquarters_state'):
                updates['headquarters_state'] = llm_enrichment['headquarters_state']
            if llm_enrichment.get('headquarters_country'):
                updates['headquarters_country'] = llm_enrichment['headquarters_country']
            if llm_enrichment.get('ownership_type'):
                updates['ownership_type'] = llm_enrichment['ownership_type']
            if llm_enrichment.get('parent_company'):
                updates['parent_company'] = llm_enrichment['parent_company']
            if llm_enrichment.get('founding_year'):
                updates['founding_year'] = llm_enrichment['founding_year']

        supabase.table("employer_metadata").update(updates).eq(
            "canonical_name", canonical_name
        ).execute()

        return True

    except Exception as e:
        print(f"    [ERROR] Failed to update {canonical_name}: {e}")
        return False


# ============================================
# Main Enrichment Function
# ============================================

def enrich_employer_metadata(
    sources: List[str] = None,
    employer_filter: List[str] = None,
    limit: Optional[int] = None,
    dry_run: bool = True,
    force: bool = False,
    model_tier: str = "flash",
    min_days: int = 180,
    export_path: Optional[str] = None,
    rate_limit: float = 1.0
):
    """
    Main enrichment function.
    """
    if sources is None:
        sources = ['greenhouse', 'lever', 'ashby', 'workable', 'adzuna']

    print("=" * 70)
    print("EMPLOYER METADATA ENRICHMENT")
    print("=" * 70)
    print(f"Mode: {'DRY RUN' if dry_run else 'APPLY'}")
    print(f"Sources: {', '.join(sources)}")
    print(f"Model: {model_tier} ({GEMINI_MODELS.get(model_tier, 'unknown')})")
    print(f"Limit: {limit or 'all'}")
    print(f"Force re-enrich: {force}")
    print(f"Min days since last enrichment: {min_days}")
    print()

    # Load ATS companies
    print("[1/4] Loading ATS configs...")
    ats_companies = load_ats_companies(sources)
    print(f"  Loaded {len(ats_companies)} companies from ATS configs")

    for source in sources:
        count = len([c for c in ats_companies if c['ats_source'] == source])
        print(f"    {source}: {count}")

    # Get employers to enrich
    print("\n[2/4] Finding employers to enrich...")
    employers = get_employers_to_enrich(
        ats_companies,
        employer_filter=employer_filter,
        min_days=min_days,
        force=force
    )

    if limit:
        employers = employers[:limit]

    print(f"  Found {len(employers)} employers to enrich")

    if not employers:
        print("\n[DONE] No employers need enrichment")
        return

    # Preview
    print(f"\n[PREVIEW] First 10 employers:")
    print("-" * 60)
    for emp in employers[:10]:
        desc_status = "[has desc]" if emp.get('has_description') else "[no desc]"
        print(f"  {emp['display_name'][:35]:<35} {emp['ats_source']:<10} {desc_status}")
    print("-" * 60)

    # Enrich employers
    print(f"\n[3/4] Enriching {len(employers)} employers...")

    stats = {
        'success': 0,
        'scrape_failed': 0,
        'llm_failed': 0,
        'db_failed': 0,
        'fields_updated': {
            'industry': 0,
            'logo_url': 0,
            'website': 0,
            'description': 0,
            'working_arrangement': 0,
            'headquarters': 0,
            'ownership': 0,
            'founding_year': 0,
        }
    }

    results = []

    for i, emp in enumerate(employers):
        canonical = emp['canonical_name']
        display = emp['db_display_name'] or emp['display_name']

        # Progress indicator
        if i > 0 and i % 20 == 0:
            print(f"  ... processed {i}/{len(employers)}")

        # Build career page URL (None for Adzuna - no career page)
        if emp.get('slug'):
            career_url = build_career_page_url(
                emp['slug'],
                emp['ats_source'],
                emp.get('url_type'),
                emp.get('instance')
            )
        else:
            career_url = None  # Adzuna - LLM-only enrichment

        # Scrape career page (skip for Adzuna)
        if career_url:
            html, status = fetch_page(career_url)

            if not html:
                print(f"  [{i+1}] {display[:30]:<30} [SCRAPE FAIL: {status}]")
                stats['scrape_failed'] += 1
                # Still try LLM with just company name
                scraped = {'logo_url': None, 'website': None, 'page_text': ''}
            else:
                scraped = extract_scraped_fields(html, career_url)
        else:
            # Adzuna: LLM-only, no scraping
            scraped = {'logo_url': None, 'website': None, 'page_text': ''}

        # Call LLM for enrichment (includes industry classification)
        llm_result = call_gemini_enrichment(
            company_name=display,
            ats_url=career_url,
            career_text=scraped.get('page_text', ''),
            model_tier=model_tier
        )

        if not llm_result:
            print(f"  [{i+1}] {display[:30]:<30} [LLM FAIL]")
            stats['llm_failed'] += 1
            continue

        # Update database
        success = update_employer_metadata(
            canonical_name=canonical,
            scraped=scraped,
            llm_enrichment=llm_result,
            dry_run=dry_run
        )

        if success:
            stats['success'] += 1

            # Track what was updated
            if llm_result.get('industry'):
                stats['fields_updated']['industry'] += 1
            if scraped.get('logo_url'):
                stats['fields_updated']['logo_url'] += 1
            if llm_result.get('website'):
                stats['fields_updated']['website'] += 1
            if llm_result.get('description'):
                stats['fields_updated']['description'] += 1
            if llm_result.get('working_arrangement'):
                stats['fields_updated']['working_arrangement'] += 1
            if llm_result.get('headquarters_city'):
                stats['fields_updated']['headquarters'] += 1
            if llm_result.get('ownership_type'):
                stats['fields_updated']['ownership'] += 1
            if llm_result.get('founding_year'):
                stats['fields_updated']['founding_year'] += 1

            # Log success - show all fields
            print(f"\n  [{i+1}/{len(employers)}] {display}")
            print(f"      industry:      {llm_result.get('industry', '-')}")
            print(f"      work_arr:      {llm_result.get('working_arrangement', '-')}")
            print(f"      headquarters:  {llm_result.get('headquarters_city', '-')}, {llm_result.get('headquarters_state', '-')}, {llm_result.get('headquarters_country', '-')}")
            print(f"      ownership:     {llm_result.get('ownership_type', '-')}")
            print(f"      founded:       {llm_result.get('founding_year', '-')}")
            print(f"      logo:          {'[OK]' if scraped.get('logo_url') else '[-]'}")
            print(f"      website:       {llm_result.get('website', '-')}")
            print(f"      careers_url:   {llm_result.get('careers_url', '-')}")
            desc = llm_result.get('description', '')
            print(f"      description:   {desc[:80]}..." if desc else "      description:   -")

            # Store for export
            results.append({
                'canonical_name': canonical,
                'display_name': display,
                'ats_source': emp['ats_source'],
                'industry': llm_result.get('industry'),
                'logo_url': scraped.get('logo_url'),
                'website': llm_result.get('website'),
                'careers_url': llm_result.get('careers_url'),
                'description': llm_result.get('description', '')[:200] + '...' if llm_result.get('description') else '',
                'working_arrangement': llm_result.get('working_arrangement'),
                'headquarters_city': llm_result.get('headquarters_city'),
                'headquarters_country': llm_result.get('headquarters_country'),
                'ownership_type': llm_result.get('ownership_type'),
                'founding_year': llm_result.get('founding_year'),
            })
        else:
            stats['db_failed'] += 1
            print(f"  [{i+1}] {display[:30]:<30} [DB FAIL]")

        # Rate limiting
        time.sleep(rate_limit)

    # Summary
    print("\n" + "=" * 70)
    print("[4/4] ENRICHMENT SUMMARY")
    print("=" * 70)
    print(f"  Success:       {stats['success']}")
    print(f"  Scrape failed: {stats['scrape_failed']}")
    print(f"  LLM failed:    {stats['llm_failed']}")
    print(f"  DB failed:     {stats['db_failed']}")

    fallback_count = get_model_fallback_count()
    if fallback_count > 0:
        print(f"  Model fallbacks: {fallback_count} (gemini-3-preview -> gemini-2.5-flash)")

    print(f"\n  Fields populated:")
    for field, count in stats['fields_updated'].items():
        pct = (count / stats['success'] * 100) if stats['success'] > 0 else 0
        print(f"    {field:<25} {count:>5} ({pct:.1f}%)")

    if dry_run:
        print(f"\n[DRY RUN] No changes made to database")
    else:
        print(f"\n[DONE] Updated {stats['success']} employers")

    # Export if requested
    if export_path and results:
        import csv
        with open(export_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        print(f"\n[EXPORT] Results saved to {export_path}")


# ============================================
# CLI
# ============================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Enrich employer metadata via career page scraping + LLM",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without database changes")
    parser.add_argument("--apply", action="store_true",
                        help="Apply changes to database")
    parser.add_argument("--source", type=str, default=None,
                        help="ATS source filter: greenhouse,lever,ashby")
    parser.add_argument("--employer", type=str, default=None,
                        help="Comma-separated canonical names to enrich")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max employers to enrich")
    parser.add_argument("--force", action="store_true",
                        help="Re-enrich even if recently enriched")
    parser.add_argument("--model", type=str, choices=["flash", "pro", "lite"], default="flash",
                        help="LLM model tier (default: flash)")
    parser.add_argument("--min-days", type=int, default=180,
                        help="Skip if enriched within N days (default: 180)")
    parser.add_argument("--export", type=str, default=None,
                        help="Export results to CSV path")
    parser.add_argument("--rate-limit", type=float, default=1.0,
                        help="Seconds between requests (default: 1.0)")

    args = parser.parse_args()

    # Determine mode
    if args.apply:
        dry_run = False
    else:
        dry_run = True  # Default to dry run for safety

    # Parse sources
    sources = None
    if args.source:
        sources = [s.strip() for s in args.source.split(',')]

    # Parse employer filter
    employer_filter = None
    if args.employer:
        employer_filter = [e.strip() for e in args.employer.split(',')]

    enrich_employer_metadata(
        sources=sources,
        employer_filter=employer_filter,
        limit=args.limit,
        dry_run=dry_run,
        force=args.force,
        model_tier=args.model,
        min_days=args.min_days,
        export_path=args.export,
        rate_limit=args.rate_limit
    )
