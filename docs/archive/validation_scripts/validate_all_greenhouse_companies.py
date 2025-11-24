"""
Comprehensive Greenhouse Company Validation Script

Validates all 91 companies in the Greenhouse mapping to confirm:
1. Company is still using Greenhouse
2. URLs are correct
3. Job listings are accessible
4. Full descriptions can be extracted

Updates company_ats_mapping.json with status column: verified, unverified, failed
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass

try:
    from scrapers.greenhouse.greenhouse_scraper import GreenhouseScraper
except ImportError:
    from greenhouse_scraper import GreenhouseScraper

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validating a single company"""
    company_name: str
    company_slug: str
    status: str  # "verified", "unverified", "failed"
    job_count: int = 0
    avg_description_length: int = 0
    error_message: str = None
    validation_time: str = None


class GreenhouseValidator:
    """Validates all Greenhouse companies and updates mapping"""

    def __init__(self, headless: bool = True, timeout_per_company: int = 30):
        self.headless = headless
        self.timeout_per_company = timeout_per_company
        self.results: Dict[str, ValidationResult] = {}
        self.mapping_file = Path("config/company_ats_mapping.json")

    async def validate_all_companies(self) -> Dict[str, ValidationResult]:
        """
        Validate all 91 Greenhouse companies

        Returns:
            Dictionary of company slug -> ValidationResult
        """
        # Load mapping
        with open(self.mapping_file, 'r') as f:
            mapping = json.load(f)

        companies = mapping.get('greenhouse', {})
        total = len(companies)

        logger.info("=" * 80)
        logger.info(f"GREENHOUSE COMPANY VALIDATION")
        logger.info("=" * 80)
        logger.info(f"Total companies to validate: {total}")
        logger.info("=" * 80 + "\n")

        # Initialize scraper
        scraper = GreenhouseScraper(headless=self.headless, max_concurrent_pages=2)
        await scraper.init()

        try:
            # Test each company
            for idx, (company_name, company_slug) in enumerate(companies.items(), 1):
                logger.info(f"[{idx}/{total}] Testing {company_name} ({company_slug})...")

                result = await self._test_company(scraper, company_name, company_slug)
                self.results[company_slug] = result

                # Print result
                status_symbol = "✓" if result.status == "verified" else ("?" if result.status == "unverified" else "✗")
                logger.info(
                    f"  {status_symbol} {result.status.upper()} - "
                    f"{result.job_count} jobs, "
                    f"avg {result.avg_description_length} chars"
                )
                if result.error_message:
                    logger.info(f"     Error: {result.error_message}")
                logger.info("")

        finally:
            await scraper.close()

        return self.results

    async def _test_company(self, scraper: GreenhouseScraper, company_name: str, company_slug: str) -> ValidationResult:
        """Test a single company"""
        start_time = datetime.now()

        try:
            # Try to scrape company
            jobs = await scraper.scrape_company(company_slug, max_retries=1)

            validation_time = (datetime.now() - start_time).total_seconds()

            if not jobs:
                # No jobs found - either company doesn't use Greenhouse or has no openings
                return ValidationResult(
                    company_name=company_name,
                    company_slug=company_slug,
                    status="unverified",
                    job_count=0,
                    error_message="No jobs found",
                    validation_time=f"{validation_time:.1f}s"
                )

            # Calculate statistics
            job_count = len(jobs)
            total_chars = sum(len(job.description or "") for job in jobs)
            avg_description_length = total_chars // job_count if job_count > 0 else 0

            # Verify we got descriptions
            if avg_description_length < 100:
                status = "unverified"
                error_msg = f"Descriptions too short (avg {avg_description_length} chars)"
            else:
                status = "verified"
                error_msg = None

            return ValidationResult(
                company_name=company_name,
                company_slug=company_slug,
                status=status,
                job_count=job_count,
                avg_description_length=avg_description_length,
                error_message=error_msg,
                validation_time=f"{validation_time:.1f}s"
            )

        except asyncio.TimeoutError:
            validation_time = (datetime.now() - start_time).total_seconds()
            return ValidationResult(
                company_name=company_name,
                company_slug=company_slug,
                status="failed",
                error_message="Timeout",
                validation_time=f"{validation_time:.1f}s"
            )

        except Exception as e:
            validation_time = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)[:100]  # Truncate long error messages
            return ValidationResult(
                company_name=company_name,
                company_slug=company_slug,
                status="failed",
                error_message=error_msg,
                validation_time=f"{validation_time:.1f}s"
            )

    def update_mapping_with_status(self) -> None:
        """Update company_ats_mapping.json with validation status"""
        # Load current mapping
        with open(self.mapping_file, 'r') as f:
            mapping = json.load(f)

        # Create new mapping with status
        updated_mapping = {}

        for ats_type, companies in mapping.items():
            updated_mapping[ats_type] = {}

            if ats_type == "greenhouse":
                # Add status for Greenhouse companies
                for company_name, company_slug in companies.items():
                    result = self.results.get(company_slug)
                    if result:
                        updated_mapping[ats_type][company_name] = {
                            "slug": company_slug,
                            "status": result.status,
                            "job_count": result.job_count,
                            "avg_description_length": result.avg_description_length,
                            "error": result.error_message
                        }
                    else:
                        updated_mapping[ats_type][company_name] = {
                            "slug": company_slug,
                            "status": "untested",
                            "error": "Not tested"
                        }
            else:
                # Keep other ATS types as-is
                updated_mapping[ats_type] = companies

        # Write updated mapping
        with open(self.mapping_file, 'w') as f:
            json.dump(updated_mapping, f, indent=2)

        logger.info(f"\nUpdated {self.mapping_file} with validation status")

    def print_summary(self) -> None:
        """Print validation summary"""
        if not self.results:
            logger.info("No results to summarize")
            return

        verified = sum(1 for r in self.results.values() if r.status == "verified")
        unverified = sum(1 for r in self.results.values() if r.status == "unverified")
        failed = sum(1 for r in self.results.values() if r.status == "failed")
        total = len(self.results)

        total_jobs = sum(r.job_count for r in self.results.values())
        avg_desc_length = int(sum(r.avg_description_length for r in self.results.values()) / len(self.results)) if self.results else 0

        logger.info("\n" + "=" * 80)
        logger.info("VALIDATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total companies tested: {total}")
        logger.info(f"  ✓ Verified (Greenhouse):     {verified} ({100*verified//total}%)")
        logger.info(f"  ? Unverified (No jobs):      {unverified} ({100*unverified//total}%)")
        logger.info(f"  ✗ Failed (Migrated/Error):   {failed} ({100*failed//total}%)")
        logger.info("")
        logger.info(f"Total jobs found: {total_jobs:,}")
        logger.info(f"Average description length: {avg_desc_length:,} chars")
        logger.info("=" * 80)

        # List failed companies
        if failed > 0:
            logger.info("\nFAILED COMPANIES (Likely migrated or unreachable):")
            for slug, result in sorted(self.results.items()):
                if result.status == "failed":
                    logger.info(f"  ✗ {result.company_name:30s} - {result.error_message}")

        # List unverified companies
        if unverified > 0:
            logger.info("\nUNVERIFIED COMPANIES (No job listings):")
            for slug, result in sorted(self.results.items()):
                if result.status == "unverified":
                    logger.info(f"  ? {result.company_name:30s} - {result.error_message}")

        logger.info("=" * 80)

    def export_results_to_csv(self, filepath: str = "greenhouse_validation_results.csv") -> None:
        """Export validation results to CSV"""
        import csv

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Company Name',
                'Company Slug',
                'Status',
                'Job Count',
                'Avg Description Length',
                'Error Message',
                'Validation Time (sec)'
            ])

            for slug, result in sorted(self.results.items(), key=lambda x: x[1].company_name):
                writer.writerow([
                    result.company_name,
                    result.company_slug,
                    result.status,
                    result.job_count,
                    result.avg_description_length,
                    result.error_message or "",
                    result.validation_time or ""
                ])

        logger.info(f"\nExported results to {filepath}")


async def main():
    """Main validation workflow"""
    validator = GreenhouseValidator(headless=True)

    # Run validation
    results = await validator.validate_all_companies()

    # Print summary
    validator.print_summary()

    # Update mapping file
    validator.update_mapping_with_status()

    # Export to CSV for easy reference
    validator.export_results_to_csv()

    logger.info("\nValidation complete!")
    logger.info("Files updated:")
    logger.info("  - config/company_ats_mapping.json (with status)")
    logger.info("  - greenhouse_validation_results.csv (detailed results)")


if __name__ == "__main__":
    asyncio.run(main())
