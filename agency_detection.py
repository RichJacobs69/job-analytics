"""
Agency Detection Module
Implements soft flagging of recruitment agencies using pattern matching.
This supplements the hard filter in fetch_adzuna_jobs.py.
"""

import yaml
from typing import Tuple

# Load agency configuration
with open('config/agency_blacklist.yaml', 'r') as f:
    AGENCY_CONFIG = yaml.safe_load(f)

# Extract config sections
HARD_FILTER = set(AGENCY_CONFIG['hard_filter'])
HIGH_CONF_KEYWORDS = set(AGENCY_CONFIG['keywords']['high_confidence'])
MED_CONF_KEYWORDS = set(AGENCY_CONFIG['keywords']['medium_confidence'])
HIGH_CONF_SUFFIXES = AGENCY_CONFIG['suffixes']['high_confidence']
MED_CONF_SUFFIXES = AGENCY_CONFIG['suffixes']['medium_confidence']
LEGITIMATE_COMPANIES = set(AGENCY_CONFIG['legitimate_companies'])

# Agency phrases in job descriptions
AGENCY_PHRASES = [
    'our client',
    'on behalf of',
    'exciting opportunity',
    'confidential client',
    'leading company',
    'growing business',
    'fantastic opportunity'
]


def detect_agency(employer_name: str, job_description: str = None) -> Tuple[bool, str]:
    """
    Detect if employer is a recruitment agency using pattern matching.
    
    This function implements the soft flagging logic - it should be called
    AFTER Claude classification to override/validate the is_agency field.
    
    Args:
        employer_name: Company name from job posting
        job_description: Full job description text (optional but improves accuracy)
    
    Returns:
        Tuple of (is_agency: bool, confidence: str)
        - is_agency: True if agency detected, False otherwise
        - confidence: 'high', 'medium', or 'low'
    
    Examples:
        >>> detect_agency("Tech Staffing Solutions")
        (True, 'high')
        
        >>> detect_agency("Accenture")  # In legitimate_companies list
        (False, 'low')
        
        >>> detect_agency("Data Consulting Partners")
        (True, 'medium')
    """
    if not employer_name:
        return False, 'low'
    
    name_lower = employer_name.lower().strip()
    
    # ========================================
    # 1. Check legitimate companies first (avoid false positives)
    # ========================================
    if name_lower in LEGITIMATE_COMPANIES:
        return False, 'low'
    
    # ========================================
    # 2. High confidence checks
    # ========================================
    
    # Check if in hard filter list (shouldn't happen, but safety check)
    if name_lower in HARD_FILTER:
        return True, 'high'
    
    # Count high-confidence keywords in name
    keyword_matches = sum(1 for kw in HIGH_CONF_KEYWORDS if kw in name_lower)
    if keyword_matches >= 2:
        return True, 'high'
    
    # Check for high-confidence suffixes
    for suffix in HIGH_CONF_SUFFIXES:
        if name_lower.endswith(suffix):
            return True, 'high'
    
    # ========================================
    # 3. Medium confidence checks
    # ========================================
    
    # Single high-confidence keyword = medium confidence
    if keyword_matches == 1:
        return True, 'medium'
    
    # Check for medium-confidence suffixes (with false positive filtering)
    for suffix in MED_CONF_SUFFIXES:
        if name_lower.endswith(suffix):
            # Avoid false positives for common business suffixes
            if suffix in ['solutions', 'consulting', 'partners', 'associates', 'group']:
                # Only flag if there's also a recruitment-related word
                if any(kw in name_lower for kw in ['talent', 'staff', 'recruit', 'search']):
                    return True, 'medium'
                # Otherwise, might be legitimate consulting/tech company
                continue
            else:
                return True, 'medium'
    
    # Count medium-confidence keywords
    med_keyword_matches = sum(1 for kw in MED_CONF_KEYWORDS if kw in name_lower)
    if med_keyword_matches >= 2:
        return True, 'medium'
    
    # ========================================
    # 4. Check job description (if provided)
    # ========================================
    
    if job_description:
        desc_lower = job_description.lower()
        
        # Check for agency phrases in description
        phrase_matches = sum(1 for phrase in AGENCY_PHRASES if phrase in desc_lower)
        
        if phrase_matches >= 2:
            # Multiple agency phrases = medium confidence
            return True, 'medium'
        elif phrase_matches == 1:
            # Single phrase + suspicious name = medium confidence
            if med_keyword_matches >= 1:
                return True, 'medium'
    
    # ========================================
    # 5. Default: Not an agency
    # ========================================
    
    return False, 'low'


def validate_agency_classification(
    employer_name: str,
    claude_is_agency: bool = None,
    claude_confidence: str = None,
    job_description: str = None
) -> Tuple[bool, str]:
    """
    Validate and override Claude's agency classification with pattern matching.
    
    Use this function to get the FINAL agency classification after Claude
    has returned its initial classification.
    
    Strategy:
    - If pattern matching says "high confidence agency", override Claude
    - If pattern matching says "medium confidence", use Claude as tiebreaker
    - If pattern matching says "low confidence", trust Claude
    
    Args:
        employer_name: Company name
        claude_is_agency: Claude's classification (True/False/None)
        claude_confidence: Claude's confidence ('high'/'medium'/'low'/None)
        job_description: Job text (optional)
    
    Returns:
        Tuple of (final_is_agency: bool, final_confidence: str)
    """
    # Run pattern detection
    pattern_is_agency, pattern_confidence = detect_agency(employer_name, job_description)
    
    # High confidence pattern match → override Claude
    if pattern_confidence == 'high':
        return pattern_is_agency, pattern_confidence
    
    # Medium confidence pattern match → use Claude as tiebreaker
    if pattern_confidence == 'medium':
        # If Claude also says agency, use high confidence
        if claude_is_agency is True:
            return True, 'high'
        # If Claude says not agency, use low confidence (conflicting signals)
        elif claude_is_agency is False:
            return False, 'low'
        # If Claude unsure, use pattern result
        else:
            return pattern_is_agency, pattern_confidence
    
    # Low confidence pattern (no match) → trust Claude if it detected something
    if claude_is_agency is not None:
        return claude_is_agency, claude_confidence or 'medium'
    
    # Default: not an agency
    return False, 'low'


# ============================================
# Test cases (run with: python agency_detection.py)
# ============================================

if __name__ == "__main__":
    print("Testing agency detection...\n")
    
    test_cases = [
        # (employer_name, expected_is_agency, description)
        ("Hays Recruitment", True, "Should catch 'recruitment' suffix"),
        ("Tech Staffing Solutions", True, "Should catch 'staffing' keyword"),
        ("Accenture", False, "Should recognize as legitimate consulting firm"),
        ("Data Consulting Partners", True, "Should catch consulting + partners pattern"),
        ("Google", False, "Should recognize as legitimate company"),
        ("Talent International Group", True, "Should catch multiple keywords"),
        ("Crimson", True, "Should catch from hard filter (if in list)"),
        ("Microsoft Solutions", False, "Should NOT flag tech company with 'solutions'"),
        ("Recruitment Solutions Ltd", True, "Should catch recruitment keyword"),
    ]
    
    print("=" * 70)
    for name, expected, reason in test_cases:
        is_agency, confidence = detect_agency(name)
        status = "✅" if is_agency == expected else "❌"
        print(f"{status} {name:40} → {is_agency:5} ({confidence:6}) - {reason}")
    print("=" * 70)
    
    print("\n\nTesting with job descriptions...\n")
    
    test_desc = """
    Our client, a leading technology company, is seeking a Data Scientist.
    This is an exciting opportunity to join a growing team.
    """
    
    is_agency, conf = detect_agency("Unknown Consulting", test_desc)
    print(f"Result with agency phrases: is_agency={is_agency}, confidence={conf}")
    print("Expected: True (medium) - has 'our client' and 'exciting opportunity'")