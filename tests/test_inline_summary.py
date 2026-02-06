"""
Tests for inline summary generation feature.

Tests the architecture where summaries are generated inline during
classification instead of via a separate batch job.

Unit tests (mocked): Verify classifier output structure and DB function signature.
Integration test (live): 1 real Gemini call to verify summary generation works.
"""

import sys
import inspect
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestClassifierSummaryOutputUnit:
    """Unit tests for classifier.py summary output (mocked)"""

    @patch('pipeline.classifier.genai')
    def test_classifier_output_schema_includes_summary(self, mock_genai):
        """Classifier prompt schema should request a 'summary' field"""
        from pipeline.classifier import classify_job

        # Mock Gemini to return valid JSON with summary
        mock_response = MagicMock()
        mock_response.text = '''{
            "job_family": "data",
            "job_subfamily": "data_engineer",
            "title_clean": "Senior Data Engineer",
            "working_arrangement": "hybrid",
            "position_type": "full_time",
            "is_agency": false,
            "summary": "Build and maintain data pipelines using Python and Spark.",
            "skills": []
        }'''
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        result = classify_job("Senior Data Engineer at Acme Corp", verbose=False)

        assert 'summary' in result
        assert isinstance(result['summary'], str)
        assert len(result['summary']) > 0

    @patch('pipeline.classifier.genai')
    def test_classifier_summary_can_be_extracted_by_pipeline(self, mock_genai):
        """Pipeline extracts summary via classification.get('summary')"""
        from pipeline.classifier import classify_job

        mock_response = MagicMock()
        mock_response.text = '''{
            "job_family": "product",
            "job_subfamily": "core_pm",
            "title_clean": "Product Manager",
            "working_arrangement": "remote",
            "position_type": "full_time",
            "is_agency": false,
            "summary": "Lead product strategy for payments platform.",
            "skills": []
        }'''
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        classification = classify_job("Product Manager at FinTech Co", verbose=False)
        summary = classification.get('summary')

        assert summary is not None
        assert isinstance(summary, str)


class TestDbConnectionSummaryParam:
    """Unit tests for db_connection.py summary parameter"""

    def test_insert_enriched_job_accepts_summary_param(self):
        """insert_enriched_job should have 'summary' in its signature"""
        from pipeline.db_connection import insert_enriched_job

        sig = inspect.signature(insert_enriched_job)
        param_names = list(sig.parameters.keys())

        assert 'summary' in param_names

    def test_insert_enriched_job_summary_defaults_to_none(self):
        """summary parameter should default to None for backward compatibility"""
        from pipeline.db_connection import insert_enriched_job

        sig = inspect.signature(insert_enriched_job)
        summary_param = sig.parameters['summary']

        assert summary_param.default is None


class TestSummaryGeneratorBackfill:
    """Tests for summary_generator.py as backfill utility"""

    def test_summary_generator_includes_ashby(self):
        """summary_generator.py should include Ashby in data_source filter"""
        from pipeline.summary_generator import generate_summaries

        source = inspect.getsource(generate_summaries)
        assert 'ashby' in source.lower()


@pytest.mark.integration
@pytest.mark.slow
class TestClassifierSummaryIntegration:
    """Integration test: 1 real Gemini call to verify summary generation"""

    def test_classifier_generates_meaningful_summary(self):
        """Classifier should generate a non-empty, concise summary from real LLM"""
        from pipeline.classifier import classify_job

        test_job = """
        Senior Data Engineer
        Acme Corp - London, UK
        Full-time - Hybrid

        We're looking for a Senior Data Engineer to build our data platform.

        You will:
        - Design and build data pipelines using Python and Spark
        - Work with our Data Science team on ML infrastructure
        - Maintain our Snowflake data warehouse

        Requirements:
        - 5+ years experience with Python, SQL
        - Experience with Spark, Airflow
        - Strong communication skills

        Salary: GBP 80,000 - 110,000
        """

        result = classify_job(test_job, verbose=False)

        assert 'summary' in result
        summary = result.get('summary')
        assert summary is not None
        assert isinstance(summary, str)
        assert len(summary) > 20, f"Summary too short: {summary}"
        assert len(summary) < 500, f"Summary too long ({len(summary)} chars)"

        # Should not contain generic filler phrases
        generic_phrases = ['exciting opportunity', 'fast-paced environment', 'dynamic team']
        summary_lower = summary.lower()
        for phrase in generic_phrases:
            assert phrase not in summary_lower, f"Summary contains generic phrase: '{phrase}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
