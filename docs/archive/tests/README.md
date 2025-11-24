# Archived Test Files

This directory contains old test files that have been superseded by newer tests or are no longer actively used.

## Files

- **test_manual_insert.py** - Manual test for inserting ground truth jobs
  - Used for validating classification on hand-selected test cases
  - Replaced by automated test suite
  - Kept for reference on how manual testing was done

- **test_skills_insert.py** - Old skills extraction test
  - Tested skills extraction on sample jobs
  - Replaced by automated tests with more comprehensive coverage
  - Kept for reference

## Current Active Tests

The current test suite is in `../../tests/`:
- test_greenhouse_scraper_simple.py - Current Greenhouse scraper test
- test_end_to_end.py - Integration test of full pipeline
- test_two_companies.py - Functional test with sample companies
- test_ats_scraping.py - ATS scraping tests (under review for potential consolidation)
- test_orchestrator.py - Orchestrator tests (under review for current validity)
- test_failed_job.py - Tests for error handling (under review)

Note: test_ats_scraping.py, test_orchestrator.py, and test_failed_job.py should be reviewed to determine if they are still relevant and not duplicating other tests.
