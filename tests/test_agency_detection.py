"""
Test agency detection module

Pure unit tests for pipeline/agency_detection.py.
All tests use the live YAML config but no external API calls.

Tests:
- detect_agency(): pattern matching for company names and descriptions
- validate_agency_classification(): combining pattern matching with Claude output
- is_agency_job(): simple boolean wrapper
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.agency_detection import (
    detect_agency,
    validate_agency_classification,
    is_agency_job,
    HARD_FILTER,
    HIGH_CONF_KEYWORDS,
    MED_CONF_KEYWORDS,
    HIGH_CONF_SUFFIXES,
    MED_CONF_SUFFIXES,
    LEGITIMATE_COMPANIES,
    AGENCY_PHRASES,
)


class TestDetectAgencyHardFilter:
    """Test hard filter matches"""

    def test_hard_filter_match(self):
        """Company in hard filter should return (True, 'high')"""
        # Pick a known entry from the hard filter
        hard_entry = next(iter(HARD_FILTER))
        is_agency, confidence = detect_agency(hard_entry)
        assert is_agency is True
        assert confidence == 'high'

    def test_hard_filter_case_insensitive(self):
        """Hard filter matching should be case-insensitive"""
        hard_entry = next(iter(HARD_FILTER))
        is_agency, confidence = detect_agency(hard_entry.upper())
        assert is_agency is True
        assert confidence == 'high'


class TestDetectAgencyHighConfidence:
    """Test high-confidence keyword and suffix detection"""

    def test_two_high_confidence_keywords(self):
        """Two high-confidence keywords in name should return (True, 'high')"""
        is_agency, confidence = detect_agency("Tech Staffing Recruitment Group")
        assert is_agency is True
        assert confidence == 'high'

    def test_high_confidence_suffix(self):
        """Name ending with high-confidence suffix should return (True, 'high')"""
        is_agency, confidence = detect_agency("Global Tech Staffing")
        assert is_agency is True
        assert confidence == 'high'

    def test_recruitment_suffix(self):
        """Name ending with 'recruitment' should be high confidence"""
        is_agency, confidence = detect_agency("Hays Recruitment")
        assert is_agency is True
        assert confidence == 'high'


class TestDetectAgencyMediumConfidence:
    """Test medium-confidence detection"""

    def test_single_high_keyword_is_medium(self):
        """Single high-confidence keyword should return (True, 'medium')"""
        # 'staffing' is a high-confidence keyword
        is_agency, confidence = detect_agency("Global Staffing Inc")
        assert is_agency is True
        assert confidence == 'medium'

    def test_medium_suffix_with_recruitment_keyword(self):
        """Medium suffix + recruitment keyword should return (True, 'medium')"""
        is_agency, confidence = detect_agency("Talent Search Solutions")
        assert is_agency is True

    def test_medium_suffix_without_recruitment_keyword(self):
        """Medium suffix without recruitment keyword should NOT flag (e.g., 'Acme Solutions')"""
        # 'solutions' alone without talent/staff/recruit/search should not flag
        is_agency, confidence = detect_agency("Acme Solutions")
        assert is_agency is False

    def test_two_medium_keywords(self):
        """Two medium-confidence keywords should return (True, 'medium')"""
        # 'consulting' and 'global' are medium keywords
        # (not in hard filter, not a legitimate company)
        is_agency, confidence = detect_agency("Apex Consulting Global")
        assert is_agency is True
        assert confidence == 'medium'


class TestDetectAgencyLegitimateCompanies:
    """Test legitimate company whitelist"""

    def test_legitimate_company_not_flagged(self):
        """Known legitimate companies should not be flagged"""
        is_agency, confidence = detect_agency("accenture")
        assert is_agency is False
        assert confidence == 'low'

    def test_google_not_flagged(self):
        """Google should not be flagged as agency"""
        is_agency, confidence = detect_agency("google")
        assert is_agency is False
        assert confidence == 'low'

    def test_legitimate_overrides_keyword_match(self):
        """Legitimate company should override keyword matching"""
        # 'boston consulting group' has 'consulting' and 'group' keywords
        is_agency, confidence = detect_agency("boston consulting group")
        assert is_agency is False
        assert confidence == 'low'


class TestDetectAgencyEdgeCases:
    """Test edge cases"""

    def test_empty_name(self):
        """Empty employer name should return (False, 'low')"""
        is_agency, confidence = detect_agency("")
        assert is_agency is False
        assert confidence == 'low'

    def test_none_name(self):
        """None employer name should return (False, 'low')"""
        is_agency, confidence = detect_agency(None)
        assert is_agency is False
        assert confidence == 'low'

    def test_normal_company_not_flagged(self):
        """Regular company name should not be flagged"""
        is_agency, confidence = detect_agency("Stripe")
        assert is_agency is False
        assert confidence == 'low'


class TestDetectAgencyDescriptionBased:
    """Test description-based agency detection"""

    def test_multiple_agency_phrases_in_description(self):
        """2+ agency phrases in description should flag as medium"""
        description = (
            "Our client, a leading technology company, is seeking a Data Scientist. "
            "This is an exciting opportunity to join a growing team."
        )
        is_agency, confidence = detect_agency("Unknown Corp", description)
        assert is_agency is True
        assert confidence == 'medium'

    def test_single_phrase_plus_suspicious_name(self):
        """1 agency phrase + medium keyword in name should flag"""
        description = "Our client is seeking a talented engineer."
        # 'consulting' is a medium keyword
        is_agency, confidence = detect_agency("DataTech Consulting", description)
        # Single phrase + 1 medium keyword
        assert is_agency is True

    def test_no_phrases_in_clean_description(self):
        """Clean description without agency phrases should not trigger"""
        description = (
            "We are building a next-generation data platform. "
            "You will work with Python and Spark to build pipelines."
        )
        is_agency, confidence = detect_agency("Normal Corp", description)
        assert is_agency is False


class TestValidateAgencyClassification:
    """Test combining pattern matching with Claude classification"""

    def test_high_confidence_overrides_claude(self):
        """High confidence pattern match should override Claude saying not agency"""
        hard_entry = next(iter(HARD_FILTER))
        is_agency, confidence = validate_agency_classification(
            employer_name=hard_entry,
            claude_is_agency=False,
            claude_confidence='high'
        )
        assert is_agency is True
        assert confidence == 'high'

    def test_medium_pattern_plus_claude_agrees(self):
        """Medium pattern + Claude agrees = high confidence agency"""
        is_agency, confidence = validate_agency_classification(
            employer_name="Global Staffing Inc",
            claude_is_agency=True,
            claude_confidence='medium'
        )
        assert is_agency is True
        assert confidence == 'high'

    def test_medium_pattern_plus_claude_disagrees(self):
        """Medium pattern + Claude says not agency = defer to Claude"""
        is_agency, confidence = validate_agency_classification(
            employer_name="Global Staffing Inc",
            claude_is_agency=False,
            claude_confidence='medium'
        )
        assert is_agency is False
        assert confidence == 'low'

    def test_low_pattern_defers_to_claude(self):
        """No pattern match should defer to Claude's classification"""
        is_agency, confidence = validate_agency_classification(
            employer_name="Normal Corp",
            claude_is_agency=True,
            claude_confidence='medium'
        )
        assert is_agency is True
        assert confidence == 'medium'

    def test_no_pattern_no_claude(self):
        """No pattern match and no Claude classification = not agency"""
        is_agency, confidence = validate_agency_classification(
            employer_name="Normal Corp",
            claude_is_agency=None,
            claude_confidence=None
        )
        assert is_agency is False
        assert confidence == 'low'


class TestIsAgencyJob:
    """Test simple boolean wrapper"""

    def test_agency_returns_true(self):
        """Known agency should return True"""
        hard_entry = next(iter(HARD_FILTER))
        assert is_agency_job(hard_entry) is True

    def test_normal_company_returns_false(self):
        """Normal company should return False"""
        assert is_agency_job("Stripe") is False

    def test_empty_returns_false(self):
        """Empty name should return False"""
        assert is_agency_job("") is False


class TestConfigLoaded:
    """Test that configuration loaded correctly"""

    def test_hard_filter_not_empty(self):
        """Hard filter should have entries"""
        assert len(HARD_FILTER) > 0

    def test_high_conf_keywords_not_empty(self):
        """High confidence keywords should have entries"""
        assert len(HIGH_CONF_KEYWORDS) > 0

    def test_legitimate_companies_not_empty(self):
        """Legitimate companies whitelist should have entries"""
        assert len(LEGITIMATE_COMPANIES) > 0

    def test_agency_phrases_not_empty(self):
        """Agency phrases list should have entries"""
        assert len(AGENCY_PHRASES) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
