"""
Query to find product manager jobs incorrectly labelled as out_of_scope.
"""

import os
import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))

# Get enriched jobs that are out_of_scope and not agency
print('Fetching out_of_scope non-agency enriched jobs...')
enriched = supabase.table('enriched_jobs').select(
    'id, raw_job_id, employer_name, title_display, job_family, job_subfamily, seniority'
).eq('job_family', 'out_of_scope').eq('is_agency', False).limit(5000).execute()

print(f'Found {len(enriched.data)} out_of_scope non-agency jobs')

# Get the raw_job_ids
raw_job_ids = [job['raw_job_id'] for job in enriched.data]

# Fetch raw_jobs with title containing 'product' 
print('Fetching raw_jobs with product in title...')
raw_jobs = supabase.table('raw_jobs').select(
    'id, title, company, posting_url'
).ilike('title', '%product%').limit(5000).execute()

print(f'Found {len(raw_jobs.data)} raw jobs with product in title')

# Create lookup dict
raw_lookup = {job['id']: job for job in raw_jobs.data}

# Join in Python
results = []
for job in enriched.data:
    raw_id = job['raw_job_id']
    if raw_id in raw_lookup:
        raw = raw_lookup[raw_id]
        results.append({
            'raw_title': raw['title'],
            'company': raw['company'],
            'enriched_title': job['title_display'],
            'employer': job['employer_name'],
            'subfamily': job['job_subfamily'],
            'seniority': job['seniority'],
            'posting_url': raw['posting_url']
        })

print(f'\n{"="*80}')
print(f'Found {len(results)} product jobs labelled as out_of_scope')
print(f'{"="*80}\n')

# Display results
for i, r in enumerate(results, 1):
    print(f'{i}. {r["raw_title"]}')
    print(f'   Company: {r["company"]} / {r["employer"]}')
    print(f'   Enriched Title: {r["enriched_title"]}')
    print(f'   Subfamily: {r["subfamily"]}, Seniority: {r["seniority"]}')
    url = r["posting_url"]
    if len(url) > 80:
        url = url[:80] + '...'
    print(f'   URL: {url}')
    print()

