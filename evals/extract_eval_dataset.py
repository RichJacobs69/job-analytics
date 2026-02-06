"""
Extract evaluation dataset for LLM provider comparison.
Focuses on Greenhouse and Lever sources (full descriptions, not truncated like Adzuna).

Usage:
    python wrappers/extract_eval_dataset.py --count 100
    python wrappers/extract_eval_dataset.py --count 50 --output tests/fixtures/eval_sample.json
"""
import argparse
import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.db_connection import supabase


def extract_eval_dataset(count: int = 100, output_path: str = None):
    """
    Extract stratified sample of jobs for LLM evaluation.

    Prioritizes Greenhouse and Lever (full descriptions).
    Stratifies across job families and seniority levels.
    """
    print(f"\n{'='*60}")
    print("EXTRACTING EVALUATION DATASET")
    print(f"Target: {count} jobs from Greenhouse/Lever")
    print(f"{'='*60}\n")

    # Fetch jobs with their classifications
    # Join raw_jobs (has raw_text) with enriched_jobs (has classifications)
    print("Fetching Greenhouse jobs...")
    gh_response = supabase.table('raw_jobs').select(
        'id, title, company, raw_text, source, hash'
    ).eq('source', 'greenhouse').not_.is_('raw_text', 'null').order(
        'scraped_at', desc=True
    ).limit(count).execute()

    print("Fetching Lever jobs...")
    lever_response = supabase.table('raw_jobs').select(
        'id, title, company, raw_text, source, hash'
    ).eq('source', 'lever').not_.is_('raw_text', 'null').order(
        'scraped_at', desc=True
    ).limit(count).execute()

    gh_jobs = gh_response.data or []
    lever_jobs = lever_response.data or []

    print(f"Found: {len(gh_jobs)} Greenhouse, {len(lever_jobs)} Lever")

    # Combine and get enriched data for each
    all_raw_jobs = gh_jobs + lever_jobs

    # Get enriched classifications by hash
    hashes = [j['hash'] for j in all_raw_jobs if j.get('hash')]

    print(f"Fetching enriched classifications for {len(hashes)} jobs...")

    # Fetch in batches (Supabase limit)
    enriched_by_hash = {}
    batch_size = 100
    for i in range(0, len(hashes), batch_size):
        batch_hashes = hashes[i:i+batch_size]
        enriched_response = supabase.table('enriched_jobs').select(
            'job_hash, job_family, job_subfamily, seniority, working_arrangement, skills, employer_name'
        ).in_('job_hash', batch_hashes).execute()

        for e in (enriched_response.data or []):
            enriched_by_hash[e['job_hash']] = e

    print(f"Found enriched data for {len(enriched_by_hash)} jobs")

    # Build dataset with ground truth classifications
    dataset = []
    stats = {'greenhouse': 0, 'lever': 0, 'families': {}, 'seniorities': {}}

    for raw_job in all_raw_jobs:
        job_hash = raw_job.get('hash')
        enriched = enriched_by_hash.get(job_hash)

        if not enriched:
            continue  # Skip jobs without classifications

        entry = {
            'id': raw_job['id'],
            'hash': job_hash,
            'source': raw_job['source'],
            'title': raw_job['title'],
            'company': raw_job['company'],
            'raw_text': raw_job['raw_text'],
            'ground_truth': {
                'job_family': enriched.get('job_family'),
                'job_subfamily': enriched.get('job_subfamily'),
                'seniority': enriched.get('seniority'),
                'working_arrangement': enriched.get('working_arrangement'),
                'skills': enriched.get('skills', [])
            }
        }
        dataset.append(entry)

        # Track stats
        stats[raw_job['source']] += 1
        family = enriched.get('job_family', 'unknown')
        seniority = enriched.get('seniority', 'unknown')
        stats['families'][family] = stats['families'].get(family, 0) + 1
        stats['seniorities'][seniority] = stats['seniorities'].get(seniority, 0) + 1

        if len(dataset) >= count:
            break

    # Balance if needed - aim for roughly equal Greenhouse/Lever
    print(f"\n{'='*60}")
    print("DATASET SUMMARY")
    print(f"{'='*60}")
    print(f"Total jobs: {len(dataset)}")
    print(f"  Greenhouse: {stats['greenhouse']}")
    print(f"  Lever: {stats['lever']}")
    print(f"\nBy job family:")
    for family, cnt in sorted(stats['families'].items(), key=lambda x: -x[1]):
        print(f"  {family}: {cnt}")
    print(f"\nBy seniority:")
    for seniority, cnt in sorted(stats['seniorities'].items(), key=lambda x: -x[1]):
        print(f"  {seniority}: {cnt}")

    # Save dataset
    if output_path is None:
        output_path = 'tests/fixtures/llm_eval_dataset.json'

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    output_data = {
        'created_at': datetime.now().isoformat(),
        'count': len(dataset),
        'sources': {'greenhouse': stats['greenhouse'], 'lever': stats['lever']},
        'jobs': dataset
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\nDataset saved to: {output_path}")
    print(f"File size: {os.path.getsize(output_path) / 1024:.1f} KB")

    return dataset


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract LLM evaluation dataset")
    parser.add_argument('--count', type=int, default=100, help='Number of jobs to extract')
    parser.add_argument('--output', type=str, default=None, help='Output file path')

    args = parser.parse_args()
    extract_eval_dataset(count=args.count, output_path=args.output)
