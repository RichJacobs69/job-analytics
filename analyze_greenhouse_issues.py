#!/usr/bin/env python3
"""
Detailed analysis of Greenhouse scraping issues
"""
import json
import re

def analyze_greenhouse_issues():
    with open('recent_jobs_analysis.json', 'r') as f:
        data = json.load(f)

    # Find Greenhouse jobs with issues
    greenhouse_jobs = [job for job in data if job.get('source') == 'greenhouse']
    problematic_jobs = []

    for job in greenhouse_jobs:
        raw_text = job.get('raw_text', '')
        issues = []

        # Check for various scraping issues
        text_lower = raw_text.lower()

        # Cookie/consent banners
        if any(term in text_lower for term in ['cookie', 'consent', 'gdpr', 'privacy policy', 'accept cookies']):
            issues.append('cookie_banner')

        # Bot detection
        if any(term in text_lower for term in ['bot', 'captcha', 'verification', 'prove you\'re human', 'automated request', 'blocked', 'rate limit']):
            issues.append('bot_detection')

        # Login required
        if any(term in text_lower for term in ['login required', 'sign in', 'log in', 'authentication required']):
            issues.append('login_required')

        # Paywall
        if any(term in text_lower for term in ['premium', 'subscription', 'upgrade', 'paywall', 'paid content']):
            issues.append('paywall')

        # Raw HTML
        if raw_text.count('<') > raw_text.count('>') or raw_text.count('<script') > 0:
            issues.append('raw_html')

        # Very long text (likely includes anti-bot content)
        if len(raw_text) > 10000:
            issues.append('excessively_long')

        # Missing job content
        job_indicators = ["responsibilities", "requirements", "qualifications", "about", "we are", "you will"]
        job_indicator_count = sum(1 for indicator in job_indicators if indicator in text_lower)
        if job_indicator_count < 2 and len(raw_text.strip()) > 500:
            issues.append("missing_job_content")

        if issues:
            problematic_jobs.append({
                'company': job.get('company', 'Unknown'),
                'title': job.get('title', 'Unknown'),
                'issues': issues,
                'text_length': len(raw_text),
                'posting_url': job.get('posting_url', ''),
                'text_sample': raw_text[:500],
                'raw_text': raw_text
            })

    print(f"=== GREENHOUSE SCRAPING ISSUES ANALYSIS ===")
    print(f"Total Greenhouse jobs: {len(greenhouse_jobs)}")
    print(f"Problematic jobs: {len(problematic_jobs)}")

    # Group by company
    from collections import defaultdict
    by_company = defaultdict(list)
    for job in problematic_jobs:
        by_company[job['company']].append(job)

    for company, jobs in sorted(by_company.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"\n{company}: {len(jobs)} problematic jobs")
        for job in jobs[:2]:  # Show up to 2 examples per company
            print(f"  Job: {job['title']}")
            print(f"  Issues: {', '.join(job['issues'])}")
            print(f"  Length: {job['text_length']} chars")
            print(f"  URL: {job['posting_url']}")

            # Show specific problematic content
            raw_text = job['raw_text']

            # Find cookie-related text
            cookie_matches = re.findall(r'.{0,50}(?:cookie|consent|gdpr).{0,50}', raw_text, re.IGNORECASE)
            if cookie_matches:
                print("  Cookie text found:")
                for match in cookie_matches[:2]:
                    print(f"    \"{match.strip()}\"")

            # Find bot-related text
            bot_matches = re.findall(r'.{0,50}(?:bot|captcha|automated|verification).{0,50}', raw_text, re.IGNORECASE)
            if bot_matches:
                print("  Bot detection text found:")
                for match in bot_matches[:2]:
                    print(f"    \"{match.strip()}\"")

            print(f"  Sample text: {job['text_sample'][:200]}...")
            print()

if __name__ == "__main__":
    analyze_greenhouse_issues()




