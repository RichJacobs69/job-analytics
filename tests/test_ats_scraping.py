"""
Test harness for ATS detection and job scraping.

This script accepts Adzuna job data and attempts to:
1. Detect the company's ATS system
2. Search for the job on that ATS
3. Scrape full job description
4. Store enriched data in Supabase

Usage:
    # Provide Adzuna sample data as CSV or JSON
    python test_ats_scraping.py --data sample_jobs.csv
    python test_ats_scraping.py --data sample_jobs.json
"""

import json
import csv
import argparse
from typing import List, Dict, Optional
from ats_scraper import scrape_full_job_text, ATSDetector, get_scraper_for_ats
from db_connection import update_raw_job_full_text, get_raw_job_by_id
import time
import sys
import io

# Handle Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


class ATSScrapingTest:
    """Test harness for ATS scraping"""

    def __init__(self):
        self.results = []
        self.successes = 0
        self.failures = 0

    def load_jobs_from_csv(self, filepath: str) -> List[Dict]:
        """
        Load Adzuna job data from CSV.

        Expected columns: employer_name, title, location, id (optional: raw_job_id)
        """
        jobs = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    jobs.append(row)
            print(f"[OK] Loaded {len(jobs)} jobs from {filepath}")
            return jobs
        except Exception as e:
            print(f"[ERROR] Error loading CSV: {e}")
            return []

    def load_jobs_from_json(self, filepath: str) -> List[Dict]:
        """
        Load Adzuna job data from JSON.

        Expected format: List of dicts with employer_name, title, location
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                jobs = json.load(f)
            if not isinstance(jobs, list):
                jobs = [jobs]
            print(f"[DONE] Loaded {len(jobs)} jobs from {filepath}")
            return jobs
        except Exception as e:
            print(f"[FAIL] Error loading JSON: {e}")
            return []

    def test_job(self, job: Dict, save_to_db: bool = False) -> Dict:
        """
        Test scraping for a single job.

        Args:
            job: Job dict with at least: employer_name, title, location
            save_to_db: If True, save results to Supabase

        Returns:
            Result dict with status, full_text, ats_info, etc.
        """
        employer = job.get('employer_name', '')
        title = job.get('title', '')
        location = job.get('location', '')
        raw_job_id = job.get('id') or job.get('raw_job_id')

        result = {
            'employer': employer,
            'title': title,
            'location': location,
            'raw_job_id': raw_job_id,
            'status': 'pending',
            'ats_detected': None,
            'job_found': False,
            'text_length': 0,
            'error': None
        }

        if not employer or not title:
            result['status'] = 'error'
            result['error'] = 'Missing employer or title'
            self.failures += 1
            return result

        print(f"\n{'='*70}")
        print(f"Testing: {title}")
        print(f"Company: {employer}")
        print(f"Location: {location}")
        print(f"{'='*70}")

        try:
            # Attempt scraping
            scrape_result = scrape_full_job_text(
                employer_name=employer,
                job_title=title,
                location=location
            )

            if scrape_result:
                result['status'] = 'success'
                result['ats_detected'] = scrape_result['ats_name']
                result['ats_type'] = scrape_result['ats_type']
                result['job_found'] = True
                result['job_url'] = scrape_result['job_url']
                result['text_length'] = len(scrape_result['full_text'])
                result['full_text'] = scrape_result['full_text'][:500] + "..." if len(scrape_result['full_text']) > 500 else scrape_result['full_text']

                print(f"\n[SUCCESS] SUCCESS!")
                print(f"   ATS: {scrape_result['ats_name']}")
                print(f"   Job URL: {scrape_result['job_url']}")
                print(f"   Text length: {result['text_length']} chars")

                # Save to Supabase if requested
                if save_to_db and raw_job_id:
                    success = update_raw_job_full_text(
                        raw_job_id=int(raw_job_id),
                        full_text=scrape_result['full_text'],
                        text_source='ats_scrape'
                    )
                    if success:
                        print(f"   [DONE] Saved to Supabase (raw_job_id: {raw_job_id})")
                    else:
                        print(f"   [WARN] Failed to save to Supabase")

                self.successes += 1

            else:
                result['status'] = 'not_found'
                result['error'] = 'Could not scrape job from ATS'
                print(f"\n[FAIL] FAILED: Could not scrape job")
                self.failures += 1

        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            print(f"\n[FAIL] ERROR: {e}")
            self.failures += 1

        self.results.append(result)
        time.sleep(2)  # Rate limiting

        return result

    def test_all_jobs(self, jobs: List[Dict], save_to_db: bool = False):
        """
        Test scraping for all jobs in list.

        Args:
            jobs: List of job dicts
            save_to_db: If True, save successful results to Supabase
        """
        print(f"\n{'='*70}")
        print(f"Testing {len(jobs)} jobs...")
        print(f"{'='*70}")

        for i, job in enumerate(jobs, 1):
            print(f"\n[{i}/{len(jobs)}]")
            self.test_job(job, save_to_db=save_to_db)

    def print_summary(self):
        """Print summary of results"""
        print(f"\n{'='*70}")
        print("SUMMARY")
        print(f"{'='*70}")
        print(f"Total jobs tested: {len(self.results)}")
        print(f"Successes: {self.successes}")
        print(f"Failures: {self.failures}")
        print(f"Success rate: {self.successes / len(self.results) * 100:.1f}%")

        print(f"\n{'='*70}")
        print("Results by ATS:")
        print(f"{'='*70}")

        ats_counts = {}
        for result in self.results:
            if result['ats_detected']:
                ats = result['ats_detected']
                ats_counts[ats] = ats_counts.get(ats, 0) + 1

        for ats, count in sorted(ats_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {ats}: {count}")

        print(f"\n{'='*70}")
        print("Failed/Not Found:")
        print(f"{'='*70}")

        failures = [r for r in self.results if r['status'] in ['error', 'not_found']]
        for result in failures[:10]:  # Show first 10
            print(f"  {result['employer']} - {result['title']}")
            if result['error']:
                print(f"    Error: {result['error']}")

    def export_results(self, output_file: str):
        """Export results to JSON"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print(f"\n[DONE] Results exported to {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Test ATS scraping with sample data")
    parser.add_argument('--data', type=str, help='Path to CSV or JSON file with job data')
    parser.add_argument('--format', type=str, choices=['csv', 'json'], default='auto',
                        help='Format of input file (auto-detect by default)')
    parser.add_argument('--save-to-db', action='store_true',
                        help='Save successful results to Supabase')
    parser.add_argument('--output', type=str, default='ats_scraping_results.json',
                        help='Output file for results')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of jobs to test')

    args = parser.parse_args()

    if not args.data:
        print("Error: Please provide --data argument with path to job data file")
        parser.print_help()
        return

    # Initialize test harness
    tester = ATSScrapingTest()

    # Load jobs
    if args.format == 'auto':
        if args.data.endswith('.csv'):
            args.format = 'csv'
        elif args.data.endswith('.json'):
            args.format = 'json'
        else:
            print("Error: Could not auto-detect format. Please specify --format")
            return

    if args.format == 'csv':
        jobs = tester.load_jobs_from_csv(args.data)
    else:
        jobs = tester.load_jobs_from_json(args.data)

    if not jobs:
        print("Error: No jobs loaded")
        return

    # Limit if specified
    if args.limit:
        jobs = jobs[:args.limit]
        print(f"Limited to {args.limit} jobs")

    # Run tests
    tester.test_all_jobs(jobs, save_to_db=args.save_to_db)

    # Print summary and export
    tester.print_summary()
    tester.export_results(args.output)


if __name__ == "__main__":
    main()
