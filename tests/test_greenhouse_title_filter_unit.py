#!/usr/bin/env python3
"""
Unit tests for Greenhouse title filtering functionality.

Tests the core pattern matching logic without browser automation.
"""

import pytest
from pathlib import Path
import tempfile
import yaml
from scrapers.greenhouse.greenhouse_scraper import (
    load_title_patterns,
    is_relevant_role
)


class TestLoadTitlePatterns:
    """Test pattern loading from YAML config"""

    def test_load_patterns_from_yaml(self):
        """Test that patterns load successfully from default YAML config"""
        patterns = load_title_patterns()

        # Should load patterns successfully
        assert len(patterns) > 0, "Should load at least one pattern"

        # Check for expected patterns (based on config file)
        pattern_str = ' '.join(patterns).lower()
        assert 'data scientist' in pattern_str, "Should include data scientist pattern"
        assert 'product manager' in pattern_str, "Should include product manager pattern"
        assert 'ml engineer' in pattern_str or 'machine learning engineer' in pattern_str, "Should include ML engineer pattern"

    def test_load_patterns_file_not_found(self):
        """Test graceful handling when config file doesn't exist"""
        fake_path = Path('/nonexistent/path/to/config.yaml')
        patterns = load_title_patterns(fake_path)

        # Should return empty list, not crash
        assert patterns == [], "Should return empty list for missing config"

    def test_load_patterns_custom_path(self):
        """Test loading patterns from custom YAML file"""
        # Create temporary YAML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            test_config = {
                'relevant_title_patterns': [
                    'test pattern 1',
                    'test pattern 2',
                ]
            }
            yaml.dump(test_config, f)
            temp_path = Path(f.name)

        try:
            patterns = load_title_patterns(temp_path)
            assert len(patterns) == 2
            assert 'test pattern 1' in patterns
            assert 'test pattern 2' in patterns
        finally:
            temp_path.unlink()  # Clean up

    def test_load_patterns_malformed_yaml(self):
        """Test handling of malformed YAML file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("this is: not: valid: yaml: syntax:")
            temp_path = Path(f.name)

        try:
            patterns = load_title_patterns(temp_path)
            # Should handle error gracefully and return empty list
            assert patterns == []
        finally:
            temp_path.unlink()


class TestIsRelevantRole:
    """Test title pattern matching logic"""

    def test_is_relevant_role_data_scientist(self):
        """Test Data Scientist family matching"""
        patterns = [
            'data scientist',
            'machine learning scientist',
            'research scientist.*(ml|ai|machine learning|data)',
            'applied (scientist|ml)'
        ]

        # Should match
        assert is_relevant_role('Data Scientist', patterns) == True
        assert is_relevant_role('Senior Data Scientist', patterns) == True
        assert is_relevant_role('Staff Data Scientist', patterns) == True
        assert is_relevant_role('Machine Learning Scientist', patterns) == True
        assert is_relevant_role('Research Scientist - ML', patterns) == True
        assert is_relevant_role('Applied Scientist', patterns) == True

        # Should NOT match
        assert is_relevant_role('Software Engineer', patterns) == False
        assert is_relevant_role('Product Manager', patterns) == False
        assert is_relevant_role('Sales Executive', patterns) == False

    def test_is_relevant_role_ml_engineer(self):
        """Test ML Engineer family matching"""
        patterns = [
            'ml engineer|machine learning engineer',
            'ai engineer',
            'mlops'
        ]

        # Should match
        assert is_relevant_role('ML Engineer', patterns) == True
        assert is_relevant_role('Machine Learning Engineer', patterns) == True
        assert is_relevant_role('Senior ML Engineer', patterns) == True
        assert is_relevant_role('AI Engineer', patterns) == True
        assert is_relevant_role('MLOps Engineer', patterns) == True
        assert is_relevant_role('Staff MLOps', patterns) == True

        # Should NOT match
        assert is_relevant_role('Data Analyst', patterns) == False
        assert is_relevant_role('DevOps Engineer', patterns) == False
        assert is_relevant_role('Software Engineer', patterns) == False

    def test_is_relevant_role_data_engineer(self):
        """Test Data Engineer family matching"""
        patterns = [
            'data engineer',
            'data platform'
        ]

        # Should match
        assert is_relevant_role('Data Engineer', patterns) == True
        assert is_relevant_role('Senior Data Engineer', patterns) == True
        assert is_relevant_role('Staff Data Engineer', patterns) == True
        assert is_relevant_role('Principal Data Engineer', patterns) == True
        assert is_relevant_role('Data Platform Engineer', patterns) == True

        # Should NOT match
        assert is_relevant_role('Software Engineer', patterns) == False
        assert is_relevant_role('Platform Engineer', patterns) == False  # Too broad
        assert is_relevant_role('Backend Engineer', patterns) == False

    def test_is_relevant_role_data_analyst(self):
        """Test Data Analyst family matching"""
        patterns = [
            'data analyst',
            'analytics (engineer|lead|manager)'
        ]

        # Should match
        assert is_relevant_role('Data Analyst', patterns) == True
        assert is_relevant_role('Senior Data Analyst', patterns) == True
        assert is_relevant_role('Analytics Engineer', patterns) == True
        assert is_relevant_role('Analytics Lead', patterns) == True
        assert is_relevant_role('Analytics Manager', patterns) == True
        assert is_relevant_role('Principal Analytics Engineer', patterns) == True

        # Should NOT match
        assert is_relevant_role('Financial Analyst', patterns) == False
        assert is_relevant_role('Business Analyst', patterns) == False
        assert is_relevant_role('Marketing Analyst', patterns) == False

    def test_is_relevant_role_product_manager(self):
        """Test Product Manager family matching"""
        patterns = [
            'product manager',
            'product owner',
            'tpm|technical program manager',
            'technical product manager',
            'growth (pm|product manager)',
            'platform (pm|product manager)',
            '(ai|ml|data).*(product manager|pm)',
            'product manager.*(ai|ml|data)'
        ]

        # Should match
        assert is_relevant_role('Product Manager', patterns) == True
        assert is_relevant_role('Senior Product Manager', patterns) == True
        assert is_relevant_role('Product Owner', patterns) == True
        assert is_relevant_role('TPM', patterns) == True
        assert is_relevant_role('Technical Program Manager', patterns) == True
        assert is_relevant_role('Technical Product Manager', patterns) == True
        assert is_relevant_role('Growth PM', patterns) == True
        assert is_relevant_role('Growth Product Manager', patterns) == True
        assert is_relevant_role('Platform PM', patterns) == True
        assert is_relevant_role('AI Product Manager', patterns) == True
        assert is_relevant_role('ML PM', patterns) == True
        assert is_relevant_role('Product Manager - AI', patterns) == True
        assert is_relevant_role('Data Product Manager', patterns) == True

        # Should NOT match
        assert is_relevant_role('Product Marketing Manager', patterns) == False
        assert is_relevant_role('Program Manager', patterns) == False  # Too broad
        assert is_relevant_role('Project Manager', patterns) == False

    def test_is_relevant_role_with_seniority(self):
        """Test that seniority prefixes work correctly"""
        patterns = ['data engineer', 'product manager']

        # All seniority levels should match
        assert is_relevant_role('Junior Data Engineer', patterns) == True
        assert is_relevant_role('Mid-Level Data Engineer', patterns) == True
        assert is_relevant_role('Senior Data Engineer', patterns) == True
        assert is_relevant_role('Staff Data Engineer', patterns) == True
        assert is_relevant_role('Principal Data Engineer', patterns) == True
        assert is_relevant_role('Lead Data Engineer', patterns) == True

        # Same for Product Manager
        assert is_relevant_role('Senior Product Manager', patterns) == True
        assert is_relevant_role('Staff Product Manager', patterns) == True
        assert is_relevant_role('Principal Product Manager', patterns) == True

    def test_is_relevant_role_negative_cases(self):
        """Test that non-Data/Product roles are correctly rejected"""
        patterns = [
            'data scientist',
            'data engineer',
            'data analyst',
            'ml engineer',
            'product manager'
        ]

        # Sales roles
        assert is_relevant_role('Account Executive', patterns) == False
        assert is_relevant_role('Sales Development Representative', patterns) == False
        assert is_relevant_role('Sales Engineer', patterns) == False

        # Marketing roles
        assert is_relevant_role('Marketing Manager', patterns) == False
        assert is_relevant_role('Product Marketing Manager', patterns) == False
        assert is_relevant_role('Growth Marketing Manager', patterns) == False

        # HR roles
        assert is_relevant_role('HR Business Partner', patterns) == False
        assert is_relevant_role('People Operations', patterns) == False
        assert is_relevant_role('Recruiter', patterns) == False

        # Legal/Finance
        assert is_relevant_role('Legal Counsel', patterns) == False
        assert is_relevant_role('Financial Analyst', patterns) == False
        assert is_relevant_role('Accountant', patterns) == False

        # Engineering (non-data)
        assert is_relevant_role('Software Engineer', patterns) == False
        assert is_relevant_role('Backend Engineer', patterns) == False
        assert is_relevant_role('Frontend Engineer', patterns) == False
        assert is_relevant_role('DevOps Engineer', patterns) == False
        assert is_relevant_role('Infrastructure Engineer', patterns) == False

    def test_is_relevant_role_edge_cases(self):
        """Test ambiguous cases and edge cases"""
        patterns = [
            'data analyst',
            'data engineer',
            'product manager'
        ]

        # "Data Analyst" should match, "Financial Analyst" should not
        assert is_relevant_role('Data Analyst', patterns) == True
        assert is_relevant_role('Financial Analyst', patterns) == False
        assert is_relevant_role('Business Analyst', patterns) == False

        # "Product Manager" should match, "Product Marketing" should not
        assert is_relevant_role('Product Manager', patterns) == True
        assert is_relevant_role('Product Marketing Manager', patterns) == False

        # Generic "Analyst" or "Engineer" should NOT match (too broad)
        assert is_relevant_role('Analyst', patterns) == False
        assert is_relevant_role('Engineer', patterns) == False

        # Case sensitivity should not matter
        assert is_relevant_role('DATA ANALYST', patterns) == True
        assert is_relevant_role('data analyst', patterns) == True
        assert is_relevant_role('Data Analyst', patterns) == True

    def test_invalid_regex_pattern(self):
        """Test graceful handling of malformed regex patterns"""
        # Invalid regex (unmatched parenthesis)
        patterns = [
            'data scientist',
            '(invalid regex pattern',  # This is invalid
            'product manager'
        ]

        # Should not crash, should skip invalid pattern
        # Valid patterns should still work
        assert is_relevant_role('Data Scientist', patterns) == True
        assert is_relevant_role('Product Manager', patterns) == True

        # Should not match non-relevant roles
        assert is_relevant_role('Sales Executive', patterns) == False

    def test_empty_patterns_list(self):
        """Test behavior when no patterns are loaded"""
        patterns = []

        # When no patterns exist, everything should match (filtering disabled)
        assert is_relevant_role('Data Scientist', patterns) == True
        assert is_relevant_role('Sales Executive', patterns) == True
        assert is_relevant_role('Any Random Title', patterns) == True

    def test_pattern_matching_with_special_characters(self):
        """Test patterns with special characters in titles"""
        patterns = ['data engineer', 'ml engineer']

        # Titles with special characters
        assert is_relevant_role('Data Engineer (Remote)', patterns) == True
        assert is_relevant_role('ML Engineer - Platform', patterns) == True
        assert is_relevant_role('Data Engineer / Analytics', patterns) == True
        assert is_relevant_role('Sr. Data Engineer', patterns) == True


class TestDeliveryRolePatterns:
    """Test Delivery role pattern matching (added v1.3)"""

    def test_is_relevant_role_delivery_manager(self):
        """Test Delivery Manager family matching"""
        patterns = [
            'delivery manager',
            'delivery lead',
            'agile delivery manager',
            'agile delivery lead'
        ]

        # Should match
        assert is_relevant_role('Delivery Manager', patterns) == True
        assert is_relevant_role('Senior Delivery Manager', patterns) == True
        assert is_relevant_role('Delivery Lead', patterns) == True
        assert is_relevant_role('Agile Delivery Manager', patterns) == True

        # Should NOT match
        assert is_relevant_role('Product Manager', patterns) == False
        assert is_relevant_role('Data Scientist', patterns) == False

    def test_is_relevant_role_project_manager(self):
        """Test Project Manager matching (must NOT match Product Manager)"""
        patterns = [
            '(?<!product )project manager',
            'technical project manager',
            'it project manager',
            'senior project manager'
        ]

        # Should match
        assert is_relevant_role('Project Manager', patterns) == True
        assert is_relevant_role('Senior Project Manager', patterns) == True
        assert is_relevant_role('Technical Project Manager', patterns) == True
        assert is_relevant_role('IT Project Manager', patterns) == True

        # CRITICAL: Should NOT match Product Manager
        assert is_relevant_role('Product Manager', patterns) == False
        assert is_relevant_role('Senior Product Manager', patterns) == False

    def test_is_relevant_role_programme_manager(self):
        """Test Programme/Program Manager matching"""
        patterns = [
            'program(me)? manager',
            'senior program(me)? manager'
        ]

        # Should match both spellings
        assert is_relevant_role('Programme Manager', patterns) == True
        assert is_relevant_role('Program Manager', patterns) == True
        assert is_relevant_role('Senior Programme Manager', patterns) == True
        assert is_relevant_role('Senior Program Manager', patterns) == True

    def test_is_relevant_role_scrum_master(self):
        """Test Scrum Master matching"""
        patterns = [
            'scrum master',
            'senior scrum master'
        ]

        # Should match
        assert is_relevant_role('Scrum Master', patterns) == True
        assert is_relevant_role('Senior Scrum Master', patterns) == True
        assert is_relevant_role('Lead Scrum Master', patterns) == True

        # Should NOT match
        assert is_relevant_role('Agile Coach', patterns) == False


class TestIntegrationWithRealPatterns:
    """Test with actual patterns from config file"""

    def test_real_patterns_data_roles(self):
        """Test with real patterns loaded from config"""
        patterns = load_title_patterns()

        if not patterns:
            pytest.skip("Config file not found, skipping real pattern tests")

        # Data Scientist variations (from validation results)
        assert is_relevant_role('Analytics Lead', patterns) == True
        assert is_relevant_role('Principal Data Scientist', patterns) == True
        assert is_relevant_role('Senior ML Engineer', patterns) == True
        assert is_relevant_role('Applied Scientist', patterns) == True  # "Applied Scientist" matches, but not "Applied Research Scientist"
        assert is_relevant_role('Research Scientist - ML', patterns) == True
        assert is_relevant_role('Data Platform Engineer', patterns) == True

    def test_real_patterns_product_roles(self):
        """Test Product roles with real patterns"""
        patterns = load_title_patterns()

        if not patterns:
            pytest.skip("Config file not found, skipping real pattern tests")

        # Product Manager variations
        assert is_relevant_role('Staff Data PM', patterns) == True
        assert is_relevant_role('Product Manager - AI/ML', patterns) == True
        assert is_relevant_role('Technical Product Manager', patterns) == True
        assert is_relevant_role('Growth Product Manager', patterns) == True

    def test_real_patterns_delivery_roles(self):
        """Test Delivery roles with real patterns (added v1.3)"""
        patterns = load_title_patterns()

        if not patterns:
            pytest.skip("Config file not found, skipping real pattern tests")

        # Delivery Manager variations
        assert is_relevant_role('Delivery Manager', patterns) == True
        assert is_relevant_role('Senior Delivery Manager', patterns) == True
        assert is_relevant_role('Agile Delivery Lead', patterns) == True

        # Project Manager (must match)
        assert is_relevant_role('Project Manager', patterns) == True
        assert is_relevant_role('Technical Project Manager', patterns) == True
        assert is_relevant_role('Senior Project Manager', patterns) == True

        # Programme Manager
        assert is_relevant_role('Programme Manager', patterns) == True
        assert is_relevant_role('Program Manager', patterns) == True

        # Scrum Master
        assert is_relevant_role('Scrum Master', patterns) == True
        assert is_relevant_role('Senior Scrum Master', patterns) == True

    def test_real_patterns_project_vs_product_manager(self):
        """CRITICAL: Ensure Project Manager matches but Product Manager has its own pattern"""
        patterns = load_title_patterns()

        if not patterns:
            pytest.skip("Config file not found, skipping real pattern tests")

        # Both should match (via different patterns)
        assert is_relevant_role('Project Manager', patterns) == True
        assert is_relevant_role('Product Manager', patterns) == True

        # Technical versions should both match
        assert is_relevant_role('Technical Project Manager', patterns) == True
        assert is_relevant_role('Technical Product Manager', patterns) == True

    def test_real_patterns_negative_cases(self):
        """Test that known filtered roles are rejected with real patterns"""
        patterns = load_title_patterns()

        if not patterns:
            pytest.skip("Config file not found, skipping real pattern tests")

        # From validation notes - these should NOT match
        assert is_relevant_role('Account Executive', patterns) == False
        assert is_relevant_role('Sales Development Representative', patterns) == False
        assert is_relevant_role('Marketing Manager', patterns) == False
        assert is_relevant_role('Product Marketing Manager', patterns) == False
        assert is_relevant_role('Software Engineer', patterns) == False
        assert is_relevant_role('DevOps Engineer', patterns) == False
        assert is_relevant_role('HR Business Partner', patterns) == False
        assert is_relevant_role('Legal Counsel', patterns) == False
        assert is_relevant_role('Finance Analyst', patterns) == False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
