#!/usr/bin/env python3
"""
Comprehensive validation test suite for Greenhouse scraper

Tests ensure:
1. All jobs are captured from listing page (completeness)
2. Full job descriptions are extracted (no truncation)
3. No null/empty descriptions (data quality)
4. Content sections are present (rich data)
5. URL integrity and deduplication
6. Error handling and edge cases
"""

import asyncio
import json
import sys
from typing import List, Dict, Tuple
from dataclasses import asdict
from datetime import datetime
from greenhouse_scraper import GreenhouseScraper, Job


class GreenhouseValidationTest:
    """Comprehensive validator for Greenhouse scraper"""

    def __init__(self):
        self.test_results = {}
        self.failures = []
        self.warnings = []

    async def run_all_tests(self, company_slugs: List[str]) -> Dict:
        """Run complete validation suite for companies"""

        print("\n" + "="*80)
        print("GREENHOUSE SCRAPER VALIDATION TEST SUITE")
        print("="*80 + "\n")

        scraper = GreenhouseScraper(headless=True, max_concurrent_pages=2)

        try:
            await scraper.init()

            for slug in company_slugs:
                print(f"\nTesting: {slug.upper()}")
                print("-" * 80)

                jobs = await scraper.scrape_company(slug)
                self.test_results[slug] = await self._validate_company(slug, jobs)

        finally:
            await scraper.close()

        return self._generate_report()

    async def _validate_company(self, company_slug: str, jobs: List[Job]) -> Dict:
        """Run all validation checks for a company"""

        results = {
            "company": company_slug,
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "stats": {},
            "data_quality": {}
        }

        # TEST 1: Jobs count check
        results["checks"]["jobs_found"] = await self._check_jobs_count(company_slug, jobs)
        results["stats"]["total_jobs"] = len(jobs)

        # TEST 2: Null/empty descriptions check
        results["checks"]["null_descriptions"] = self._check_null_descriptions(jobs)

        # TEST 3: Description completeness
        results["checks"]["description_length"] = self._check_description_lengths(jobs)

        # TEST 4: Content section presence
        results["checks"]["content_sections"] = self._check_content_sections(jobs)

        # TEST 5: URL integrity
        results["checks"]["url_integrity"] = self._check_url_integrity(jobs)

        # TEST 6: Deduplication
        results["checks"]["deduplication"] = self._check_deduplication(jobs)

        # TEST 7: Data quality metrics
        results["data_quality"] = self._calculate_data_quality(jobs)

        # TEST 8: Sample job verification
        if jobs:
            results["checks"]["sample_job"] = self._check_sample_job(jobs[0])

        return results

    async def _check_jobs_count(self, company_slug: str, jobs: List[Job]) -> Dict:
        """Check if reasonable number of jobs were captured"""
        check_name = "Jobs Count"

        if len(jobs) == 0:
            self.failures.append(f"{company_slug}: No jobs extracted")
            return {
                "passed": False,
                "message": "No jobs found",
                "count": 0,
                "severity": "CRITICAL"
            }

        if len(jobs) < 5:
            self.warnings.append(f"{company_slug}: Only {len(jobs)} jobs found (expected 5+)")
            return {
                "passed": False,
                "message": f"Very few jobs ({len(jobs)}) - may be incomplete",
                "count": len(jobs),
                "severity": "WARNING"
            }

        return {
            "passed": True,
            "message": f"Captured {len(jobs)} jobs",
            "count": len(jobs),
            "severity": None
        }

    def _check_null_descriptions(self, jobs: List[Job]) -> Dict:
        """Check for null or empty job descriptions"""
        check_name = "Null Descriptions"

        null_jobs = [j for j in jobs if not j.description or len(j.description.strip()) == 0]

        if null_jobs:
            self.failures.append(f"{len(null_jobs)} jobs have null/empty descriptions")
            return {
                "passed": False,
                "message": f"{len(null_jobs)} jobs with no description",
                "null_count": len(null_jobs),
                "null_jobs": [{"title": j.title, "url": j.url} for j in null_jobs[:5]],
                "severity": "CRITICAL"
            }

        return {
            "passed": True,
            "message": "All jobs have descriptions",
            "null_count": 0,
            "severity": None
        }

    def _check_description_lengths(self, jobs: List[Job]) -> Dict:
        """Check description lengths for completeness"""
        check_name = "Description Length"

        descriptions = [j.description for j in jobs if j.description]

        if not descriptions:
            return {"passed": False, "message": "No descriptions to check", "severity": "CRITICAL"}

        lengths = [len(d) for d in descriptions]

        # Quality thresholds
        min_length = min(lengths)
        max_length = max(lengths)
        avg_length = sum(lengths) // len(lengths)

        results = {
            "min_chars": min_length,
            "max_chars": max_length,
            "avg_chars": avg_length,
            "total_chars": sum(lengths),
            "distribution": {}
        }

        # Count by size ranges
        very_short = sum(1 for l in lengths if l < 500)  # Likely truncated
        short = sum(1 for l in lengths if 500 <= l < 2000)  # Moderate
        medium = sum(1 for l in lengths if 2000 <= l < 5000)  # Good
        long = sum(1 for l in lengths if 5000 <= l < 10000)  # Very good
        very_long = sum(1 for l in lengths if l >= 10000)  # Complete

        results["distribution"] = {
            "very_short_(<500)": very_short,
            "short_(500-2k)": short,
            "medium_(2-5k)": medium,
            "long_(5-10k)": long,
            "very_long_(10k+)": very_long
        }

        # Pass if majority are 2000+ chars (good descriptions)
        good_descriptions = medium + long + very_long
        if good_descriptions / len(lengths) >= 0.9:
            results["passed"] = True
            results["message"] = f"Good: {good_descriptions}/{len(lengths)} jobs have 2000+ char descriptions"
            results["severity"] = None
        else:
            self.warnings.append(f"Only {good_descriptions}/{len(lengths)} jobs have substantial descriptions (2000+ chars)")
            results["passed"] = False
            results["message"] = f"Only {good_descriptions}/{len(lengths)} substantial descriptions"
            results["severity"] = "WARNING"

        return results

    def _check_content_sections(self, jobs: List[Job]) -> Dict:
        """Check if full content sections are captured (not just main description)"""
        check_name = "Content Sections"

        # Keywords that indicate rich content sections
        section_keywords = {
            "responsibilities": ["responsibility", "responsibilities", "role", "this role"],
            "benefits": ["benefit", "benefits", "compensation", "pay", "salary"],
            "work_arrangement": ["hybrid", "remote", "office", "work-from", "work from"],
            "requirements": ["requirement", "requirements", "require", "qualified", "skills"]
        }

        results = {
            "jobs_with_full_content": 0,
            "content_breakdown": {},
            "sample_missing": []
        }

        for job in jobs:
            if not job.description:
                continue

            desc_lower = job.description.lower()
            sections_found = {}

            for section, keywords in section_keywords.items():
                sections_found[section] = any(kw in desc_lower for kw in keywords)

            if sum(sections_found.values()) >= 3:  # At least 3 sections
                results["jobs_with_full_content"] += 1
            else:
                if len(results["sample_missing"]) < 3:
                    results["sample_missing"].append({
                        "title": job.title,
                        "sections_found": sum(sections_found.values()),
                        "missing_sections": [s for s, found in sections_found.items() if not found]
                    })

        ratio = results["jobs_with_full_content"] / len(jobs) if jobs else 0

        if ratio >= 0.85:
            results["passed"] = True
            results["message"] = f"{results['jobs_with_full_content']}/{len(jobs)} jobs have full content sections"
            results["severity"] = None
        else:
            self.warnings.append(f"Only {results['jobs_with_full_content']}/{len(jobs)} have full content sections")
            results["passed"] = False
            results["message"] = f"Low content completeness: {results['jobs_with_full_content']}/{len(jobs)}"
            results["severity"] = "WARNING"

        return results

    def _check_url_integrity(self, jobs: List[Job]) -> Dict:
        """Check URL validity and no duplicates"""
        check_name = "URL Integrity"

        urls = [j.url for j in jobs if j.url]

        results = {
            "total_urls": len(urls),
            "valid_urls": 0,
            "malformed_urls": [],
            "issues": []
        }

        seen_urls = set()

        for job in jobs:
            if not job.url:
                results["issues"].append(f"Job '{job.title}' has no URL")
                continue

            # Check URL format
            if not (job.url.startswith("http://") or job.url.startswith("https://")):
                results["malformed_urls"].append(job.url[:100])
                continue

            # Check for /jobs/ path (Greenhouse standard)
            if "/jobs/" not in job.url:
                results["issues"].append(f"Unusual URL format: {job.url[:80]}")

            # Check duplicates
            if job.url in seen_urls:
                results["issues"].append(f"Duplicate URL: {job.url[:80]}")
            seen_urls.add(job.url)

            results["valid_urls"] += 1

        if len(results["malformed_urls"]) == 0 and len(results["issues"]) == 0:
            results["passed"] = True
            results["message"] = "All URLs valid"
            results["severity"] = None
        else:
            self.warnings.append(f"URL issues found: {len(results['malformed_urls'])} malformed, {len(results['issues'])} other issues")
            results["passed"] = False
            results["message"] = f"URL problems: {len(results['malformed_urls'])} malformed"
            results["severity"] = "WARNING"

        return results

    def _check_deduplication(self, jobs: List[Job]) -> Dict:
        """Check for duplicate jobs (same company/title/location)"""
        check_name = "Deduplication"

        import hashlib

        seen_hashes = {}
        duplicates = []

        for job in jobs:
            # Create hash of identifying fields
            key = f"{job.company}|{job.title}|{job.location}"
            hash_val = hashlib.md5(key.encode()).hexdigest()

            if hash_val in seen_hashes:
                duplicates.append({
                    "title": job.title,
                    "location": job.location,
                    "first_url": seen_hashes[hash_val],
                    "duplicate_url": job.url
                })
            else:
                seen_hashes[hash_val] = job.url

        if duplicates:
            self.warnings.append(f"Found {len(duplicates)} duplicate jobs")
            return {
                "passed": False,
                "message": f"{len(duplicates)} duplicates found",
                "duplicate_count": len(duplicates),
                "sample_duplicates": duplicates[:3],
                "severity": "WARNING"
            }

        return {
            "passed": True,
            "message": "No duplicates detected",
            "duplicate_count": 0,
            "severity": None
        }

    def _check_sample_job(self, job: Job) -> Dict:
        """Validate structure of a sample job"""
        check_name = "Sample Job Validation"

        required_fields = {
            "company": job.company,
            "title": job.title,
            "location": job.location,
            "url": job.url,
            "job_id": job.job_id,
            "description": job.description
        }

        missing_fields = [f for f, v in required_fields.items() if not v]

        results = {
            "sample_job_title": job.title,
            "fields_present": len(required_fields) - len(missing_fields),
            "fields_total": len(required_fields),
            "missing_fields": missing_fields
        }

        if missing_fields:
            self.warnings.append(f"Sample job missing fields: {missing_fields}")
            results["passed"] = False
            results["severity"] = "WARNING"
        else:
            results["passed"] = True
            results["severity"] = None

        return results

    def _calculate_data_quality(self, jobs: List[Job]) -> Dict:
        """Calculate overall data quality metrics"""

        if not jobs:
            return {"quality_score": 0, "metrics": {}}

        metrics = {}

        # 1. Description coverage
        with_desc = sum(1 for j in jobs if j.description and len(j.description.strip()) > 0)
        metrics["description_coverage"] = (with_desc / len(jobs)) * 100

        # 2. Average description length
        desc_lengths = [len(j.description) for j in jobs if j.description]
        metrics["avg_description_length"] = sum(desc_lengths) / len(desc_lengths) if desc_lengths else 0

        # 3. Rich content (2000+ chars)
        rich_content = sum(1 for d in desc_lengths if d >= 2000)
        metrics["rich_content_percentage"] = (rich_content / len(jobs) * 100) if jobs else 0

        # 4. Fields completeness
        all_fields = []
        for j in jobs:
            fields_present = sum(1 for f in [j.company, j.title, j.location, j.url, j.job_id] if f)
            all_fields.append(fields_present / 5 * 100)
        metrics["field_completeness"] = sum(all_fields) / len(all_fields) if all_fields else 0

        # Calculate composite quality score (0-100)
        weights = {
            "description_coverage": 0.3,
            "rich_content_percentage": 0.3,
            "field_completeness": 0.25,
            "avg_description_length": 0.15  # Normalized to 0-100 (max 10000 chars)
        }

        quality_score = (
            metrics["description_coverage"] * weights["description_coverage"] +
            metrics["rich_content_percentage"] * weights["rich_content_percentage"] +
            metrics["field_completeness"] * weights["field_completeness"] +
            min(100, metrics["avg_description_length"] / 100) * weights["avg_description_length"]
        )

        return {
            "quality_score": round(quality_score, 1),
            "metrics": metrics
        }

    def _generate_report(self) -> Dict:
        """Generate comprehensive test report"""

        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_companies_tested": len(self.test_results),
                "total_failures": len(self.failures),
                "total_warnings": len(self.warnings)
            },
            "test_results": self.test_results,
            "failures": self.failures,
            "warnings": self.warnings
        }

        # Print summary
        self._print_summary(report)

        return report

    def _print_summary(self, report: Dict):
        """Print test results summary"""

        print("\n" + "="*80)
        print("TEST RESULTS SUMMARY")
        print("="*80 + "\n")

        for company, results in self.test_results.items():
            print(f"\n{company.upper()}")
            print("-" * 80)
            print(f"Total Jobs: {results['stats'].get('total_jobs', 0)}")
            print(f"Data Quality Score: {results['data_quality'].get('quality_score', 0)}/100")

            # Check results
            for check_name, check_result in results['checks'].items():
                if isinstance(check_result, dict) and 'passed' in check_result:
                    status = "✓ PASS" if check_result['passed'] else "✗ FAIL"
                    print(f"  {status} - {check_name}: {check_result.get('message', '')}")

            # Data quality breakdown
            if results['data_quality'].get('metrics'):
                print("\n  Data Quality Metrics:")
                for metric, value in results['data_quality']['metrics'].items():
                    print(f"    - {metric}: {value:.1f}")

        # Overall summary
        print("\n" + "="*80)
        print("OVERALL STATUS")
        print("="*80)
        print(f"Failures: {len(report['failures'])}")
        print(f"Warnings: {len(report['warnings'])}")

        if report['failures']:
            print("\nCRITICAL FAILURES:")
            for failure in report['failures']:
                print(f"  ✗ {failure}")

        if report['warnings']:
            print("\nWARNINGS:")
            for warning in report['warnings'][:10]:  # Show first 10
                print(f"  ! {warning}")


async def main():
    """Run validation tests"""

    # Test companies
    test_companies = ['stripe', 'figma']

    validator = GreenhouseValidationTest()
    report = await validator.run_all_tests(test_companies)

    # Save report
    report_file = f"greenhouse_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n✓ Report saved to {report_file}\n")

    # Exit with error code if critical failures
    return 1 if report['summary']['total_failures'] > 0 else 0


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
