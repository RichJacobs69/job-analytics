"""
Unified Job Ingester: Merge Adzuna + Greenhouse with Deduplication

Purpose:
--------
Combines job results from multiple sources (Adzuna API + Greenhouse scraper)
into a single deduplicated job list with intelligent source preference.

Key Features:
- Deduplicates by (company + title + location) MD5 hash
- Prefers Greenhouse descriptions (9,000+ chars vs Adzuna's 100-200)
- Tracks data source for each job
- Handles data format normalization
- Optional filtering by function/location

Usage:
------
ingester = UnifiedJobIngester()
merged_jobs = await ingester.merge(adzuna_jobs, greenhouse_jobs)

# Or with filtering
merged_jobs = await ingester.merge(
    adzuna_jobs,
    greenhouse_jobs,
    function_filter=['data_engineer', 'data_scientist'],
    location_code='lon'
)

Author: Claude Code
"""

import hashlib
import asyncio
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum


class DataSource(Enum):
    """Enum for job data sources"""
    ADZUNA = "adzuna"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    WORKABLE = "workable"
    CUSTOM = "custom"  # Config-driven scrapers for custom career sites (Google, FAANG, banks)
    HYBRID = "hybrid"  # When Adzuna job data + Greenhouse description


@dataclass
class UnifiedJob:
    """Unified job posting structure"""
    # Required fields
    company: str
    title: str
    location: str
    description: str
    url: str

    # Optional fields
    department: Optional[str] = None
    job_type: Optional[str] = None
    job_id: Optional[str] = None

    # Tracking fields
    source: DataSource = DataSource.ADZUNA
    original_url: Optional[str] = None  # URL from original source
    description_source: DataSource = DataSource.ADZUNA
    adzuna_description: Optional[str] = None  # Keep original for reference
    greenhouse_description: Optional[str] = None  # Keep original for reference

    # Adzuna API metadata (for classifier context)
    adzuna_category: Optional[str] = None  # e.g., "IT Jobs"
    adzuna_salary_min: Optional[float] = None
    adzuna_salary_max: Optional[float] = None
    adzuna_salary_predicted: Optional[bool] = None

    # Lever API metadata (for classifier context)
    lever_id: Optional[str] = None
    lever_team: Optional[str] = None
    lever_department: Optional[str] = None
    lever_commitment: Optional[str] = None  # Full-time, Part-time, etc.
    lever_workplace_type: Optional[str] = None  # onsite, hybrid, remote, unspecified
    lever_description: Optional[str] = None  # Keep original for reference

    # Classification results (added after Claude processing)
    classification: Optional[Dict] = None  # Claude classification results

    # Metadata
    deduplicated: bool = False  # Was this a duplicate merge?
    merged_from_id: Optional[str] = None  # If duplicate, URL of merged job
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert enums to strings
        data['source'] = self.source.value
        data['description_source'] = self.description_source.value
        # Convert datetime
        data['created_at'] = self.created_at.isoformat()
        return data


class UnifiedJobIngester:
    """Merges jobs from multiple sources with intelligent deduplication"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.dedup_key_map: Dict[str, UnifiedJob] = {}
        self.merge_log: List[Dict] = []

    async def merge(
        self,
        adzuna_jobs: List = None,
        greenhouse_jobs: List = None,
        function_filter: Optional[List[str]] = None,
        location_code: Optional[str] = None
    ) -> Tuple[List[UnifiedJob], Dict]:
        """
        Merge jobs from multiple sources with deduplication.

        Args:
            adzuna_jobs: List of Job objects from Adzuna API
            greenhouse_jobs: List of Job objects from Greenhouse scraper
            function_filter: Optional list of job functions to keep (e.g., ['data_engineer'])
            location_code: Optional location code to filter by (e.g., 'lon')

        Returns:
            Tuple of (merged_jobs, merge_stats)
        """

        if not adzuna_jobs:
            adzuna_jobs = []
        if not greenhouse_jobs:
            greenhouse_jobs = []

        self._log(f"Starting merge: {len(adzuna_jobs)} Adzuna + {len(greenhouse_jobs)} Greenhouse jobs")

        merged_jobs = []

        # Normalize jobs to ensure they all have required attributes
        # Handle both dict and object formats by creating wrapper objects
        class JobWrapper:
            """Minimal wrapper to provide attribute access for dicts or objects"""
            def __init__(self, job):
                if isinstance(job, dict):
                    self.company = job.get('company', '')
                    self.title = job.get('title', '')
                    self.location = job.get('location', '')
                    self.description = job.get('description', '')
                    self.url = job.get('url', '')
                    self.job_id = job.get('job_id')
                    self.department = job.get('department')
                    self.job_type = job.get('job_type')
                    self._original = job
                else:
                    # It's an object - use as-is
                    self.company = getattr(job, 'company', '')
                    self.title = getattr(job, 'title', '')
                    self.location = getattr(job, 'location', '')
                    self.description = getattr(job, 'description', '')
                    self.url = getattr(job, 'url', '')
                    self.job_id = getattr(job, 'job_id', None)
                    self.department = getattr(job, 'department', None)
                    self.job_type = getattr(job, 'job_type', None)
                    self._original = job

        # Normalize all greenhouse jobs
        greenhouse_jobs = [JobWrapper(job) for job in greenhouse_jobs]
        # Normalize all adzuna jobs
        adzuna_jobs = [JobWrapper(job) for job in adzuna_jobs]

        # Process Greenhouse jobs first (higher priority due to quality)
        self._log("Processing Greenhouse jobs (higher priority)")
        for job in greenhouse_jobs:
            dedup_key = self._make_dedup_key(job.company, job.title, job.location)

            if dedup_key not in self.dedup_key_map:
                unified_job = self._convert_to_unified(
                    job,
                    source=DataSource.GREENHOUSE,
                    description_source=DataSource.GREENHOUSE
                )
                self.dedup_key_map[dedup_key] = unified_job
                merged_jobs.append(unified_job)
                self._log(f"  [NEW] {job.company} - {job.title[:50]}")
            else:
                self._log(f"  [DUP-SKIPPED] {job.company} - {job.title[:50]} (already in Adzuna)")

        # Process Adzuna jobs
        self._log("Processing Adzuna jobs")
        for job in adzuna_jobs:
            dedup_key = self._make_dedup_key(job.company, job.title, job.location)

            if dedup_key not in self.dedup_key_map:
                # New job from Adzuna
                unified_job = self._convert_to_unified(
                    job,
                    source=DataSource.ADZUNA,
                    description_source=DataSource.ADZUNA
                )
                self.dedup_key_map[dedup_key] = unified_job
                merged_jobs.append(unified_job)
                self._log(f"  [NEW] {job.company} - {job.title[:50]}")
            else:
                # Duplicate: we already have this job from Greenhouse
                existing = self.dedup_key_map[dedup_key]

                # Check if we should prefer Adzuna description (unlikely, but possible)
                if (len(job.description or "") > len(existing.description or "") * 1.2):
                    # Adzuna description is significantly longer
                    self._log(f"  [DUP-UPGRADED] {job.company} - Using Adzuna desc ({len(job.description)} vs {len(existing.description)})")
                    existing.adzuna_description = existing.description
                    existing.description = job.description
                    existing.description_source = DataSource.ADZUNA
                    existing.deduplicated = True
                else:
                    # Keep Greenhouse description (standard case)
                    self._log(f"  [DUP-KEPT] {job.company} - Keeping Greenhouse desc ({len(existing.description)} vs {len(job.description)})")
                    existing.adzuna_description = job.description
                    existing.deduplicated = True

        # Apply filters if specified
        if function_filter or location_code:
            merged_jobs = self._apply_filters(
                merged_jobs,
                function_filter=function_filter,
                location_code=location_code
            )

        # Generate statistics
        stats = self._generate_stats(merged_jobs, len(adzuna_jobs), len(greenhouse_jobs))

        self._log(f"\nMerge complete: {len(merged_jobs)} final jobs")
        self._log(f"  - New from Greenhouse: {stats['greenhouse_only']}")
        self._log(f"  - New from Adzuna: {stats['adzuna_only']}")
        self._log(f"  - Deduplicated: {stats['deduplicated']}")

        return merged_jobs, stats

    def _make_dedup_key(self, company: str, title: str, location: str) -> str:
        """Create MD5 deduplication key from company + title + location"""
        key_str = f"{company.lower()}|{title.lower()}|{location.lower()}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _convert_to_unified(self, job, source: DataSource, description_source: DataSource) -> UnifiedJob:
        """Convert job from any format to UnifiedJob
        
        Handles Job dataclass, JobWrapper, and dict formats.
        Since we wrap all jobs in JobWrapper before calling this, we can safely use attribute access.
        """

        # JobWrapper provides attribute access for both dicts and objects
        # So we can safely use getattr with defaults
        company = getattr(job, 'company', '')
        title = getattr(job, 'title', '')
        location = getattr(job, 'location', '')
        description = getattr(job, 'description', '') or ""
        url = getattr(job, 'url', '') or ""
        department = getattr(job, 'department', None)
        job_type = getattr(job, 'job_type', None)
        job_id = getattr(job, 'job_id', None)

        return UnifiedJob(
            company=company,
            title=title,
            location=location,
            description=description,
            url=url,
            department=department,
            job_type=job_type,
            job_id=job_id,
            source=source,
            original_url=url,
            description_source=description_source,
            adzuna_description=description if source == DataSource.ADZUNA else None,
            greenhouse_description=description if source == DataSource.GREENHOUSE else None
        )

    def _apply_filters(
        self,
        jobs: List[UnifiedJob],
        function_filter: Optional[List[str]] = None,
        location_code: Optional[str] = None
    ) -> List[UnifiedJob]:
        """Apply optional filters to merged jobs"""

        # Note: function_filter would require classification results
        # For now, we only support location filtering
        if location_code:
            jobs = [j for j in jobs if self._normalize_location(j.location) == location_code.lower()]

        return jobs

    def _normalize_location(self, location: str) -> str:
        """Normalize location string to code (e.g., 'London' -> 'lon')"""
        if not location:
            return 'unknown'

        location_lower = location.lower()

        # Map common location names to codes
        location_map = {
            'london': 'lon',
            'new york': 'nyc',
            'new york city': 'nyc',
            'denver': 'den',
            'united kingdom': 'lon',
            'uk': 'lon',
            'us': 'usa',
            'united states': 'usa',
        }

        # Check if location matches any known mappings
        for name, code in location_map.items():
            if name in location_lower:
                return code

        # Return first 3 letters if no mapping found
        return location_lower[:3]

    def _generate_stats(self, merged_jobs, adzuna_count, greenhouse_count) -> Dict:
        """Generate merge statistics"""

        greenhouse_only = sum(1 for j in merged_jobs if j.source == DataSource.GREENHOUSE and not j.deduplicated)
        adzuna_only = sum(1 for j in merged_jobs if j.source == DataSource.ADZUNA)
        deduplicated = sum(1 for j in merged_jobs if j.deduplicated)

        avg_description_length = sum(len(j.description) for j in merged_jobs) // len(merged_jobs) if merged_jobs else 0

        return {
            'total_merged': len(merged_jobs),
            'greenhouse_input': greenhouse_count,
            'adzuna_input': adzuna_count,
            'greenhouse_only': greenhouse_only,
            'adzuna_only': adzuna_only,
            'deduplicated': deduplicated,
            'dedup_rate': f"{100 * deduplicated // (adzuna_count + greenhouse_count)}%" if (adzuna_count + greenhouse_count) > 0 else "0%",
            'avg_description_length': avg_description_length,
            'source_breakdown': {
                'greenhouse': sum(1 for j in merged_jobs if j.description_source == DataSource.GREENHOUSE),
                'adzuna': sum(1 for j in merged_jobs if j.description_source == DataSource.ADZUNA),
            }
        }

    def _log(self, message: str):
        """Log message if verbose mode enabled"""
        if self.verbose:
            print(message)

    def export_to_json(self, jobs: List[UnifiedJob], filepath: str):
        """Export merged jobs to JSON file"""
        import json

        jobs_dict = [j.to_dict() for j in jobs]

        with open(filepath, 'w') as f:
            json.dump(jobs_dict, f, indent=2)

        self._log(f"Exported {len(jobs)} jobs to {filepath}")

    def export_to_csv(self, jobs: List[UnifiedJob], filepath: str):
        """Export merged jobs to CSV file"""
        import csv

        if not jobs:
            self._log("No jobs to export")
            return

        fieldnames = [
            'company', 'title', 'location', 'url', 'source',
            'description_source', 'description_length', 'deduplicated'
        ]

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for job in jobs:
                writer.writerow({
                    'company': job.company,
                    'title': job.title,
                    'location': job.location,
                    'url': job.url,
                    'source': job.source.value,
                    'description_source': job.description_source.value,
                    'description_length': len(job.description),
                    'deduplicated': job.deduplicated
                })

        self._log(f"Exported {len(jobs)} jobs to {filepath}")


async def main():
    """Example usage of UnifiedJobIngester"""

    # This would normally come from fetch_adzuna_jobs.py and greenhouse_scraper.py
    # For now, showing the interface

    ingester = UnifiedJobIngester(verbose=True)

    # Example with empty lists (would use real data in production)
    merged_jobs, stats = await ingester.merge(
        adzuna_jobs=[],
        greenhouse_jobs=[],
    )

    print("\n=== Merge Statistics ===")
    for key, value in stats.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
