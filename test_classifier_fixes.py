"""
Quick test to verify classifier fixes for Research Scientist and Data Analyst roles
"""
import sys
from pathlib import Path

# Add both root and pipeline to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'pipeline'))

from pipeline.classifier import classify_job_with_claude

# Test cases that were being misclassified
test_jobs = [
    {
        "title": "Staff Applied Scientist- Embodied AI via Smarter Data",
        "company": "Wayve",
        "description": "We are looking for a Staff Applied Scientist to join our team working on embodied AI and autonomous driving. You will develop novel ML algorithms for perception, prediction, and planning using our large-scale driving dataset.",
        "expected_family": "data",
        "expected_subfamily": "research_scientist_ml"
    },
    {
        "title": "Research Scientist Intern, Embodied Foundation Models",
        "company": "Wayve",
        "description": "Research internship focused on foundation models for robotics and embodied AI. Work on cutting-edge ML research for autonomous systems.",
        "expected_family": "data",
        "expected_subfamily": "research_scientist_ml"
    },
    {
        "title": "Senior Data Analyst, GTM (Go-To-Market)",
        "company": "Fora Travel",
        "description": "We're looking for a Senior Data Analyst to support our Go-To-Market team. You'll build dashboards, run SQL queries, and provide insights to stakeholders using Looker and Snowflake.",
        "expected_family": "data",
        "expected_subfamily": "data_analyst"
    },
    {
        "title": "Business Intelligence Engineer 2",
        "company": "Behavox",
        "description": "Join our BI team building data models, semantic layers, and analytics infrastructure using dbt and SQL. You'll design dimensional models and metrics frameworks.",
        "expected_family": "data",
        "expected_subfamily": "analytics_engineer"
    }
]

print("Testing classifier fixes...\n")
print("=" * 80)

passed = 0
failed = 0

for i, test in enumerate(test_jobs, 1):
    print(f"\nTest {i}: {test['title']}")
    print("-" * 80)

    structured_input = {
        'title': test['title'],
        'company': test['company'],
        'description': test['description'],
        'location': None,
        'category': None,
        'salary_min': None,
        'salary_max': None,
    }

    try:
        result = classify_job_with_claude(
            job_text=test['description'],
            structured_input=structured_input
        )

        # Check job_family
        actual_family = result.get('role', {}).get('job_family')
        actual_subfamily = result.get('role', {}).get('job_subfamily')

        family_match = actual_family == test['expected_family']
        subfamily_match = actual_subfamily == test['expected_subfamily']

        status = "PASS" if (family_match and subfamily_match) else "FAIL"

        print(f"Expected: {test['expected_family']} -> {test['expected_subfamily']}")
        print(f"Actual:   {actual_family} -> {actual_subfamily}")
        print(f"Status:   {status}")

        if family_match and subfamily_match:
            passed += 1
        else:
            failed += 1

    except Exception as e:
        print(f"ERROR: {str(e)[:100]}")
        failed += 1

print("\n" + "=" * 80)
print(f"Results: {passed} passed, {failed} failed out of {len(test_jobs)} tests")
print("=" * 80)
