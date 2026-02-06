"""
Test Lever fetcher module

All HTTP calls mocked. Tests dataclass, HTML stripping, job parsing, and fetch behavior.

Tests:
1. LeverJob dataclass structure
2. strip_html() utility
3. Job parsing from API response
4. Fetch jobs (success, 404, timeout, EU endpoint)
5. Company mapping loading
"""

import sys
from pathlib import Path
from unittest.mock import patch, Mock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.lever.lever_fetcher import (
    LeverJob,
    strip_html,
    build_full_description,
    parse_lever_job,
    fetch_lever_jobs,
    load_company_mapping,
    LEVER_API_URLS,
)


class TestLeverJobDataclass:
    """Test LeverJob dataclass"""

    def test_minimal_job(self):
        """Test creating job with minimal required fields"""
        job = LeverJob(
            id="abc-123",
            title="Data Engineer",
            company_slug="spotify",
            location="London, UK",
            description="Build data pipelines...",
            url="https://jobs.lever.co/spotify/abc-123",
            apply_url="https://jobs.lever.co/spotify/abc-123/apply"
        )
        assert job.id == "abc-123"
        assert job.title == "Data Engineer"
        assert job.company_slug == "spotify"
        assert job.team is None
        assert job.workplace_type is None
        assert job.instance == "global"

    def test_full_job(self):
        """Test creating job with all fields"""
        job = LeverJob(
            id="abc-123",
            title="Senior Data Engineer",
            company_slug="spotify",
            location="London, UK / Berlin, DE",
            description="Build data pipelines...",
            url="https://jobs.lever.co/spotify/abc-123",
            apply_url="https://jobs.lever.co/spotify/abc-123/apply",
            team="Data Platform",
            department="Engineering",
            commitment="Full-time",
            workplace_type="hybrid",
            instance="global"
        )
        assert job.workplace_type == "hybrid"
        assert job.team == "Data Platform"
        assert job.commitment == "Full-time"
        assert job.department == "Engineering"

    def test_eu_instance(self):
        """Test creating job with EU instance"""
        job = LeverJob(
            id="eu-001",
            title="Analyst",
            company_slug="eu-company",
            location="Paris",
            description="Analytics role...",
            url="https://jobs.eu.lever.co/eu-company/eu-001",
            apply_url="https://jobs.eu.lever.co/eu-company/eu-001/apply",
            instance="eu"
        )
        assert job.instance == "eu"


class TestStripHtml:
    """Test HTML stripping utility"""

    def test_basic_tags(self):
        """Test stripping basic HTML tags"""
        result = strip_html("<p>Hello world</p>")
        assert "Hello world" in result
        assert "<p>" not in result

    def test_html_entities(self):
        """Test decoding HTML entities"""
        result = strip_html("AT&amp;T &lt;company&gt;")
        assert "AT&T" in result
        assert "<company>" in result

    def test_nested_tags(self):
        """Test stripping nested HTML tags"""
        result = strip_html("<div><p><strong>Bold</strong> text</p></div>")
        assert "Bold" in result
        assert "text" in result
        assert "<" not in result

    def test_empty_string(self):
        """Test empty string returns empty"""
        assert strip_html("") == ""

    def test_none_returns_empty(self):
        """Test None returns empty string"""
        assert strip_html(None) == ""

    def test_whitespace_normalization(self):
        """Test whitespace is normalized"""
        result = strip_html("<p>Hello</p>  <p>World</p>")
        # Should not have excessive whitespace
        assert "  " not in result or result.count("  ") == 0


class TestBuildFullDescription:
    """Test building full description from Lever fields"""

    def test_basic_description(self):
        """Test building description from descriptionPlain"""
        job_data = {
            "descriptionPlain": "We are looking for a Data Engineer."
        }
        result = build_full_description(job_data)
        assert "We are looking for a Data Engineer" in result

    def test_with_lists(self):
        """Test including lists (Responsibilities, Requirements)"""
        job_data = {
            "descriptionPlain": "Main description.",
            "lists": [
                {
                    "text": "Requirements",
                    "content": "<li>Python</li><li>SQL</li>"
                }
            ]
        }
        result = build_full_description(job_data)
        assert "Main description" in result
        assert "Requirements" in result
        assert "Python" in result

    def test_with_additional(self):
        """Test including additional info"""
        job_data = {
            "descriptionPlain": "Main description.",
            "additional": "<p>We offer great benefits.</p>"
        }
        result = build_full_description(job_data)
        assert "Main description" in result
        assert "great benefits" in result


class TestParseLeverJob:
    """Test job parsing from API response"""

    def test_parse_basic_job(self):
        """Test parsing basic Lever job data"""
        raw_data = {
            "id": "lever-001",
            "text": "Product Manager",
            "hostedUrl": "https://jobs.lever.co/company/lever-001",
            "applyUrl": "https://jobs.lever.co/company/lever-001/apply",
            "descriptionPlain": "Lead product development...",
            "categories": {
                "location": "New York, NY",
                "team": "Product",
                "department": "Engineering",
                "commitment": "Full-time"
            }
        }
        job = parse_lever_job(raw_data, "company")
        assert job.id == "lever-001"
        assert job.title == "Product Manager"
        assert job.location == "New York, NY"
        assert job.team == "Product"
        assert job.department == "Engineering"
        assert job.commitment == "Full-time"

    def test_parse_with_all_locations(self):
        """Test parsing job with allLocations in categories"""
        raw_data = {
            "id": "lever-002",
            "text": "Engineer",
            "hostedUrl": "https://jobs.lever.co/company/lever-002",
            "applyUrl": "https://jobs.lever.co/company/lever-002/apply",
            "descriptionPlain": "Engineering role...",
            "categories": {
                "location": "New York",
                "allLocations": ["New York", "San Francisco", "London"]
            }
        }
        job = parse_lever_job(raw_data, "company")
        assert "New York" in job.location
        assert "San Francisco" in job.location
        assert "London" in job.location

    def test_parse_with_workplace_type(self):
        """Test parsing job with workplaceType"""
        raw_data = {
            "id": "lever-003",
            "text": "Remote Engineer",
            "hostedUrl": "https://jobs.lever.co/company/lever-003",
            "applyUrl": "https://jobs.lever.co/company/lever-003/apply",
            "descriptionPlain": "Remote role...",
            "workplaceType": "remote",
            "categories": {"location": "Remote"}
        }
        job = parse_lever_job(raw_data, "company")
        assert job.workplace_type == "remote"

    def test_parse_empty_categories(self):
        """Test parsing job with empty categories"""
        raw_data = {
            "id": "lever-004",
            "text": "Role",
            "hostedUrl": "https://jobs.lever.co/company/lever-004",
            "applyUrl": "https://jobs.lever.co/company/lever-004/apply",
            "descriptionPlain": "Description...",
            "categories": {}
        }
        job = parse_lever_job(raw_data, "company")
        assert job.location == ""
        assert job.team is None

    def test_parse_eu_instance(self):
        """Test parsing with EU instance"""
        raw_data = {
            "id": "eu-001",
            "text": "EU Role",
            "hostedUrl": "https://jobs.eu.lever.co/company/eu-001",
            "applyUrl": "https://jobs.eu.lever.co/company/eu-001/apply",
            "descriptionPlain": "EU role...",
            "categories": {"location": "Berlin"}
        }
        job = parse_lever_job(raw_data, "company", instance="eu")
        assert job.instance == "eu"


class TestLoadCompanyMapping:
    """Test company mapping loading"""

    def test_load_mapping(self):
        """Test loading company mapping from config"""
        mapping = load_company_mapping()
        assert 'lever' in mapping

    def test_mapping_has_companies(self):
        """Test mapping has company entries"""
        mapping = load_company_mapping()
        lever = mapping.get('lever', {})
        assert len(lever) > 0


class TestFetchLeverJobs:
    """Test fetching jobs from Lever API"""

    @patch('scrapers.lever.lever_fetcher.requests.get')
    @patch('scrapers.lever.lever_fetcher.time.sleep')
    def test_fetch_jobs_success(self, mock_sleep, mock_get):
        """Test successful job fetch"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "lever-001",
                "text": "Data Analyst",
                "hostedUrl": "https://jobs.lever.co/test/lever-001",
                "applyUrl": "https://jobs.lever.co/test/lever-001/apply",
                "descriptionPlain": "Analyze data...",
                "categories": {
                    "location": "London, UK",
                    "team": "Analytics"
                }
            }
        ]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        jobs, stats = fetch_lever_jobs(
            "test", filter_titles=False, filter_locations=False
        )

        assert len(jobs) == 1
        assert jobs[0].id == "lever-001"
        assert jobs[0].title == "Data Analyst"
        assert stats['jobs_fetched'] == 1
        assert stats['jobs_kept'] == 1
        assert stats['error'] is None

    @patch('scrapers.lever.lever_fetcher.requests.get')
    @patch('scrapers.lever.lever_fetcher.time.sleep')
    def test_fetch_jobs_not_found(self, mock_sleep, mock_get):
        """Test handling 404 response"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        jobs, stats = fetch_lever_jobs("nonexistent")

        assert len(jobs) == 0
        assert stats['error'] == 'Site not found'

    @patch('scrapers.lever.lever_fetcher.requests.get')
    @patch('scrapers.lever.lever_fetcher.time.sleep')
    def test_fetch_jobs_timeout(self, mock_sleep, mock_get):
        """Test handling timeout"""
        mock_get.side_effect = requests.exceptions.Timeout()

        jobs, stats = fetch_lever_jobs("timeout-co")

        assert len(jobs) == 0
        assert stats['error'] == 'Timeout'

    @patch('scrapers.lever.lever_fetcher.requests.get')
    @patch('scrapers.lever.lever_fetcher.time.sleep')
    def test_fetch_jobs_eu_endpoint(self, mock_sleep, mock_get):
        """Test EU endpoint selection"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        fetch_lever_jobs("eu-company", instance="eu", filter_titles=False, filter_locations=False)

        # Verify EU URL was used
        call_url = mock_get.call_args[0][0]
        assert "eu.lever.co" in call_url

    @patch('scrapers.lever.lever_fetcher.requests.get')
    @patch('scrapers.lever.lever_fetcher.time.sleep')
    def test_fetch_jobs_invalid_json(self, mock_sleep, mock_get):
        """Test handling invalid JSON response"""
        import json
        mock_get.side_effect = json.JSONDecodeError("", "", 0)

        jobs, stats = fetch_lever_jobs("bad-json")

        assert len(jobs) == 0
        assert stats['error'] == 'Invalid JSON'


class TestLeverApiUrls:
    """Test API URL configuration"""

    def test_global_url(self):
        """Test global API URL"""
        assert LEVER_API_URLS['global'] == "https://api.lever.co/v0/postings"

    def test_eu_url(self):
        """Test EU API URL"""
        assert LEVER_API_URLS['eu'] == "https://api.eu.lever.co/v0/postings"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
