"""
Report Generator - Codified queries for hiring market reports.

This module provides standardized queries for generating hiring market reports.
All SQL-equivalent logic is centralized here for consistency across reports.

Usage:
    from pipeline.report_generator import ReportGenerator

    generator = ReportGenerator()
    data = generator.generate_report_data(
        city_code='lon',
        job_family='data',
        start_date='2025-12-01',
        end_date='2025-12-31'
    )

    # Access structured data
    print(data['summary']['total_jobs'])
    print(data['seniority']['distribution'])
    print(data['skills']['top_skills'])

CLI Usage:
    python pipeline/report_generator.py --city lon --family data --start 2025-12-01 --end 2025-12-31
    python pipeline/report_generator.py --city lon --family data --start 2025-12-01 --end 2025-12-31 --output json
"""

import os
import json
import argparse
from datetime import datetime
from collections import Counter
from typing import Optional
from dotenv import load_dotenv


def normalize_employer_name(name: str) -> str:
    """Normalize employer name to match employer_metadata.canonical_name format."""
    if not name:
        return ''
    return name.lower().replace(' ', '_').replace(',', '').replace('.', '').replace("'", '')


def calculate_maturity_category(founding_year: int, current_year: int = 2025) -> str:
    """Calculate company maturity category from founding year."""
    if not founding_year:
        return None
    age = current_year - founding_year
    if age <= 5:
        return 'young'      # Early-stage, higher risk/reward
    elif age <= 15:
        return 'growth'     # Scale-up phase, Series B+ typically
    else:
        return 'mature'     # Established enterprises


class ReportGenerator:
    """
    Generate standardized hiring market report data.

    All queries are codified here to ensure consistency across reports.
    """

    # City to country/region mapping for inclusive location filtering
    CITY_CONFIG = {
        'london': {'country_code': 'GB', 'region': 'EMEA'},
        'new_york': {'country_code': 'US', 'region': 'AMER'},
        'denver': {'country_code': 'US', 'region': 'AMER'},
        'san_francisco': {'country_code': 'US', 'region': 'AMER'},
        'singapore': {'country_code': 'SG', 'region': 'APAC'},
    }

    # Legacy city_code to city name mapping
    CITY_CODE_MAP = {
        'lon': 'london',
        'nyc': 'new_york',
        'den': 'denver',
        'sfo': 'san_francisco',
        'sgp': 'singapore',
    }

    # Industry display labels
    INDUSTRY_LABELS = {
        'ai_ml': 'AI & Machine Learning',
        'data_infra': 'Data Infrastructure',
        'fintech': 'Fintech',
        'financial_services': 'Financial Services',
        'healthtech': 'Healthcare & Biotech',
        'consumer': 'Consumer Tech',
        'ecommerce': 'E-commerce & Retail',
        'professional_services': 'Professional Services',
        'mobility': 'Mobility & Transportation',
        'martech': 'Marketing Technology',
        'cybersecurity': 'Cybersecurity',
        'hr_tech': 'HR Technology',
        'proptech': 'Property Technology',
        'devtools': 'Developer Tools',
        'edtech': 'Education Technology',
        'climate': 'Climate & Sustainability',
        'crypto': 'Crypto & Web3',
        'productivity': 'Productivity Software',
        'other': 'Other',
    }

    # Seniority display labels
    SENIORITY_LABELS = {
        'junior': 'Junior',
        'mid': 'Mid-Level',
        'senior': 'Senior',
        'staff_principal': 'Staff/Principal',
        'director_plus': 'Director+',
    }

    # Subfamily display labels (Data family)
    DATA_SUBFAMILY_LABELS = {
        'data_engineer': 'Data Engineer',
        'ml_engineer': 'ML Engineer',
        'data_analyst': 'Data Analyst',
        'data_scientist': 'Data Scientist',
        'data_architect': 'Data Architect',
        'product_analytics': 'Product Analytics',
        'analytics_engineer': 'Analytics Engineer',
        'research_scientist_ml': 'Research Scientist (ML)',
        'ai_engineer': 'AI Engineer',
    }

    # Working arrangement display labels
    ARRANGEMENT_LABELS = {
        'hybrid': 'Hybrid',
        'onsite': 'Onsite',
        'remote': 'Remote',
        'flexible': 'Flexible',
        'unknown': 'Unknown',
    }

    # Employer size display labels
    SIZE_LABELS = {
        'enterprise': 'Enterprise (1,000+)',
        'scaleup': 'Scale-up (50-1,000)',
        'startup': 'Startup (<50)',
    }

    # Track display labels
    TRACK_LABELS = {
        'ic': 'Individual Contributor',
        'management': 'Management',
    }

    def __init__(self):
        """Initialize the report generator with Supabase connection."""
        load_dotenv()
        from supabase import create_client
        self.supabase = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )
        self._employer_metadata = None

    def _build_location_filter(self, city: str) -> str:
        """
        Build inclusive location filter for a city.

        Includes:
        - Direct city match
        - Global remote jobs
        - Country-scoped remote jobs
        - Country-wide jobs
        - Region jobs (for non-US cities)
        """
        config = self.CITY_CONFIG.get(city, {})
        country_code = config.get('country_code', 'US')
        region = config.get('region')

        parts = [
            f'locations.cs.[{{"city":"{city}"}}]',
            'locations.cs.[{"scope":"global"}]',
            'locations.cs.[{"scope":"country"}]',
            'locations.cs.[{"type":"country"}]',
        ]

        if region:
            parts.append(f'locations.cs.[{{"region":"{region}"}}]')

        return ','.join(parts)

    def _fetch_all_jobs(self, city_code: str, job_family: str,
                        start_date: str, end_date: str) -> list:
        """
        Fetch all jobs matching criteria with pagination.

        Uses INCLUSIVE location filtering - includes all jobs accessible
        to candidates in the specified city (local + remote + regional).

        Supabase has a 1000-row limit per query, so we paginate.
        """
        # Convert legacy city_code to city name
        city = self.CITY_CODE_MAP.get(city_code, city_code)

        # Build inclusive location filter
        location_filter = self._build_location_filter(city)

        all_jobs = []
        offset = 0

        while True:
            batch = (
                self.supabase.table('enriched_jobs')
                .select('*')
                .eq('job_family', job_family)
                .gte('posted_date', start_date)
                .lte('posted_date', end_date)
                .or_(location_filter)
                .range(offset, offset + 999)
                .execute()
            )

            if not batch.data:
                break

            all_jobs.extend(batch.data)
            offset += 1000

            if len(batch.data) < 1000:
                break

        return all_jobs

    def _fetch_employer_metadata(self) -> dict:
        """
        Fetch and cache employer metadata lookup.

        Returns dict keyed by canonical_name for O(1) lookups.
        """
        if self._employer_metadata is not None:
            return self._employer_metadata

        all_meta = []
        offset = 0

        while True:
            batch = (
                self.supabase.table('employer_metadata')
                .select('*')
                .range(offset, offset + 999)
                .execute()
            )

            if not batch.data:
                break

            all_meta.extend(batch.data)
            offset += 1000

            if len(batch.data) < 1000:
                break

        self._employer_metadata = {m['canonical_name']: m for m in all_meta}
        return self._employer_metadata

    def _filter_direct_jobs(self, jobs: list) -> tuple:
        """
        Filter out agency jobs.

        Returns (direct_jobs, agency_count).
        """
        agency_jobs = [j for j in jobs if j.get('is_agency') == True]
        direct_jobs = [j for j in jobs if not j.get('is_agency')]
        return direct_jobs, len(agency_jobs)

    def _calculate_distribution(self, jobs: list, field: str,
                                labels: dict = None) -> dict:
        """
        Calculate distribution for a categorical field.

        Returns dict with counts, percentages, and coverage.
        """
        counts = {}
        unknown_count = 0

        for job in jobs:
            value = job.get(field)
            if value is None or value == 'unknown' or value == 'null':
                unknown_count += 1
            else:
                counts[value] = counts.get(value, 0) + 1

        total = len(jobs)
        known = total - unknown_count
        coverage = known / total if total > 0 else 0

        # Sort by count descending
        sorted_items = sorted(counts.items(), key=lambda x: -x[1])

        distribution = []
        for value, count in sorted_items:
            label = labels.get(value, value) if labels else value
            pct = count / known if known > 0 else 0
            distribution.append({
                'code': value,
                'label': label,
                'count': count,
                'percentage': round(pct * 100, 1),
            })

        return {
            'distribution': distribution,
            'total': total,
            'known': known,
            'unknown': unknown_count,
            'coverage': round(coverage * 100, 1),
        }

    def _calculate_employer_metrics(self, jobs: list) -> dict:
        """
        Calculate employer-level metrics.

        - Top employers by job count
        - Market concentration (top 5, top 15)
        - Jobs per employer ratio
        """
        employer_counts = {}
        for job in jobs:
            emp = job.get('employer_name', 'unknown')
            employer_counts[emp] = employer_counts.get(emp, 0) + 1

        unique_employers = len(employer_counts)
        total_jobs = len(jobs)
        jobs_per_employer = total_jobs / unique_employers if unique_employers > 0 else 0

        # Sort by count descending
        sorted_employers = sorted(employer_counts.items(), key=lambda x: -x[1])

        # Top employers
        top_employers = []
        for emp, count in sorted_employers[:15]:
            pct = count / total_jobs if total_jobs > 0 else 0
            top_employers.append({
                'name': emp,
                'count': count,
                'percentage': round(pct * 100, 1),
            })

        # Concentration metrics
        counts_sorted = [c for _, c in sorted_employers]
        top_5 = sum(counts_sorted[:5])
        top_15 = sum(counts_sorted[:15])

        top_5_concentration = top_5 / total_jobs if total_jobs > 0 else 0
        top_15_concentration = top_15 / total_jobs if total_jobs > 0 else 0

        return {
            'unique_employers': unique_employers,
            'jobs_per_employer': round(jobs_per_employer, 2),
            'top_5_concentration': round(top_5_concentration * 100, 1),
            'top_15_concentration': round(top_15_concentration * 100, 1),
            'top_employers': top_employers,
        }

    def _calculate_seniority_metrics(self, jobs: list) -> dict:
        """
        Calculate seniority-specific metrics.

        - Distribution by level
        - Senior-to-junior ratio
        - Entry accessibility rate
        """
        dist = self._calculate_distribution(jobs, 'seniority', self.SENIORITY_LABELS)

        # Count by level for ratio calculations
        counts = {item['code']: item['count'] for item in dist['distribution']}

        senior_plus = (
            counts.get('senior', 0) +
            counts.get('staff_principal', 0) +
            counts.get('director_plus', 0)
        )
        junior = counts.get('junior', 0)

        # Senior-to-junior ratio
        senior_to_junior = senior_plus / junior if junior > 0 else float('inf')

        # Entry accessibility (junior + mid)
        entry_level = counts.get('junior', 0) + counts.get('mid', 0)
        entry_accessibility = entry_level / dist['known'] if dist['known'] > 0 else 0

        return {
            **dist,
            'senior_to_junior_ratio': round(senior_to_junior, 1),
            'entry_accessibility_rate': round(entry_accessibility * 100, 1),
        }

    def _calculate_skills_metrics(self, jobs: list) -> dict:
        """
        Calculate skills-related metrics.

        - Top skills by frequency
        - Common skill pairs
        """
        jobs_with_skills = [j for j in jobs if j.get('skills') and len(j.get('skills', [])) > 0]

        if not jobs_with_skills:
            return {
                'total_with_skills': 0,
                'coverage': 0,
                'top_skills': [],
                'skill_pairs': [],
            }

        # Count skills
        skill_counts = {}
        for job in jobs_with_skills:
            for skill in job.get('skills', []):
                if isinstance(skill, dict):
                    name = skill.get('name', 'unknown')
                else:
                    name = str(skill)
                skill_counts[name] = skill_counts.get(name, 0) + 1

        # Top skills
        sorted_skills = sorted(skill_counts.items(), key=lambda x: -x[1])
        top_skills = []
        for skill, count in sorted_skills[:15]:
            pct = count / len(jobs_with_skills)
            top_skills.append({
                'name': skill,
                'count': count,
                'percentage': round(pct * 100, 1),
            })

        # Skill pairs
        pairs = Counter()
        for job in jobs_with_skills:
            job_skills = []
            for s in job.get('skills', []):
                if isinstance(s, dict):
                    job_skills.append(s.get('name', ''))
                else:
                    job_skills.append(str(s))
            job_skills = sorted(set(job_skills))

            for i in range(len(job_skills)):
                for k in range(i + 1, len(job_skills)):
                    pairs[(job_skills[i], job_skills[k])] += 1

        skill_pairs = []
        for (s1, s2), count in pairs.most_common(10):
            pct = count / len(jobs_with_skills)
            skill_pairs.append({
                'skill_1': s1,
                'skill_2': s2,
                'count': count,
                'percentage': round(pct * 100, 1),
            })

        coverage = len(jobs_with_skills) / len(jobs) if jobs else 0

        return {
            'total_with_skills': len(jobs_with_skills),
            'coverage': round(coverage * 100, 1),
            'top_skills': top_skills,
            'skill_pairs': skill_pairs,
        }

    def _calculate_metadata_enriched_metrics(self, jobs: list) -> dict:
        """
        Calculate metrics from employer_metadata enrichment.

        - Industry distribution
        - Employer size (from metadata)
        - Company maturity (from founding_year)
        - Ownership type
        """
        meta_lookup = self._fetch_employer_metadata()

        # Enrich jobs with metadata
        industry_counts = {}
        size_counts = {}
        maturity_counts = {}
        ownership_counts = {}
        matched_count = 0

        for job in jobs:
            canonical = normalize_employer_name(job.get('employer_name', ''))
            meta = meta_lookup.get(canonical)

            if meta:
                matched_count += 1

                # Industry
                if meta.get('industry'):
                    ind = meta['industry']
                    industry_counts[ind] = industry_counts.get(ind, 0) + 1

                # Employer size
                if meta.get('employer_size'):
                    sz = meta['employer_size']
                    size_counts[sz] = size_counts.get(sz, 0) + 1

                # Maturity
                if meta.get('founding_year'):
                    mat = calculate_maturity_category(meta['founding_year'])
                    if mat:
                        maturity_counts[mat] = maturity_counts.get(mat, 0) + 1

                # Ownership
                if meta.get('ownership_type'):
                    own = meta['ownership_type']
                    ownership_counts[own] = ownership_counts.get(own, 0) + 1

        total = len(jobs)

        def build_distribution(counts, labels=None):
            if not counts:
                return {'distribution': [], 'total': 0, 'coverage': 0}

            total_known = sum(counts.values())
            sorted_items = sorted(counts.items(), key=lambda x: -x[1])

            dist = []
            for code, count in sorted_items:
                label = labels.get(code, code) if labels else code
                pct = count / total_known if total_known > 0 else 0
                dist.append({
                    'code': code,
                    'label': label,
                    'count': count,
                    'percentage': round(pct * 100, 1),
                })

            return {
                'distribution': dist,
                'total': total_known,
                'coverage': round(total_known / total * 100, 1) if total > 0 else 0,
            }

        return {
            'matched_jobs': matched_count,
            'match_rate': round(matched_count / total * 100, 1) if total > 0 else 0,
            'industry': build_distribution(industry_counts, self.INDUSTRY_LABELS),
            'employer_size': build_distribution(size_counts, self.SIZE_LABELS),
            'maturity': build_distribution(maturity_counts, {
                'young': 'Young (<=5 yrs)',
                'growth': 'Growth (6-15 yrs)',
                'mature': 'Mature (>15 yrs)',
            }),
            'ownership': build_distribution(ownership_counts, {
                'private': 'Private',
                'public': 'Public',
                'subsidiary': 'Subsidiary',
                'acquired': 'Acquired',
            }),
        }

    def _calculate_compensation_metrics(self, jobs: list, city_code: str) -> dict:
        """
        Calculate compensation metrics (US cities only).

        London and Singapore are excluded due to lack of pay transparency laws.
        """
        # Skip non-US cities
        if city_code not in ('nyc', 'den', 'sfo'):
            return {
                'available': False,
                'reason': 'Compensation data excluded due to low disclosure rates in markets without pay transparency legislation.',
            }

        jobs_with_salary = [
            j for j in jobs
            if j.get('salary_min') is not None and j.get('salary_max') is not None
        ]

        if len(jobs_with_salary) < 20:
            return {
                'available': False,
                'reason': f'Insufficient salary data ({len(jobs_with_salary)} jobs with salary disclosed).',
            }

        # Calculate midpoints
        midpoints = [
            (j['salary_min'] + j['salary_max']) / 2
            for j in jobs_with_salary
        ]
        midpoints.sort()

        n = len(midpoints)
        p25 = midpoints[int(n * 0.25)]
        median = midpoints[int(n * 0.50)]
        p75 = midpoints[int(n * 0.75)]

        # Salary by seniority
        by_seniority = {}
        for job in jobs_with_salary:
            sen = job.get('seniority')
            if sen and sen not in ('unknown', 'null'):
                if sen not in by_seniority:
                    by_seniority[sen] = []
                by_seniority[sen].append((job['salary_min'] + job['salary_max']) / 2)

        seniority_stats = []
        for sen, salaries in by_seniority.items():
            if len(salaries) >= 10:
                salaries.sort()
                n = len(salaries)
                seniority_stats.append({
                    'seniority': sen,
                    'label': self.SENIORITY_LABELS.get(sen, sen),
                    'p25': round(salaries[int(n * 0.25)]),
                    'median': round(salaries[int(n * 0.50)]),
                    'p75': round(salaries[int(n * 0.75)]),
                    'sample': n,
                })

        # Salary by subfamily
        by_subfamily = {}
        for job in jobs_with_salary:
            sub = job.get('job_subfamily')
            if sub and sub not in ('unknown', 'null'):
                if sub not in by_subfamily:
                    by_subfamily[sub] = []
                by_subfamily[sub].append((job['salary_min'] + job['salary_max']) / 2)

        subfamily_stats = []
        for sub, salaries in by_subfamily.items():
            if len(salaries) >= 10:
                salaries.sort()
                n = len(salaries)
                subfamily_stats.append({
                    'subfamily': sub,
                    'label': self.DATA_SUBFAMILY_LABELS.get(sub, sub),
                    'p25': round(salaries[int(n * 0.25)]),
                    'median': round(salaries[int(n * 0.50)]),
                    'p75': round(salaries[int(n * 0.75)]),
                    'sample': n,
                })

        coverage = len(jobs_with_salary) / len(jobs) if jobs else 0

        return {
            'available': True,
            'total_with_salary': len(jobs_with_salary),
            'coverage': round(coverage * 100, 1),
            'overall': {
                'p25': round(p25),
                'median': round(median),
                'p75': round(p75),
                'iqr': round(p75 - p25),
            },
            'by_seniority': sorted(seniority_stats, key=lambda x: -x['median']),
            'by_subfamily': sorted(subfamily_stats, key=lambda x: -x['median']),
        }

    def generate_report_data(self, city_code: str, job_family: str,
                             start_date: str, end_date: str) -> dict:
        """
        Generate complete report data for a market segment.

        Args:
            city_code: Location code (lon, nyc, den, sfo, sgp)
            job_family: Job family (data, product, delivery)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Dict containing all report metrics and distributions.
        """
        # Fetch all jobs
        all_jobs = self._fetch_all_jobs(city_code, job_family, start_date, end_date)

        # Filter agencies
        direct_jobs, agency_count = self._filter_direct_jobs(all_jobs)

        # Calculate all metrics
        employer_metrics = self._calculate_employer_metrics(direct_jobs)
        seniority_metrics = self._calculate_seniority_metrics(direct_jobs)
        subfamily_dist = self._calculate_distribution(
            direct_jobs, 'job_subfamily', self.DATA_SUBFAMILY_LABELS
        )
        track_dist = self._calculate_distribution(
            direct_jobs, 'track', self.TRACK_LABELS
        )
        arrangement_dist = self._calculate_distribution(
            direct_jobs, 'working_arrangement', self.ARRANGEMENT_LABELS
        )
        skills_metrics = self._calculate_skills_metrics(direct_jobs)
        metadata_metrics = self._calculate_metadata_enriched_metrics(direct_jobs)
        compensation_metrics = self._calculate_compensation_metrics(direct_jobs, city_code)

        return {
            'meta': {
                'city_code': city_code,
                'job_family': job_family,
                'start_date': start_date,
                'end_date': end_date,
                'generated_at': datetime.now().isoformat(),
            },
            'summary': {
                'total_jobs': len(all_jobs),
                'direct_jobs': len(direct_jobs),
                'agency_jobs': agency_count,
                'agency_rate': round(agency_count / len(all_jobs) * 100, 1) if all_jobs else 0,
                'unique_employers': employer_metrics['unique_employers'],
            },
            'employers': employer_metrics,
            'seniority': seniority_metrics,
            'subfamily': subfamily_dist,
            'track': track_dist,
            'working_arrangement': arrangement_dist,
            'skills': skills_metrics,
            'metadata_enrichment': metadata_metrics,
            'compensation': compensation_metrics,
            'market_metrics': {
                'structure': {
                    'jobs_per_employer': employer_metrics['jobs_per_employer'],
                    'top_5_concentration': employer_metrics['top_5_concentration'],
                    'top_15_concentration': employer_metrics['top_15_concentration'],
                },
                'accessibility': {
                    'senior_to_junior_ratio': seniority_metrics['senior_to_junior_ratio'],
                    'entry_accessibility_rate': seniority_metrics['entry_accessibility_rate'],
                    'management_opportunity_rate': next(
                        (d['percentage'] for d in track_dist['distribution'] if d['code'] == 'management'),
                        0
                    ),
                },
                'flexibility': {
                    'remote_rate': next(
                        (d['percentage'] for d in arrangement_dist['distribution'] if d['code'] == 'remote'),
                        0
                    ),
                    'flexibility_rate': sum(
                        d['percentage'] for d in arrangement_dist['distribution']
                        if d['code'] in ('remote', 'hybrid', 'flexible')
                    ),
                },
                'data_quality': {
                    'seniority_coverage': seniority_metrics['coverage'],
                    'arrangement_coverage': arrangement_dist['coverage'],
                    'skills_coverage': skills_metrics['coverage'],
                    'metadata_coverage': metadata_metrics['match_rate'],
                },
            },
        }


def main():
    """CLI entry point for report generation."""
    parser = argparse.ArgumentParser(
        description='Generate hiring market report data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python pipeline/report_generator.py --city lon --family data --start 2025-12-01 --end 2025-12-31
    python pipeline/report_generator.py --city nyc --family data --start 2025-12-01 --end 2025-12-31 --output json
        """
    )
    parser.add_argument('--city', required=True, choices=['lon', 'nyc', 'den', 'sfo', 'sgp'],
                        help='City code')
    parser.add_argument('--family', required=True, choices=['data', 'product', 'delivery'],
                        help='Job family')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--output', choices=['json', 'summary'], default='summary',
                        help='Output format')

    args = parser.parse_args()

    generator = ReportGenerator()
    data = generator.generate_report_data(
        city_code=args.city,
        job_family=args.family,
        start_date=args.start,
        end_date=args.end,
    )

    if args.output == 'json':
        print(json.dumps(data, indent=2))
    else:
        # Summary output
        print(f"\n{'='*60}")
        print(f"REPORT DATA: {args.city.upper()} {args.family.upper()}")
        print(f"Period: {args.start} to {args.end}")
        print(f"{'='*60}\n")

        s = data['summary']
        print(f"SUMMARY")
        print(f"  Total jobs: {s['total_jobs']}")
        print(f"  Direct employer jobs: {s['direct_jobs']}")
        print(f"  Agency jobs excluded: {s['agency_jobs']} ({s['agency_rate']}%)")
        print(f"  Unique employers: {s['unique_employers']}")

        print(f"\nMARKET STRUCTURE")
        m = data['market_metrics']['structure']
        print(f"  Jobs per employer: {m['jobs_per_employer']}")
        print(f"  Top 5 concentration: {m['top_5_concentration']}%")
        print(f"  Top 15 concentration: {m['top_15_concentration']}%")

        print(f"\nSENIORITY (coverage: {data['seniority']['coverage']}%)")
        for item in data['seniority']['distribution'][:5]:
            print(f"  {item['label']}: {item['percentage']}%")
        a = data['market_metrics']['accessibility']
        print(f"  Senior-to-Junior ratio: {a['senior_to_junior_ratio']}:1")
        print(f"  Entry accessibility: {a['entry_accessibility_rate']}%")

        print(f"\nROLE SPECIALIZATION")
        for item in data['subfamily']['distribution'][:8]:
            print(f"  {item['label']}: {item['percentage']}%")

        print(f"\nWORKING ARRANGEMENT (coverage: {data['working_arrangement']['coverage']}%)")
        for item in data['working_arrangement']['distribution']:
            if item['code'] != 'unknown':
                print(f"  {item['label']}: {item['percentage']}%")

        print(f"\nSKILLS (coverage: {data['skills']['coverage']}%)")
        for item in data['skills']['top_skills'][:10]:
            print(f"  {item['name']}: {item['percentage']}%")

        print(f"\nTOP EMPLOYERS")
        for item in data['employers']['top_employers'][:10]:
            print(f"  {item['name']}: {item['count']} jobs ({item['percentage']}%)")

        if data['compensation'].get('available'):
            c = data['compensation']
            print(f"\nCOMPENSATION (coverage: {c['coverage']}%)")
            print(f"  P25: ${c['overall']['p25']:,}")
            print(f"  Median: ${c['overall']['median']:,}")
            print(f"  P75: ${c['overall']['p75']:,}")
        else:
            print(f"\nCOMPENSATION")
            print(f"  {data['compensation'].get('reason', 'Not available')}")


if __name__ == '__main__':
    main()
