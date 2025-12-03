"""
Script to scrape job titles from Adzuna job pages.

For jobs where the Adzuna API didn't return a title, this script
visits the original Adzuna URLs and extracts the job title from the HTML.

Usage:
    python scripts/scrape_adzuna_titles.py [--update-db]
"""
import os
import sys
import json
import re
import time
import argparse
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Required packages: pip install requests beautifulsoup4")
    sys.exit(1)

from pipeline.db_connection import supabase


def extract_adzuna_job_id(url: str) -> Optional[str]:
    """Extract job ID from Adzuna URL."""
    # Pattern: /jobs/land/ad/5519126617 or /jobs/details/5519126617
    match = re.search(r'/(?:ad|details)/(\d+)', url)
    if match:
        return match.group(1)
    return None


def scrape_adzuna_title(url: str) -> Tuple[Optional[str], str]:
    """
    Scrape job title from Adzuna job page.
    
    Args:
        url: Adzuna job URL
        
    Returns:
        Tuple of (title or None, status message)
    """
    try:
        # Follow redirects to get the final page
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try multiple selectors for job title
        title_selectors = [
            'h1.job-title',
            'h1[data-testid="job-title"]',
            '.job-title h1',
            'h1.title',
            '.adp-title h1',
            'h1[itemprop="title"]',
            '.ui-job-title',
            'h1',  # Fallback to first h1
        ]
        
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                # Filter out generic/company names
                if title and len(title) > 3 and len(title) < 200:
                    # Check if it looks like a job title (not company name)
                    if not any(skip in title.lower() for skip in ['404', 'not found', 'error', 'home page']):
                        return title, "scraped"
        
        # Also try meta tags
        og_title = soup.select_one('meta[property="og:title"]')
        if og_title and og_title.get('content'):
            title = og_title['content']
            # Clean up "Job Title at Company - Adzuna" format
            if ' at ' in title:
                title = title.split(' at ')[0].strip()
            elif ' - ' in title:
                title = title.split(' - ')[0].strip()
            if title and len(title) > 3:
                return title, "scraped_meta"
        
        return None, "title_not_found"
        
    except requests.exceptions.Timeout:
        return None, "timeout"
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return None, "job_expired_404"
        return None, f"http_error_{e.response.status_code}"
    except Exception as e:
        return None, f"error: {str(e)[:50]}"


def update_enriched_job_title(enriched_id: int, new_title: str) -> bool:
    """Update the title_display field in enriched_jobs table."""
    try:
        result = supabase.table("enriched_jobs").update({
            "title_display": new_title
        }).eq("id", enriched_id).execute()
        return len(result.data) > 0
    except Exception as e:
        print(f"Error updating enriched job {enriched_id}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Scrape job titles from Adzuna pages for records with Unknown Title'
    )
    parser.add_argument(
        '--update-db',
        action='store_true',
        help='Update the database with scraped titles'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be updated without making changes'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=1.0,
        help='Delay between requests in seconds (default: 1.0)'
    )
    args = parser.parse_args()
    
    # Read the results from derive_missing_titles.py
    results_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "output",
        "title_derivation_results.json"
    )
    
    if not os.path.exists(results_path):
        print(f"Results file not found: {results_path}")
        print("Please run derive_missing_titles.py first")
        sys.exit(1)
    
    with open(results_path, 'r', encoding='utf-8') as f:
        records = json.load(f)
    
    print(f"Loaded {len(records)} records from previous analysis")
    print(f"Delay between requests: {args.delay}s")
    print()
    
    # Process records that don't have a derived title
    results = []
    
    for i, record in enumerate(records):
        enriched_id = record['enriched_id']
        employer = record['employer']
        posting_url = record.get('posting_url', '')
        existing_title = record.get('derived_title')
        
        print(f"[{i+1}/{len(records)}] {employer} (ID: {enriched_id})")
        
        # Skip if we already have a derived title
        if existing_title:
            print(f"  -> Already has title: {existing_title}")
            results.append({
                **record,
                'scraped_title': existing_title,
                'scrape_status': 'already_derived'
            })
            continue
        
        # Skip if no URL
        if not posting_url or 'adzuna' not in posting_url.lower():
            print(f"  -> No Adzuna URL available")
            results.append({
                **record,
                'scraped_title': None,
                'scrape_status': 'no_url'
            })
            continue
        
        # Scrape the title
        print(f"  -> Scraping: {posting_url[:80]}...")
        title, status = scrape_adzuna_title(posting_url)
        
        if title:
            print(f"  -> Found title: {title}")
        else:
            print(f"  -> Failed: {status}")
        
        results.append({
            **record,
            'scraped_title': title,
            'scrape_status': status
        })
        
        # Delay between requests
        if i < len(records) - 1:
            time.sleep(args.delay)
    
    # Summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    scraped_count = sum(1 for r in results if r.get('scraped_title'))
    already_derived = sum(1 for r in results if r.get('scrape_status') == 'already_derived')
    
    print(f"Total records: {len(results)}")
    print(f"Already had titles: {already_derived}")
    print(f"Successfully scraped: {scraped_count - already_derived}")
    print(f"Failed to scrape: {len(results) - scraped_count}")
    
    # Group by status
    statuses = {}
    for r in results:
        status = r.get('scrape_status', 'unknown')
        statuses[status] = statuses.get(status, 0) + 1
    
    print("\nBy status:")
    for status, count in sorted(statuses.items(), key=lambda x: -x[1]):
        print(f"  {status}: {count}")
    
    # Show scraped titles
    print("\n" + "=" * 80)
    print("SCRAPED TITLES")
    print("=" * 80)
    for r in results:
        title = r.get('scraped_title')
        if title:
            status = r.get('scrape_status', '')
            marker = "[EXISTING]" if status == 'already_derived' else "[NEW]"
            print(f"  {marker} [{r['enriched_id']}] {r['employer']}: {title}")
    
    # Update database if requested
    if args.update_db or args.dry_run:
        print("\n" + "=" * 80)
        print("DATABASE UPDATES" + (" (DRY RUN)" if args.dry_run else ""))
        print("=" * 80)
        
        update_count = 0
        for r in results:
            title = r.get('scraped_title')
            status = r.get('scrape_status', '')
            
            # Only update new scraped titles (not already_derived)
            if title and status not in ['already_derived', 'no_url']:
                enriched_id = int(r['enriched_id'])
                
                if args.dry_run:
                    print(f"  [DRY RUN] Would update ID {enriched_id}: '{title}'")
                    update_count += 1
                else:
                    success = update_enriched_job_title(enriched_id, title)
                    if success:
                        print(f"  [UPDATED] ID {enriched_id}: '{title}'")
                        update_count += 1
                    else:
                        print(f"  [FAILED] ID {enriched_id}")
        
        print(f"\nTotal {'would update' if args.dry_run else 'updated'}: {update_count}")
    
    # Show jobs that still need manual review
    print("\n" + "=" * 80)
    print("STILL NEED MANUAL REVIEW")
    print("=" * 80)
    for r in results:
        if not r.get('scraped_title'):
            print(f"  [{r['enriched_id']}] {r['employer']}: {r.get('scrape_status', 'unknown')}")
            if r.get('posting_url'):
                print(f"    URL: {r['posting_url'][:100]}...")
    
    # Save results
    output_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "output",
        "adzuna_scrape_results.json"
    )
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()

