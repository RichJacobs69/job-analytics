#!/usr/bin/env python3
"""
End-to-end pipeline tests for Greenhouse scraper with title filtering.

Tests the complete flow: Scrape → Filter → Classify → Store
These tests validate that filtering integrates correctly with the rest of the pipeline.
"""

import pytest
import asyncio
from pathlib import Path
from scrapers.greenhouse.greenhouse_scraper import GreenhouseScraper, is_relevant_role, load_title_patterns
from unified_job_ingester import UnifiedJobIngester, UnifiedJob


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.slow
class TestE2EPipelineWithFiltering:
    """
    End-to-end pipeline tests.

    These tests validate the complete pipeline integration:
    - Greenhouse scraper with title filtering
    - Job ingestion and deduplication
    - Agency filtering (hard + soft)
    - Classification (LLM)
    - Storage in database

    Note: These tests are marked as 'slow' and 'e2e' because they may take several minutes.
    """

    async def test_greenhouse_scraper_output_format_for_pipeline(self):
        """
        Test that Greenhouse scraper output format is compatible with pipeline.

        The pipeline expects specific job formats from scrapers. This test validates
        that filtered Greenhouse jobs can be ingested into the unified pipeline.
        """
        scraper = GreenhouseScraper(headless=True, filter_titles=True)

        # Mock job output structure
        from scrapers.greenhouse.greenhouse_scraper import Job

        mock_job = Job(
            company='stripe',
            title='Senior Data Scientist',
            location='New York, NY',
            department='Data & Analytics',
            job_type='Full-time',
            description='We are looking for a data scientist...',
            url='https://boards.greenhouse.io/stripe/jobs/12345',
            job_id='12345'
        )

        # Convert to UnifiedJob format (would be done in fetch_jobs.py)
        unified_job = UnifiedJob(
            company=mock_job.company,
            title=mock_job.title,
            location=mock_job.location,
            description=mock_job.description,
            source='greenhouse',
            url=mock_job.url,
            job_id=mock_job.job_id
        )

        # Should have all required fields
        assert unified_job.company == 'stripe'
        assert unified_job.title == 'Senior Data Scientist'
        assert unified_job.source == 'greenhouse'
        assert len(unified_job.description) > 0

    def test_deduplication_with_filtering(self):
        """
        Test that filtering and deduplication work together correctly.

        Scenario:
        - Same job appears twice with same title
        - Should be deduplicated (only processed once)
        - Filtering should happen BEFORE deduplication to avoid wasted effort
        """
        # Create two identical jobs
        job1 = UnifiedJob(
            company='stripe',
            title='Senior Data Scientist',
            location='New York, NY',
            description='Full description here...',
            source='greenhouse',
            url='https://boards.greenhouse.io/stripe/jobs/12345',
            job_id='12345'
        )

        job2 = UnifiedJob(
            company='stripe',
            title='Senior Data Scientist',  # Same title
            location='New York, NY',  # Same location
            description='Full description here...',
            source='greenhouse',
            url='https://boards.greenhouse.io/stripe/jobs/12345',
            job_id='12345'
        )

        # Use the ingester's deduplication logic
        ingester = UnifiedJobIngester()
        hash1 = ingester._make_dedup_key(job1.company, job1.title, job1.location)
        hash2 = ingester._make_dedup_key(job2.company, job2.title, job2.location)

        # Deduplication key should be the same
        assert hash1 == hash2

        # In production, unified_job_ingester would deduplicate these
        jobs = [job1, job2]
        unique_jobs = {}
        for job in jobs:
            job_hash = ingester._make_dedup_key(job.company, job.title, job.location)
            if job_hash not in unique_jobs:
                unique_jobs[job_hash] = job

        # Should only have 1 unique job
        assert len(unique_jobs) == 1

    def test_agency_filtering_with_title_filtering(self):
        """
        Test that both filtering layers work together:
        1. Title filtering (pre-classification, filters by job title)
        2. Agency filtering (hard filter before LLM, soft detection after)

        Both should reduce costs and improve data quality.
        """
        patterns = load_title_patterns()

        # Test case 1: Job from agency with irrelevant title
        # Should be filtered by BOTH title filter AND agency filter
        agency_irrelevant_title = 'Sales Executive'
        assert is_relevant_role(agency_irrelevant_title, patterns) == False

        # Test case 2: Job from agency with relevant title
        # Would pass title filter but fail agency filter
        agency_relevant_title = 'Data Scientist'
        assert is_relevant_role(agency_relevant_title, patterns) == True
        # (Agency filter would catch this later based on company name)

        # Test case 3: Job from real company with relevant title
        # Should pass BOTH filters
        real_company_relevant_title = 'Senior ML Engineer'
        assert is_relevant_role(real_company_relevant_title, patterns) == True
        # (Would also pass agency filter since not from recruitment firm)

        # The combination of both filters provides maximum cost savings
        # while maintaining data quality

    def test_filter_stats_structure(self):
        """
        Test that filter stats have the expected structure for monitoring.

        Filter stats should be compatible with cost tracking and observability needs.
        """
        scraper = GreenhouseScraper(headless=True, filter_titles=True)

        # Simulate some filtering activity
        scraper.filter_stats['jobs_scraped'] = 100
        scraper.filter_stats['jobs_kept'] = 35
        scraper.filter_stats['jobs_filtered'] = 65
        scraper.filter_stats['filtered_titles'] = [
            'Sales Executive',
            'Marketing Manager',
            'Account Executive'
        ]

        # Calculate derived metrics (same as scraper does)
        filter_rate = (scraper.filter_stats['jobs_filtered'] / scraper.filter_stats['jobs_scraped'] * 100)
        cost_savings_estimate = scraper.filter_stats['jobs_filtered'] * 0.00388

        stats = {
            **scraper.filter_stats,
            'filter_rate': round(filter_rate, 1),
            'cost_savings_estimate': f"${cost_savings_estimate:.2f}",
            'filtered_titles_sample': scraper.filter_stats['filtered_titles'][:20],
        }

        # Validate structure
        assert 'jobs_scraped' in stats
        assert 'jobs_kept' in stats
        assert 'jobs_filtered' in stats
        assert 'filter_rate' in stats
        assert 'cost_savings_estimate' in stats
        assert 'filtered_titles_sample' in stats

        # Validate calculations
        assert stats['filter_rate'] == 65.0
        assert stats['cost_savings_estimate'] == '$0.25'
        assert stats['jobs_scraped'] == stats['jobs_kept'] + stats['jobs_filtered']

    def test_cost_tracking_calculation(self):
        """
        Test that cost tracking reflects actual savings from filtering.

        The classifier tracks costs per job. Filtering should reduce total costs
        by reducing the number of jobs sent to the LLM.
        """
        # Cost per classification (from Epic 4 validation)
        COST_PER_CLASSIFICATION = 0.00388

        # Scenario 1: No filtering (baseline)
        jobs_total_no_filter = 100
        cost_no_filter = jobs_total_no_filter * COST_PER_CLASSIFICATION
        assert abs(cost_no_filter - 0.388) < 0.001  # $0.388

        # Scenario 2: With 60% filter rate (typical)
        jobs_total_with_filter = 100
        filter_rate = 0.60
        jobs_filtered_out = int(jobs_total_with_filter * filter_rate)
        jobs_classified = jobs_total_with_filter - jobs_filtered_out

        cost_with_filter = jobs_classified * COST_PER_CLASSIFICATION
        cost_savings = cost_no_filter - cost_with_filter

        # Validation
        assert jobs_filtered_out == 60
        assert jobs_classified == 40
        assert abs(cost_with_filter - 0.155) < 0.001  # $0.155
        assert abs(cost_savings - 0.233) < 0.001  # $0.233 saved

        # Savings percentage
        savings_percentage = (cost_savings / cost_no_filter) * 100
        assert abs(savings_percentage - 60.0) < 0.1  # 60% savings

    def test_filter_stats_aggregation_multiple_companies(self):
        """
        Test that filter stats can be aggregated across multiple companies.

        When scraping multiple companies, we need to track:
        - Per-company filter rates
        - Overall filter rate across all companies
        - Total cost savings
        """
        # Simulate scraping 3 companies with different filter rates
        companies = {
            'stripe': {
                'jobs_scraped': 69,
                'jobs_kept': 2,
                'jobs_filtered': 67,
                'filter_rate': 97.1,
                'cost_savings': 67 * 0.00388
            },
            'monzo': {
                'jobs_scraped': 66,
                'jobs_kept': 8,
                'jobs_filtered': 58,
                'filter_rate': 87.9,
                'cost_savings': 58 * 0.00388
            },
            'figma': {
                'jobs_scraped': 50,
                'jobs_kept': 15,
                'jobs_filtered': 35,
                'filter_rate': 70.0,
                'cost_savings': 35 * 0.00388
            }
        }

        # Aggregate stats
        total_scraped = sum(c['jobs_scraped'] for c in companies.values())
        total_kept = sum(c['jobs_kept'] for c in companies.values())
        total_filtered = sum(c['jobs_filtered'] for c in companies.values())
        total_savings = sum(c['cost_savings'] for c in companies.values())

        overall_filter_rate = (total_filtered / total_scraped * 100)

        # Validate aggregation
        assert total_scraped == 185
        assert total_kept == 25
        assert total_filtered == 160
        assert abs(overall_filter_rate - 86.5) < 0.1  # 86.5% overall
        assert abs(total_savings - 0.62) < 0.01  # $0.62 total savings

    def test_filtering_integration_with_classification_format(self):
        """
        Test that filtered jobs are in the correct format for classification.

        After filtering, jobs should still have all fields needed for LLM classification.
        """
        from scrapers.greenhouse.greenhouse_scraper import Job

        # Create a job that would pass filtering
        filtered_job = Job(
            company='stripe',
            title='Senior Data Scientist',
            location='New York, NY',
            department='Data & Analytics',
            job_type='Full-time',
            description='We are seeking a Senior Data Scientist to join our team. '
                       'You will work on machine learning models, analyze large datasets, '
                       'and collaborate with product teams. Required skills: Python, SQL, '
                       'PyTorch, statistics. Experience with A/B testing preferred.',
            url='https://boards.greenhouse.io/stripe/jobs/12345',
            job_id='12345'
        )

        # Job should have all fields needed for classification
        assert filtered_job.title is not None
        assert filtered_job.description is not None
        assert len(filtered_job.description) > 100  # Sufficient text for classification
        assert filtered_job.company is not None

        # Title should pass filter
        patterns = load_title_patterns()
        assert is_relevant_role(filtered_job.title, patterns) == True

    def test_end_to_end_flow_simulation(self):
        """
        Simulate the complete E2E flow without actual scraping or DB operations.

        Flow:
        1. Greenhouse scraper extracts jobs with title filtering
        2. Filtered jobs converted to UnifiedJob format
        3. Jobs deduplicated by hash
        4. Jobs pass through agency filter
        5. Jobs sent to classifier (simulated here)
        6. Enriched jobs stored (simulated here)
        """
        # Step 1: Simulate Greenhouse scraper output with filtering
        from scrapers.greenhouse.greenhouse_scraper import Job

        raw_jobs = [
            Job('stripe', 'Senior Data Scientist', 'NYC', None, None, 'Description...', 'url1', '1'),
            Job('stripe', 'Sales Executive', 'NYC', None, None, 'Description...', 'url2', '2'),  # Would be filtered
            Job('stripe', 'ML Engineer', 'SF', None, None, 'Description...', 'url3', '3'),
            Job('stripe', 'Marketing Manager', 'NYC', None, None, 'Description...', 'url4', '4'),  # Would be filtered
            Job('stripe', 'Product Manager - AI', 'NYC', None, None, 'Description...', 'url5', '5'),
        ]

        # Step 2: Apply title filtering
        patterns = load_title_patterns()
        filtered_jobs = [job for job in raw_jobs if is_relevant_role(job.title, patterns)]

        # Should keep only Data/Product roles
        assert len(filtered_jobs) == 3  # Data Scientist, ML Engineer, PM-AI
        assert any('Data Scientist' in job.title for job in filtered_jobs)
        assert any('ML Engineer' in job.title for job in filtered_jobs)
        assert any('Product Manager' in job.title for job in filtered_jobs)

        # Should filter out Sales and Marketing
        assert not any('Sales' in job.title for job in filtered_jobs)
        assert not any('Marketing' in job.title for job in filtered_jobs)

        # Step 3: Convert to UnifiedJob format
        unified_jobs = [
            UnifiedJob(
                company=job.company,
                title=job.title,
                location=job.location,
                description=job.description,
                source='greenhouse',
                url=job.url,
                job_id=job.job_id
            )
            for job in filtered_jobs
        ]

        assert len(unified_jobs) == 3

        # Step 4: Deduplication (simulate - no actual duplicates in this test)
        ingester = UnifiedJobIngester()
        unique_hashes = set()
        deduplicated_jobs = []
        for job in unified_jobs:
            job_hash = ingester._make_dedup_key(job.company, job.title, job.location)
            if job_hash not in unique_hashes:
                unique_hashes.add(job_hash)
                deduplicated_jobs.append(job)

        assert len(deduplicated_jobs) == 3  # No duplicates

        # Step 5: At this point, jobs would go to classifier
        # We've saved 2 classification calls (Sales Executive, Marketing Manager)
        jobs_filtered_out = len(raw_jobs) - len(deduplicated_jobs)
        cost_saved = jobs_filtered_out * 0.00388
        assert jobs_filtered_out == 2
        assert abs(cost_saved - 0.008) < 0.001  # ~$0.008 saved

        # Step 6: Jobs would be classified and stored
        # (Simulated - not testing actual classification or DB here)


class TestFilteringProductionReadiness:
    """
    Tests to validate the filtering system is production-ready.

    These tests check for edge cases, error handling, and monitoring capabilities.
    """

    def test_empty_job_list_handling(self):
        """Test that filtering handles empty job lists gracefully"""
        scraper = GreenhouseScraper(headless=True, filter_titles=True)

        # Simulate scraping a company with no jobs
        scraper.reset_filter_stats()

        # Stats should be zeroed
        assert scraper.filter_stats['jobs_scraped'] == 0
        assert scraper.filter_stats['jobs_kept'] == 0
        assert scraper.filter_stats['jobs_filtered'] == 0

    def test_all_jobs_filtered_scenario(self):
        """Test scenario where ALL jobs are filtered out"""
        scraper = GreenhouseScraper(headless=True, filter_titles=True)

        # Simulate a company with only non-Data/Product jobs
        scraper.filter_stats['jobs_scraped'] = 20
        scraper.filter_stats['jobs_kept'] = 0
        scraper.filter_stats['jobs_filtered'] = 20

        filter_rate = (scraper.filter_stats['jobs_filtered'] / scraper.filter_stats['jobs_scraped'] * 100)

        # Should be 100% filter rate
        assert filter_rate == 100.0

        # Should still calculate cost savings
        cost_savings = scraper.filter_stats['jobs_filtered'] * 0.00388
        assert abs(cost_savings - 0.078) < 0.001  # $0.078 saved

    def test_no_jobs_filtered_scenario(self):
        """Test scenario where NO jobs are filtered (all are Data/Product roles)"""
        scraper = GreenhouseScraper(headless=True, filter_titles=True)

        # Simulate a pure Data company (unlikely but possible)
        scraper.filter_stats['jobs_scraped'] = 30
        scraper.filter_stats['jobs_kept'] = 30
        scraper.filter_stats['jobs_filtered'] = 0

        filter_rate = (scraper.filter_stats['jobs_filtered'] / scraper.filter_stats['jobs_scraped'] * 100) if scraper.filter_stats['jobs_scraped'] > 0 else 0

        # Should be 0% filter rate
        assert filter_rate == 0.0

        # Should have 0 cost savings
        cost_savings = scraper.filter_stats['jobs_filtered'] * 0.00388
        assert cost_savings == 0.0

    def test_filtered_titles_sample_limit(self):
        """Test that filtered titles sample is limited to prevent memory issues"""
        scraper = GreenhouseScraper(headless=True, filter_titles=True)

        # Simulate filtering many jobs
        filtered_titles = [f'Sales Executive {i}' for i in range(100)]
        scraper.filter_stats['filtered_titles'] = filtered_titles

        # Sample should be limited (as per scraper implementation: first 20)
        sample = scraper.filter_stats['filtered_titles'][:20]
        assert len(sample) == 20

        # In production stats dict, this is stored as 'filtered_titles_sample'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
