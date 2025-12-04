"""
Test the improved classifier with structured input on previously misclassified jobs.
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

print("="*80)
print("TESTING IMPROVED CLASSIFIER WITH STRUCTURED INPUT")
print("="*80)

# Get a few misclassified Product Manager jobs
print("\nFetching misclassified jobs...")

# Get enriched jobs that are out_of_scope
enriched = supabase.table('enriched_jobs').select(
    'id, raw_job_id, employer_name, title_display'
).eq('job_family', 'out_of_scope').eq('is_agency', False).limit(500).execute()

# Get raw_jobs with 'product manager' in title
raw_jobs = supabase.table('raw_jobs').select(
    'id, title, company, raw_text'
).ilike('title', '%product manager%').limit(200).execute()

# Find matches
raw_lookup = {job['id']: job for job in raw_jobs.data}
samples = []

for job in enriched.data:
    if job['raw_job_id'] in raw_lookup:
        raw = raw_lookup[job['raw_job_id']]
        samples.append({
            'title': raw['title'],
            'company': raw['company'],
            'raw_text': raw['raw_text']
        })
        if len(samples) >= 3:
            break

print(f"Found {len(samples)} misclassified jobs to test\n")

# Test each one with the improved classifier
for i, sample in enumerate(samples, 1):
    print(f"\n{'#'*80}")
    print(f"TEST {i}: {sample['title']}")
    print(f"Company: {sample['company']}")
    print(f"{'#'*80}")
    
    # Test 1: OLD way (just raw_text)
    print("\n--- OLD METHOD (raw_text only) ---")
    try:
        old_result = classify_job_with_claude(sample['raw_text'], verbose=False)
        old_family = old_result.get('role', {}).get('job_family', 'MISSING')
        old_subfamily = old_result.get('role', {}).get('job_subfamily', 'MISSING')
        old_title = old_result.get('role', {}).get('title_display', 'MISSING')
        print(f"  job_family: {old_family}")
        print(f"  job_subfamily: {old_subfamily}")
        print(f"  title_display: {old_title}")
    except Exception as e:
        print(f"  ERROR: {e}")
        old_family = "ERROR"
    
    # Test 2: NEW way (structured input)
    print("\n--- NEW METHOD (structured input) ---")
    try:
        structured_input = {
            'title': sample['title'],
            'company': sample['company'],
            'description': sample['raw_text'],
            'category': 'IT Jobs',  # Typical Adzuna category for PM roles
            'location': 'London',  # Placeholder
        }
        
        new_result = classify_job_with_claude(
            job_text=sample['raw_text'],
            structured_input=structured_input,
            verbose=False
        )
        new_family = new_result.get('role', {}).get('job_family', 'MISSING')
        new_subfamily = new_result.get('role', {}).get('job_subfamily', 'MISSING')
        new_title = new_result.get('role', {}).get('title_display', 'MISSING')
        print(f"  job_family: {new_family}")
        print(f"  job_subfamily: {new_subfamily}")
        print(f"  title_display: {new_title}")
    except Exception as e:
        print(f"  ERROR: {e}")
        new_family = "ERROR"
    
    # Comparison
    print("\n--- COMPARISON ---")
    if old_family == 'out_of_scope' and new_family == 'product':
        print("  ✅ FIXED! Now correctly classified as 'product'")
    elif new_family == 'product':
        print("  ✅ Correctly classified as 'product'")
    else:
        print(f"  ❌ Still classified as '{new_family}' (expected 'product')")

print("\n" + "="*80)
print("TEST COMPLETE")
print("="*80)

