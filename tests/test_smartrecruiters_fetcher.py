"""
Test SmartRecruiters fetcher module

All HTTP calls mocked. Follows test_workable_fetcher.py pattern.

Tests:
1. SmartRecruitersJob dataclass structure
2. API response parsing (parse_smartrecruiters_job)
3. Company mapping loading
4. Fetch jobs (success, 404, rate limited, timeout, pagination)
"""

import sys
from pathlib import Path
from unittest.mock import patch, Mock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.smartrecruiters.smartrecruiters_fetcher import (
    SmartRecruitersJob,
    parse_smartrecruiters_job,
    fetch_smartrecruiters_jobs,
    load_company_mapping,
    check_company_exists,
    SMARTRECRUITERS_API_URL,
)


class TestSmartRecruitersJobDataclass:
    """Test SmartRecruitersJob dataclass"""

    def test_minimal_job(self):
        """Test creating job with minimal required fields"""
        job = SmartRecruitersJob(
            id="abc-123",
            title="Data Engineer",
            company_slug="visa",
            location="London, UK",
            description="Build data pipelines...",
            url="https://jobs.smartrecruiters.com/visa/abc-123",
            apply_url="https://jobs.smartrecruiters.com/visa/abc-123-apply"
        )
        assert job.id == "abc-123"
        assert job.title == "Data Engineer"
        assert job.company_slug == "visa"
        assert job.department is None
        assert job.location_type is None
        assert job.experience_level is None

    def test_full_job(self):
        """Test creating job with all fields"""
        job = SmartRecruitersJob(
            id="abc-123",
            title="Senior Data Engineer",
            company_slug="visa",
            location="London, Greater London, United Kingdom",
            description="Build data pipelines...",
            url="https://jobs.smartrecruiters.com/visa/abc-123",
            apply_url="https://jobs.smartrecruiters.com/visa/abc-123-apply",
            department="Engineering",
            employment_type="full_time",
            location_type="remote",
            experience_level="mid_senior",
            industry="Technology",
            function="Engineering",
            city="London",
            region="Greater London",
            country_code="United Kingdom",
            published_at="2026-01-15T10:00:00Z"
        )
        assert job.location_type == "remote"
        assert job.experience_level == "mid_senior"
        assert job.department == "Engineering"
        assert job.city == "London"

    def test_location_type_values(self):
        """Test different location_type values"""
        for lt in ['remote', 'onsite']:
            job = SmartRecruitersJob(
                id="TEST",
                title="Test",
                company_slug="test",
                location="Test",
                description="Test",
                url="https://test.com",
                apply_url="https://test.com/apply",
                location_type=lt
            )
            assert job.location_type == lt


class TestParseSmartRecruitersJob:
    """Test job parsing from API response"""

    def test_parse_basic_job(self):
        """Test parsing basic job data"""
        raw_data = {
            "id": "uuid-001",
            "name": "Product Manager",
            "location": {
                "city": "New York",
                "region": "NY",
                "country": "US",
                "remote": False
            },
            "jobAd": {
                "sections": {
                    "jobDescription": {"text": "Lead product development..."},
                    "qualifications": {"text": "5+ years PM experience"}
                }
            },
            "applyUrl": "https://jobs.smartrecruiters.com/visa/uuid-001-apply"
        }
        job = parse_smartrecruiters_job(raw_data, "visa")
        assert job.id == "uuid-001"
        assert job.title == "Product Manager"
        assert job.location == "New York, NY, US"
        assert job.location_type == "onsite"
        assert "Lead product development" in job.description

    def test_parse_with_nested_location(self):
        """Test parsing job with nested location object"""
        raw_data = {
            "id": "uuid-002",
            "name": "Data Analyst",
            "location": {
                "city": "London",
                "region": "Greater London",
                "country": "United Kingdom",
                "remote": True
            }
        }
        job = parse_smartrecruiters_job(raw_data, "acme")
        assert job.location == "London, Greater London, United Kingdom"
        assert job.location_type == "remote"
        assert job.city == "London"
        assert job.country_code == "United Kingdom"

    def test_parse_with_department_and_experience(self):
        """Test parsing job with department and experience_level"""
        raw_data = {
            "id": "uuid-003",
            "name": "Senior Engineer",
            "location": {"city": "SF", "remote": False},
            "department": {"id": "eng", "label": "Engineering"},
            "experienceLevel": {"id": "mid_senior", "label": "Mid-Senior Level"},
            "typeOfEmployment": {"id": "full_time", "label": "Full-time"}
        }
        job = parse_smartrecruiters_job(raw_data, "company")
        assert job.department == "Engineering"
        assert job.experience_level == "mid_senior"
        assert job.employment_type == "full_time"

    def test_parse_with_jobad_description_sections(self):
        """Test parsing jobAd with multiple description sections"""
        raw_data = {
            "id": "uuid-004",
            "name": "ML Engineer",
            "location": {},
            "jobAd": {
                "sections": {
                    "jobDescription": {"text": "Build ML models."},
                    "qualifications": {"text": "Python, TensorFlow."},
                    "additionalInformation": {"text": "Remote-friendly."},
                    "companyDescription": {"text": "We are a startup."}
                }
            }
        }
        job = parse_smartrecruiters_job(raw_data, "startup")
        assert "Build ML models" in job.description
        assert "Python, TensorFlow" in job.description
        assert "Remote-friendly" in job.description
        assert "We are a startup" in job.description

    def test_parse_empty_fields(self):
        """Test parsing job with empty/null fields"""
        raw_data = {
            "id": "uuid-005",
            "name": "Test Role",
            "location": None
        }
        job = parse_smartrecruiters_job(raw_data, "test")
        assert job.id == "uuid-005"
        assert job.location == ""
        assert job.description == ""
        assert job.location_type == "onsite"

    def test_parse_url_construction(self):
        """Test that URLs are correctly constructed"""
        raw_data = {
            "id": "uuid-006",
            "name": "Analyst",
            "location": {}
        }
        job = parse_smartrecruiters_job(raw_data, "mycompany")
        assert job.url == "https://jobs.smartrecruiters.com/mycompany/uuid-006"

    def test_parse_with_released_date(self):
        """Test parsing job with releasedDate"""
        raw_data = {
            "id": "uuid-007",
            "name": "PM",
            "location": {},
            "releasedDate": "2026-01-20T08:00:00Z"
        }
        job = parse_smartrecruiters_job(raw_data, "co")
        assert job.published_at == "2026-01-20T08:00:00Z"


class TestLoadCompanyMapping:
    """Test company mapping loading"""

    def test_load_mapping(self):
        """Test loading company mapping from config"""
        mapping = load_company_mapping()
        assert 'smartrecruiters' in mapping

    def test_mapping_has_meta(self):
        """Test mapping has _meta section"""
        mapping = load_company_mapping()
        assert '_meta' in mapping


class TestCheckCompanyExists:
    """Test company existence check"""

    @patch('scrapers.smartrecruiters.smartrecruiters_fetcher.requests.get')
    def test_company_exists(self, mock_get):
        """Test checking existing company"""
        mock_get.return_value.status_code = 200
        assert check_company_exists("visa") is True

    @patch('scrapers.smartrecruiters.smartrecruiters_fetcher.requests.get')
    def test_company_not_found(self, mock_get):
        """Test checking non-existent company"""
        mock_get.return_value.status_code = 404
        assert check_company_exists("nonexistent") is False

    @patch('scrapers.smartrecruiters.smartrecruiters_fetcher.requests.get')
    def test_company_check_timeout(self, mock_get):
        """Test handling timeout during check"""
        mock_get.side_effect = Exception("Timeout")
        assert check_company_exists("timeout-co") is False


class TestFetchSmartRecruitersJobs:
    """Test fetching jobs from SmartRecruiters API"""

    @patch('scrapers.smartrecruiters.smartrecruiters_fetcher.requests.get')
    @patch('scrapers.smartrecruiters.smartrecruiters_fetcher.time.sleep')
    def test_fetch_jobs_success(self, mock_sleep, mock_get):
        """Test successful job fetch"""
        # First call: list endpoint
        list_response = Mock()
        list_response.status_code = 200
        list_response.json.return_value = {
            "totalFound": 1,
            "offset": 0,
            "limit": 100,
            "content": [
                {
                    "id": "job-001",
                    "name": "Data Analyst",
                    "location": {
                        "city": "London",
                        "country": "UK",
                        "remote": False
                    },
                    "ref": "https://api.smartrecruiters.com/v1/companies/test/postings/job-001"
                }
            ]
        }
        list_response.raise_for_status = Mock()

        # Second call: detail endpoint
        detail_response = Mock()
        detail_response.status_code = 200
        detail_response.json.return_value = {
            "jobAd": {
                "sections": {
                    "jobDescription": {"text": "Analyze data..."}
                }
            },
            "applyUrl": "https://apply.url"
        }

        mock_get.side_effect = [list_response, detail_response]

        jobs, stats = fetch_smartrecruiters_jobs(
            "test", filter_titles=False, filter_locations=False
        )

        assert len(jobs) == 1
        assert jobs[0].id == "job-001"
        assert jobs[0].title == "Data Analyst"
        assert stats['jobs_fetched'] == 1
        assert stats['jobs_kept'] == 1
        assert stats['error'] is None

    @patch('scrapers.smartrecruiters.smartrecruiters_fetcher.requests.get')
    @patch('scrapers.smartrecruiters.smartrecruiters_fetcher.time.sleep')
    def test_fetch_jobs_not_found(self, mock_sleep, mock_get):
        """Test handling 404 response"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        jobs, stats = fetch_smartrecruiters_jobs("nonexistent")

        assert len(jobs) == 0
        assert stats['error'] == 'Company not found'

    @patch('scrapers.smartrecruiters.smartrecruiters_fetcher.requests.get')
    @patch('scrapers.smartrecruiters.smartrecruiters_fetcher.time.sleep')
    def test_fetch_jobs_rate_limited(self, mock_sleep, mock_get):
        """Test handling 429 rate limit response"""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        jobs, stats = fetch_smartrecruiters_jobs("rate-limited")

        assert len(jobs) == 0
        assert stats['error'] == 'Rate limited'

    @patch('scrapers.smartrecruiters.smartrecruiters_fetcher.requests.get')
    @patch('scrapers.smartrecruiters.smartrecruiters_fetcher.time.sleep')
    def test_fetch_jobs_timeout(self, mock_sleep, mock_get):
        """Test handling timeout"""
        mock_get.side_effect = requests.exceptions.Timeout()

        jobs, stats = fetch_smartrecruiters_jobs("timeout-co")

        assert len(jobs) == 0
        assert stats['error'] == 'Timeout'

    @patch('scrapers.smartrecruiters.smartrecruiters_fetcher.requests.get')
    @patch('scrapers.smartrecruiters.smartrecruiters_fetcher.time.sleep')
    def test_fetch_jobs_pagination(self, mock_sleep, mock_get):
        """Test pagination across multiple pages"""
        # Page 1
        page1_response = Mock()
        page1_response.status_code = 200
        page1_response.json.return_value = {
            "totalFound": 150,
            "offset": 0,
            "limit": 100,
            "content": [
                {"id": f"job-{i}", "name": f"Job {i}", "location": {}}
                for i in range(100)
            ]
        }
        page1_response.raise_for_status = Mock()

        # Page 2
        page2_response = Mock()
        page2_response.status_code = 200
        page2_response.json.return_value = {
            "totalFound": 150,
            "offset": 100,
            "limit": 100,
            "content": [
                {"id": f"job-{i}", "name": f"Job {i}", "location": {}}
                for i in range(100, 150)
            ]
        }
        page2_response.raise_for_status = Mock()

        mock_get.side_effect = [page1_response, page2_response]

        jobs, stats = fetch_smartrecruiters_jobs(
            "big-company", filter_titles=False, filter_locations=False
        )

        assert stats['jobs_fetched'] == 150
        assert len(jobs) == 150


class TestApiUrl:
    """Test API URL configuration"""

    def test_api_url_format(self):
        """Test API URL is correctly formatted"""
        assert SMARTRECRUITERS_API_URL == "https://api.smartrecruiters.com/v1/companies"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
