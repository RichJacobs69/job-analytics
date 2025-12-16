#!/usr/bin/env python3
"""
Detailed analysis of blank Greenhouse jobs
"""
from pipeline.db_connection import supabase
from datetime import datetime, timedelta
from collections import defaultdict

def analyze_blank_details():
    # Get more details about the blank jobs
    print('Getting detailed information about blank jobs...')

    query = supabase.table('raw_jobs').select('''
        id, source, posting_url, title, company, raw_text, scraped_at, metadata
    ''').gte('scraped_at', (datetime.now() - timedelta(days=30)).isoformat()).eq('source', 'greenhouse')

    result = query.execute()

    blank_jobs = [job for job in result.data if len(job.get('raw_text', '').strip()) == 0]

    print(f'\n=== DETAILED ANALYSIS OF {len(blank_jobs)} BLANK GREENHOUSE JOBS ===')

    by_company = defaultdict(list)
    for job in blank_jobs:
        by_company[job.get('company', 'Unknown')].append(job)

    for company, jobs in sorted(by_company.items(), key=lambda x: len(x[1]), reverse=True):
        print(f'\n{company}: {len(jobs)} blank jobs')
        for job in jobs[:3]:  # Show up to 3 examples per company
            print(f'  - {job.get("title", "Unknown")}')
            print(f'    URL: {job.get("posting_url", "")}')
            print(f'    Scraped: {job.get("scraped_at", "")[:19]}')
            metadata = job.get('metadata', {})
            if metadata:
                print(f'    Metadata keys: {list(metadata.keys())}')
            print()

if __name__ == "__main__":
    analyze_blank_details()




