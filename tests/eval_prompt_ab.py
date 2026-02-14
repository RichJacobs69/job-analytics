"""
A/B Test: Classifier Prompt V1 vs V2

Classifies the same real jobs with both prompts via the production classify path,
then compares results. Uses Ashby, Lever, and Workable APIs to fetch fresh, diverse
postings. Pool-then-bucket sampling ensures coverage across job families, sources,
and regions.

Compared fields:
    - job_subfamily / job_family  (role classification)
    - seniority                   (intern -> director_plus)
    - track                       (IC vs Manager)
    - working_arrangement         (remote / hybrid / onsite)
    - skills                      (extracted list, Jaccard similarity + per-skill diffs)
    - summary                     (presence check)
    - input token count           (prompt cost comparison)

Outputs:
    - Console: per-job comparison + summary statistics
    - CSV:     temp/eval_prompt_ab_<timestamp>.csv with full classified output per job

Usage:
    python tests/eval_prompt_ab.py                          # Default: 10 jobs
    python tests/eval_prompt_ab.py --sample 20              # More samples
    python tests/eval_prompt_ab.py --verbose                # Show full skill lists and diffs
    python tests/eval_prompt_ab.py --seed 42                # Reproducible sampling
    python tests/eval_prompt_ab.py --sample 12 --seed 42    # Combined
"""
import argparse
import csv
import json
import os
import random
import re
import sys
import time
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from pipeline.classifier import (
    _classify_job_with_model,
    build_classification_prompt,
    build_classification_prompt_v2,
    adapt_prompt_for_gemini,
    get_gemini_model_for_source,
    gemini_client,
    _gemini_generation_config,
    sanitize_null_strings,
    PROVIDER_COSTS,
    _get_model_costs,
    GEMINI_FALLBACK_MODEL,
)
from pipeline.job_family_mapper import get_correct_job_family
from pipeline.skill_family_mapper import enrich_skills_with_families

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("[ERROR] Missing GOOGLE_API_KEY in .env")
    sys.exit(1)

# Primary model (Gemini 3 Flash Preview for ATS sources)
MODEL = get_gemini_model_for_source("ashby")
# Fallback model matches production behaviour
FALLBACK_MODEL = GEMINI_FALLBACK_MODEL

# Diverse company roster: (source, slug, instance_or_none, region)
# Covers UK, US, Singapore; product-heavy, data-heavy, delivery-likely, engineering
COMPANY_ROSTER = [
    # Ashby - US
    ("ashby", "notion", None, "us"),
    ("ashby", "ramp", None, "us"),           # Fintech, PM-heavy
    ("ashby", "linear", None, "us"),         # Dev tools
    ("ashby", "retool", None, "us"),         # PM-heavy
    ("ashby", "cohere", None, "us"),         # ML/AI
    ("ashby", "snowflake", None, "us"),      # Data platform, high volume
    ("ashby", "airtable", None, "us"),       # Product SaaS
    ("ashby", "perplexity", None, "us"),     # AI search, ML-heavy
    ("ashby", "zapier", None, "us"),         # Automation, PM/data
    ("ashby", "clickup", None, "us"),        # Productivity, PM-heavy
    ("ashby", "openai", None, "us"),         # AI, strong delivery + data + product
    # Ashby - UK
    ("ashby", "deliveroo", None, "uk"),
    ("ashby", "incident", None, "uk"),       # incident.io
    ("ashby", "posthog", None, "uk"),
    ("ashby", "eightsleep", None, "uk"),     # Data/product/delivery mix
    # Lever - US
    ("lever", "zoox", "global", "us"),       # ML/robotics
    ("lever", "palantir", "global", "us"),   # Data-heavy, high volume
    ("lever", "attentive", "global", "us"),  # Product/marketing
    ("lever", "gohighlevel", "global", "us"),# Marketing SaaS, product-heavy
    ("lever", "outreach", "global", "us"),   # Product + delivery
    # Lever - UK
    ("lever", "wise", "global", "uk"),       # London fintech
    ("lever", "octoenergy", "global", "uk"), # London energy, high volume
    ("lever", "spotify", "global", "uk"),    # Massive data/product/analytics
    ("lever", "mistral", "global", "uk"),    # AI/LLM, ML-heavy
    ("lever", "zopa", "global", "uk"),       # UK fintech, data/product
    ("lever", "welocalize", "global", "us"), # Data + delivery, zero OOS
    # Lever - Singapore
    ("lever", "shopback-2", "global", "sg"),
    ("lever", "binance", "global", "sg"),    # Crypto, data + product at scale
    # Workable - UK
    ("workable", "starling-bank", None, "uk"),  # London fintech
    ("workable", "quantexa", None, "uk"),       # Data intelligence
    ("workable", "unison consulting", None, "uk"),  # Delivery + data
    # Workable - US
    ("workable", "rokt", None, "us"),           # Ecommerce platform
    ("workable", "tetrascience", None, "us"),   # Scientific data platform
]

JOBS_PER_COMPANY = 15  # Max jobs to fetch per company for the pool

# CSV output directory
TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp")


# ============================================
# Title-based Family Guessing
# ============================================

_title_patterns_cache = None


def _load_title_patterns() -> List[Tuple[str, List[re.Pattern]]]:
    """Load title patterns from config and group them by family."""
    global _title_patterns_cache
    if _title_patterns_cache is not None:
        return _title_patterns_cache

    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", "greenhouse", "title_patterns.yaml",
    )
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    raw_patterns = config.get("relevant_title_patterns", [])

    # Classify each pattern into a family based on keyword heuristics.
    # The YAML groups patterns under DATA, PRODUCT, DELIVERY comments.
    data_keywords = [
        "data", "analyst", "analytics", "bi ", "business intelligence",
        "machine learning", "ml ", "ai ", "mlops", "scientist", "research scientist",
    ]
    product_keywords = [
        "product manager", "product owner", "product", "pm", "growth pm",
        "platform pm", "cpo", "chief product",
    ]
    delivery_keywords = [
        "delivery", "project manager", "program", "scrum", "agile",
        "release manager", "iteration manager", "pmo",
    ]

    def classify_pattern(pat_str: str) -> str:
        pat_lower = pat_str.lower()
        for kw in data_keywords:
            if kw in pat_lower:
                return "data"
        for kw in product_keywords:
            if kw in pat_lower:
                return "product"
        for kw in delivery_keywords:
            if kw in pat_lower:
                return "delivery"
        return "data"  # Default for ambiguous patterns

    family_patterns = {"data": [], "product": [], "delivery": []}
    for pat_str in raw_patterns:
        family = classify_pattern(pat_str)
        try:
            compiled = re.compile(pat_str, re.IGNORECASE)
            family_patterns[family].append(compiled)
        except re.error:
            pass

    _title_patterns_cache = [
        (fam, pats) for fam, pats in family_patterns.items()
    ]
    return _title_patterns_cache


def guess_family_from_title(title: str) -> str:
    """Bucket a title into product/data/delivery/out_of_scope using existing regex patterns."""
    patterns_by_family = _load_title_patterns()
    for family, patterns in patterns_by_family:
        for pat in patterns:
            if pat.search(title):
                return family
    return "out_of_scope"


# ============================================
# Job Fetching
# ============================================

def _fetch_from_source(source: str, slug: str, instance: Optional[str]) -> List[Dict]:
    """Fetch unfiltered jobs from a single company. Returns list of job dicts."""
    jobs = []
    try:
        if source == "ashby":
            from scrapers.ashby.ashby_fetcher import fetch_ashby_jobs
            fetched, _ = fetch_ashby_jobs(slug, filter_titles=False, filter_locations=False)
            for job in fetched[:JOBS_PER_COMPANY]:
                jobs.append({
                    "source": "ashby",
                    "title": job.title,
                    "company": slug,
                    "description": job.description,
                    "salary_min": job.salary_min,
                    "salary_max": job.salary_max,
                })
        elif source == "lever":
            from scrapers.lever.lever_fetcher import fetch_lever_jobs
            fetched, _ = fetch_lever_jobs(
                slug, instance=instance or "global",
                filter_titles=False, filter_locations=False,
            )
            for job in fetched[:JOBS_PER_COMPANY]:
                jobs.append({
                    "source": "lever",
                    "title": job.title,
                    "company": slug,
                    "description": job.description,
                    "salary_min": None,
                    "salary_max": None,
                })
        elif source == "workable":
            from scrapers.workable.workable_fetcher import fetch_workable_jobs
            fetched, _ = fetch_workable_jobs(slug, filter_titles=False, filter_locations=False)
            for job in fetched[:JOBS_PER_COMPANY]:
                jobs.append({
                    "source": "workable",
                    "title": job.title,
                    "company": slug,
                    "description": job.description,
                    "salary_min": job.salary_min,
                    "salary_max": job.salary_max,
                })
    except Exception as e:
        print(f"  [WARN] {source}/{slug}: {e}")
    return jobs


def _pick_diverse(jobs: List[Dict], n: int) -> List[Dict]:
    """Pick up to n jobs, prioritizing different (source, region) combos."""
    if len(jobs) <= n:
        return list(jobs)

    # Group by (source, region)
    groups = {}
    for job in jobs:
        key = (job["source"], job.get("region", "?"))
        groups.setdefault(key, []).append(job)

    picked = []
    # Round-robin across groups
    while len(picked) < n:
        added_this_round = False
        for key in list(groups.keys()):
            if len(picked) >= n:
                break
            if groups[key]:
                picked.append(groups[key].pop(0))
                added_this_round = True
            if not groups[key]:
                del groups[key]
        if not added_this_round:
            break

    return picked


def _select_diverse_sample(buckets: Dict[str, List[Dict]], target_count: int,
                           exclude_oos: bool = False) -> List[Dict]:
    """Select a balanced sample across family buckets with source/region diversity.

    If exclude_oos is True, out_of_scope jobs are excluded entirely and the full
    budget goes to relevant families.  Otherwise, OOS is capped at 20% of target.
    """
    relevant_families = [f for f in buckets if f != "out_of_scope"]

    if exclude_oos:
        oos_cap = 0
        relevant_budget = target_count
    else:
        oos_cap = max(target_count // 5, 2)
        relevant_budget = target_count - oos_cap

    per_relevant = max(relevant_budget // max(len(relevant_families), 1), 1)

    selected = []
    overflow = []

    # Pick from relevant families first
    for family in relevant_families:
        jobs = buckets.get(family, [])
        random.shuffle(jobs)
        picked = _pick_diverse(jobs, per_relevant)
        selected.extend(picked)
        picked_set = set(id(j) for j in picked)
        overflow.extend(j for j in jobs if id(j) not in picked_set)

    # Pick capped out_of_scope (skipped when exclude_oos)
    if not exclude_oos:
        oos_jobs = buckets.get("out_of_scope", [])
        random.shuffle(oos_jobs)
        oos_picked = _pick_diverse(oos_jobs, oos_cap)
        selected.extend(oos_picked)
        oos_picked_set = set(id(j) for j in oos_picked)
        overflow.extend(j for j in oos_jobs if id(j) not in oos_picked_set)

    # Fill remaining slots from overflow (relevant families only when excluding OOS)
    remaining = target_count - len(selected)
    if remaining > 0:
        rel_overflow = [j for j in overflow if j.get("_guessed_family") != "out_of_scope"]
        random.shuffle(rel_overflow)
        selected.extend(rel_overflow[:remaining])
        remaining = target_count - len(selected)
        if remaining > 0 and not exclude_oos:
            oos_overflow = [j for j in overflow if j.get("_guessed_family") == "out_of_scope"]
            random.shuffle(oos_overflow)
            selected.extend(oos_overflow[:remaining])

    return selected[:target_count]


def fetch_sample_jobs(target_count: int, exclude_oos: bool = False) -> List[Dict]:
    """Fetch a diverse pool of jobs, then sample evenly across family buckets."""
    print(f"  Fetching from {len(COMPANY_ROSTER)} companies across 3 sources...")
    pool = []
    for source, slug, instance, region in COMPANY_ROSTER:
        fetched = _fetch_from_source(source, slug, instance)
        for job in fetched:
            job["region"] = region
            job["_guessed_family"] = guess_family_from_title(job["title"])
            pool.append(job)

    print(f"  Pool: {len(pool)} jobs from {len(set(j['company'] for j in pool))} companies")

    if not pool:
        return []

    # Bucket by guessed family
    buckets = {"product": [], "data": [], "delivery": [], "out_of_scope": []}
    for job in pool:
        buckets[job["_guessed_family"]].append(job)

    bucket_summary = ", ".join(f"{len(v)} {k}" for k, v in buckets.items() if v)
    print(f"  Pool breakdown: {bucket_summary}")

    selected = _select_diverse_sample(buckets, target_count, exclude_oos=exclude_oos)
    return selected


def _format_distribution(jobs: List[Dict]) -> str:
    """Format a one-line distribution summary for the selected sample."""
    family_counts = Counter(j.get("_guessed_family", "?") for j in jobs)
    source_counts = Counter(j["source"] for j in jobs)
    region_counts = Counter(j.get("region", "?") for j in jobs)

    family_str = ", ".join(f"{v} {k}" for k, v in sorted(family_counts.items()))
    source_str = ", ".join(f"{v} {k}" for k, v in sorted(source_counts.items()))
    region_str = ", ".join(f"{v} {k}" for k, v in sorted(region_counts.items()))
    return f"{family_str} | {source_str} | {region_str}"


# ============================================
# Classification (uses production code paths)
# ============================================

def _classify_v1(job: Dict, model: str = None) -> Dict:
    """Classify using the production V1 path (build_classification_prompt + adapt_prompt_for_gemini)."""
    model = model or MODEL
    structured_input = {
        "title": job["title"],
        "company": job["company"],
        "description": job["description"],
        "location": None,
        "category": None,
        "salary_min": job.get("salary_min"),
        "salary_max": job.get("salary_max"),
    }
    result = _classify_job_with_model(
        job["description"], model,
        verbose=False, structured_input=structured_input,
    )
    result['_model_used'] = model
    return result


def _classify_v2(job: Dict, model: str = None) -> Dict:
    """Classify using V2 prompt (build_classification_prompt_v2), same post-processing as production."""
    model = model or MODEL
    structured_input = {
        "title": job["title"],
        "company": job["company"],
        "description": job["description"],
        "location": None,
        "category": None,
        "salary_min": job.get("salary_min"),
        "salary_max": job.get("salary_max"),
    }

    prompt = build_classification_prompt_v2(job["description"], structured_input=structured_input)

    start_time = time.time()
    response = gemini_client.models.generate_content(
        model=model,
        contents=prompt,
        config=_gemini_generation_config,
    )
    latency_ms = (time.time() - start_time) * 1000

    usage = response.usage_metadata
    input_tokens = usage.prompt_token_count if usage else 0
    output_tokens = usage.candidates_token_count if usage else 0

    costs = _get_model_costs(model)
    input_cost = (input_tokens / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]
    total_cost = input_cost + output_cost

    cost_data = {
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'input_cost': input_cost,
        'output_cost': output_cost,
        'total_cost': total_cost,
        'latency_ms': latency_ms,
        'provider': 'gemini',
        'model': model,
    }

    result = json.loads(response.text)
    result = sanitize_null_strings(result)

    if isinstance(result, list):
        result = result[0] if result else {}

    if 'employer' not in result:
        result['employer'] = {}
    result['employer']['is_agency'] = None
    result['employer']['agency_confidence'] = None

    role = result.get('role', {})
    if isinstance(role, dict) and role.get('job_subfamily'):
        job_subfamily = role['job_subfamily']
        if job_subfamily == 'out_of_scope':
            result['role']['job_family'] = 'out_of_scope'
        else:
            job_family = get_correct_job_family(job_subfamily)
            result['role']['job_family'] = job_family if job_family else None
    else:
        if 'role' not in result:
            result['role'] = {}
        result['role']['job_family'] = None

    if 'skills' in result and result['skills']:
        result['skills'] = enrich_skills_with_families(result['skills'])

    result['_cost_data'] = cost_data
    result['_model_used'] = model
    return result


def _classify_with_fallback(job: Dict, classify_fn, label: str) -> Tuple[Optional[Dict], str]:
    """Run a classify function with fallback to FALLBACK_MODEL on JSON errors.

    Returns (result, status) where status is one of:
      'ok'       - primary model succeeded
      'fallback' - primary failed, fallback succeeded
      'error'    - both models failed
    """
    try:
        result = classify_fn(job, model=MODEL)
        return result, "ok"
    except Exception as primary_err:
        print(f" {label} PRIMARY ERROR ({MODEL}): {primary_err}", end="", flush=True)

    # Fallback
    try:
        print(f" -> falling back to {FALLBACK_MODEL}...", end="", flush=True)
        result = classify_fn(job, model=FALLBACK_MODEL)
        return result, "fallback"
    except Exception as fallback_err:
        print(f" {label} FALLBACK ERROR: {fallback_err}", end="", flush=True)
        return None, "error"


def classify_job_ab(job: Dict) -> Tuple[Optional[Dict], Optional[Dict], str, str]:
    """Classify a single job with both V1 and V2 prompts, with fallback.

    Returns (v1_result, v2_result, v1_status, v2_status).
    Status is 'ok', 'fallback', or 'error'.
    """
    v1_result, v1_status = _classify_with_fallback(job, _classify_v1, "V1")

    time.sleep(0.3)

    v2_result, v2_status = _classify_with_fallback(job, _classify_v2, "V2")

    return v1_result, v2_result, v1_status, v2_status


# ============================================
# Result Extraction Helpers
# ============================================

def _extract_skills_str(result: Dict) -> str:
    """Extract comma-separated skill names from classification result."""
    skills = result.get("skills", []) or []
    return ", ".join(s.get("name", "") for s in skills if s.get("name"))


def _skill_names(result: Dict) -> set:
    """Extract skill name set from a classification result."""
    skills = result.get("skills", []) or []
    return {s.get("name", "").lower() for s in skills if s.get("name")}


def _jaccard(a: set, b: set) -> float:
    """Jaccard similarity between two sets."""
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def _extract_flat(result: Dict, prefix: str) -> Dict:
    """Extract key classified fields from a result into a flat dict with prefix."""
    role = result.get("role", {}) or {}
    loc = result.get("location", {}) or {}
    cost = result.get("_cost_data", {}) or {}
    return {
        f"{prefix}_subfamily": role.get("job_subfamily"),
        f"{prefix}_family": role.get("job_family"),
        f"{prefix}_seniority": role.get("seniority"),
        f"{prefix}_track": role.get("track"),
        f"{prefix}_arrangement": loc.get("working_arrangement"),
        f"{prefix}_summary": (result.get("summary") or "")[:120],
        f"{prefix}_skills": _extract_skills_str(result),
        f"{prefix}_skill_count": len(result.get("skills", []) or []),
        f"{prefix}_input_tokens": cost.get("input_tokens", 0),
        f"{prefix}_output_tokens": cost.get("output_tokens", 0),
        f"{prefix}_latency_ms": round(cost.get("latency_ms", 0)),
    }


# ============================================
# CSV Output
# ============================================

CSV_COLUMNS = [
    "job_num", "source", "region", "company", "title", "guessed_family",
    "status", "v1_model", "v2_model",
    # Side-by-side comparison: V1 | V2 | match for each field
    "v1_subfamily", "v2_subfamily", "subfamily_match",
    "v1_family", "v2_family", "family_match",
    "v1_seniority", "v2_seniority", "seniority_match",
    "v1_track", "v2_track", "track_match",
    "v1_arrangement", "v2_arrangement", "arrangement_match",
    "v1_skills", "v2_skills", "skill_jaccard",
    "v1_skill_count", "v2_skill_count",
    "v1_summary", "v2_summary",
    "v1_input_tokens", "v2_input_tokens",
    "v1_output_tokens", "v2_output_tokens",
    "v1_latency_ms", "v2_latency_ms",
]


def _write_csv(rows: List[Dict], seed: Optional[int]) -> str:
    """Write results CSV to temp/ and return the file path."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    seed_suffix = f"_seed{seed}" if seed is not None else ""
    filename = f"eval_prompt_ab_{ts}{seed_suffix}.csv"
    filepath = os.path.join(TEMP_DIR, filename)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return filepath


# ============================================
# Main
# ============================================

def run_ab_test(sample_size: int = 10, verbose: bool = False, seed: Optional[int] = None,
                exclude_oos: bool = False):
    """Run the full A/B test."""
    if seed is not None:
        random.seed(seed)
        print(f"  Random seed: {seed}")

    oos_label = "  |  OOS: excluded" if exclude_oos else ""
    print(f"\n{'='*70}")
    print(f"  PROMPT A/B TEST: V1 (adapted) vs V2 (native)")
    print(f"  Primary: {MODEL}  |  Fallback: {FALLBACK_MODEL}")
    print(f"  Sample: {sample_size} jobs{oos_label}")
    print(f"{'='*70}\n")

    print("Fetching jobs...")
    jobs = fetch_sample_jobs(sample_size, exclude_oos=exclude_oos)
    dist = _format_distribution(jobs)
    print(f"  Got {len(jobs)} jobs: {dist}\n")

    if not jobs:
        print("[ERROR] No jobs fetched. Check API keys and network.")
        sys.exit(1)

    csv_rows = []
    comparisons = []
    errors = 0
    v1_fallbacks = 0
    v2_fallbacks = 0

    for i, job in enumerate(jobs, 1):
        title_short = job["title"][:45]
        family_tag = job.get("_guessed_family", "?")[:4]
        region_tag = job.get("region", "?")
        print(f"[{i}/{len(jobs)}] [{family_tag}/{region_tag}] {title_short}...", end=" ", flush=True)

        v1_result, v2_result, v1_status, v2_status = classify_job_ab(job)

        if v1_status == "fallback":
            v1_fallbacks += 1
        if v2_status == "fallback":
            v2_fallbacks += 1

        # Determine row-level status
        if v1_result is None or v2_result is None:
            errors += 1
            row_status = "error"
        elif v1_status == "fallback" or v2_status == "fallback":
            row_status = "fallback"
        else:
            row_status = "ok"

        # Build base row (always written to CSV)
        row = {
            "job_num": i,
            "source": job["source"],
            "region": job.get("region", "?"),
            "company": job["company"],
            "title": job["title"],
            "guessed_family": job.get("_guessed_family", "?"),
            "status": row_status,
            "v1_model": v1_result.get("_model_used", "") if v1_result else "FAILED",
            "v2_model": v2_result.get("_model_used", "") if v2_result else "FAILED",
        }

        if v1_result is None or v2_result is None:
            # Write error row to CSV with whatever we have
            if v1_result:
                row.update(_extract_flat(v1_result, "v1"))
            if v2_result:
                row.update(_extract_flat(v2_result, "v2"))
            csv_rows.append(row)
            print(" ERROR")
            time.sleep(0.5)
            continue

        # Both sides succeeded - full comparison
        v1_flat = _extract_flat(v1_result, "v1")
        v2_flat = _extract_flat(v2_result, "v2")

        v1_skills = _skill_names(v1_result)
        v2_skills = _skill_names(v2_result)

        comp = {
            "subfamily_match": v1_flat["v1_subfamily"] == v2_flat["v2_subfamily"],
            "family_match": v1_flat["v1_family"] == v2_flat["v2_family"],
            "seniority_match": v1_flat["v1_seniority"] == v2_flat["v2_seniority"],
            "track_match": v1_flat["v1_track"] == v2_flat["v2_track"],
            "arrangement_match": v1_flat["v1_arrangement"] == v2_flat["v2_arrangement"],
            "skill_jaccard": round(_jaccard(v1_skills, v2_skills), 3),
        }

        row.update({**v1_flat, **v2_flat, **comp})
        csv_rows.append(row)

        # Store for summary stats
        comp["title"] = job["title"][:50]
        comp["source"] = job["source"]
        comp["region"] = job.get("region", "?")
        comp["guessed_family"] = job.get("_guessed_family", "?")
        comp["v1_subfamily"] = v1_flat["v1_subfamily"]
        comp["v2_subfamily"] = v2_flat["v2_subfamily"]
        comp["v1_seniority"] = v1_flat["v1_seniority"]
        comp["v2_seniority"] = v2_flat["v2_seniority"]
        comp["v1_arrangement"] = v1_flat["v1_arrangement"]
        comp["v2_arrangement"] = v2_flat["v2_arrangement"]
        comp["v1_input_tokens"] = v1_flat["v1_input_tokens"]
        comp["v2_input_tokens"] = v2_flat["v2_input_tokens"]
        comp["v1_skill_count"] = v1_flat["v1_skill_count"]
        comp["v2_skill_count"] = v2_flat["v2_skill_count"]
        comp["v1_has_summary"] = bool(v1_flat["v1_summary"])
        comp["v2_has_summary"] = bool(v2_flat["v2_summary"])
        comp["v1_model"] = v1_result.get("_model_used", MODEL)
        comp["v2_model"] = v2_result.get("_model_used", MODEL)
        comparisons.append(comp)

        # Print inline status
        flags = []
        if not comp["subfamily_match"]:
            flags.append(f"subfamily: {comp['v1_subfamily']}->{comp['v2_subfamily']}")
        if not comp["seniority_match"]:
            flags.append(f"seniority: {comp['v1_seniority']}->{comp['v2_seniority']}")
        if not comp["arrangement_match"]:
            flags.append(f"arr: {comp['v1_arrangement']}->{comp['v2_arrangement']}")

        fb_tag = ""
        if v1_status == "fallback" or v2_status == "fallback":
            fb_parts = []
            if v1_status == "fallback":
                fb_parts.append("V1")
            if v2_status == "fallback":
                fb_parts.append("V2")
            fb_tag = f" [{'+'.join(fb_parts)} fallback]"

        token_saving = comp["v1_input_tokens"] - comp["v2_input_tokens"]
        token_pct = (token_saving / comp["v1_input_tokens"] * 100) if comp["v1_input_tokens"] > 0 else 0

        if flags:
            print(f"DIFF ({', '.join(flags)}){fb_tag} tokens: -{token_saving} ({token_pct:.0f}%)")
        else:
            print(f"MATCH{fb_tag}  tokens: -{token_saving} ({token_pct:.0f}%)")

        if verbose:
            only_v1 = sorted(v1_skills - v2_skills)
            only_v2 = sorted(v2_skills - v1_skills)
            if only_v1:
                print(f"        Skills only in V1: {only_v1}")
            if only_v2:
                print(f"        Skills only in V2: {only_v2}")

        # Rate limit between jobs
        time.sleep(0.5)

    # ========================================
    # Write CSV
    # ========================================
    if csv_rows:
        csv_path = _write_csv(csv_rows, seed)
        print(f"\n  CSV saved: {csv_path}")

    # ========================================
    # Summary Statistics
    # ========================================
    n = len(comparisons)
    if n == 0:
        print("\n[ERROR] No successful comparisons.")
        return

    print(f"\n{'='*70}")
    print("  SUMMARY")
    print(f"{'='*70}")
    print(f"  Jobs tested: {len(jobs)}  |  Compared: {n}  |  Errors: {errors}")
    print(f"  Fallbacks:  V1={v1_fallbacks}  V2={v2_fallbacks}  (to {FALLBACK_MODEL})")
    comp_dist = _format_distribution(
        [{"source": c["source"], "region": c["region"], "_guessed_family": c["guessed_family"]} for c in comparisons]
    )
    print(f"  Distribution: {comp_dist}\n")

    # Field agreement rates
    fields = [
        ("job_subfamily", "subfamily_match"),
        ("job_family", "family_match"),
        ("seniority", "seniority_match"),
        ("working_arrangement", "arrangement_match"),
        ("track", "track_match"),
        ("summary_present", None),
    ]

    print(f"  {'Field':<25} {'Agreement':>10} {'Rate':>8}")
    print(f"  {'-'*25} {'-'*10} {'-'*8}")

    for label, key in fields:
        if key:
            matches = sum(1 for c in comparisons if c[key])
            rate = matches / n * 100
            print(f"  {label:<25} {matches:>6}/{n:<3} {rate:>6.1f}%")
        else:
            v1_sum = sum(1 for c in comparisons if c["v1_has_summary"])
            v2_sum = sum(1 for c in comparisons if c["v2_has_summary"])
            print(f"  {'V1 summary present':<25} {v1_sum:>6}/{n:<3}")
            print(f"  {'V2 summary present':<25} {v2_sum:>6}/{n:<3}")

    # Skill overlap
    avg_jaccard = sum(c["skill_jaccard"] for c in comparisons) / n
    avg_v1_skills = sum(c["v1_skill_count"] for c in comparisons) / n
    avg_v2_skills = sum(c["v2_skill_count"] for c in comparisons) / n
    print(f"\n  Avg skill Jaccard similarity: {avg_jaccard:.2f}")
    print(f"  Avg V1 skill count: {avg_v1_skills:.1f}  |  V2: {avg_v2_skills:.1f}")

    # Token savings
    v1_tokens = [c["v1_input_tokens"] for c in comparisons]
    v2_tokens = [c["v2_input_tokens"] for c in comparisons]
    avg_v1 = sum(v1_tokens) / n
    avg_v2 = sum(v2_tokens) / n
    saving = avg_v1 - avg_v2
    saving_pct = (saving / avg_v1 * 100) if avg_v1 > 0 else 0

    print(f"\n  Avg input tokens  V1: {avg_v1:.0f}  |  V2: {avg_v2:.0f}")
    print(f"  Token reduction:  {saving:.0f} ({saving_pct:.1f}%)")

    # Mismatches detail
    subfamily_mismatches = [c for c in comparisons if not c["subfamily_match"]]
    seniority_mismatches = [c for c in comparisons if not c["seniority_match"]]

    if subfamily_mismatches:
        print(f"\n  Subfamily mismatches ({len(subfamily_mismatches)}):")
        for c in subfamily_mismatches[:5]:
            v1_sub = c['v1_subfamily'] or 'None'
            v2_sub = c['v2_subfamily'] or 'None'
            print(f"    [{c['guessed_family'][:4]}/{c['region']}] {c['title'][:35]:<35} V1={v1_sub:<20} V2={v2_sub}")

    if seniority_mismatches:
        print(f"\n  Seniority mismatches ({len(seniority_mismatches)}):")
        for c in seniority_mismatches[:5]:
            v1_sen = c['v1_seniority'] or 'None'
            v2_sen = c['v2_seniority'] or 'None'
            print(f"    [{c['guessed_family'][:4]}/{c['region']}] {c['title'][:35]:<35} V1={v1_sen:<15} V2={v2_sen}")

    # Verdict
    subfamily_rate = sum(1 for c in comparisons if c["subfamily_match"]) / n * 100
    seniority_rate = sum(1 for c in comparisons if c["seniority_match"]) / n * 100

    print(f"\n{'='*70}")
    if subfamily_rate >= 90 and seniority_rate >= 80 and saving_pct > 0:
        print(f"  [OK] V2 looks safe to promote.")
        print(f"    subfamily agreement: {subfamily_rate:.0f}%  |  seniority: {seniority_rate:.0f}%  |  tokens: -{saving_pct:.0f}%")
    else:
        print(f"  [REVIEW] Check mismatches before promoting V2.")
        print(f"    subfamily agreement: {subfamily_rate:.0f}%  |  seniority: {seniority_rate:.0f}%  |  tokens: -{saving_pct:.0f}%")
    print(f"{'='*70}\n")


def run_retest(csv_path: str, field: str = "arrangement", verbose: bool = False):
    """Re-run only the mismatched jobs from a previous eval CSV.

    Reads the CSV, identifies rows where <field>_match == False,
    re-fetches those specific jobs from their APIs, re-classifies with
    both prompts, and outputs a focused comparison.
    """
    match_col = f"{field}_match"

    # Read previous CSV and find mismatches
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_rows = list(reader)

    mismatches = [r for r in all_rows if r.get(match_col) == "False"]
    if not mismatches:
        print(f"\n  No {field} mismatches found in {csv_path}")
        return

    print(f"\n{'='*70}")
    print(f"  RETEST: {len(mismatches)} {field} mismatches from previous run")
    print(f"  Model: {MODEL}")
    print(f"  Source CSV: {os.path.basename(csv_path)}")
    print(f"{'='*70}\n")

    # Build lookup: (source, company) -> instance from COMPANY_ROSTER
    roster_lookup = {}
    for source, slug, instance, region in COMPANY_ROSTER:
        roster_lookup[(source, slug)] = (instance, region)

    # Group mismatches by (source, company) to minimise API calls
    needed = {}
    for row in mismatches:
        key = (row["source"], row["company"])
        needed.setdefault(key, []).append(row["title"])

    # Fetch from each company and find matching jobs by title
    jobs_to_test = []
    for (source, company), titles in needed.items():
        instance, region = roster_lookup.get((source, company), (None, "?"))
        print(f"  Fetching {source}/{company}...", end=" ", flush=True)
        fetched = _fetch_from_source(source, company, instance)
        print(f"{len(fetched)} jobs")

        for target_title in titles:
            # Exact match first, then prefix match
            match = None
            for job in fetched:
                if job["title"] == target_title:
                    match = job
                    break
            if not match:
                # Try prefix match (titles may have been truncated in CSV)
                for job in fetched:
                    if job["title"].startswith(target_title[:40]):
                        match = job
                        break
            if match:
                match["region"] = region
                match["_guessed_family"] = guess_family_from_title(match["title"])
                jobs_to_test.append(match)
            else:
                print(f"    [WARN] Could not find: {target_title[:50]}")

    if not jobs_to_test:
        print("\n  [ERROR] No matching jobs found in live APIs.")
        return

    print(f"\n  Matched {len(jobs_to_test)}/{len(mismatches)} jobs. Classifying...\n")

    csv_rows = []
    comparisons = []
    errors = 0

    for i, job in enumerate(jobs_to_test, 1):
        title_short = job["title"][:45]
        family_tag = job.get("_guessed_family", "?")[:4]
        region_tag = job.get("region", "?")
        print(f"[{i}/{len(jobs_to_test)}] [{family_tag}/{region_tag}] {title_short}...", end=" ", flush=True)

        v1_result, v2_result = classify_job_ab(job)

        if v1_result is None or v2_result is None:
            errors += 1
            print("SKIP (error)")
            continue

        v1_flat = _extract_flat(v1_result, "v1")
        v2_flat = _extract_flat(v2_result, "v2")
        v1_skills = _skill_names(v1_result)
        v2_skills = _skill_names(v2_result)

        comp = {
            "subfamily_match": v1_flat["v1_subfamily"] == v2_flat["v2_subfamily"],
            "family_match": v1_flat["v1_family"] == v2_flat["v2_family"],
            "seniority_match": v1_flat["v1_seniority"] == v2_flat["v2_seniority"],
            "track_match": v1_flat["v1_track"] == v2_flat["v2_track"],
            "arrangement_match": v1_flat["v1_arrangement"] == v2_flat["v2_arrangement"],
            "skill_jaccard": round(_jaccard(v1_skills, v2_skills), 3),
        }

        row = {
            "job_num": i,
            "source": job["source"],
            "region": job.get("region", "?"),
            "company": job["company"],
            "title": job["title"],
            "guessed_family": job.get("_guessed_family", "?"),
            **v1_flat, **v2_flat, **comp,
        }
        csv_rows.append(row)

        comp["title"] = job["title"][:50]
        comp["source"] = job["source"]
        comp["region"] = job.get("region", "?")
        comp["guessed_family"] = job.get("_guessed_family", "?")
        comp["v1_arrangement"] = v1_flat["v1_arrangement"]
        comp["v2_arrangement"] = v2_flat["v2_arrangement"]
        comp["v1_input_tokens"] = v1_flat["v1_input_tokens"]
        comp["v2_input_tokens"] = v2_flat["v2_input_tokens"]
        comparisons.append(comp)

        # Print inline status
        v1_arr = v1_flat["v1_arrangement"] or "None"
        v2_arr = v2_flat["v2_arrangement"] or "None"
        status = "MATCH" if comp["arrangement_match"] else f"DIFF (V1={v1_arr}, V2={v2_arr})"
        token_saving = comp["v1_input_tokens"] - comp["v2_input_tokens"]
        token_pct = (token_saving / comp["v1_input_tokens"] * 100) if comp["v1_input_tokens"] > 0 else 0
        print(f"{status}  tokens: -{token_saving} ({token_pct:.0f}%)")

        time.sleep(0.5)

    # Write CSV
    if csv_rows:
        csv_path_out = _write_csv(csv_rows, seed=None)
        print(f"\n  CSV saved: {csv_path_out}")

    # Summary
    n = len(comparisons)
    if n == 0:
        print("\n  [ERROR] No successful comparisons.")
        return

    print(f"\n{'='*70}")
    print(f"  RETEST SUMMARY ({field} mismatches)")
    print(f"{'='*70}")
    print(f"  Jobs re-tested: {n}  |  Errors: {errors}")

    arr_matches = sum(1 for c in comparisons if c["arrangement_match"])
    arr_rate = arr_matches / n * 100
    print(f"\n  {field}_match:  {arr_matches}/{n}  ({arr_rate:.0f}%)")

    still_diff = [c for c in comparisons if not c["arrangement_match"]]
    if still_diff:
        print(f"\n  Still mismatched ({len(still_diff)}):")
        for c in still_diff:
            v1_a = c["v1_arrangement"] or "None"
            v2_a = c["v2_arrangement"] or "None"
            print(f"    [{c['guessed_family'][:4]}/{c['region']}] {c['title'][:40]:<40} V1={v1_a:<10} V2={v2_a}")
    else:
        print(f"\n  [OK] All previous {field} mismatches now agree!")

    print(f"{'='*70}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A/B test V1 vs V2 classifier prompt")
    parser.add_argument("--sample", type=int, default=10, help="Number of jobs to test (default: 10)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full skill lists and diffs")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible sampling")
    parser.add_argument("--exclude-oos", action="store_true",
                        help="Exclude out_of_scope roles entirely from sample")
    parser.add_argument("--retest", type=str, default=None,
                        help="Path to previous CSV to re-test mismatched jobs")
    parser.add_argument("--field", type=str, default="arrangement",
                        help="Field to retest mismatches for (default: arrangement)")
    args = parser.parse_args()

    if args.retest:
        run_retest(csv_path=args.retest, field=args.field, verbose=args.verbose)
    else:
        run_ab_test(sample_size=args.sample, verbose=args.verbose, seed=args.seed,
                    exclude_oos=args.exclude_oos)
