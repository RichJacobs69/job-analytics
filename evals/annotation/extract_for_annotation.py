"""
Extract Jobs for Annotation

Pulls a stratified sample of jobs from the database into the annotation queue.

Usage:
    python evals/annotation/extract_for_annotation.py --count 50
    python evals/annotation/extract_for_annotation.py --count 100 --source greenhouse
    python evals/annotation/extract_for_annotation.py --edge-cases
    python evals/annotation/extract_for_annotation.py --max-per-company 2

Options:
    --count N             Number of jobs to extract (default: 50)
    --source              Filter by source (greenhouse, lever, ashby, workable)
    --edge-cases          Prioritize ambiguous titles
    --family              Filter by job_family
    --max-per-company N   Max jobs per company for diversity (default: 2)
    --dry-run             Preview without adding to queue
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import argparse
import random
from typing import List, Dict
from collections import defaultdict

from pipeline.db_connection import supabase
from evals.annotation.db import add_pending_job, get_pending_count, init_db

# Edge case patterns - titles that are often misclassified
EDGE_CASE_PATTERNS = [
    "Data Product Manager",      # Product or Data?
    "Technical Project Manager", # Delivery, not Product
    "Product Analyst",           # Product Analytics or Data Analyst?
    "AI Engineer",               # ML Engineer or Out of Scope?
    "Applied Scientist",         # Research Scientist ML
    "BI Engineer",               # Analytics Engineer or Data Analyst?
    "Growth Analyst",            # Product Analytics?
    "Platform Engineer",         # Out of Scope (SWE)
    "Product Engineer",          # Out of Scope (SWE)
    "Engineering Manager",       # Out of Scope
    "Scrum Master",              # Delivery
    "Technical Program Manager", # Delivery
]


def fetch_jobs_by_family(family: str, limit: int, source: str = None) -> List[Dict]:
    """Fetch jobs for a specific family directly from enriched_jobs."""
    jobs = []
    offset = 0
    batch_size = 200

    while len(jobs) < limit:
        query = supabase.table("enriched_jobs").select(
            "id, title_display, employer_name, job_hash, data_source, job_family, job_subfamily, seniority"
        ).eq("job_family", family)

        if source:
            query = query.eq("data_source", source)

        query = query.order("posted_date", desc=True).range(offset, offset + batch_size - 1)
        result = query.execute()

        if not result.data:
            break

        # Map data_source to source for consistency
        for job in result.data:
            job["source"] = job.pop("data_source", None)

        jobs.extend(result.data)
        offset += batch_size

        if offset > 2000:
            break

    return jobs


def fetch_jobs_from_db(
    count: int,
    source: str = None,
    family: str = None,
    edge_cases: bool = False,
    max_per_company: int = 2
) -> List[Dict]:
    """Fetch jobs with proper stratification and company diversity."""

    families_to_fetch = [family] if family else ["product", "data", "delivery", "out_of_scope"]
    per_family = max(count // len(families_to_fetch), 5)

    print(f"Fetching ~{per_family} jobs per family...")

    # Fetch jobs by family directly from enriched_jobs
    by_family = {}
    for fam in families_to_fetch:
        fam_jobs = fetch_jobs_by_family(fam, per_family * 3, source)
        by_family[fam] = fam_jobs
        print(f"  {fam}: {len(fam_jobs)} candidates")

    # Get raw_text for these jobs from raw_jobs table
    all_hashes = []
    for fam_jobs in by_family.values():
        all_hashes.extend([j["job_hash"] for j in fam_jobs if j.get("job_hash")])

    print(f"\nFetching raw_text for {len(all_hashes)} jobs...")

    raw_by_hash = {}
    for i in range(0, len(all_hashes), 100):
        batch = all_hashes[i:i+100]
        result = supabase.table("raw_jobs").select(
            "hash, raw_text"
        ).in_("hash", batch).execute()

        for r in (result.data or []):
            if r.get("raw_text") and len(r["raw_text"]) > 200:
                raw_by_hash[r["hash"]] = r["raw_text"]

    print(f"  Found raw_text for {len(raw_by_hash)} jobs")

    # Build combined job list with raw_text
    all_jobs = []
    for fam, fam_jobs in by_family.items():
        for job in fam_jobs:
            raw_text = raw_by_hash.get(job.get("job_hash"))
            if raw_text:
                all_jobs.append({
                    "id": job["id"],
                    "hash": job["job_hash"],
                    "title": job["title_display"],
                    "company": job["employer_name"],
                    "source": job["source"],
                    "raw_text": raw_text,
                    "current_family": job["job_family"],
                    "current_subfamily": job["job_subfamily"],
                    "current_seniority": job["seniority"],
                })

    print(f"Total jobs with raw_text: {len(all_jobs)}")

    # Apply company diversity limit
    company_counts = defaultdict(int)
    diverse_jobs = []

    # Shuffle to avoid recency bias within each batch
    random.shuffle(all_jobs)

    for job in all_jobs:
        company = job.get("company", "").lower()
        if company_counts[company] < max_per_company:
            diverse_jobs.append(job)
            company_counts[company] += 1

    print(f"After company diversity filter (max {max_per_company}/company): {len(diverse_jobs)} jobs")

    # Prioritize edge cases if requested
    if edge_cases:
        edge_jobs = []
        normal_jobs = []

        for job in diverse_jobs:
            title = job.get("title", "").lower()
            is_edge = any(pattern.lower() in title for pattern in EDGE_CASE_PATTERNS)
            if is_edge:
                edge_jobs.append(job)
            else:
                normal_jobs.append(job)

        print(f"Found {len(edge_jobs)} edge case jobs")
        diverse_jobs = edge_jobs + normal_jobs

    # Stratified selection
    selected = []
    by_family_filtered = defaultdict(list)

    for job in diverse_jobs:
        fam = job.get("current_family") or "unknown"
        by_family_filtered[fam].append(job)

    print("\nDistribution after filtering:")
    for fam, jobs in by_family_filtered.items():
        print(f"  {fam}: {len(jobs)}")

    # Take equal from each family
    target_per_family = max(count // len(families_to_fetch), 1)

    for fam in families_to_fetch:
        fam_jobs = by_family_filtered.get(fam, [])
        selected.extend(fam_jobs[:target_per_family])

    # Fill remaining if needed
    remaining = count - len(selected)
    if remaining > 0:
        used_ids = {j["id"] for j in selected}
        for job in diverse_jobs:
            if job["id"] not in used_ids:
                selected.append(job)
                if len(selected) >= count:
                    break

    return selected[:count]


def add_jobs_to_queue(jobs: List[Dict], dry_run: bool = False) -> int:
    """Add jobs to the pending annotation queue."""
    added = 0

    for job in jobs:
        job_id = f"gs_{job['hash'][:12]}"

        if dry_run:
            print(f"  Would add: {job['title'][:50]} ({job['company']})")
            added += 1
            continue

        # Determine priority (edge cases get higher priority)
        title = job.get("title", "").lower()
        is_edge = any(pattern.lower() in title for pattern in EDGE_CASE_PATTERNS)
        priority = 10 if is_edge else 0

        success = add_pending_job(
            job_id=job_id,
            source_job_id=job["id"],
            source=job["source"],
            title=job["title"],
            company=job["company"],
            raw_text=job["raw_text"],
            priority=priority
        )

        if success:
            added += 1

    return added


def main():
    parser = argparse.ArgumentParser(description="Extract jobs for annotation")
    parser.add_argument("--count", type=int, default=50, help="Number of jobs")
    parser.add_argument("--source", type=str, help="Filter by source")
    parser.add_argument("--family", type=str, help="Filter by job_family")
    parser.add_argument("--edge-cases", action="store_true", help="Prioritize edge cases")
    parser.add_argument("--max-per-company", type=int, default=2, help="Max jobs per company (default: 2)")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    args = parser.parse_args()

    print("=" * 60)
    print("EXTRACT JOBS FOR ANNOTATION")
    print("=" * 60)
    print(f"Target count: {args.count}")
    print(f"Source filter: {args.source or 'all'}")
    print(f"Family filter: {args.family or 'all'}")
    print(f"Edge cases priority: {args.edge_cases}")
    print(f"Max per company: {args.max_per_company}")
    print(f"Dry run: {args.dry_run}")
    print()

    # Initialize database
    init_db()

    current_pending = get_pending_count()
    print(f"Current pending queue: {current_pending} jobs")
    print()

    # Fetch jobs
    print("[1/2] Fetching jobs from database...")
    jobs = fetch_jobs_from_db(
        count=args.count,
        source=args.source,
        family=args.family,
        edge_cases=args.edge_cases,
        max_per_company=args.max_per_company
    )

    print(f"\nSelected {len(jobs)} jobs for annotation")

    # Preview
    print("\n[PREVIEW] First 10 jobs:")
    print("-" * 60)
    for job in jobs[:10]:
        fam = job.get("current_family", "?")
        print(f"  [{fam:<12}] {job['title'][:40]:<40} ({job['company'][:15]})")
    print("-" * 60)

    # Add to queue
    print(f"\n[2/2] Adding to annotation queue...")
    added = add_jobs_to_queue(jobs, dry_run=args.dry_run)

    print()
    print("=" * 60)
    if args.dry_run:
        print(f"[DRY RUN] Would add {added} jobs to queue")
    else:
        print(f"[DONE] Added {added} jobs to annotation queue")
        print(f"New pending queue size: {get_pending_count()}")

    print()
    print("Next step: Run the annotation app:")
    print("  streamlit run evals/annotation/app.py")


if __name__ == "__main__":
    main()
