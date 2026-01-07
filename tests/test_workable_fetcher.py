"""
Test Workable fetcher module

This test validates:
1. WorkableJob dataclass structure
2. API response parsing
3. Company mapping loading
4. Filter pattern loading and application
5. Rate limiting behavior
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.workable.workable_fetcher import (
    WorkableJob,
    parse_workable_job,
    fetch_workable_jobs,
    load_company_mapping,
    check_company_exists,
    WORKABLE_API_URL
)


class TestWorkableJobDataclass:
    """Test WorkableJob dataclass"""

    def test_minimal_job(self):
        """Test creating job with minimal required fields"""
        job = WorkableJob(
            id="ABC123",
            title="Data Engineer",
            company_slug="acme",
            location="London, UK",
            description="Great opportunity...",
            url="https://apply.workable.com/acme/j/ABC123/",
            apply_url="https://apply.workable.com/acme/j/ABC123/apply"
        )
        assert job.id == "ABC123"
        assert job.title == "Data Engineer"
        assert job.company_slug == "acme"
        assert job.workplace_type is None  # Optional field

    def test_full_job(self):
        """Test creating job with all fields"""
        job = WorkableJob(
            id="ABC123",
            title="Data Engineer",
            company_slug="acme",
            location="London, UK",
            description="Great opportunity...",
            url="https://apply.workable.com/acme/j/ABC123/",
            apply_url="https://apply.workable.com/acme/j/ABC123/apply",
            department="Engineering",
            employment_type="full_time",
            workplace_type="hybrid",
            salary_min=80000,
            salary_max=120000,
            salary_currency="GBP",
            city="London",
            region="Greater London",
            country_code="GB",
            published_at="2026-01-01"
        )
        assert job.workplace_type == "hybrid"
        assert job.salary_min == 80000
        assert job.salary_max == 120000
        assert job.salary_currency == "GBP"
        assert job.city == "London"
        assert job.country_code == "GB"

    def test_workplace_types(self):
        """Test different workplace_type values"""
        for wt in ['on_site', 'hybrid', 'remote']:
            job = WorkableJob(
                id="TEST",
                title="Test Role",
                company_slug="test",
                location="Test",
                description="Test",
                url="https://test.com",
                apply_url="https://test.com/apply",
                workplace_type=wt
            )
            assert job.workplace_type == wt


class TestParseWorkableJob:
    """Test job parsing from API response"""

    def test_parse_basic_job(self):
        """Test parsing basic job data"""
        raw_data = {
            "shortcode": "XYZ789",
            "title": "Product Manager",
            "description": "Lead product development...",
            "url": "https://apply.workable.com/test/j/XYZ789/",
            "application_url": "https://apply.workable.com/test/j/XYZ789/apply",
            "location": {
                "location_str": "New York, NY",
                "city": "New York",
                "region": "NY",
                "country_code": "US"
            }
        }
        job = parse_workable_job(raw_data, "test")
        assert job.id == "XYZ789"
        assert job.title == "Product Manager"
        assert job.city == "New York"
        assert job.country_code == "US"
        assert job.location == "New York, NY"

    def test_parse_with_workplace_type(self):
        """Test parsing job with workplace_type"""
        raw_data = {
            "shortcode": "REM001",
            "title": "Remote Data Analyst",
            "description": "Work from anywhere...",
            "url": "https://apply.workable.com/remote/j/REM001/",
            "application_url": "https://apply.workable.com/remote/j/REM001/apply",
            "workplace_type": "remote",
            "location": {}
        }
        job = parse_workable_job(raw_data, "remote")
        assert job.workplace_type == "remote"

    def test_parse_with_salary(self):
        """Test parsing job with salary data"""
        raw_data = {
            "shortcode": "SAL001",
            "title": "ML Engineer",
            "description": "Build models...",
            "url": "https://apply.workable.com/ml/j/SAL001/",
            "application_url": "https://apply.workable.com/ml/j/SAL001/apply",
            "salary": {
                "salary_from": 150000,
                "salary_to": 200000,
                "salary_currency": "USD"
            },
            "location": {"city": "San Francisco"}
        }
        job = parse_workable_job(raw_data, "ml")
        assert job.salary_min == 150000
        assert job.salary_max == 200000
        assert job.salary_currency == "USD"

    def test_parse_with_department(self):
        """Test parsing job with department"""
        raw_data = {
            "shortcode": "DEP001",
            "title": "Data Scientist",
            "description": "Data science role...",
            "url": "https://apply.workable.com/company/j/DEP001/",
            "application_url": "https://apply.workable.com/company/j/DEP001/apply",
            "department": "Data Science",
            "employment_type": "full_time",
            "location": {}
        }
        job = parse_workable_job(raw_data, "company")
        assert job.department == "Data Science"
        assert job.employment_type == "full_time"

    def test_parse_location_fallback(self):
        """Test location string fallback when location_str is missing"""
        raw_data = {
            "shortcode": "LOC001",
            "title": "Engineer",
            "description": "Engineering role...",
            "url": "https://apply.workable.com/company/j/LOC001/",
            "application_url": "https://apply.workable.com/company/j/LOC001/apply",
            "location": {
                "city": "London",
                "region": "Greater London",
                "country": "United Kingdom"
            }
        }
        job = parse_workable_job(raw_data, "company")
        assert job.location == "London, Greater London, United Kingdom"

    def test_parse_empty_location(self):
        """Test parsing job with empty location"""
        raw_data = {
            "shortcode": "EMP001",
            "title": "Remote Engineer",
            "description": "Remote role...",
            "url": "https://apply.workable.com/company/j/EMP001/",
            "application_url": "https://apply.workable.com/company/j/EMP001/apply",
            "location": None
        }
        job = parse_workable_job(raw_data, "company")
        assert job.location == ""


class TestLoadCompanyMapping:
    """Test company mapping loading"""

    def test_load_mapping(self):
        """Test loading company mapping from config"""
        mapping = load_company_mapping()
        assert 'workable' in mapping
        # Should have _meta section
        assert '_meta' in mapping

    def test_load_mapping_structure(self):
        """Test mapping has correct structure"""
        mapping = load_company_mapping()
        meta = mapping.get('_meta', {})
        assert 'validated_at' in meta or 'last_updated' in meta


class TestCheckCompanyExists:
    """Test company existence check"""

    @patch('scrapers.workable.workable_fetcher.requests.get')
    def test_company_exists(self, mock_get):
        """Test checking if company exists"""
        mock_get.return_value.status_code = 200
        assert check_company_exists("valid-company") is True
        mock_get.assert_called_once()

    @patch('scrapers.workable.workable_fetcher.requests.get')
    def test_company_not_found(self, mock_get):
        """Test checking if company does not exist"""
        mock_get.return_value.status_code = 404
        assert check_company_exists("invalid-company") is False

    @patch('scrapers.workable.workable_fetcher.requests.get')
    def test_company_check_timeout(self, mock_get):
        """Test handling timeout during company check"""
        mock_get.side_effect = Exception("Timeout")
        assert check_company_exists("timeout-company") is False


class TestFetchWorkableJobs:
    """Test fetching jobs from Workable API"""

    @patch('scrapers.workable.workable_fetcher.requests.get')
    @patch('scrapers.workable.workable_fetcher.time.sleep')
    def test_fetch_jobs_success(self, mock_sleep, mock_get):
        """Test successful job fetch"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "Test Company",
            "jobs": [
                {
                    "shortcode": "JOB001",
                    "title": "Data Analyst",
                    "description": "Analyze data...",
                    "url": "https://apply.workable.com/test/j/JOB001/",
                    "application_url": "https://apply.workable.com/test/j/JOB001/apply",
                    "workplace_type": "hybrid",
                    "location": {
                        "location_str": "London, UK",
                        "city": "London",
                        "country_code": "GB"
                    }
                }
            ]
        }
        mock_get.return_value = mock_response

        jobs, stats = fetch_workable_jobs("test", filter_titles=False, filter_locations=False)

        assert len(jobs) == 1
        assert jobs[0].id == "JOB001"
        assert jobs[0].title == "Data Analyst"
        assert jobs[0].workplace_type == "hybrid"
        assert stats['jobs_fetched'] == 1
        assert stats['jobs_kept'] == 1
        assert stats['error'] is None

    @patch('scrapers.workable.workable_fetcher.requests.get')
    @patch('scrapers.workable.workable_fetcher.time.sleep')
    def test_fetch_jobs_not_found(self, mock_sleep, mock_get):
        """Test handling 404 response"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        jobs, stats = fetch_workable_jobs("nonexistent")

        assert len(jobs) == 0
        assert stats['error'] == 'Company not found'

    @patch('scrapers.workable.workable_fetcher.requests.get')
    @patch('scrapers.workable.workable_fetcher.time.sleep')
    def test_fetch_jobs_rate_limited(self, mock_sleep, mock_get):
        """Test handling 429 rate limit response"""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        jobs, stats = fetch_workable_jobs("rate-limited")

        assert len(jobs) == 0
        assert stats['error'] == 'Rate limited'

    @patch('scrapers.workable.workable_fetcher.requests.get')
    @patch('scrapers.workable.workable_fetcher.time.sleep')
    def test_fetch_jobs_timeout(self, mock_sleep, mock_get):
        """Test handling timeout"""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()

        jobs, stats = fetch_workable_jobs("timeout-company")

        assert len(jobs) == 0
        assert stats['error'] == 'Timeout'


class TestWorkableApiUrl:
    """Test API URL configuration"""

    def test_api_url_format(self):
        """Test API URL is correctly formatted"""
        assert WORKABLE_API_URL == "https://www.workable.com/api/accounts"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
