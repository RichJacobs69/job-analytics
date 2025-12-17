"""
Lever ATS Scraper Module

This module provides tools for fetching job postings from companies using the Lever
applicant tracking system. Unlike Greenhouse (which requires browser automation),
Lever provides a public Postings API that returns JSON without authentication.

Components:
- discover_lever_companies.py: Find companies that use Lever ATS
- validate_lever_sites.py: Validate discovered slugs against Lever API
- lever_fetcher.py: Fetch and parse job postings from Lever API

API Documentation: https://github.com/lever/postings-api
"""

from .lever_fetcher import (
    fetch_lever_jobs,
    fetch_all_lever_companies,
    LEVER_API_URLS,
)

__all__ = [
    'fetch_lever_jobs',
    'fetch_all_lever_companies',
    'LEVER_API_URLS',
]
