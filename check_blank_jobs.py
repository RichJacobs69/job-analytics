#!/usr/bin/env python3
"""
Check for blank/minimal text jobs in the database
"""
from pipeline.db_connection import supabase
from datetime import datetime, timedelta

def check_blank_jobs():
    print('Querying for jobs with blank or minimal text...')

    query = supabase.table('raw_jobs').select('''
        id, source, posting_url, title, company, raw_text, scraped_at
    ''').gte('scraped_at', (datetime.now() - timedelta(days=7)).isoformat()).limit(1000)

    result = query.execute()

    blank_jobs = []
    minimal_jobs = []
    short_jobs = []

    for job in result.data:
        raw_text = job.get('raw_text', '').strip()
        length = len(raw_text)

        if length == 0:
            blank_jobs.append(job)
        elif length < 10:
            minimal_jobs.append(job)
        elif length < 100:
            short_jobs.append(job)

    print(f'\n=== BLANK TEXT ANALYSIS (Last 7 days) ===')
    print(f'Total jobs checked: {len(result.data)}')
    print(f'Blank text (0 chars): {len(blank_jobs)}')
    print(f'Minimal text (<10 chars): {len(minimal_jobs)}')
    print(f'Short text (10-99 chars): {len(short_jobs)}')

    if blank_jobs:
        print(f'\n=== BLANK JOBS ===')
        for job in blank_jobs[:5]:
            print(f'- {job.get("company", "Unknown")}: {job.get("title", "Unknown")} ({job.get("source", "unknown")})')

    if minimal_jobs:
        print(f'\n=== MINIMAL TEXT JOBS ===')
        for job in minimal_jobs[:5]:
            print(f'- {job.get("company", "Unknown")}: "{job.get("raw_text", "")}" ({job.get("source", "unknown")})')

    if short_jobs:
        print(f'\n=== SHORT TEXT JOBS (examples) ===')
        for job in short_jobs[:3]:
            raw_text = job.get('raw_text', '')
            print(f'- {job.get("company", "Unknown")}: "{raw_text[:100]}" ({len(raw_text)} chars, {job.get("source", "unknown")})')

if __name__ == "__main__":
    check_blank_jobs()




