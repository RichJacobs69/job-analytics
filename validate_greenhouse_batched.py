"""
Batched Greenhouse Company Validation Script

Validates all 91 companies in batches to prevent token limits and allow recovery.
Saves progress after each batch so you can resume if interrupted.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict

try:
    from scrapers.greenhouse.greenhouse_scraper import GreenhouseScraper
except ImportError:
    from greenhouse_scraper import GreenhouseScraper

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
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

    def to_dict(self):
        return asdict(self)


class BatchedGreenhouseValidator:
    """Validates Greenhouse companies in batches"""

    def __init__(self, batch_size: int = 20, headless: bool = True):
        self.batch_size = batch_size
        self.headless = headless
        self.mapping_file = Path("config/company_ats_mapping.json")
        self.results_file = Path("greenhouse_validation_results.json")
        self.results: Dict[str, ValidationResult] = {}

        # Load any existing results
        self._load_existing_results()

    def _load_existing_results(self):
        """Load previously saved results if they exist"""
        if self.results_file.exists():
            with open(self.results_file, 'r') as f:
                data = json.load(f)
                for slug, result_dict in data.items():
                    self.results[slug] = ValidationResult(**result_dict)
            logger.info(f"Loaded {len(self.results)} existing results from {self.results_file}")

    def _save_results(self):
        """Save results to file"""
        data = {slug: result.to_dict() for slug, result in self.results.items()}
        with open(self.results_file, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved {len(self.results)} results to {self.results_file}")

    async def validate_batch(self, companies: Dict[str, str], batch_num: int, total_batches: int) -> Dict[str, ValidationResult]:
        """
        Validate a single batch of companies

        Args:
            companies: Dict of company_name -> company_slug
            batch_num: Current batch number (1-indexed)
            total_batches: Total number of batches

        Returns:
            Dictionary of slug -> ValidationResult for this batch
        """
        batch_results = {}
        scraper = GreenhouseScraper(headless=self.headless, max_concurrent_pages=2)
        await scraper.init()

        try:
            company_list = list(companies.items())
            logger.info(f"\n{'='*80}")
            logger.info(f"BATCH {batch_num}/{total_batches} - Testing {len(company_list)} companies")
            logger.info(f"{'='*80}\n")

            for idx, (company_name, company_slug) in enumerate(company_list, 1):
                global_idx = (batch_num - 1) * self.batch_size + idx

                # Check if already validated
                if company_slug in self.results:
                    result = self.results[company_slug]
                    logger.info(f"[{global_idx}/91] {company_name:30s} ✓ CACHED - {result.status.upper()}")
                    batch_results[company_slug] = result
                    continue

                # Validate company
                logger.info(f"[{global_idx}/91] {company_name:30s} Testing...")
                result = await self._test_company(scraper, company_name, company_slug)
                self.results[company_slug] = result
                batch_results[company_slug] = result

                # Log result
                status_symbol = "✓" if result.status == "verified" else ("?" if result.status == "unverified" else "✗")
                logger.info(f"       {status_symbol} {result.status.upper()} - {result.job_count} jobs, {result.avg_description_length} chars avg")

                if result.error_message:
                    logger.info(f"       Error: {result.error_message}")

        finally:
            await scraper.close()

        return batch_results

    async def _test_company(self, scraper: GreenhouseScraper, company_name: str, company_slug: str) -> ValidationResult:
        """Test a single company by checking if at least 1 job with substantial description exists"""
        start_time = datetime.now()

        try:
            # Try to scrape company with single retry, limit to first 5 jobs for speed
            jobs = await scraper.scrape_company(company_slug, max_retries=1)
            validation_time = (datetime.now() - start_time).total_seconds()

            if not jobs:
                return ValidationResult(
                    company_name=company_name,
                    company_slug=company_slug,
                    status="unverified",
                    job_count=0,
                    error_message="No jobs found",
                    validation_time=f"{validation_time:.1f}s"
                )

            # Check only first job to verify Greenhouse is active and has descriptions
            # If first job has good description, we can assume others do too
            first_job = jobs[0]
            desc_length = len(first_job.description or "")

            # Determine status based on first job description quality
            if desc_length >= 100:
                status = "verified"
                error_msg = None
                # Report actual job count and average from what we scraped
                job_count = len(jobs)
                total_chars = sum(len(job.description or "") for job in jobs)
                avg_description_length = total_chars // job_count if job_count > 0 else 0
            else:
                status = "unverified"
                error_msg = f"Description too short ({desc_length} chars)"
                job_count = len(jobs)
                avg_description_length = desc_length

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
                error_message="Timeout (likely migrated)",
                validation_time=f"{validation_time:.1f}s"
            )

        except Exception as e:
            validation_time = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)[:80]
            return ValidationResult(
                company_name=company_name,
                company_slug=company_slug,
                status="failed",
                error_message=error_msg,
                validation_time=f"{validation_time:.1f}s"
            )

    async def validate_all_companies(self) -> Dict[str, ValidationResult]:
        """
        Validate all 91 companies in batches

        Returns:
            Dictionary of all results
        """
        # Load mapping
        with open(self.mapping_file, 'r') as f:
            mapping = json.load(f)

        companies = mapping.get('greenhouse', {})
        total = len(companies)

        # Split into batches
        company_items = list(companies.items())
        batches = [
            dict(company_items[i:i + self.batch_size])
            for i in range(0, len(company_items), self.batch_size)
        ]

        total_batches = len(batches)

        logger.info(f"Total companies: {total}")
        logger.info(f"Batch size: {self.batch_size}")
        logger.info(f"Total batches: {total_batches}")

        # Process each batch
        for batch_num, batch_companies in enumerate(batches, 1):
            await self.validate_batch(batch_companies, batch_num, total_batches)

            # Save after each batch
            self._save_results()

            if batch_num < total_batches:
                logger.info(f"\nBatch {batch_num} complete. Saving progress...")
                logger.info(f"Progress: {len([r for r in self.results.values() if r.status == 'verified'])}/{total} verified")
                logger.info(f"Waiting 10 seconds before next batch...\n")
                await asyncio.sleep(10)

        return self.results

    def update_mapping_with_status(self):
        """Update company_ats_mapping.json with validation status"""
        with open(self.mapping_file, 'r') as f:
            mapping = json.load(f)

        # Create new mapping with status
        updated_mapping = {}

        for ats_type, companies in mapping.items():
            if ats_type == "greenhouse":
                updated_mapping[ats_type] = {}
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
                # Keep other ATS types unchanged
                updated_mapping[ats_type] = companies

        # Write updated mapping
        with open(self.mapping_file, 'w') as f:
            json.dump(updated_mapping, f, indent=2)

        logger.info(f"\nUpdated {self.mapping_file} with validation status")

    def print_summary(self):
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
        logger.info("FINAL VALIDATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total companies tested: {total}")
        logger.info(f"  ✓ Verified (Greenhouse):     {verified:3d} ({100*verified//total:3d}%)")
        logger.info(f"  ? Unverified (No jobs):      {unverified:3d} ({100*unverified//total:3d}%)")
        logger.info(f"  ✗ Failed (Migrated/Error):   {failed:3d} ({100*failed//total:3d}%)")
        logger.info("")
        logger.info(f"Total jobs found: {total_jobs:,}")
        logger.info(f"Average description length: {avg_desc_length:,} chars")
        logger.info("=" * 80)

        # List failed companies
        if failed > 0:
            logger.info("\nFAILED COMPANIES (likely migrated):")
            failed_companies = [(r.company_name, r.error_message) for r in self.results.values() if r.status == "failed"]
            for name, error in sorted(failed_companies):
                logger.info(f"  ✗ {name:30s} - {error}")

        # List unverified companies
        if unverified > 0:
            logger.info("\nUNVERIFIED COMPANIES (no open jobs):")
            unverified_companies = [r.company_name for r in self.results.values() if r.status == "unverified"]
            for name in sorted(unverified_companies):
                logger.info(f"  ? {name}")

        logger.info("=" * 80)

    def export_to_csv(self, filepath: str = "greenhouse_validation_results.csv"):
        """Export results to CSV"""
        import csv

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Company Name',
                'Status',
                'Job Count',
                'Avg Description Length',
                'Error Message'
            ])

            for result in sorted(self.results.values(), key=lambda r: r.company_name):
                writer.writerow([
                    result.company_name,
                    result.status,
                    result.job_count,
                    result.avg_description_length,
                    result.error_message or ""
                ])

        logger.info(f"Exported results to {filepath}")


async def main():
    """Main validation workflow"""
    logger.info("Starting batched Greenhouse company validation...\n")

    validator = BatchedGreenhouseValidator(batch_size=20, headless=True)

    # Run validation (will resume from previous results if interrupted)
    results = await validator.validate_all_companies()

    # Print summary
    validator.print_summary()

    # Update mapping file
    validator.update_mapping_with_status()

    # Export to CSV
    validator.export_to_csv()

    logger.info("\nValidation complete!")
    logger.info("Files created/updated:")
    logger.info("  - greenhouse_validation_results.json (all results, resumable)")
    logger.info("  - config/company_ats_mapping.json (with status)")
    logger.info("  - greenhouse_validation_results.csv (for easy review)")


if __name__ == "__main__":
    asyncio.run(main())
