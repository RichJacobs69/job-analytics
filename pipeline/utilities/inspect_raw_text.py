"""
Inspect the raw_text of misclassified jobs to understand what Claude is seeing.
"""

import os
import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))

print("="*80)
print("INSPECTING RAW_TEXT OF MISCLASSIFIED JOBS")
print("="*80)

# Get a few raw jobs with 'product manager' in title
print("\nFetching raw jobs with 'product manager' in title...")
raw_jobs = supabase.table('raw_jobs').select(
    'id, title, company, raw_text, source'
).ilike('title', '%product manager%').limit(5).execute()

for i, job in enumerate(raw_jobs.data[:3], 1):
    print(f"\n{'#'*80}")
    print(f"SAMPLE {i}")
    print(f"{'#'*80}")
    print(f"Title (from raw_jobs.title column): {job['title']}")
    print(f"Company: {job['company']}")
    print(f"Source: {job['source']}")
    print(f"raw_text length: {len(job['raw_text'])} chars")
    
    # Check if title appears in raw_text
    title_lower = job['title'].lower() if job['title'] else ''
    raw_lower = job['raw_text'].lower()
    
    if title_lower and title_lower in raw_lower:
        print("✅ Title appears in raw_text")
    else:
        print("❌ Title does NOT appear in raw_text!")
    
    if 'product manager' in raw_lower:
        print("✅ 'product manager' appears in raw_text")
    else:
        print("❌ 'product manager' does NOT appear in raw_text!")
    
    # Show the raw_text
    print(f"\n--- FULL RAW_TEXT ---")
    # Show first 2000 chars
    text = job['raw_text']
    if len(text) > 2000:
        print(text[:2000])
        print(f"\n... [truncated, {len(text) - 2000} more chars]")
    else:
        print(text)
    print("-"*80)

