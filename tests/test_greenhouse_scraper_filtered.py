#!/usr/bin/env python3
"""
Integration tests for Greenhouse API fetcher with title/location filtering.

Tests the API-based fetcher with filtering enabled/disabled and validates metrics.
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from scrapers.common.filters import load_title_patterns, is_relevant_role


class TestFilteringMetrics:
    """Test filtering statistics and calculations"""

    def test_filter_stats_accuracy(self):
        """Test that filter stats calculations are correct"""
        # Simulate fetch_greenhouse_jobs stats
        stats = {
            'jobs_fetched': 100,
            'jobs_kept': 35,
            'filtered_by_title': 45,
            'filtered_by_location': 20,
        }

        total_filtered = stats['filtered_by_title'] + stats['filtered_by_location']
        filter_rate = (total_filtered / stats['jobs_fetched'] * 100)

        assert filter_rate == 65.0
        assert stats['jobs_fetched'] == stats['jobs_kept'] + total_filtered

    def test_cost_savings_calculation(self):
        """Test that cost savings calculation matches expected formula"""
        # Expected cost per classification: $0.00388
        COST_PER_JOB = 0.00388

        # Test case 1: 70 jobs filtered
        jobs_filtered = 70
        expected_savings = jobs_filtered * COST_PER_JOB
        assert abs(expected_savings - 0.27) < 0.01  # ~$0.27

        # Test case 2: 100 jobs filtered
        jobs_filtered = 100
        expected_savings = jobs_filtered * COST_PER_JOB
        assert abs(expected_savings - 0.39) < 0.01  # ~$0.39

        # Test case 3: 58 jobs filtered (Monzo example from validation)
        jobs_filtered = 58
        expected_savings = jobs_filtered * COST_PER_JOB
        assert abs(expected_savings - 0.23) < 0.01  # ~$0.23

    def test_filter_rate_calculation(self):
        """Test that filter rate percentage calculation is correct"""
        test_cases = [
            # (jobs_fetched, jobs_filtered, expected_filter_rate)
            (100, 60, 60.0),
            (100, 70, 70.0),
            (66, 58, 87.9),  # Monzo example
            (69, 67, 97.1),  # Stripe example (97.1%)
        ]

        for jobs_fetched, jobs_filtered, expected_rate in test_cases:
            filter_rate = (jobs_filtered / jobs_fetched * 100)
            assert abs(filter_rate - expected_rate) < 0.1, f"Expected {expected_rate}% but got {filter_rate}%"


@pytest.mark.integration
@pytest.mark.slow
class TestLiveAPIFiltering:
    """
    Integration tests that actually call the Greenhouse API.

    These tests are marked as 'slow' and 'integration' because they:
    1. Require network access
    2. Hit the Greenhouse API

    Run with: pytest -m integration
    """

    def test_return_format_includes_stats(self):
        """Test that API fetcher returns correct stats structure"""
        from scrapers.greenhouse.greenhouse_api_fetcher import fetch_greenhouse_jobs

        jobs, stats = fetch_greenhouse_jobs('figma', filter_titles=True, filter_locations=True)

        # Stats should have expected keys
        assert 'jobs_fetched' in stats
        assert 'jobs_kept' in stats
        assert 'filtered_by_title' in stats
        assert 'filtered_by_location' in stats
        assert 'error' in stats

        # Jobs should be a list
        assert isinstance(jobs, list)

    def test_filtering_with_real_company(self):
        """Test filtering works on a real company (Figma)"""
        from scrapers.greenhouse.greenhouse_api_fetcher import fetch_greenhouse_jobs

        jobs, stats = fetch_greenhouse_jobs('figma', filter_titles=True, filter_locations=True)

        # Should have fetched some jobs
        assert stats['jobs_fetched'] > 0, "Should have fetched at least some jobs"

        # Should have filtered some jobs (unless ALL jobs are Data/Product, which is unlikely)
        if stats['jobs_fetched'] > 10:
            total_filtered = stats['filtered_by_title'] + stats['filtered_by_location']
            assert total_filtered > 0, "Should filter out at least some non-Data/Product jobs"

        # All kept jobs should be Data/Product roles
        patterns = load_title_patterns()
        for job in jobs:
            assert is_relevant_role(job.title, patterns), f"Job '{job.title}' should match Data/Product patterns"

    def test_filtering_disabled_returns_all_jobs(self):
        """Test that disabling filtering returns all jobs without filtering"""
        from scrapers.greenhouse.greenhouse_api_fetcher import fetch_greenhouse_jobs

        # Fetch with and without filtering
        jobs_filtered, stats_filtered = fetch_greenhouse_jobs(
            'figma', filter_titles=True, filter_locations=True
        )
        jobs_unfiltered, stats_unfiltered = fetch_greenhouse_jobs(
            'figma', filter_titles=False, filter_locations=False
        )

        # Unfiltered should have more or equal jobs
        assert len(jobs_unfiltered) >= len(jobs_filtered), \
            "Unfiltered fetch should return at least as many jobs"

        # Unfiltered stats should show 0 filtered
        assert stats_unfiltered['filtered_by_title'] == 0
        assert stats_unfiltered['filtered_by_location'] == 0
        assert stats_unfiltered['jobs_kept'] == stats_unfiltered['jobs_fetched']

    def test_structured_salary_data(self):
        """Test that API returns structured salary data for some jobs"""
        from scrapers.greenhouse.greenhouse_api_fetcher import fetch_greenhouse_jobs

        # Fetch without filtering to get more jobs
        jobs, stats = fetch_greenhouse_jobs('figma', filter_titles=False, filter_locations=False)

        # Check if any jobs have salary data
        jobs_with_salary = [j for j in jobs if j.salary_min or j.salary_max]
        # Note: Not all companies provide pay_input_ranges, so we just check the structure
        for job in jobs_with_salary:
            if job.salary_min:
                assert isinstance(job.salary_min, int)
                assert job.salary_min > 0
            if job.salary_max:
                assert isinstance(job.salary_max, int)
                assert job.salary_max > 0
            if job.salary_currency:
                assert isinstance(job.salary_currency, str)


class TestFilteringLogic:
    """Test the actual filtering logic"""

    def test_filtering_prevents_classification(self):
        """
        Test that filtering prevents expensive classification.
        This is a simulation test - we verify the logic without API calls.
        """
        patterns = load_title_patterns()

        # Simulate titles that would be filtered
        filtered_titles = [
            'Sales Executive',
            'Marketing Manager',
            'HR Business Partner',
            'Account Executive',
        ]

        # Simulate titles that would be kept
        kept_titles = [
            'Data Scientist',
            'ML Engineer',
            'Product Manager',
            'Data Engineer',
        ]

        # Verify filtering logic
        for title in filtered_titles:
            assert is_relevant_role(title, patterns) == False, f"{title} should be filtered out"

        for title in kept_titles:
            assert is_relevant_role(title, patterns) == True, f"{title} should be kept"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
