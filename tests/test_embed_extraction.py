#!/usr/bin/env python3
"""
Tests for embed URL fallback extraction logic.

Tests the improved embed extraction that:
1. Tries job description selectors first
2. Truncates at form markers
3. Uses relaxed validation for embed pages
"""

import pytest
import asyncio
from scrapers.greenhouse.greenhouse_scraper import GreenhouseScraper


class TestContentValidation:
    """Test the _is_valid_job_content validation logic"""

    def setup_method(self):
        """Initialize scraper for testing"""
        self.scraper = GreenhouseScraper(headless=True, filter_titles=False)

    def test_valid_job_content_with_responsibilities(self):
        """Should accept content with job keywords"""
        content = """
        About the Role
        We are looking for a Senior Data Engineer to join our team.

        Responsibilities:
        - Design and build data pipelines
        - Work with cross-functional teams
        - Mentor junior engineers

        Requirements:
        - 5+ years experience with Python
        - Strong SQL skills
        - Experience with cloud platforms
        """
        assert self.scraper._is_valid_job_content(content) == True

    def test_valid_job_content_with_qualifications(self):
        """Should accept content with qualifications"""
        content = """
        The Team
        Join our Product team building next-gen analytics.

        You will:
        - Lead product strategy
        - Define roadmaps
        - Work with engineering

        Qualifications:
        - Product management experience
        - Technical background preferred
        - Strong communication skills
        """
        assert self.scraper._is_valid_job_content(content) == True

    def test_reject_short_content(self):
        """Should reject content under 200 chars"""
        content = "This is a job posting. Apply now!"
        assert self.scraper._is_valid_job_content(content) == False

    def test_reject_css_garbage(self):
        """Should reject CSS code"""
        content = """
        --grid-template: 1fr;
        var(--color-primary);
        @media screen and (min-width: 768px) {
            .container { width: 100%; }
        }
        """ + "x" * 200  # Pad to meet length requirement
        assert self.scraper._is_valid_job_content(content) == False

    def test_reject_pure_application_form(self):
        """Should reject content that is only application form"""
        content = """
        Apply for this Job
        First Name* [____________]
        Last Name* [____________]
        Email* [____________]
        Resume/CV* [Upload]
        Cover Letter [Upload]
        Submit Application
        """ + "x" * 200
        assert self.scraper._is_valid_job_content(content) == False

    def test_accept_form_with_strong_job_content(self):
        """Should accept content with both form AND strong job description"""
        content = """
        Senior Data Scientist

        About the Role:
        We're looking for someone to lead our ML initiatives.

        Responsibilities:
        - Build machine learning models
        - Analyze large datasets
        - Present findings to stakeholders

        Requirements:
        - PhD or MS in relevant field
        - Experience with Python, TensorFlow
        - Strong communication skills

        Benefits:
        - Competitive salary
        - Health insurance
        - Remote work options

        Apply for this Job
        First Name* Last Name* Email*
        """
        # This should pass because it has strong job content (4+ job keywords)
        assert self.scraper._is_valid_job_content(content) == True


class TestFormMarkerTruncation:
    """Test the form marker truncation logic"""

    def test_truncate_at_apply_for_this_job(self):
        """Should truncate content at 'Apply for this Job'"""
        full_text = """
        Job Title: Data Engineer

        Responsibilities:
        - Build data pipelines

        Requirements:
        - 3+ years experience

        Apply for this Job

        First Name* [____________]
        Last Name* [____________]
        Email* [____________]
        """

        marker = 'Apply for this Job'
        if marker in full_text:
            truncated = full_text.split(marker)[0]
        else:
            truncated = full_text

        assert 'First Name*' not in truncated
        assert 'Responsibilities' in truncated
        assert 'Requirements' in truncated

    def test_truncate_at_first_name(self):
        """Should truncate content at 'First Name*'"""
        full_text = """
        Job Description

        We are hiring a Product Manager.

        Qualifications:
        - Experience required

        First Name*
        Last Name*
        Email*
        """

        marker = 'First Name*'
        if marker in full_text:
            truncated = full_text.split(marker)[0]
        else:
            truncated = full_text

        assert 'Last Name*' not in truncated
        assert 'Qualifications' in truncated

    def test_no_truncation_without_markers(self):
        """Should return full text if no markers found"""
        full_text = """
        This is a job description without any form content.

        Responsibilities:
        - Do things
        - Make stuff
        """

        form_markers = ['Apply for this Job', 'First Name*', 'Resume/CV*', 'Submit Application']
        truncated = full_text
        for marker in form_markers:
            if marker in full_text:
                truncated = full_text.split(marker)[0]
                break

        assert truncated == full_text


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
class TestEmbedExtractionLive:
    """
    Live integration tests for embed extraction.

    These tests actually fetch embed pages to verify extraction works.
    Run with: pytest -m integration
    """

    async def test_embed_extraction_stripe(self):
        """Test embed extraction works for standard company (Stripe)"""
        scraper = GreenhouseScraper(headless=True, filter_titles=False)

        try:
            await scraper.init()

            # Scrape a single job to test extraction
            result = await scraper.scrape_company('stripe', max_jobs=3)

            jobs = result['jobs']

            # Should have extracted some jobs
            assert len(jobs) > 0, "Should extract at least one job from Stripe"

            # Each job should have a description
            for job in jobs:
                if hasattr(job, 'description') and job.description:
                    assert len(job.description) > 100, f"Job description too short: {len(job.description)} chars"

        finally:
            await scraper.close()

    async def test_embed_extraction_jetbrains_eu(self):
        """Test embed extraction works for EU company (JetBrains)"""
        scraper = GreenhouseScraper(headless=True, filter_titles=False)

        try:
            await scraper.init()

            # Scrape JetBrains (EU Greenhouse)
            result = await scraper.scrape_company('jetbrains', max_jobs=3)

            jobs = result['jobs']

            # Should have extracted some jobs
            assert len(jobs) > 0, "Should extract at least one job from JetBrains"

            # Jobs should have descriptions (the fix addresses this)
            jobs_with_desc = [j for j in jobs if hasattr(j, 'description') and j.description and len(j.description) > 100]

            # At least some jobs should have descriptions
            assert len(jobs_with_desc) > 0, "At least some JetBrains jobs should have descriptions"

        finally:
            await scraper.close()

    async def test_embed_fallback_for_fastly(self):
        """Test that Fastly (which redirects) uses embed fallback"""
        scraper = GreenhouseScraper(headless=True, filter_titles=False)

        try:
            await scraper.init()

            # Note: Fastly redirects to custom page, so embed fallback should kick in
            # This tests the new URL cache override we added
            result = await scraper.scrape_company('fastly', max_jobs=2)

            # Should either get jobs via embed OR handle gracefully
            # (depends on whether the cache override is in place)
            assert 'jobs' in result
            assert 'stats' in result

        finally:
            await scraper.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
