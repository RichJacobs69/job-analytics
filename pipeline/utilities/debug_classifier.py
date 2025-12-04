"""
Debug classifier by testing it on known misclassified jobs.
"""

import os
import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
from supabase import create_client
from pipeline.classifier import classify_job_with_claude
import json

load_dotenv()
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))


def get_sample_misclassified_jobs(limit=5):
    """Get some jobs with 'product' in title that were classified as out_of_scope."""
    
    # Get enriched jobs that are out_of_scope
    enriched = supabase.table('enriched_jobs').select(
        'id, raw_job_id, employer_name, title_display, job_family, job_subfamily, seniority'
    ).eq('job_family', 'out_of_scope').eq('is_agency', False).limit(1000).execute()
    
    # Get raw_jobs with 'product manager' in title (case insensitive)
    raw_jobs = supabase.table('raw_jobs').select(
        'id, title, company, posting_url, raw_text'
    ).ilike('title', '%product manager%').limit(500).execute()
    
    # Create lookup
    raw_lookup = {job['id']: job for job in raw_jobs.data}
    
    # Find matches
    results = []
    for job in enriched.data:
        raw_id = job['raw_job_id']
        if raw_id in raw_lookup:
            raw = raw_lookup[raw_id]
            results.append({
                'raw_job_id': raw_id,
                'raw_title': raw['title'],
                'company': raw['company'],
                'enriched_title': job['title_display'],
                'job_family': job['job_family'],
                'job_subfamily': job['job_subfamily'],
                'raw_text': raw['raw_text'],
                'posting_url': raw['posting_url']
            })
            if len(results) >= limit:
                break
    
    return results


def test_classification(job_text: str, expected_family: str = 'product', verbose: bool = True):
    """Test classification on a job text."""
    print("\n" + "="*80)
    print("TESTING CLASSIFICATION")
    print("="*80)
    
    # Truncate for display
    display_text = job_text[:500] + "..." if len(job_text) > 500 else job_text
    print(f"\nJob Text (first 500 chars):\n{display_text}")
    print(f"\nExpected job_family: {expected_family}")
    
    result = classify_job_with_claude(job_text, verbose=verbose)
    
    actual_family = result.get('role', {}).get('job_family', 'MISSING')
    actual_subfamily = result.get('role', {}).get('job_subfamily', 'MISSING')
    
    print("\n" + "-"*80)
    print("CLASSIFICATION RESULT")
    print("-"*80)
    print(f"job_family: {actual_family}")
    print(f"job_subfamily: {actual_subfamily}")
    print(f"title_display: {result.get('role', {}).get('title_display', 'MISSING')}")
    print(f"employer: {result.get('employer', {}).get('name', 'MISSING')}")
    
    match = "✅ CORRECT" if actual_family == expected_family else "❌ WRONG"
    print(f"\nResult: {match}")
    
    return result


def main():
    print("="*80)
    print("CLASSIFIER DEBUG SESSION")
    print("="*80)
    
    # Get sample misclassified jobs
    print("\nFetching sample misclassified 'Product Manager' jobs...")
    samples = get_sample_misclassified_jobs(limit=3)
    
    if not samples:
        print("No misclassified jobs found!")
        return
    
    print(f"\nFound {len(samples)} sample jobs to test\n")
    
    # Test each one
    for i, sample in enumerate(samples, 1):
        print(f"\n{'#'*80}")
        print(f"SAMPLE {i}: {sample['raw_title']}")
        print(f"Company: {sample['company']}")
        print(f"Original classification: job_family={sample['job_family']}, subfamily={sample['job_subfamily']}")
        print(f"{'#'*80}")
        
        # Test classification
        result = test_classification(
            job_text=sample['raw_text'],
            expected_family='product',
            verbose=False  # Set to True to see full prompt
        )
        
        # Show full result
        print("\nFull classification result:")
        print(json.dumps(result, indent=2, default=str))
        
        input("\nPress Enter to continue to next sample...")


if __name__ == "__main__":
    main()

