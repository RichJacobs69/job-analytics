"""
[DEPRECATED] Employer Industry Classifier
==========================================
This module has been deprecated and merged into enrich_employer_metadata.py

Use instead:
    python -m pipeline.utilities.enrich_employer_metadata --apply

The new enrichment script:
- Uses career page text instead of job titles (fixes ai_ml over-classification)
- Combines industry classification with other metadata enrichment
- Includes rule-based pre-classification for staffing/VC/banks
- Adds anti-bias rules in the LLM prompt

Deprecation date: 2026-01-05
See: docs/temp/INDUSTRY_CLASSIFIER_ANALYSIS.md for why this was deprecated

---

[ORIGINAL DOCSTRING - kept for reference]

Employer Industry Classifier
=============================
Classifies employers into industry categories using LLM inference.

Part of: Epic - Employer Metadata Enrichment

Uses company name and sample job descriptions to infer industry classification.
See docs/schema_taxonomy.yaml for the 18-category taxonomy.

Usage:
    python -m pipeline.utilities.classify_employer_industry --dry-run
    python -m pipeline.utilities.classify_employer_industry --limit=100
    python -m pipeline.utilities.classify_employer_industry --min-jobs=5
    python -m pipeline.utilities.classify_employer_industry --force  # Reclassify existing

Options:
    --dry-run       Preview classifications without updating database
    --limit N       Only classify first N employers (default: all)
    --min-jobs N    Only classify employers with N+ jobs (default: 1)
    --force         Reclassify even if industry already set
    --batch-size N  Process N employers between saves (default: 50)
"""

import sys
sys.path.insert(0, '.')

import os
import json
import time
import argparse
from datetime import date
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

from pipeline.db_connection import supabase

# ============================================
# Gemini Configuration
# ============================================

from google import genai
from google.genai import types

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("Missing GOOGLE_API_KEY in .env file")

gemini_client = genai.Client(api_key=GOOGLE_API_KEY)

_classification_config = types.GenerateContentConfig(
    temperature=0.2,  # Lower temp for more consistent classification
    max_output_tokens=200,
    response_mime_type="application/json"
)

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
    "hardware",
    "other"
]

INDUSTRY_DESCRIPTIONS = {
    "fintech": "Tech-first financial disruptors - payments, neobanks, lending platforms, insurtech",
    "financial_services": "Traditional banks, insurers, asset managers, investment firms",
    "healthtech": "Digital health, biotech, pharma, medical devices, healthcare platforms",
    "ecommerce": "Online retail, marketplaces, delivery platforms, consumer commerce",
    "ai_ml": "AI-first companies building foundation models, AI tools, ML products",
    "consumer": "Consumer apps, social media, entertainment, gaming, content",
    "mobility": "Transportation, autonomous vehicles, logistics, fleet management",
    "proptech": "Real estate technology, property management, home services",
    "edtech": "Education technology, learning platforms, training, upskilling",
    "climate": "Clean energy, sustainability, carbon tracking, environmental tech",
    "crypto": "Blockchain, cryptocurrency, DeFi, NFTs, web3 infrastructure",
    "devtools": "Developer productivity, IDEs, CI/CD, code collaboration, infra tools",
    "data_infra": "Data platforms, analytics tools, data pipelines, BI",
    "cybersecurity": "Security software, identity management, compliance, threat detection",
    "hr_tech": "HR software, payroll, workforce management, recruiting platforms",
    "martech": "Marketing automation, analytics, CRM, customer data platforms",
    "professional_services": "Consulting, legal tech, accounting tech, business services",
    "hardware": "Hardware products, robotics, semiconductors, IoT devices",
    "other": "Diversified or industries not fitting other categories"
}

# ============================================
# Classification Prompt
# ============================================

CLASSIFICATION_PROMPT = """You are an industry classifier for tech companies. Given a company name and sample job titles, classify the company into ONE industry category.

COMPANY: {company_name}

SAMPLE JOB TITLES:
{job_titles}

---

INDUSTRY CATEGORIES (choose exactly one):
{industry_list}

CLASSIFICATION RULES:
1. Choose the category that best describes the company's CORE PRODUCT/SERVICE
2. "B2B SaaS" is NOT a category - classify by the domain they serve (e.g., Stripe = fintech, not devtools)
3. For conglomerates, use the industry most relevant to the job titles shown
4. Use "other" only if no category fits

Return JSON with:
- "industry": one of the valid category codes
- "confidence": "high", "medium", or "low"
- "reasoning": brief explanation (1 sentence)

Example response:
{{"industry": "fintech", "confidence": "high", "reasoning": "Payments and financial services company"}}
"""

def format_industry_list() -> str:
    """Format industry list for prompt."""
    lines = []
    for code in VALID_INDUSTRIES:
        desc = INDUSTRY_DESCRIPTIONS[code]
        lines.append(f"- {code}: {desc}")
    return "\n".join(lines)


def classify_employer(company_name: str, job_titles: List[str], max_retries: int = 3) -> Optional[Dict]:
    """
    Classify a single employer using Gemini.

    Args:
        company_name: Display name of the company
        job_titles: Sample job titles from this employer

    Returns:
        Dict with 'industry', 'confidence', 'reasoning', or None on failure
    """
    # Format job titles (limit to 10 for prompt size)
    titles_str = "\n".join(f"- {t}" for t in job_titles[:10])

    prompt = CLASSIFICATION_PROMPT.format(
        company_name=company_name,
        job_titles=titles_str,
        industry_list=format_industry_list()
    )

    for attempt in range(max_retries):
        try:
            response = gemini_client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
                config=_classification_config
            )
            result = json.loads(response.text)

            # Validate industry code
            industry = result.get("industry", "").lower()
            if industry not in VALID_INDUSTRIES:
                print(f"    [WARNING] Invalid industry '{industry}', defaulting to 'other'")
                result["industry"] = "other"

            return result

        except json.JSONDecodeError as e:
            print(f"    [ERROR] JSON parse error (attempt {attempt + 1}): {e}")
            time.sleep(1)
        except Exception as e:
            print(f"    [ERROR] API error (attempt {attempt + 1}): {e}")
            time.sleep(2 ** attempt)  # Exponential backoff

    return None


def get_employers_to_classify(min_jobs: int = 1, force: bool = False) -> List[Dict]:
    """
    Get employers that need classification.

    Returns list of dicts with: canonical_name, display_name, job_count
    """
    # Get employers with job counts
    # Using raw SQL via RPC for aggregation
    query = """
        SELECT
            em.canonical_name,
            em.display_name,
            em.industry,
            COUNT(ej.id) as job_count
        FROM employer_metadata em
        LEFT JOIN enriched_jobs ej ON em.canonical_name = ej.employer_name
        GROUP BY em.canonical_name, em.display_name, em.industry
        HAVING COUNT(ej.id) >= {min_jobs}
        ORDER BY COUNT(ej.id) DESC
    """.format(min_jobs=min_jobs)

    # Use simpler approach: get all employers, then filter in Python
    employers = []
    offset = 0
    batch_size = 1000

    while True:
        batch = supabase.table("employer_metadata").select(
            "canonical_name, display_name, industry"
        ).range(offset, offset + batch_size - 1).execute()

        if not batch.data:
            break

        employers.extend(batch.data)
        offset += batch_size

    # Get job counts for each employer
    job_counts = defaultdict(int)
    offset = 0

    print(f"  Counting jobs for {len(employers)} employers...")
    while True:
        batch = supabase.table("enriched_jobs").select(
            "employer_name"
        ).range(offset, offset + batch_size - 1).execute()

        if not batch.data:
            break

        for job in batch.data:
            job_counts[job["employer_name"]] += 1
        offset += batch_size

    # Filter and enrich employers
    result = []
    for emp in employers:
        job_count = job_counts.get(emp["canonical_name"], 0)

        # Skip if below min_jobs threshold
        if job_count < min_jobs:
            continue

        # Skip if already classified (unless force=True)
        if emp.get("industry") and not force:
            continue

        result.append({
            "canonical_name": emp["canonical_name"],
            "display_name": emp["display_name"],
            "job_count": job_count,
            "current_industry": emp.get("industry")
        })

    # Sort by job count descending
    result.sort(key=lambda x: x["job_count"], reverse=True)

    return result


def get_sample_job_titles(canonical_name: str, limit: int = 5) -> List[str]:
    """Get sample job titles for an employer."""
    result = supabase.table("enriched_jobs").select(
        "title_display"
    ).eq("employer_name", canonical_name).limit(limit).execute()

    return [job["title_display"] for job in result.data]


def update_employer_industry(canonical_name: str, industry: str,
                              confidence: str, reasoning: str) -> bool:
    """Update employer_metadata with industry classification."""
    try:
        supabase.table("employer_metadata").update({
            "industry": industry,
            "enrichment_source": "inferred",
            "enrichment_date": str(date.today())
        }).eq("canonical_name", canonical_name).execute()
        return True
    except Exception as e:
        print(f"    [ERROR] Failed to update {canonical_name}: {e}")
        return False


def classify_employers(
    dry_run: bool = False,
    limit: Optional[int] = None,
    min_jobs: int = 1,
    force: bool = False,
    batch_size: int = 50
):
    """
    Main classification function.
    """
    print("=" * 70)
    print("EMPLOYER INDUSTRY CLASSIFICATION")
    print("=" * 70)
    print(f"Dry run: {dry_run}")
    print(f"Limit: {limit or 'all'}")
    print(f"Min jobs: {min_jobs}")
    print(f"Force reclassify: {force}")
    print()

    # Get employers to classify
    print("[1/3] Finding employers to classify...")
    employers = get_employers_to_classify(min_jobs=min_jobs, force=force)

    if limit:
        employers = employers[:limit]

    print(f"  Found {len(employers)} employers to classify")

    if not employers:
        print("\n[DONE] No employers need classification")
        return

    # Preview top employers
    print(f"\n[PREVIEW] Top 10 employers by job count:")
    print("-" * 50)
    for emp in employers[:10]:
        current = emp.get("current_industry") or "-"
        print(f"  {emp['display_name'][:30]:<30} {emp['job_count']:>5} jobs  [{current}]")
    print("-" * 50)

    if dry_run:
        print("\n[DRY RUN] Would classify these employers (not making changes)")

    # Classify employers
    print(f"\n[2/3] Classifying {len(employers)} employers...")

    stats = {
        "success": 0,
        "failed": 0,
        "by_industry": defaultdict(int),
        "by_confidence": defaultdict(int)
    }

    for i, emp in enumerate(employers):
        canonical = emp["canonical_name"]
        display = emp["display_name"]

        # Rate limiting - 60 RPM for Gemini
        if i > 0 and i % 50 == 0:
            print(f"  ... processed {i}/{len(employers)}")
            time.sleep(1)  # Brief pause every 50

        # Get sample job titles
        job_titles = get_sample_job_titles(canonical)

        if not job_titles:
            print(f"  [{i+1}] {display}: No jobs found, skipping")
            continue

        # Classify
        result = classify_employer(display, job_titles)

        if result:
            industry = result["industry"]
            confidence = result.get("confidence", "medium")
            reasoning = result.get("reasoning", "")

            if not dry_run:
                success = update_employer_industry(
                    canonical, industry, confidence, reasoning
                )
                if success:
                    stats["success"] += 1
                else:
                    stats["failed"] += 1
            else:
                stats["success"] += 1

            stats["by_industry"][industry] += 1
            stats["by_confidence"][confidence] += 1

            # Log high-confidence only for cleaner output
            if confidence == "high" or i < 20:
                print(f"  [{i+1}] {display[:25]:<25} -> {industry:<20} ({confidence})")
        else:
            stats["failed"] += 1
            print(f"  [{i+1}] {display}: Classification failed")

    # Summary
    print("\n" + "=" * 70)
    print("[3/3] CLASSIFICATION SUMMARY")
    print("=" * 70)
    print(f"  Success: {stats['success']}")
    print(f"  Failed: {stats['failed']}")

    print(f"\n  By Industry:")
    for industry, count in sorted(stats["by_industry"].items(), key=lambda x: -x[1]):
        print(f"    {industry:<25} {count:>5}")

    print(f"\n  By Confidence:")
    for conf, count in sorted(stats["by_confidence"].items()):
        print(f"    {conf:<15} {count:>5}")

    if dry_run:
        print(f"\n[DRY RUN] No changes made to database")
    else:
        print(f"\n[DONE] Updated {stats['success']} employers")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Classify employers by industry")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    parser.add_argument("--limit", type=int, default=None, help="Max employers to classify")
    parser.add_argument("--min-jobs", type=int, default=1, help="Min jobs per employer")
    parser.add_argument("--force", action="store_true", help="Reclassify existing")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for saves")
    args = parser.parse_args()

    classify_employers(
        dry_run=args.dry_run,
        limit=args.limit,
        min_jobs=args.min_jobs,
        force=args.force,
        batch_size=args.batch_size
    )
