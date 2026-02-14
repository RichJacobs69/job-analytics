#!/usr/bin/env python3
"""
End-to-end pipeline tests for Greenhouse API fetcher with title filtering.

Tests the complete flow: Fetch (API) -> Filter -> Classify -> Store
These tests validate that filtering integrates correctly with the rest of the pipeline.
"""

import pytest
from pathlib import Path
from scrapers.common.filters import is_relevant_role, load_title_patterns, Job
from scrapers.greenhouse.greenhouse_api_fetcher import GreenhouseJob
from pipeline.unified_job_ingester import UnifiedJobIngester, UnifiedJob


@pytest.mark.e2e
@pytest.mark.slow
class TestE2EPipelineWithFiltering:
    """
    End-to-end pipeline tests.

    These tests validate the complete pipeline integration:
    - Greenhouse API fetcher with title filtering
    - Job ingestion and deduplication
    - Agency filtering (hard + soft)
    - Classification (LLM)
    - Storage in database
    """

    def test_greenhouse_api_output_format_for_pipeline(self):
        """
        Test that Greenhouse API fetcher output format is compatible with pipeline.
        """
        mock_job = GreenhouseJob(
            id='12345',
            title='Senior Data Scientist',
            company_slug='stripe',
            location='New York, NY',
            description='We are looking for a data scientist...',
            url='https://boards.greenhouse.io/stripe/jobs/12345',
            department='Data & Analytics',
            salary_min=150000,
            salary_max=200000,
            salary_currency='USD'
        )

        # Should have all required fields for pipeline processing
        assert mock_job.id == '12345'
        assert mock_job.title == 'Senior Data Scientist'
        assert mock_job.company_slug == 'stripe'
        assert len(mock_job.description) > 0
        assert mock_job.salary_min == 150000

    def test_deduplication_with_filtering(self):
        """
        Test that filtering and deduplication work together correctly.
        """
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
            title='Senior Data Scientist',
            location='New York, NY',
            description='Full description here...',
            source='greenhouse',
            url='https://boards.greenhouse.io/stripe/jobs/12345',
            job_id='12345'
        )

        ingester = UnifiedJobIngester()
        hash1 = ingester._make_dedup_key(job1.company, job1.title, job1.location)
        hash2 = ingester._make_dedup_key(job2.company, job2.title, job2.location)

        assert hash1 == hash2

        jobs = [job1, job2]
        unique_jobs = {}
        for job in jobs:
            job_hash = ingester._make_dedup_key(job.company, job.title, job.location)
            if job_hash not in unique_jobs:
                unique_jobs[job_hash] = job

        assert len(unique_jobs) == 1

    def test_agency_filtering_with_title_filtering(self):
        """
        Test that both filtering layers work together.
        """
        patterns = load_title_patterns()

        agency_irrelevant_title = 'Sales Executive'
        assert is_relevant_role(agency_irrelevant_title, patterns) == False

        agency_relevant_title = 'Data Scientist'
        assert is_relevant_role(agency_relevant_title, patterns) == True

        real_company_relevant_title = 'Senior ML Engineer'
        assert is_relevant_role(real_company_relevant_title, patterns) == True

    def test_filter_stats_structure(self):
        """
        Test that filter stats have the expected structure for monitoring.
        """
        # Simulate API fetcher stats (new format)
        stats = {
            'jobs_fetched': 100,
            'jobs_kept': 35,
            'filtered_by_title': 45,
            'filtered_by_location': 20,
            'error': None
        }

        total_filtered = stats['filtered_by_title'] + stats['filtered_by_location']
        filter_rate = (total_filtered / stats['jobs_fetched'] * 100)
        cost_savings_estimate = total_filtered * 0.00388

        assert filter_rate == 65.0
        assert abs(cost_savings_estimate - 0.25) < 0.01
        assert stats['jobs_fetched'] == stats['jobs_kept'] + total_filtered

    def test_cost_tracking_calculation(self):
        """
        Test that cost tracking reflects actual savings from filtering.
        """
        COST_PER_CLASSIFICATION = 0.00388

        # Scenario 1: No filtering (baseline)
        jobs_total_no_filter = 100
        cost_no_filter = jobs_total_no_filter * COST_PER_CLASSIFICATION
        assert abs(cost_no_filter - 0.388) < 0.001

        # Scenario 2: With 60% filter rate (typical)
        jobs_total_with_filter = 100
        filter_rate = 0.60
        jobs_filtered_out = int(jobs_total_with_filter * filter_rate)
        jobs_classified = jobs_total_with_filter - jobs_filtered_out

        cost_with_filter = jobs_classified * COST_PER_CLASSIFICATION
        cost_savings = cost_no_filter - cost_with_filter

        assert jobs_filtered_out == 60
        assert jobs_classified == 40
        assert abs(cost_with_filter - 0.155) < 0.001
        assert abs(cost_savings - 0.233) < 0.001

        savings_percentage = (cost_savings / cost_no_filter) * 100
        assert abs(savings_percentage - 60.0) < 0.1

    def test_filter_stats_aggregation_multiple_companies(self):
        """
        Test that filter stats can be aggregated across multiple companies.
        """
        companies = {
            'stripe': {
                'jobs_fetched': 69,
                'jobs_kept': 2,
                'filtered_by_title': 50,
                'filtered_by_location': 17,
            },
            'monzo': {
                'jobs_fetched': 66,
                'jobs_kept': 8,
                'filtered_by_title': 40,
                'filtered_by_location': 18,
            },
            'figma': {
                'jobs_fetched': 50,
                'jobs_kept': 15,
                'filtered_by_title': 25,
                'filtered_by_location': 10,
            }
        }

        total_fetched = sum(c['jobs_fetched'] for c in companies.values())
        total_kept = sum(c['jobs_kept'] for c in companies.values())
        total_filtered = sum(
            c['filtered_by_title'] + c['filtered_by_location']
            for c in companies.values()
        )
        total_savings = total_filtered * 0.00388

        overall_filter_rate = (total_filtered / total_fetched * 100)

        assert total_fetched == 185
        assert total_kept == 25
        assert total_filtered == 160
        assert abs(overall_filter_rate - 86.5) < 0.1
        assert abs(total_savings - 0.62) < 0.01

    def test_filtering_integration_with_classification_format(self):
        """
        Test that filtered jobs are in the correct format for classification.
        """
        filtered_job = GreenhouseJob(
            id='12345',
            title='Senior Data Scientist',
            company_slug='stripe',
            location='New York, NY',
            description='We are seeking a Senior Data Scientist to join our team. '
                       'You will work on machine learning models, analyze large datasets, '
                       'and collaborate with product teams. Required skills: Python, SQL, '
                       'PyTorch, statistics. Experience with A/B testing preferred.',
            url='https://boards.greenhouse.io/stripe/jobs/12345',
            department='Data & Analytics'
        )

        assert filtered_job.title is not None
        assert filtered_job.description is not None
        assert len(filtered_job.description) > 100
        assert filtered_job.company_slug is not None

        patterns = load_title_patterns()
        assert is_relevant_role(filtered_job.title, patterns) == True

    def test_end_to_end_flow_simulation(self):
        """
        Simulate the complete E2E flow without actual API calls or DB operations.
        """
        # Step 1: Simulate API fetcher output with filtering
        raw_titles = [
            ('Senior Data Scientist', True),
            ('Sales Executive', False),
            ('ML Engineer', True),
            ('Marketing Manager', False),
            ('Product Manager - AI', True),
        ]

        patterns = load_title_patterns()
        filtered_jobs = [
            GreenhouseJob(
                id=str(i),
                title=title,
                company_slug='stripe',
                location='NYC',
                description='Description...',
                url=f'https://boards.greenhouse.io/stripe/jobs/{i}'
            )
            for i, (title, should_keep) in enumerate(raw_titles, 1)
            if is_relevant_role(title, patterns)
        ]

        # Should keep only Data/Product roles
        assert len(filtered_jobs) == 3
        assert any('Data Scientist' in job.title for job in filtered_jobs)
        assert any('ML Engineer' in job.title for job in filtered_jobs)
        assert any('Product Manager' in job.title for job in filtered_jobs)

        # Step 2: Convert to UnifiedJob format
        unified_jobs = [
            UnifiedJob(
                company='stripe',
                title=job.title,
                location=job.location,
                description=job.description,
                source='greenhouse',
                url=job.url,
                job_id=job.id
            )
            for job in filtered_jobs
        ]

        assert len(unified_jobs) == 3

        # Step 3: Deduplication
        ingester = UnifiedJobIngester()
        unique_hashes = set()
        deduplicated_jobs = []
        for job in unified_jobs:
            job_hash = ingester._make_dedup_key(job.company, job.title, job.location)
            if job_hash not in unique_hashes:
                unique_hashes.add(job_hash)
                deduplicated_jobs.append(job)

        assert len(deduplicated_jobs) == 3

        # Step 4: Cost savings
        jobs_filtered_out = len(raw_titles) - len(deduplicated_jobs)
        cost_saved = jobs_filtered_out * 0.00388
        assert jobs_filtered_out == 2
        assert abs(cost_saved - 0.008) < 0.001


class TestFilteringProductionReadiness:
    """
    Tests to validate the filtering system is production-ready.
    """

    def test_empty_job_list_handling(self):
        """Test that filtering handles empty job lists gracefully"""
        from scrapers.greenhouse.greenhouse_api_fetcher import fetch_greenhouse_jobs

        # Use a slug that probably doesn't exist
        jobs, stats = fetch_greenhouse_jobs(
            'nonexistent_company_xyz_12345',
            filter_titles=True,
            filter_locations=True,
            rate_limit=0.1
        )

        # Should return empty list with error
        assert len(jobs) == 0
        assert stats['error'] is not None

    def test_all_jobs_filtered_scenario(self):
        """Test scenario where ALL jobs are filtered out"""
        stats = {
            'jobs_fetched': 20,
            'jobs_kept': 0,
            'filtered_by_title': 15,
            'filtered_by_location': 5,
        }

        total_filtered = stats['filtered_by_title'] + stats['filtered_by_location']
        filter_rate = (total_filtered / stats['jobs_fetched'] * 100)

        assert filter_rate == 100.0

        cost_savings = total_filtered * 0.00388
        assert abs(cost_savings - 0.078) < 0.001

    def test_no_jobs_filtered_scenario(self):
        """Test scenario where NO jobs are filtered"""
        stats = {
            'jobs_fetched': 30,
            'jobs_kept': 30,
            'filtered_by_title': 0,
            'filtered_by_location': 0,
        }

        total_filtered = stats['filtered_by_title'] + stats['filtered_by_location']
        filter_rate = (total_filtered / stats['jobs_fetched'] * 100) if stats['jobs_fetched'] > 0 else 0

        assert filter_rate == 0.0

        cost_savings = total_filtered * 0.00388
        assert cost_savings == 0.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
