#!/usr/bin/env python3
"""
Check the original analysis data for blank jobs
"""
import json

def check_original_analysis():
    # Load the original analysis data
    with open('recent_jobs_analysis.json', 'r') as f:
        data = json.load(f)

    print('Checking for actual blank/empty raw_text in the analysis data...')

    blank_count = 0
    short_count = 0
    samples = []

    for job in data:
        # Check raw_jobs nested data
        raw_jobs = job.get('raw_jobs', [])
        if raw_jobs:
            raw_job = raw_jobs[0] if isinstance(raw_jobs, list) else raw_jobs
            raw_text = raw_job.get('raw_text', '').strip()
            length = len(raw_text)

            if length == 0:
                blank_count += 1
                if blank_count <= 3:
                    samples.append({
                        'company': job.get('employer_name', 'Unknown'),
                        'title': job.get('title_display', 'Unknown'),
                        'source': raw_job.get('source', 'unknown'),
                        'url': raw_job.get('posting_url', '')
                    })
            elif length < 50:
                short_count += 1

    print(f'Blank raw_text (0 chars): {blank_count}')
    print(f'Short raw_text (<50 chars): {short_count}')

    if samples:
        print('\nExamples of blank jobs:')
        for sample in samples:
            print(f'- {sample["company"]}: {sample["title"]} ({sample["source"]})')
            print(f'  URL: {sample["url"]}')

if __name__ == "__main__":
    check_original_analysis()




