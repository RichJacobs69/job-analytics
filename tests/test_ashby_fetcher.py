"""
Test Ashby fetcher module

All HTTP calls mocked. Tests dataclass, compensation parsing, job parsing, and fetch behavior.

Tests:
1. AshbyJob dataclass structure
2. parse_compensation() - all three methods
3. parse_ashby_job() - job parsing from API response
4. Company mapping loading
5. Fetch jobs (success, 404, timeout)
"""

import sys
from pathlib import Path
from unittest.mock import patch, Mock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.ashby.ashby_fetcher import (
    AshbyJob,
    parse_compensation,
    parse_ashby_job,
    fetch_ashby_jobs,
    load_company_mapping,
    check_company_exists,
    ASHBY_API_URL,
)


class TestAshbyJobDataclass:
    """Test AshbyJob dataclass"""

    def test_minimal_job(self):
        """Test creating job with minimal required fields"""
        job = AshbyJob(
            id="abc-123",
            title="Data Scientist",
            company_slug="notion",
            location="San Francisco, CA",
            description="ML and analytics...",
            url="https://jobs.ashbyhq.com/notion/abc-123",
            apply_url="https://jobs.ashbyhq.com/notion/abc-123/apply"
        )
        assert job.id == "abc-123"
        assert job.title == "Data Scientist"
        assert job.is_remote is False
        assert job.salary_min is None
        assert job.salary_currency is None

    def test_full_job(self):
        """Test creating job with all fields"""
        job = AshbyJob(
            id="abc-123",
            title="Senior ML Engineer",
            company_slug="anthropic",
            location="San Francisco, CA",
            description="Build foundation models...",
            url="https://jobs.ashbyhq.com/anthropic/abc-123",
            apply_url="https://jobs.ashbyhq.com/anthropic/abc-123/apply",
            department="Research",
            team="ML Infrastructure",
            employment_type="FullTime",
            is_remote=True,
            salary_min=200000,
            salary_max=350000,
            salary_currency="USD",
            compensation_summary="$200,000 - $350,000",
            city="San Francisco",
            region="California",
            country="US",
            published_at="2026-01-15T10:00:00Z"
        )
        assert job.is_remote is True
        assert job.salary_min == 200000
        assert job.salary_max == 350000
        assert job.salary_currency == "USD"
        assert job.department == "Research"

    def test_is_remote_variations(self):
        """Test different is_remote values"""
        for remote in [True, False]:
            job = AshbyJob(
                id="TEST",
                title="Test",
                company_slug="test",
                location="Test",
                description="Test",
                url="https://test.com",
                apply_url="https://test.com/apply",
                is_remote=remote
            )
            assert job.is_remote is remote


class TestParseCompensation:
    """Test compensation parsing from Ashby's nested format"""

    def test_method1_salary_range_in_tiers(self):
        """Test Method 1: salaryRange in compensationTiers"""
        comp_data = {
            "compensationTierSummary": "$150K - $200K",
            "compensationTiers": [
                {
                    "salaryRange": {
                        "min": {"value": 150000, "currency": "USD"},
                        "max": {"value": 200000, "currency": "USD"}
                    }
                }
            ]
        }
        result = parse_compensation(comp_data)
        assert result['min'] == 150000
        assert result['max'] == 200000
        assert result['currency'] == "USD"
        assert result['summary'] == "$150K - $200K"

    def test_method2_components_array(self):
        """Test Method 2: components array within tier (Ramp pattern)"""
        comp_data = {
            "compensationTiers": [
                {
                    "components": [
                        {
                            "compensationType": "Salary",
                            "minValue": 120000,
                            "maxValue": 180000,
                            "currencyCode": "USD"
                        },
                        {
                            "compensationType": "Equity",
                            "minValue": 50000,
                            "maxValue": 100000,
                            "currencyCode": "USD"
                        }
                    ]
                }
            ]
        }
        result = parse_compensation(comp_data)
        assert result['min'] == 120000
        assert result['max'] == 180000
        assert result['currency'] == "USD"

    def test_method3_summary_components(self):
        """Test Method 3: summaryComponents at top level"""
        comp_data = {
            "summaryComponents": [
                {
                    "compensationType": "Salary",
                    "minValue": 80000,
                    "maxValue": 110000,
                    "currencyCode": "GBP"
                }
            ]
        }
        result = parse_compensation(comp_data)
        assert result['min'] == 80000
        assert result['max'] == 110000
        assert result['currency'] == "GBP"

    def test_empty_compensation(self):
        """Test parsing None compensation data"""
        result = parse_compensation(None)
        assert result == {}

    def test_empty_dict_compensation(self):
        """Test parsing empty dict compensation"""
        result = parse_compensation({})
        assert 'min' not in result
        assert 'max' not in result

    def test_missing_values_in_salary_range(self):
        """Test handling missing values in salaryRange"""
        comp_data = {
            "compensationTiers": [
                {
                    "salaryRange": {
                        "min": {},
                        "max": {}
                    }
                }
            ]
        }
        result = parse_compensation(comp_data)
        assert 'min' not in result
        assert 'max' not in result

    def test_method1_takes_priority_over_method3(self):
        """Test that Method 1 takes priority when available"""
        comp_data = {
            "compensationTiers": [
                {
                    "salaryRange": {
                        "min": {"value": 150000, "currency": "USD"},
                        "max": {"value": 200000, "currency": "USD"}
                    }
                }
            ],
            "summaryComponents": [
                {
                    "compensationType": "Salary",
                    "minValue": 999999,
                    "maxValue": 999999,
                    "currencyCode": "GBP"
                }
            ]
        }
        result = parse_compensation(comp_data)
        assert result['min'] == 150000
        assert result['currency'] == "USD"


class TestParseAshbyJob:
    """Test job parsing from API response"""

    def test_parse_basic_job(self):
        """Test parsing basic job data"""
        raw_data = {
            "id": "job-001",
            "title": "Data Engineer",
            "location": "London, UK",
            "descriptionPlain": "Build data pipelines...",
            "jobUrl": "https://jobs.ashbyhq.com/co/job-001",
            "applyUrl": "https://jobs.ashbyhq.com/co/job-001/apply",
            "isRemote": False
        }
        job = parse_ashby_job(raw_data, "co")
        assert job.id == "job-001"
        assert job.title == "Data Engineer"
        assert job.location == "London, UK"
        assert job.is_remote is False

    def test_parse_with_compensation(self):
        """Test parsing job with compensation data"""
        raw_data = {
            "id": "job-002",
            "title": "Senior Engineer",
            "location": "New York",
            "descriptionPlain": "Engineering role...",
            "jobUrl": "https://jobs.ashbyhq.com/co/job-002",
            "applyUrl": "https://jobs.ashbyhq.com/co/job-002/apply",
            "compensation": {
                "compensationTiers": [
                    {
                        "salaryRange": {
                            "min": {"value": 180000, "currency": "USD"},
                            "max": {"value": 250000, "currency": "USD"}
                        }
                    }
                ]
            }
        }
        job = parse_ashby_job(raw_data, "co")
        assert job.salary_min == 180000
        assert job.salary_max == 250000
        assert job.salary_currency == "USD"

    def test_parse_with_secondary_locations(self):
        """Test parsing job with multiple secondary locations"""
        raw_data = {
            "id": "job-003",
            "title": "PM",
            "location": "New York",
            "secondaryLocations": [
                {"location": "San Francisco"},
                {"location": "London"}
            ],
            "descriptionPlain": "Product role...",
            "jobUrl": "https://jobs.ashbyhq.com/co/job-003",
            "applyUrl": "https://jobs.ashbyhq.com/co/job-003/apply"
        }
        job = parse_ashby_job(raw_data, "co")
        assert "New York" in job.location
        assert "San Francisco" in job.location
        assert "London" in job.location

    def test_parse_with_is_remote(self):
        """Test parsing job with isRemote=True"""
        raw_data = {
            "id": "job-004",
            "title": "Remote Analyst",
            "location": "Remote",
            "descriptionPlain": "Remote analytics role...",
            "jobUrl": "https://jobs.ashbyhq.com/co/job-004",
            "applyUrl": "https://jobs.ashbyhq.com/co/job-004/apply",
            "isRemote": True
        }
        job = parse_ashby_job(raw_data, "co")
        assert job.is_remote is True

    def test_parse_with_structured_address(self):
        """Test parsing job with structured address"""
        raw_data = {
            "id": "job-005",
            "title": "Engineer",
            "location": "San Francisco, CA",
            "descriptionPlain": "Engineering role...",
            "jobUrl": "https://jobs.ashbyhq.com/co/job-005",
            "applyUrl": "https://jobs.ashbyhq.com/co/job-005/apply",
            "address": {
                "postalAddress": {
                    "addressLocality": "San Francisco",
                    "addressRegion": "California",
                    "addressCountry": "US"
                }
            }
        }
        job = parse_ashby_job(raw_data, "co")
        assert job.city == "San Francisco"
        assert job.region == "California"
        assert job.country == "US"

    def test_parse_empty_address(self):
        """Test parsing job with empty address"""
        raw_data = {
            "id": "job-006",
            "title": "Remote Role",
            "location": "Remote",
            "descriptionPlain": "Remote role...",
            "jobUrl": "https://jobs.ashbyhq.com/co/job-006",
            "applyUrl": "https://jobs.ashbyhq.com/co/job-006/apply",
            "address": None
        }
        job = parse_ashby_job(raw_data, "co")
        assert job.city is None
        assert job.region is None
        assert job.country is None

    def test_parse_with_department_and_team(self):
        """Test parsing job with department and team"""
        raw_data = {
            "id": "job-007",
            "title": "Data Scientist",
            "location": "London",
            "descriptionPlain": "Data science role...",
            "jobUrl": "https://jobs.ashbyhq.com/co/job-007",
            "applyUrl": "https://jobs.ashbyhq.com/co/job-007/apply",
            "department": "Data Science",
            "team": "ML Platform",
            "employmentType": "FullTime"
        }
        job = parse_ashby_job(raw_data, "co")
        assert job.department == "Data Science"
        assert job.team == "ML Platform"
        assert job.employment_type == "FullTime"

    def test_parse_html_fallback_description(self):
        """Test that descriptionHtml is used as fallback"""
        raw_data = {
            "id": "job-008",
            "title": "Engineer",
            "location": "NYC",
            "descriptionPlain": "",
            "descriptionHtml": "<p>HTML description</p>",
            "jobUrl": "https://jobs.ashbyhq.com/co/job-008",
            "applyUrl": "https://jobs.ashbyhq.com/co/job-008/apply"
        }
        job = parse_ashby_job(raw_data, "co")
        assert "HTML description" in job.description


class TestLoadCompanyMapping:
    """Test company mapping loading"""

    def test_load_mapping(self):
        """Test loading company mapping from config"""
        mapping = load_company_mapping()
        assert 'ashby' in mapping

    def test_mapping_has_companies(self):
        """Test mapping has company entries"""
        mapping = load_company_mapping()
        ashby = mapping.get('ashby', {})
        assert len(ashby) > 0


class TestCheckCompanyExists:
    """Test company existence check"""

    @patch('scrapers.ashby.ashby_fetcher.requests.get')
    def test_company_exists(self, mock_get):
        """Test checking existing company"""
        mock_get.return_value.status_code = 200
        assert check_company_exists("notion") is True

    @patch('scrapers.ashby.ashby_fetcher.requests.get')
    def test_company_not_found(self, mock_get):
        """Test checking non-existent company"""
        mock_get.return_value.status_code = 404
        assert check_company_exists("nonexistent") is False

    @patch('scrapers.ashby.ashby_fetcher.requests.get')
    def test_company_check_timeout(self, mock_get):
        """Test handling timeout during check"""
        mock_get.side_effect = Exception("Timeout")
        assert check_company_exists("timeout-co") is False


class TestFetchAshbyJobs:
    """Test fetching jobs from Ashby API"""

    @patch('scrapers.ashby.ashby_fetcher.requests.get')
    @patch('scrapers.ashby.ashby_fetcher.time.sleep')
    def test_fetch_jobs_success(self, mock_sleep, mock_get):
        """Test successful job fetch"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jobs": [
                {
                    "id": "job-001",
                    "title": "Data Engineer",
                    "location": "London, UK",
                    "descriptionPlain": "Build pipelines...",
                    "jobUrl": "https://jobs.ashbyhq.com/co/job-001",
                    "applyUrl": "https://jobs.ashbyhq.com/co/job-001/apply",
                    "isRemote": False
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        jobs, stats = fetch_ashby_jobs(
            "co", filter_titles=False, filter_locations=False
        )

        assert len(jobs) == 1
        assert jobs[0].id == "job-001"
        assert stats['jobs_fetched'] == 1
        assert stats['jobs_kept'] == 1
        assert stats['error'] is None

    @patch('scrapers.ashby.ashby_fetcher.requests.get')
    @patch('scrapers.ashby.ashby_fetcher.time.sleep')
    def test_fetch_jobs_not_found(self, mock_sleep, mock_get):
        """Test handling 404 response"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        jobs, stats = fetch_ashby_jobs("nonexistent")

        assert len(jobs) == 0
        assert stats['error'] == 'Company not found'

    @patch('scrapers.ashby.ashby_fetcher.requests.get')
    @patch('scrapers.ashby.ashby_fetcher.time.sleep')
    def test_fetch_jobs_timeout(self, mock_sleep, mock_get):
        """Test handling timeout"""
        mock_get.side_effect = requests.exceptions.Timeout()

        jobs, stats = fetch_ashby_jobs("timeout-co")

        assert len(jobs) == 0
        assert stats['error'] == 'Timeout'

    @patch('scrapers.ashby.ashby_fetcher.requests.get')
    @patch('scrapers.ashby.ashby_fetcher.time.sleep')
    def test_fetch_jobs_invalid_json(self, mock_sleep, mock_get):
        """Test handling invalid JSON response"""
        import json
        mock_get.side_effect = json.JSONDecodeError("", "", 0)

        jobs, stats = fetch_ashby_jobs("bad-json")

        assert len(jobs) == 0
        assert stats['error'] == 'Invalid JSON'


class TestApiUrl:
    """Test API URL configuration"""

    def test_api_url_format(self):
        """Test API URL is correctly formatted"""
        assert ASHBY_API_URL == "https://api.ashbyhq.com/posting-api/job-board"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
