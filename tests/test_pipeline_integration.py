"""
Simulated pipeline integration tests for pipeline/fetch_jobs.py

Tests the full per-job orchestration flow for each ATS source with all
external calls mocked (scrapers, classifier, database, agency detection).

Flow tested per source:
    scraper output -> insert_raw_job_upsert -> is_agency_job -> classify_job ->
    validate_agency_classification -> extract_locations -> insert_enriched_job

Run with: pytest tests/test_pipeline_integration.py -v
Cost: $0.00 (all mocked)
"""

import copy
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, ANY

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

MOCK_CLASSIFICATION = {
    "employer": {"department": "data", "is_agency": None, "agency_confidence": None},
    "role": {
        "job_family": "data",
        "job_subfamily": "data_engineer",
        "seniority": "senior",
        "track": "ic",
        "position_type": "full_time",
        "experience_range": "5-8 years",
    },
    "location": {"working_arrangement": "hybrid"},
    "compensation": {
        "currency": "gbp",
        "base_salary_range": {"min": 80000, "max": 110000},
        "equity_eligible": None,
    },
    "skills": [
        {"name": "Python", "family_code": "programming"},
        {"name": "SQL", "family_code": "programming"},
    ],
    "summary": "Build data pipelines using Python and Spark.",
    "_cost_data": {
        "input_tokens": 2500,
        "output_tokens": 400,
        "total_cost": 0.002,
        "provider": "gemini",
    },
}

MOCK_FETCH_STATS = {
    "jobs_fetched": 2,
    "jobs_kept": 2,
    "filtered_by_title": 0,
    "filtered_by_location": 0,
    "error": None,
}


def make_upsert_result(raw_id=1, was_duplicate=False):
    return {
        "id": raw_id,
        "action": "updated" if was_duplicate else "inserted",
        "was_duplicate": was_duplicate,
    }


def _classify_side_effect(*args, **kwargs):
    """Return a fresh deep copy of MOCK_CLASSIFICATION for each call."""
    return copy.deepcopy(MOCK_CLASSIFICATION)


def _classify_unknown_wa(*args, **kwargs):
    """Return classification with working_arrangement='unknown'."""
    c = copy.deepcopy(MOCK_CLASSIFICATION)
    c["location"]["working_arrangement"] = "unknown"
    return c


# ---------------------------------------------------------------------------
# Job factory helpers
# ---------------------------------------------------------------------------

def make_lever_job(**overrides):
    from scrapers.lever.lever_fetcher import LeverJob

    defaults = dict(
        id="lev-1",
        title="Senior Data Engineer",
        company_slug="acme",
        location="London, UK",
        description="Build data pipelines using Python and Spark.",
        url="https://jobs.lever.co/acme/lev-1",
        apply_url="https://jobs.lever.co/acme/lev-1/apply",
        team="Data",
        department="Engineering",
        commitment="Full-time",
        workplace_type="hybrid",
        instance="global",
    )
    defaults.update(overrides)
    return LeverJob(**defaults)


def make_ashby_job(**overrides):
    from scrapers.ashby.ashby_fetcher import AshbyJob

    defaults = dict(
        id="ash-1",
        title="Senior Data Engineer",
        company_slug="acme",
        location="London, UK",
        description="Build data pipelines using Python and Spark.",
        url="https://jobs.ashbyhq.com/acme/ash-1",
        apply_url="https://jobs.ashbyhq.com/acme/ash-1/apply",
        department="Engineering",
        team="Data",
        employment_type="FullTime",
        is_remote=False,
        salary_min=80000,
        salary_max=110000,
        salary_currency="GBP",
        city="London",
        region="England",
        country="GB",
    )
    defaults.update(overrides)
    return AshbyJob(**defaults)


def make_workable_job(**overrides):
    from scrapers.workable.workable_fetcher import WorkableJob

    defaults = dict(
        id="wrk-1",
        title="Senior Data Engineer",
        company_slug="acme",
        location="London, UK",
        description="Build data pipelines using Python and Spark.",
        url="https://apply.workable.com/acme/j/wrk-1/",
        apply_url="https://apply.workable.com/acme/j/wrk-1/apply",
        department="Engineering",
        employment_type="full_time",
        workplace_type="hybrid",
        salary_min=80000,
        salary_max=110000,
        salary_currency="GBP",
        city="London",
        region="England",
        country_code="GB",
    )
    defaults.update(overrides)
    return WorkableJob(**defaults)


def make_smartrecruiters_job(**overrides):
    from scrapers.smartrecruiters.smartrecruiters_fetcher import SmartRecruitersJob

    defaults = dict(
        id="sr-1",
        title="Senior Data Engineer",
        company_slug="acme",
        location="London, UK",
        description="Build data pipelines using Python and Spark.",
        url="https://jobs.smartrecruiters.com/acme/sr-1",
        apply_url="https://jobs.smartrecruiters.com/acme/sr-1-apply",
        department="Engineering",
        employment_type="full_time",
        location_type="onsite",
        experience_level="mid_senior",
        city="London",
        region="England",
        country_code="GB",
    )
    defaults.update(overrides)
    return SmartRecruitersJob(**defaults)


def make_greenhouse_job(**overrides):
    from scrapers.greenhouse.greenhouse_api_fetcher import GreenhouseJob

    defaults = dict(
        id="gh-123",
        title="Senior Data Engineer",
        company_slug="acme",
        location="London, UK",
        description="Build data pipelines using Python and Spark.",
        url="https://boards.greenhouse.io/acme/jobs/123",
    )
    defaults.update(overrides)
    return GreenhouseJob(**defaults)


# ---------------------------------------------------------------------------
# Lever Pipeline Tests
# ---------------------------------------------------------------------------

class TestLeverPipelineIntegration:
    """Test process_lever_incremental() with all external calls mocked."""

    @patch("scrapers.lever.lever_fetcher.load_company_mapping")
    @patch("scrapers.lever.lever_fetcher.fetch_lever_jobs")
    @patch("pipeline.fetch_jobs.extract_locations")
    @patch("pipeline.agency_detection.validate_agency_classification")
    @patch("pipeline.agency_detection.is_agency_job")
    @patch("pipeline.classifier.classify_job")
    @patch("pipeline.db_connection.ensure_employer_metadata")
    @patch("pipeline.db_connection.get_working_arrangement_fallback")
    @patch("pipeline.db_connection.insert_enriched_job")
    @patch("pipeline.db_connection.insert_raw_job_upsert")
    async def test_happy_path(
        self,
        mock_upsert,
        mock_enriched,
        mock_wa_fallback,
        mock_ensure_meta,
        mock_classify,
        mock_is_agency,
        mock_validate_agency,
        mock_extract_loc,
        mock_fetch_lever,
        mock_load_mapping,
    ):
        """2 jobs for 1 company: upsert x2, classify x2, enriched x2."""
        from pipeline.fetch_jobs import process_lever_incremental

        mock_load_mapping.return_value = {
            "lever": {"Acme Corp": {"slug": "acme", "instance": "global"}}
        }
        mock_fetch_lever.return_value = (
            [make_lever_job(id="lev-1"), make_lever_job(id="lev-2", title="ML Engineer")],
            copy.deepcopy(MOCK_FETCH_STATS),
        )
        mock_upsert.side_effect = [
            make_upsert_result(raw_id=1),
            make_upsert_result(raw_id=2),
        ]
        mock_is_agency.return_value = False
        mock_classify.side_effect = _classify_side_effect
        mock_validate_agency.return_value = (False, "low")
        mock_extract_loc.return_value = [{"type": "city", "country_code": "GB", "city": "london"}]
        mock_wa_fallback.return_value = None
        mock_enriched.side_effect = [101, 102]

        stats = await process_lever_incremental(companies=["acme"])

        assert mock_upsert.call_count == 2
        assert mock_classify.call_count == 2
        assert mock_enriched.call_count == 2
        assert stats["companies_processed"] == 1
        assert stats["companies_with_jobs"] == 1
        assert stats["jobs_classified"] == 2
        assert stats["jobs_written_enriched"] == 2

        # Verify classifier was called with correct source
        call_kwargs = mock_classify.call_args_list[0]
        assert call_kwargs.kwargs.get("source") == "lever"

    @patch("scrapers.lever.lever_fetcher.load_company_mapping")
    @patch("scrapers.lever.lever_fetcher.fetch_lever_jobs")
    @patch("pipeline.fetch_jobs.extract_locations")
    @patch("pipeline.agency_detection.validate_agency_classification")
    @patch("pipeline.agency_detection.is_agency_job")
    @patch("pipeline.classifier.classify_job")
    @patch("pipeline.db_connection.ensure_employer_metadata")
    @patch("pipeline.db_connection.get_working_arrangement_fallback")
    @patch("pipeline.db_connection.insert_enriched_job")
    @patch("pipeline.db_connection.insert_raw_job_upsert")
    async def test_duplicate_skips_classification(
        self,
        mock_upsert,
        mock_enriched,
        mock_wa_fallback,
        mock_ensure_meta,
        mock_classify,
        mock_is_agency,
        mock_validate_agency,
        mock_extract_loc,
        mock_fetch_lever,
        mock_load_mapping,
    ):
        """Duplicate job should skip classification entirely."""
        from pipeline.fetch_jobs import process_lever_incremental

        mock_load_mapping.return_value = {
            "lever": {"Acme Corp": {"slug": "acme", "instance": "global"}}
        }
        mock_fetch_lever.return_value = (
            [make_lever_job()],
            copy.deepcopy(MOCK_FETCH_STATS),
        )
        mock_upsert.return_value = make_upsert_result(was_duplicate=True)

        stats = await process_lever_incremental(companies=["acme"])

        assert mock_classify.call_count == 0
        assert mock_enriched.call_count == 0
        assert stats["jobs_duplicate"] == 1

    @patch("scrapers.lever.lever_fetcher.load_company_mapping")
    @patch("scrapers.lever.lever_fetcher.fetch_lever_jobs")
    @patch("pipeline.fetch_jobs.extract_locations")
    @patch("pipeline.agency_detection.validate_agency_classification")
    @patch("pipeline.agency_detection.is_agency_job")
    @patch("pipeline.classifier.classify_job")
    @patch("pipeline.db_connection.ensure_employer_metadata")
    @patch("pipeline.db_connection.get_working_arrangement_fallback")
    @patch("pipeline.db_connection.insert_enriched_job")
    @patch("pipeline.db_connection.insert_raw_job_upsert")
    async def test_agency_hard_filter(
        self,
        mock_upsert,
        mock_enriched,
        mock_wa_fallback,
        mock_ensure_meta,
        mock_classify,
        mock_is_agency,
        mock_validate_agency,
        mock_extract_loc,
        mock_fetch_lever,
        mock_load_mapping,
    ):
        """Hard agency filter should skip classification."""
        from pipeline.fetch_jobs import process_lever_incremental

        mock_load_mapping.return_value = {
            "lever": {"Acme Corp": {"slug": "acme", "instance": "global"}}
        }
        mock_fetch_lever.return_value = (
            [make_lever_job()],
            copy.deepcopy(MOCK_FETCH_STATS),
        )
        mock_upsert.return_value = make_upsert_result()
        mock_is_agency.return_value = True

        stats = await process_lever_incremental(companies=["acme"])

        assert mock_classify.call_count == 0
        assert mock_enriched.call_count == 0
        assert stats["jobs_agency_filtered"] == 1

    @patch("scrapers.lever.lever_fetcher.load_company_mapping")
    @patch("scrapers.lever.lever_fetcher.fetch_lever_jobs")
    @patch("pipeline.fetch_jobs.extract_locations")
    @patch("pipeline.agency_detection.validate_agency_classification")
    @patch("pipeline.agency_detection.is_agency_job")
    @patch("pipeline.classifier.classify_job")
    @patch("pipeline.db_connection.ensure_employer_metadata")
    @patch("pipeline.db_connection.get_working_arrangement_fallback")
    @patch("pipeline.db_connection.insert_enriched_job")
    @patch("pipeline.db_connection.insert_raw_job_upsert")
    async def test_classification_failure_continues(
        self,
        mock_upsert,
        mock_enriched,
        mock_wa_fallback,
        mock_ensure_meta,
        mock_classify,
        mock_is_agency,
        mock_validate_agency,
        mock_extract_loc,
        mock_fetch_lever,
        mock_load_mapping,
    ):
        """Classification failure should not crash the pipeline."""
        from pipeline.fetch_jobs import process_lever_incremental

        mock_load_mapping.return_value = {
            "lever": {"Acme Corp": {"slug": "acme", "instance": "global"}}
        }
        mock_fetch_lever.return_value = (
            [make_lever_job()],
            copy.deepcopy(MOCK_FETCH_STATS),
        )
        mock_upsert.return_value = make_upsert_result()
        mock_is_agency.return_value = False
        mock_classify.side_effect = Exception("LLM API timeout")

        stats = await process_lever_incremental(companies=["acme"])

        assert mock_classify.call_count == 1
        assert mock_enriched.call_count == 0
        assert stats["jobs_written_enriched"] == 0

    @patch("pipeline.fetch_jobs.get_recently_processed_companies")
    @patch("scrapers.lever.lever_fetcher.load_company_mapping")
    @patch("scrapers.lever.lever_fetcher.fetch_lever_jobs")
    @patch("pipeline.fetch_jobs.extract_locations")
    @patch("pipeline.agency_detection.validate_agency_classification")
    @patch("pipeline.agency_detection.is_agency_job")
    @patch("pipeline.classifier.classify_job")
    @patch("pipeline.db_connection.ensure_employer_metadata")
    @patch("pipeline.db_connection.get_working_arrangement_fallback")
    @patch("pipeline.db_connection.insert_enriched_job")
    @patch("pipeline.db_connection.insert_raw_job_upsert")
    async def test_resume_skips_companies(
        self,
        mock_upsert,
        mock_enriched,
        mock_wa_fallback,
        mock_ensure_meta,
        mock_classify,
        mock_is_agency,
        mock_validate_agency,
        mock_extract_loc,
        mock_fetch_lever,
        mock_load_mapping,
        mock_get_recent,
    ):
        """Resume mode should skip recently processed companies."""
        from pipeline.fetch_jobs import process_lever_incremental

        mock_load_mapping.return_value = {
            "lever": {
                "Acme Corp": {"slug": "acme", "instance": "global"},
                "Beta Inc": {"slug": "beta", "instance": "global"},
            }
        }
        mock_get_recent.return_value = {"acme"}
        mock_fetch_lever.return_value = (
            [make_lever_job(company_slug="beta")],
            copy.deepcopy(MOCK_FETCH_STATS),
        )
        mock_upsert.return_value = make_upsert_result()
        mock_is_agency.return_value = False
        mock_classify.side_effect = _classify_side_effect
        mock_validate_agency.return_value = (False, "low")
        mock_extract_loc.return_value = [{"type": "city", "country_code": "GB", "city": "london"}]
        mock_wa_fallback.return_value = None
        mock_enriched.return_value = 101

        stats = await process_lever_incremental(resume_hours=24)

        assert stats["companies_skipped"] == 1
        # Only beta should have been fetched
        assert mock_fetch_lever.call_count == 1


# ---------------------------------------------------------------------------
# Ashby Pipeline Tests
# ---------------------------------------------------------------------------

class TestAshbyPipelineIntegration:
    """Test process_ashby_incremental() -- salary pass-through and is_remote."""

    @patch("scrapers.ashby.ashby_fetcher.load_company_mapping")
    @patch("scrapers.ashby.ashby_fetcher.fetch_ashby_jobs")
    @patch("pipeline.fetch_jobs.extract_locations")
    @patch("pipeline.agency_detection.validate_agency_classification")
    @patch("pipeline.agency_detection.is_agency_job")
    @patch("pipeline.classifier.classify_job")
    @patch("pipeline.db_connection.ensure_employer_metadata")
    @patch("pipeline.db_connection.get_working_arrangement_fallback")
    @patch("pipeline.db_connection.insert_enriched_job")
    @patch("pipeline.db_connection.insert_raw_job_upsert")
    async def test_salary_passthrough(
        self,
        mock_upsert,
        mock_enriched,
        mock_wa_fallback,
        mock_ensure_meta,
        mock_classify,
        mock_is_agency,
        mock_validate_agency,
        mock_extract_loc,
        mock_fetch_ashby,
        mock_load_mapping,
    ):
        """Ashby salary_min/max should be passed to classifier and prioritized in enriched insert."""
        from pipeline.fetch_jobs import process_ashby_incremental

        mock_load_mapping.return_value = {
            "ashby": {"Acme Corp": {"slug": "acme"}}
        }
        mock_fetch_ashby.return_value = (
            [make_ashby_job(salary_min=90000, salary_max=120000, salary_currency="GBP")],
            copy.deepcopy(MOCK_FETCH_STATS),
        )
        mock_upsert.return_value = make_upsert_result()
        mock_is_agency.return_value = False
        mock_classify.side_effect = _classify_side_effect
        mock_validate_agency.return_value = (False, "low")
        mock_extract_loc.return_value = [{"type": "city", "country_code": "GB", "city": "london"}]
        mock_wa_fallback.return_value = None
        mock_enriched.return_value = 101

        stats = await process_ashby_incremental(companies=["acme"])

        # Verify salary passed to classifier
        classify_call = mock_classify.call_args
        structured = classify_call.kwargs.get("structured_input")
        assert structured["salary_min"] == 90000
        assert structured["salary_max"] == 120000

        # Verify salary suppressed for London (no pay transparency laws)
        enriched_call = mock_enriched.call_args
        assert enriched_call.kwargs["salary_min"] is None
        assert enriched_call.kwargs["salary_max"] is None
        assert enriched_call.kwargs["currency"] is None

    @patch("scrapers.ashby.ashby_fetcher.load_company_mapping")
    @patch("scrapers.ashby.ashby_fetcher.fetch_ashby_jobs")
    @patch("pipeline.fetch_jobs.extract_locations")
    @patch("pipeline.agency_detection.validate_agency_classification")
    @patch("pipeline.agency_detection.is_agency_job")
    @patch("pipeline.classifier.classify_job")
    @patch("pipeline.db_connection.ensure_employer_metadata")
    @patch("pipeline.db_connection.get_working_arrangement_fallback")
    @patch("pipeline.db_connection.insert_enriched_job")
    @patch("pipeline.db_connection.insert_raw_job_upsert")
    async def test_is_remote_working_arrangement(
        self,
        mock_upsert,
        mock_enriched,
        mock_wa_fallback,
        mock_ensure_meta,
        mock_classify,
        mock_is_agency,
        mock_validate_agency,
        mock_extract_loc,
        mock_fetch_ashby,
        mock_load_mapping,
    ):
        """is_remote=True + classifier WA=unknown -> working_arrangement='remote'."""
        from pipeline.fetch_jobs import process_ashby_incremental

        mock_load_mapping.return_value = {
            "ashby": {"Acme Corp": {"slug": "acme"}}
        }
        mock_fetch_ashby.return_value = (
            [make_ashby_job(is_remote=True)],
            copy.deepcopy(MOCK_FETCH_STATS),
        )
        mock_upsert.return_value = make_upsert_result()
        mock_is_agency.return_value = False
        mock_classify.side_effect = _classify_unknown_wa
        mock_validate_agency.return_value = (False, "low")
        mock_extract_loc.return_value = [{"type": "remote", "scope": "global"}]
        mock_wa_fallback.return_value = None
        mock_enriched.return_value = 101

        await process_ashby_incremental(companies=["acme"])

        enriched_call = mock_enriched.call_args
        assert enriched_call.kwargs["working_arrangement"] == "remote"


# ---------------------------------------------------------------------------
# SmartRecruiters Pipeline Tests
# ---------------------------------------------------------------------------

class TestSmartRecruitersPipelineIntegration:
    """Test process_smartrecruiters_incremental() -- experience_level and location_type."""

    @patch("scrapers.smartrecruiters.smartrecruiters_fetcher.load_company_mapping")
    @patch("scrapers.smartrecruiters.smartrecruiters_fetcher.fetch_smartrecruiters_jobs")
    @patch("pipeline.fetch_jobs.extract_locations")
    @patch("pipeline.agency_detection.validate_agency_classification")
    @patch("pipeline.agency_detection.is_agency_job")
    @patch("pipeline.classifier.classify_job")
    @patch("pipeline.db_connection.ensure_employer_metadata")
    @patch("pipeline.db_connection.get_working_arrangement_fallback")
    @patch("pipeline.db_connection.insert_enriched_job")
    @patch("pipeline.db_connection.insert_raw_job_upsert")
    async def test_experience_level_hint(
        self,
        mock_upsert,
        mock_enriched,
        mock_wa_fallback,
        mock_ensure_meta,
        mock_classify,
        mock_is_agency,
        mock_validate_agency,
        mock_extract_loc,
        mock_fetch_sr,
        mock_load_mapping,
    ):
        """experience_level should be passed as hint to classifier."""
        from pipeline.fetch_jobs import process_smartrecruiters_incremental

        mock_load_mapping.return_value = {
            "smartrecruiters": {"Acme Corp": {"slug": "acme"}},
            "_meta": {"last_updated": "2026-01-01"},
        }
        mock_fetch_sr.return_value = (
            [make_smartrecruiters_job(experience_level="mid_senior")],
            copy.deepcopy(MOCK_FETCH_STATS),
        )
        mock_upsert.return_value = make_upsert_result()
        mock_is_agency.return_value = False
        mock_classify.side_effect = _classify_side_effect
        mock_validate_agency.return_value = (False, "low")
        mock_extract_loc.return_value = [{"type": "city", "country_code": "GB", "city": "london"}]
        mock_wa_fallback.return_value = None
        mock_enriched.return_value = 101

        await process_smartrecruiters_incremental(companies=["acme"])

        # Verify experience_level_hint passed to classifier
        classify_call = mock_classify.call_args
        structured = classify_call.kwargs.get("structured_input")
        assert structured.get("experience_level_hint") == "mid_senior"

    @patch("scrapers.smartrecruiters.smartrecruiters_fetcher.load_company_mapping")
    @patch("scrapers.smartrecruiters.smartrecruiters_fetcher.fetch_smartrecruiters_jobs")
    @patch("pipeline.fetch_jobs.extract_locations")
    @patch("pipeline.agency_detection.validate_agency_classification")
    @patch("pipeline.agency_detection.is_agency_job")
    @patch("pipeline.classifier.classify_job")
    @patch("pipeline.db_connection.ensure_employer_metadata")
    @patch("pipeline.db_connection.get_working_arrangement_fallback")
    @patch("pipeline.db_connection.insert_enriched_job")
    @patch("pipeline.db_connection.insert_raw_job_upsert")
    async def test_location_type_remote(
        self,
        mock_upsert,
        mock_enriched,
        mock_wa_fallback,
        mock_ensure_meta,
        mock_classify,
        mock_is_agency,
        mock_validate_agency,
        mock_extract_loc,
        mock_fetch_sr,
        mock_load_mapping,
    ):
        """location_type='remote' + classifier WA=unknown -> working_arrangement='remote'."""
        from pipeline.fetch_jobs import process_smartrecruiters_incremental

        mock_load_mapping.return_value = {
            "smartrecruiters": {"Acme Corp": {"slug": "acme"}},
            "_meta": {"last_updated": "2026-01-01"},
        }
        mock_fetch_sr.return_value = (
            [make_smartrecruiters_job(location_type="remote")],
            copy.deepcopy(MOCK_FETCH_STATS),
        )
        mock_upsert.return_value = make_upsert_result()
        mock_is_agency.return_value = False
        mock_classify.side_effect = _classify_unknown_wa
        mock_validate_agency.return_value = (False, "low")
        mock_extract_loc.return_value = [{"type": "remote", "scope": "global"}]
        mock_wa_fallback.return_value = None
        mock_enriched.return_value = 101

        await process_smartrecruiters_incremental(companies=["acme"])

        enriched_call = mock_enriched.call_args
        assert enriched_call.kwargs["working_arrangement"] == "remote"


# ---------------------------------------------------------------------------
# Workable Pipeline Tests
# ---------------------------------------------------------------------------

class TestWorkablePipelineIntegration:
    """Test process_workable_incremental() -- workplace_type pass-through."""

    @patch("scrapers.workable.workable_fetcher.load_company_mapping")
    @patch("scrapers.workable.workable_fetcher.fetch_workable_jobs")
    @patch("pipeline.fetch_jobs.extract_locations")
    @patch("pipeline.agency_detection.validate_agency_classification")
    @patch("pipeline.agency_detection.is_agency_job")
    @patch("pipeline.classifier.classify_job")
    @patch("pipeline.db_connection.ensure_employer_metadata")
    @patch("pipeline.db_connection.get_working_arrangement_fallback")
    @patch("pipeline.db_connection.insert_enriched_job")
    @patch("pipeline.db_connection.insert_raw_job_upsert")
    async def test_workplace_type_remote(
        self,
        mock_upsert,
        mock_enriched,
        mock_wa_fallback,
        mock_ensure_meta,
        mock_classify,
        mock_is_agency,
        mock_validate_agency,
        mock_extract_loc,
        mock_fetch_workable,
        mock_load_mapping,
    ):
        """workplace_type='remote' + classifier WA=unknown -> working_arrangement='remote'."""
        from pipeline.fetch_jobs import process_workable_incremental

        mock_load_mapping.return_value = {
            "workable": {"Acme Corp": {"slug": "acme"}},
            "_meta": {"last_updated": "2026-01-01"},
        }
        mock_fetch_workable.return_value = (
            [make_workable_job(workplace_type="remote")],
            copy.deepcopy(MOCK_FETCH_STATS),
        )
        mock_upsert.return_value = make_upsert_result()
        mock_is_agency.return_value = False
        mock_classify.side_effect = _classify_unknown_wa
        mock_validate_agency.return_value = (False, "low")
        mock_extract_loc.return_value = [{"type": "remote", "scope": "global"}]
        mock_wa_fallback.return_value = None
        mock_enriched.return_value = 101

        await process_workable_incremental(companies=["acme"])

        enriched_call = mock_enriched.call_args
        assert enriched_call.kwargs["working_arrangement"] == "remote"


# ---------------------------------------------------------------------------
# Greenhouse Pipeline Tests
# ---------------------------------------------------------------------------

class TestGreenhousePipelineIntegration:
    """Test process_greenhouse_incremental() -- API-based pattern (same as Ashby/Lever)."""

    @patch("scrapers.greenhouse.greenhouse_api_fetcher.load_company_mapping")
    @patch("scrapers.greenhouse.greenhouse_api_fetcher.fetch_greenhouse_jobs")
    @patch("pipeline.fetch_jobs.extract_locations")
    @patch("pipeline.agency_detection.validate_agency_classification")
    @patch("pipeline.agency_detection.is_agency_job")
    @patch("pipeline.classifier.classify_job")
    @patch("pipeline.db_connection.ensure_employer_metadata")
    @patch("pipeline.db_connection.get_working_arrangement_fallback")
    @patch("pipeline.db_connection.insert_enriched_job")
    @patch("pipeline.db_connection.insert_raw_job_upsert")
    async def test_happy_path(
        self,
        mock_upsert,
        mock_enriched,
        mock_wa_fallback,
        mock_ensure_meta,
        mock_classify,
        mock_is_agency,
        mock_validate_agency,
        mock_extract_loc,
        mock_fetch_gh,
        mock_load_mapping,
    ):
        """2 jobs for 1 company: upsert x2, classify x2, enriched x2."""
        from pipeline.fetch_jobs import process_greenhouse_incremental

        mock_load_mapping.return_value = {
            "greenhouse": {"Acme Corp": {"slug": "acme"}}
        }
        mock_fetch_gh.return_value = (
            [make_greenhouse_job(id="gh-1"), make_greenhouse_job(id="gh-2", title="ML Engineer")],
            copy.deepcopy(MOCK_FETCH_STATS),
        )
        mock_upsert.side_effect = [
            make_upsert_result(raw_id=1),
            make_upsert_result(raw_id=2),
        ]
        mock_is_agency.return_value = False
        mock_classify.side_effect = _classify_side_effect
        mock_validate_agency.return_value = (False, "low")
        mock_extract_loc.return_value = [{"type": "city", "country_code": "GB", "city": "london"}]
        mock_wa_fallback.return_value = None
        mock_enriched.side_effect = [101, 102]

        stats = await process_greenhouse_incremental(companies=["acme"])

        assert mock_upsert.call_count == 2
        assert mock_classify.call_count == 2
        assert mock_enriched.call_count == 2
        assert stats["companies_processed"] == 1
        assert stats["companies_with_jobs"] == 1
        assert stats["jobs_written_enriched"] == 2

        # Verify classifier called with source="greenhouse"
        call_kwargs = mock_classify.call_args_list[0]
        assert call_kwargs.kwargs.get("source") == "greenhouse"

    @patch("pipeline.fetch_jobs.get_recently_processed_companies")
    @patch("scrapers.greenhouse.greenhouse_api_fetcher.load_company_mapping")
    @patch("scrapers.greenhouse.greenhouse_api_fetcher.fetch_greenhouse_jobs")
    @patch("pipeline.fetch_jobs.extract_locations")
    @patch("pipeline.agency_detection.validate_agency_classification")
    @patch("pipeline.agency_detection.is_agency_job")
    @patch("pipeline.classifier.classify_job")
    @patch("pipeline.db_connection.ensure_employer_metadata")
    @patch("pipeline.db_connection.get_working_arrangement_fallback")
    @patch("pipeline.db_connection.insert_enriched_job")
    @patch("pipeline.db_connection.insert_raw_job_upsert")
    async def test_resume_mode(
        self,
        mock_upsert,
        mock_enriched,
        mock_wa_fallback,
        mock_ensure_meta,
        mock_classify,
        mock_is_agency,
        mock_validate_agency,
        mock_extract_loc,
        mock_fetch_gh,
        mock_load_mapping,
        mock_get_recent,
    ):
        """Resume mode should skip recently processed companies."""
        from pipeline.fetch_jobs import process_greenhouse_incremental

        mock_load_mapping.return_value = {
            "greenhouse": {"Acme Corp": {"slug": "acme"}}
        }
        mock_get_recent.return_value = {"acme"}

        stats = await process_greenhouse_incremental(companies=["acme"], resume_hours=24)

        assert stats["companies_skipped"] == 1
        assert stats["companies_processed"] == 0


# ---------------------------------------------------------------------------
# Cross-cutting behavior
# ---------------------------------------------------------------------------

class TestCrossCuttingBehavior:
    """Test behavior that applies across all pipeline sources."""

    @patch("scrapers.lever.lever_fetcher.load_company_mapping")
    @patch("scrapers.lever.lever_fetcher.fetch_lever_jobs")
    @patch("pipeline.fetch_jobs.extract_locations")
    @patch("pipeline.agency_detection.validate_agency_classification")
    @patch("pipeline.agency_detection.is_agency_job")
    @patch("pipeline.classifier.classify_job")
    @patch("pipeline.db_connection.ensure_employer_metadata")
    @patch("pipeline.db_connection.get_working_arrangement_fallback")
    @patch("pipeline.db_connection.insert_enriched_job")
    @patch("pipeline.db_connection.insert_raw_job_upsert")
    async def test_soft_agency_flags_but_continues(
        self,
        mock_upsert,
        mock_enriched,
        mock_wa_fallback,
        mock_ensure_meta,
        mock_classify,
        mock_is_agency,
        mock_validate_agency,
        mock_extract_loc,
        mock_fetch_lever,
        mock_load_mapping,
    ):
        """Soft agency detection should flag but still store the job."""
        from pipeline.fetch_jobs import process_lever_incremental

        mock_load_mapping.return_value = {
            "lever": {"Acme Corp": {"slug": "acme", "instance": "global"}}
        }
        mock_fetch_lever.return_value = (
            [make_lever_job()],
            copy.deepcopy(MOCK_FETCH_STATS),
        )
        mock_upsert.return_value = make_upsert_result()
        mock_is_agency.return_value = False
        mock_classify.side_effect = _classify_side_effect
        mock_validate_agency.return_value = (True, "medium")
        mock_extract_loc.return_value = [{"type": "city", "country_code": "GB", "city": "london"}]
        mock_wa_fallback.return_value = None
        mock_enriched.return_value = 101

        stats = await process_lever_incremental(companies=["acme"])

        # Job should still be stored
        assert mock_enriched.call_count == 1
        assert stats["jobs_written_enriched"] == 1

        # But agency flags should be set
        enriched_call = mock_enriched.call_args
        assert enriched_call.kwargs["is_agency"] is True
        assert enriched_call.kwargs["agency_confidence"] == "medium"

        # Agency counter should be incremented
        assert stats["jobs_agency_filtered"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
