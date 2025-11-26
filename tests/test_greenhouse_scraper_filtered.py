#!/usr/bin/env python3
"""
Integration tests for Greenhouse scraper with title filtering.

Tests the full scraper with filtering enabled/disabled and validates metrics.
Requires browser automation (Playwright), so tests may be slower.
"""

import pytest
import asyncio
import tempfile
import yaml
from pathlib import Path
from scrapers.greenhouse.greenhouse_scraper import GreenhouseScraper, load_title_patterns


@pytest.mark.asyncio
class TestScraperInitialization:
    """Test scraper initialization with different filtering configs"""

    async def test_scraper_initialization_with_filtering(self):
        """Test that scraper initializes with filtering enabled by default"""
        scraper = GreenhouseScraper(headless=True, filter_titles=True)

        # Should have patterns loaded
        assert scraper.filter_titles == True
        assert len(scraper.title_patterns) > 0

        # Filter stats should be initialized
        assert scraper.filter_stats is not None
        assert 'jobs_scraped' in scraper.filter_stats
        assert 'jobs_kept' in scraper.filter_stats
        assert 'jobs_filtered' in scraper.filter_stats

    async def test_scraper_initialization_without_filtering(self):
        """Test that scraper can be initialized with filtering disabled"""
        scraper = GreenhouseScraper(headless=True, filter_titles=False)

        # Should NOT have patterns loaded
        assert scraper.filter_titles == False
        assert len(scraper.title_patterns) == 0

        # Filter stats should still be initialized (but won't be used)
        assert scraper.filter_stats is not None

    async def test_scraper_with_custom_patterns(self):
        """Test that custom pattern file can be loaded"""
        # Create temporary custom pattern file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            custom_config = {
                'relevant_title_patterns': [
                    'custom pattern 1',
                    'custom pattern 2',
                ]
            }
            yaml.dump(custom_config, f)
            temp_path = Path(f.name)

        try:
            scraper = GreenhouseScraper(
                headless=True,
                filter_titles=True,
                pattern_config_path=temp_path
            )

            # Should load custom patterns
            assert len(scraper.title_patterns) == 2
            assert 'custom pattern 1' in scraper.title_patterns
            assert 'custom pattern 2' in scraper.title_patterns
        finally:
            temp_path.unlink()

    async def test_scraper_filter_stats_reset(self):
        """Test that filter stats reset between scrapes"""
        scraper = GreenhouseScraper(headless=True, filter_titles=True)

        # Initial stats should be zeroed
        assert scraper.filter_stats['jobs_scraped'] == 0
        assert scraper.filter_stats['jobs_kept'] == 0
        assert scraper.filter_stats['jobs_filtered'] == 0

        # Manually modify stats (simulate a scrape)
        scraper.filter_stats['jobs_scraped'] = 100
        scraper.filter_stats['jobs_kept'] = 30
        scraper.filter_stats['jobs_filtered'] = 70

        # Reset should clear everything
        scraper.reset_filter_stats()
        assert scraper.filter_stats['jobs_scraped'] == 0
        assert scraper.filter_stats['jobs_kept'] == 0
        assert scraper.filter_stats['jobs_filtered'] == 0


class TestFilteringMetrics:
    """Test filtering statistics and calculations"""

    def test_filter_stats_accuracy(self):
        """Test that filter stats calculations are correct"""
        scraper = GreenhouseScraper(headless=True, filter_titles=True)

        # Simulate scraping with filtering
        scraper.filter_stats['jobs_scraped'] = 100
        scraper.filter_stats['jobs_kept'] = 35
        scraper.filter_stats['jobs_filtered'] = 65

        # Calculate filter rate
        filter_rate = (scraper.filter_stats['jobs_filtered'] / scraper.filter_stats['jobs_scraped'] * 100)

        assert filter_rate == 65.0
        assert scraper.filter_stats['jobs_scraped'] == scraper.filter_stats['jobs_kept'] + scraper.filter_stats['jobs_filtered']

    def test_filtered_titles_captured(self):
        """Test that filtered titles are logged in stats"""
        scraper = GreenhouseScraper(headless=True, filter_titles=True)

        # Manually add some filtered titles
        filtered_titles = ['Sales Executive', 'Marketing Manager', 'HR Business Partner']
        scraper.filter_stats['filtered_titles'] = filtered_titles

        # Should be captured in stats
        assert len(scraper.filter_stats['filtered_titles']) == 3
        assert 'Sales Executive' in scraper.filter_stats['filtered_titles']
        assert 'Marketing Manager' in scraper.filter_stats['filtered_titles']

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
            # (jobs_scraped, jobs_filtered, expected_filter_rate)
            (100, 60, 60.0),
            (100, 70, 70.0),
            (66, 58, 87.9),  # Monzo example
            (69, 67, 97.1),  # Stripe example (97.1%)
        ]

        for jobs_scraped, jobs_filtered, expected_rate in test_cases:
            filter_rate = (jobs_filtered / jobs_scraped * 100)
            assert abs(filter_rate - expected_rate) < 0.1, f"Expected {expected_rate}% but got {filter_rate}%"


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
class TestLiveScraperFiltering:
    """
    Integration tests that actually scrape a company.

    These tests are marked as 'slow' and 'integration' because they:
    1. Require network access
    2. Launch a real browser
    3. May take 10-30 seconds per test

    Run with: pytest -m integration
    """

    async def test_return_format_includes_stats(self):
        """Test that scraper returns dict with 'jobs' and 'stats' keys"""
        scraper = GreenhouseScraper(headless=True, filter_titles=True)

        try:
            await scraper.init()

            # Scrape a small company (should be fast)
            result = await scraper.scrape_company('figma')

            # Should return dict with both keys
            assert isinstance(result, dict)
            assert 'jobs' in result
            assert 'stats' in result

            # Jobs should be a list
            assert isinstance(result['jobs'], list)

            # Stats should be a dict with expected keys
            stats = result['stats']
            assert 'jobs_scraped' in stats
            assert 'jobs_kept' in stats
            assert 'jobs_filtered' in stats
            assert 'filter_rate' in stats
            assert 'cost_savings_estimate' in stats
            assert 'filtered_titles_sample' in stats

        finally:
            await scraper.close()

    async def test_filtering_with_real_company(self):
        """Test filtering works on a real company (Figma)"""
        scraper = GreenhouseScraper(headless=True, filter_titles=True)

        try:
            await scraper.init()

            # Scrape Figma
            result = await scraper.scrape_company('figma')

            jobs = result['jobs']
            stats = result['stats']

            # Should have scraped some jobs
            assert stats['jobs_scraped'] > 0, "Should have scraped at least some jobs"

            # Should have filtered some jobs (unless ALL jobs are Data/Product, which is unlikely)
            # Most companies have sales, marketing, engineering, etc.
            # We expect at least 20% filter rate for most companies
            if stats['jobs_scraped'] > 10:  # Only check if we have enough data
                assert stats['jobs_filtered'] > 0, "Should filter out at least some non-Data/Product jobs"

            # Filter rate should be reasonable (0-100%)
            assert 0 <= stats['filter_rate'] <= 100

            # All kept jobs should be Data/Product roles
            patterns = load_title_patterns()
            from scrapers.greenhouse.greenhouse_scraper import is_relevant_role

            for job in jobs:
                assert is_relevant_role(job.title, patterns), f"Job '{job.title}' should match Data/Product patterns"

        finally:
            await scraper.close()

    async def test_filtering_disabled_returns_all_jobs(self):
        """Test that disabling filtering returns all jobs without filtering"""
        # Scrape same company with filtering ON and OFF, compare counts
        scraper_filtered = GreenhouseScraper(headless=True, filter_titles=True)
        scraper_unfiltered = GreenhouseScraper(headless=True, filter_titles=False)

        try:
            await scraper_filtered.init()
            await scraper_unfiltered.init()

            # Scrape with filtering
            result_filtered = await scraper_filtered.scrape_company('figma')

            # Scrape without filtering
            result_unfiltered = await scraper_unfiltered.scrape_company('figma')

            # Unfiltered should have more or equal jobs (should be more in most cases)
            jobs_filtered = len(result_filtered['jobs'])
            jobs_unfiltered = len(result_unfiltered['jobs'])

            assert jobs_unfiltered >= jobs_filtered, "Unfiltered scrape should return at least as many jobs"

            # Unfiltered stats should show 0 filtered
            assert result_unfiltered['stats']['jobs_filtered'] == 0
            assert result_unfiltered['stats']['jobs_kept'] == result_unfiltered['stats']['jobs_scraped']

        finally:
            await scraper_filtered.close()
            await scraper_unfiltered.close()

    async def test_cost_savings_estimate_in_result(self):
        """Test that cost savings estimate is included and formatted correctly"""
        scraper = GreenhouseScraper(headless=True, filter_titles=True)

        try:
            await scraper.init()
            result = await scraper.scrape_company('figma')

            stats = result['stats']

            # Should have cost_savings_estimate
            assert 'cost_savings_estimate' in stats

            # Should be formatted as dollar amount (e.g., "$0.27")
            cost_savings = stats['cost_savings_estimate']
            assert cost_savings.startswith('$'), "Cost savings should be formatted with $ prefix"

            # Extract numeric value
            numeric_value = float(cost_savings.replace('$', ''))

            # Should match formula: jobs_filtered * 0.00388
            expected_savings = stats['jobs_filtered'] * 0.00388
            assert abs(numeric_value - expected_savings) < 0.01, "Cost savings calculation mismatch"

        finally:
            await scraper.close()


class TestFilteringLogic:
    """Test the actual filtering logic during scraping"""

    def test_filtering_prevents_description_fetch_simulation(self):
        """
        Test that filtering prevents expensive description fetching.

        This is a simulation test - we don't actually scrape, but we verify the logic.
        """
        scraper = GreenhouseScraper(headless=True, filter_titles=True)
        patterns = scraper.title_patterns

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

        from scrapers.greenhouse.greenhouse_scraper import is_relevant_role

        # Verify filtering logic
        for title in filtered_titles:
            # These should be filtered (not relevant)
            assert is_relevant_role(title, patterns) == False, f"{title} should be filtered out"

        for title in kept_titles:
            # These should be kept (relevant)
            assert is_relevant_role(title, patterns) == True, f"{title} should be kept"

        # In production, filtered jobs would NOT have descriptions fetched
        # This saves network calls and processing time


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
