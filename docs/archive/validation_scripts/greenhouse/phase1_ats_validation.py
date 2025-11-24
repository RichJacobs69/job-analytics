#!/usr/bin/env python3
"""
Phase 1: ATS Validation Test

Purpose: Validate which of the 6 sample companies actually use Greenhouse
and capture their job data for quality review.

This script:
1. Tests each company on both Greenhouse domains
2. Runs 8-point validation on results
3. Generates detailed HTML report for visual inspection
4. Saves JSON results for programmatic analysis
5. Produces summary statistics

Output Files:
- phase1_results.json - Complete raw data
- phase1_report.html - Human-readable report with job previews
- phase1_summary.txt - Text summary

Usage:
    python scrapers/greenhouse/phase1_ats_validation.py
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import asdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scrapers.greenhouse.greenhouse_scraper import GreenhouseScraper, Job


class Phase1Validator:
    """Validates 6 sample companies for ATS platform compatibility"""

    def __init__(self):
        self.results = {}
        self.test_companies = [
            'github',
            'openai',
            'coinbase',
            'mongodb',
            'datadog',
            'etsy'
        ]

    async def run_validation(self):
        """Run complete Phase 1 validation"""

        print("\n" + "="*80)
        print("PHASE 1: ATS VALIDATION - Sample 6 Companies")
        print("="*80 + "\n")

        scraper = GreenhouseScraper(headless=True, max_concurrent_pages=2)

        try:
            await scraper.init()

            for company in self.test_companies:
                print(f"\nTesting: {company.upper()}")
                print("-" * 80)

                try:
                    jobs = await scraper.scrape_company(company)
                    self.results[company] = self._analyze_company(company, jobs)

                except Exception as e:
                    print(f"ERROR: {str(e)[:200]}")
                    self.results[company] = {
                        "status": "ERROR",
                        "error": str(e),
                        "jobs_found": 0,
                        "validation": {}
                    }

        finally:
            await scraper.close()

        return self._generate_reports()

    def _analyze_company(self, company: str, jobs: List[Job]) -> Dict:
        """Analyze scraped jobs for a company"""

        results = {
            "company": company,
            "timestamp": datetime.now().isoformat(),
            "status": "SUCCESS" if jobs else "FAILED",
            "jobs_found": len(jobs),
            "validation": {},
            "jobs_summary": []
        }

        if not jobs:
            results["validation"]["result"] = "FAIL - No jobs found (company may not use Greenhouse)"
            return results

        # Run validation checks
        results["validation"] = self._run_validation_checks(jobs)

        # Capture job summaries for review
        results["jobs_summary"] = [
            {
                "title": job.title,
                "location": job.location,
                "url": job.url,
                "description_length": len(job.description) if job.description else 0,
                "has_content_sections": self._check_content_sections(job.description),
                "null_description": job.description is None or len(job.description.strip()) == 0,
            }
            for job in jobs[:5]  # First 5 for review
        ]

        # Print summary
        print(f"✓ Found {len(jobs)} jobs")
        print(f"  Avg description: {sum(len(j.description) for j in jobs if j.description) // len(jobs):,} chars")
        print(f"  Quality: {results['validation'].get('quality_score', 'N/A')}/100")

        return results

    def _run_validation_checks(self, jobs: List[Job]) -> Dict:
        """Run 8 validation checks"""

        checks = {}

        # 1. Jobs count
        checks["jobs_count"] = {
            "passed": len(jobs) >= 5,
            "message": f"{len(jobs)} jobs found"
        }

        # 2. Null descriptions
        null_jobs = [j for j in jobs if not j.description or len(j.description.strip()) == 0]
        checks["null_descriptions"] = {
            "passed": len(null_jobs) == 0,
            "message": f"{len(null_jobs)} jobs with null description" if null_jobs else "All jobs have descriptions"
        }

        # 3. Description length
        descriptions = [j.description for j in jobs if j.description]
        if descriptions:
            lengths = [len(d) for d in descriptions]
            substantial = sum(1 for l in lengths if l >= 2000)
            checks["description_length"] = {
                "passed": substantial / len(jobs) >= 0.9,
                "avg_chars": sum(lengths) // len(lengths),
                "min_chars": min(lengths),
                "max_chars": max(lengths),
                "substantial_pct": (substantial / len(jobs) * 100) if jobs else 0,
                "message": f"{substantial}/{len(jobs)} jobs with 2000+ chars"
            }
        else:
            checks["description_length"] = {
                "passed": False,
                "message": "No descriptions to analyze"
            }

        # 4. Content sections (hybrid, remote, benefits, requirements)
        jobs_with_sections = self._count_jobs_with_content_sections(jobs)
        checks["content_sections"] = {
            "passed": jobs_with_sections / len(jobs) >= 0.85 if jobs else False,
            "jobs_with_full_content": jobs_with_sections,
            "percentage": (jobs_with_sections / len(jobs) * 100) if jobs else 0,
            "message": f"{jobs_with_sections}/{len(jobs)} with full content sections"
        }

        # 5. URL integrity
        malformed = [j for j in jobs if not j.url or not j.url.startswith(('http://', 'https://'))]
        checks["url_integrity"] = {
            "passed": len(malformed) == 0,
            "malformed_count": len(malformed),
            "message": "All URLs valid" if len(malformed) == 0 else f"{len(malformed)} malformed URLs"
        }

        # 6. Deduplication
        urls = [j.url for j in jobs]
        duplicates = len(urls) - len(set(urls))
        checks["deduplication"] = {
            "passed": duplicates == 0,
            "duplicate_count": duplicates,
            "message": "No duplicates" if duplicates == 0 else f"{duplicates} duplicate URLs"
        }

        # 7. Field completeness
        complete_jobs = sum(
            1 for j in jobs
            if all([j.company, j.title, j.location, j.url, j.job_id, j.description])
        )
        checks["field_completeness"] = {
            "passed": complete_jobs / len(jobs) >= 0.95 if jobs else False,
            "complete_jobs": complete_jobs,
            "percentage": (complete_jobs / len(jobs) * 100) if jobs else 0,
            "message": f"{complete_jobs}/{len(jobs)} with all fields"
        }

        # 8. Quality score (composite)
        quality_components = {
            "description_coverage": (len(descriptions) / len(jobs) * 100) if jobs else 0,
            "substantial_content": checks.get("description_length", {}).get("substantial_pct", 0),
            "field_completeness": checks["field_completeness"]["percentage"],
            "content_sections": checks["content_sections"]["percentage"]
        }

        # Weighted score
        quality_score = (
            quality_components["description_coverage"] * 0.25 +
            quality_components["substantial_content"] * 0.30 +
            quality_components["field_completeness"] * 0.25 +
            quality_components["content_sections"] * 0.20
        )

        checks["quality_score"] = round(quality_score, 1)

        # Overall result
        passed = sum(1 for c in checks.values() if isinstance(c, dict) and c.get("passed", False))
        checks["result"] = f"PASS - {passed}/7 checks passed" if passed >= 6 else f"FAIL - Only {passed}/7 checks passed"

        return checks

    def _check_content_sections(self, description: str) -> Dict:
        """Check which content sections are present in description"""

        if not description:
            return {}

        desc_lower = description.lower()
        sections = {
            "responsibilities": any(kw in desc_lower for kw in ["responsibility", "responsibilities", "role", "this role"]),
            "benefits": any(kw in desc_lower for kw in ["benefit", "benefits", "compensation", "pay", "salary"]),
            "work_arrangement": any(kw in desc_lower for kw in ["hybrid", "remote", "office", "work-from"]),
            "requirements": any(kw in desc_lower for kw in ["requirement", "requirements", "qualified", "skills"])
        }

        return sections

    def _count_jobs_with_content_sections(self, jobs: List[Job]) -> int:
        """Count how many jobs have 3+ content sections"""

        count = 0
        for job in jobs:
            if job.description:
                sections = self._check_content_sections(job.description)
                if sum(sections.values()) >= 3:
                    count += 1

        return count

    def _generate_reports(self):
        """Generate JSON, HTML, and text reports"""

        print("\n" + "="*80)
        print("GENERATING REPORTS")
        print("="*80 + "\n")

        # 1. JSON Report (raw data)
        json_file = "phase1_results.json"
        with open(json_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        print(f"✓ {json_file} - Complete JSON results")

        # 2. HTML Report (visual inspection)
        html_file = "phase1_report.html"
        self._generate_html_report(html_file)
        print(f"✓ {html_file} - Open in browser for detailed review")

        # 3. Text Summary
        txt_file = "phase1_summary.txt"
        self._generate_text_summary(txt_file)
        print(f"✓ {txt_file} - Summary statistics")

        # 4. Console Summary
        self._print_console_summary()

        return self.results

    def _generate_html_report(self, filename: str):
        """Generate HTML report for visual inspection"""

        html = """
<!DOCTYPE html>
<html>
<head>
    <title>Phase 1: ATS Validation Results</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .header { background: #333; color: white; padding: 20px; border-radius: 5px; }
        .company-section { background: white; margin: 20px 0; padding: 20px; border-radius: 5px; border-left: 5px solid #007bff; }
        .success { border-left-color: #28a745; }
        .failed { border-left-color: #dc3545; }
        .check { padding: 10px; margin: 5px 0; background: #f9f9f9; border-left: 3px solid #ddd; }
        .check.pass { border-left-color: #28a745; color: #28a745; font-weight: bold; }
        .check.fail { border-left-color: #dc3545; color: #dc3545; font-weight: bold; }
        .job-preview { background: #f0f0f0; padding: 10px; margin: 10px 0; border-radius: 3px; font-size: 12px; }
        .metric { display: inline-block; margin: 10px 20px 10px 0; }
        .metric-label { font-weight: bold; }
        table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f0f0f0; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Phase 1: ATS Validation - Sample 6 Companies</h1>
        <p>Timestamp: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
    </div>
"""

        for company, data in self.results.items():
            status_class = "success" if data["status"] == "SUCCESS" else "failed"
            html += f"""
    <div class="company-section {status_class}">
        <h2>{company.upper()}</h2>
        <div class="metric">
            <span class="metric-label">Status:</span> {data['status']}
        </div>
        <div class="metric">
            <span class="metric-label">Jobs Found:</span> {data['jobs_found']}
        </div>
        <div class="metric">
            <span class="metric-label">Quality Score:</span> {data['validation'].get('quality_score', 'N/A')}/100
        </div>

        <h3>Validation Checks</h3>
"""

            for check_name, check_result in data["validation"].items():
                if isinstance(check_result, dict) and "passed" in check_result:
                    status_class = "pass" if check_result.get("passed") else "fail"
                    status_text = "✓ PASS" if check_result.get("passed") else "✗ FAIL"
                    message = check_result.get("message", "")
                    html += f'<div class="check {status_class}">{status_text} - {check_name}: {message}</div>\n'

            # Job previews
            if data['jobs_summary']:
                html += "<h3>Job Samples (First 5)</h3>\n<table>\n"
                html += "<tr><th>Title</th><th>Location</th><th>Desc Length</th><th>Content Sections</th><th>Issues</th></tr>\n"

                for job in data['jobs_summary']:
                    issues = []
                    if job['null_description']:
                        issues.append("NO DESC")
                    if job['description_length'] < 1000:
                        issues.append("SHORT DESC")

                    sections = sum(job['has_content_sections'].values()) if job['has_content_sections'] else 0
                    issues_text = ", ".join(issues) if issues else "✓"

                    html += f"""
                    <tr>
                        <td>{job['title']}</td>
                        <td>{job['location']}</td>
                        <td>{job['description_length']:,}</td>
                        <td>{sections}/4 sections</td>
                        <td>{issues_text}</td>
                    </tr>
"""

                html += "</table>\n"

                # Full job preview for first job
                if data['jobs_summary']:
                    first_job = data['jobs_summary'][0]
                    html += f"""
        <h3>First Job Detail: {first_job['title']}</h3>
        <div class="job-preview">
            <strong>Location:</strong> {first_job['location']}<br>
            <strong>Description Length:</strong> {first_job['description_length']:,} chars<br>
            <strong>URL:</strong> <a href="{first_job['url']}" target="_blank">{first_job['url']}</a><br>
            <strong>Content Sections Found:</strong> {sum(first_job['has_content_sections'].values()) if first_job['has_content_sections'] else 0}/4
        </div>
"""

            html += "    </div>\n"

        html += """
</body>
</html>
"""

        with open(filename, 'w') as f:
            f.write(html)

    def _generate_text_summary(self, filename: str):
        """Generate text summary for easy review"""

        with open(filename, 'w') as f:
            f.write("="*80 + "\n")
            f.write("PHASE 1: ATS VALIDATION - Summary Report\n")
            f.write("="*80 + "\n\n")

            # Overall summary
            successful = sum(1 for r in self.results.values() if r["status"] == "SUCCESS" and r["jobs_found"] > 0)
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Companies Tested: {len(self.results)}\n")
            f.write(f"Companies Successful: {successful}/{len(self.results)}\n\n")

            # Per-company summary
            for company, data in self.results.items():
                f.write(f"\n{company.upper()}\n")
                f.write("-" * 40 + "\n")
                f.write(f"  Status: {data['status']}\n")
                f.write(f"  Jobs Found: {data['jobs_found']}\n")

                if data['validation']:
                    quality = data['validation'].get('quality_score', 'N/A')
                    result = data['validation'].get('result', 'N/A')
                    f.write(f"  Quality Score: {quality}/100\n")
                    f.write(f"  Overall: {result}\n")

                    # Validation details
                    if data['jobs_found'] > 0:
                        f.write(f"\n  Validation Checks:\n")
                        for check_name, check_result in data['validation'].items():
                            if isinstance(check_result, dict) and "passed" in check_result:
                                status = "✓" if check_result.get("passed") else "✗"
                                message = check_result.get("message", "")
                                f.write(f"    {status} {check_name}: {message}\n")

    def _print_console_summary(self):
        """Print summary to console"""

        print("\n" + "="*80)
        print("PHASE 1 RESULTS SUMMARY")
        print("="*80 + "\n")

        successful = 0
        for company, data in self.results.items():
            if data["status"] == "SUCCESS" and data["jobs_found"] > 0:
                quality = data['validation'].get('quality_score', 0)
                result = "✓ PASS" if quality >= 70 else "! WARNING" if quality >= 50 else "✗ FAIL"
                print(f"{company.upper():12} | {data['jobs_found']:3} jobs | Quality: {quality:5.1f}/100 | {result}")
                successful += 1
            else:
                print(f"{company.upper():12} | FAILED - No jobs found or error")

        print("\n" + "="*80)
        print(f"Summary: {successful}/{len(self.results)} companies use Greenhouse")
        print("="*80 + "\n")

        # Recommendations
        if successful == len(self.results):
            print("✓ RECOMMENDATION: All companies use Greenhouse. Proceed to Phase 2.")
        elif successful >= 4:
            print("~ RECOMMENDATION: Most companies use Greenhouse. Proceed to Phase 2, investigate failures.")
        else:
            print("✗ RECOMMENDATION: Many companies have migrated. Reassess strategy before Phase 2.")

        print("\nNext Steps:")
        print("1. Review phase1_report.html in browser for visual inspection")
        print("2. Check phase1_summary.txt for detailed metrics")
        print("3. If successful: Run validation on all 91 companies")
        print("4. If issues: Debug failed companies\n")


async def main():
    """Run Phase 1 validation"""

    validator = Phase1Validator()
    results = await validator.run_validation()

    return 0 if sum(1 for r in results.values() if r.get("jobs_found", 0) > 0) >= 4 else 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
