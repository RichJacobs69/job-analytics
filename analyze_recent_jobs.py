#!/usr/bin/env python3
"""
Analyze recent job scraping for quality issues
"""
import sys
import json
from datetime import datetime, timedelta
from collections import defaultdict

# Add current directory to path
sys.path.append('.')

from pipeline.db_connection import supabase

def main():
    # Calculate date range for last week
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    print(f'Analyzing jobs scraped between {start_date.date()} and {end_date.date()}')

    # Query raw_jobs for recent entries, then join with enriched_jobs
    raw_query = supabase.table('raw_jobs').select('''
        id,
        raw_text,
        source,
        scraped_at,
        posting_url,
        title,
        company,
        enriched_jobs(employer_name, title_display, job_family, city_code, posted_date)
    ''').gte('scraped_at', start_date.isoformat()).lte('scraped_at', end_date.isoformat()).limit(500)

    result = raw_query.execute()
    print(f'Found {len(result.data)} raw jobs to analyze')

    # Save raw data for analysis
    with open('recent_jobs_analysis.json', 'w') as f:
        json.dump(result.data, f, indent=2, default=str)

    print('Data saved to recent_jobs_analysis.json')

    # Analyze for scraping issues (Greenhouse only)
    issues_by_company = defaultdict(list)
    greenhouse_jobs = [job for job in result.data if job.get('source') == 'greenhouse']
    total_greenhouse_jobs = len(greenhouse_jobs)

    print(f"Filtering to Greenhouse jobs: {total_greenhouse_jobs} out of {len(result.data)} total")

    for raw_job in greenhouse_jobs:
        raw_text = raw_job.get('raw_text', '')
        source = raw_job.get('source', 'unknown')
        posting_url = raw_job.get('posting_url', '')

        # Get enriched job data if available
        enriched_jobs = raw_job.get('enriched_jobs', [])
        if enriched_jobs:
            enriched = enriched_jobs[0] if isinstance(enriched_jobs, list) else enriched_jobs
            employer = enriched.get('employer_name', raw_job.get('company', 'Unknown'))
            title = enriched.get('title_display', raw_job.get('title', 'Unknown'))
        else:
            employer = raw_job.get('company', 'Unknown')
            title = raw_job.get('title', 'Unknown')

        issues = analyze_text_for_issues(raw_text)

        if issues:
            issues_by_company[employer].append({
                'title': title,
                'issues': issues,
                'text_length': len(raw_text),
                'text_sample': raw_text[:1000] + '...' if len(raw_text) > 1000 else raw_text,
                'source': source,
                'posting_url': posting_url,
                'full_text': raw_text  # Keep full text for detailed analysis
            })

    # Print Greenhouse-specific summary
    print(f"\n=== GREENHOUSE SCRAPING ISSUES SUMMARY ===")
    print(f"Greenhouse jobs analyzed: {total_greenhouse_jobs}")
    print(f"Companies with issues: {len(issues_by_company)}")

    if not issues_by_company:
        print("No scraping issues found in recent Greenhouse jobs!")
        return

    # Sort companies by number of problematic jobs
    sorted_companies = sorted(issues_by_company.items(), key=lambda x: len(x[1]), reverse=True)

    print(f"\n=== DETAILED ANALYSIS BY COMPANY ===")

    for company, jobs in sorted_companies[:20]:  # Top 20 problematic companies
        print(f"\n{company}: {len(jobs)} problematic jobs")

        # Show most common issues
        issue_counts = defaultdict(int)
        for job in jobs:
            for issue in job['issues']:
                issue_counts[issue] += 1

        for issue, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {issue}: {count} jobs")

        # Show detailed example with problematic content
        example = jobs[0]
        print(f"  Example - {example['text_length']} chars:")
        print(f"    URL: {example['posting_url']}")
        print(f"    Title: {example['title']}")

        # Show specific problematic text patterns
        full_text = example['full_text']
        print(f"    Sample text: {example['text_sample'][:500]}...")

        # Look for specific anti-scraping patterns
        if 'cookie' in full_text.lower() or 'consent' in full_text.lower():
            print("    ⚠️  CONTAINS COOKIE BANNER TEXT")
        if 'bot' in full_text.lower() or 'captcha' in full_text.lower() or 'automated' in full_text.lower():
            print("    ⚠️  CONTAINS BOT DETECTION TEXT")
        if 'login' in full_text.lower() or 'sign in' in full_text.lower():
            print("    ⚠️  CONTAINS LOGIN REQUIREMENT")
        if len(full_text) > 10000:
            print("    ⚠️  UNUSUALLY LONG TEXT (>10k chars)")

        print()

    # Overall patterns summary
    print(f"=== OVERALL GREENHOUSE PATTERNS ===")
    all_issues = defaultdict(int)
    for jobs in issues_by_company.values():
        for job in jobs:
            for issue in job['issues']:
                all_issues[issue] += 1

    print("Most common issues across all Greenhouse jobs:")
    for issue, count in sorted(all_issues.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {issue}: {count} total occurrences")

def analyze_text_for_issues(text):
    """Analyze text for scraping issues"""
    issues = []
    text_lower = text.lower()

    # Check for very short text (likely truncated)
    if len(text.strip()) < 200:
        issues.append("very_short_text")

    # Check for cookie/consent banners
    cookie_indicators = [
        "cookie", "consent", "gdpr", "privacy policy", "accept cookies",
        "we use cookies", "cookie preferences", "manage cookies"
    ]
    if any(indicator in text_lower for indicator in cookie_indicators):
        issues.append("cookie_banner")

    # Check for bot detection
    bot_indicators = [
        "bot", "captcha", "verification", "prove you're human",
        "automated request", "blocked", "access denied",
        "rate limit", "too many requests"
    ]
    if any(indicator in text_lower for indicator in bot_indicators):
        issues.append("bot_detection")

    # Check for login required
    login_indicators = [
        "login required", "sign in", "log in", "authentication required",
        "please log in", "account required"
    ]
    if any(indicator in text_lower for indicator in login_indicators):
        issues.append("login_required")

    # Check for paywall
    paywall_indicators = [
        "premium", "subscription", "upgrade", "paywall",
        "paid content", "subscribe to view"
    ]
    if any(indicator in text_lower for indicator in paywall_indicators):
        issues.append("paywall")

    # Check for raw HTML (unparsed)
    if text.count('<') > text.count('>') or text.count('<script') > 0 or text.count('<style') > 0:
        if len(text) < 1000:  # Only flag if it's short (likely failed parsing)
            issues.append("raw_html")

    # Check for repetitive content (scraping failure)
    words = text.split()
    if len(words) > 10:
        # Check if first 50 words repeat in next 50
        first_50 = ' '.join(words[:50]).lower()
        next_50 = ' '.join(words[50:100]).lower() if len(words) > 100 else ''
        if len(next_50) > 10 and first_50 in next_50:
            issues.append("repetitive_content")

    # Check for missing job content indicators
    job_indicators = ["responsibilities", "requirements", "qualifications", "about", "we are", "you will"]
    job_indicator_count = sum(1 for indicator in job_indicators if indicator in text_lower)
    if job_indicator_count < 2 and len(text.strip()) > 100:
        issues.append("missing_job_content")

    return issues

if __name__ == "__main__":
    main()
