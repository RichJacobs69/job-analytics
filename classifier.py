"""
Job classification using Claude 3.5 Haiku
UPDATED: Removed agency detection from Claude prompt (handled by Python pattern matching)
"""
import os
import json
import yaml
from typing import Dict
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

# ============================================
# Configuration
# ============================================
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not ANTHROPIC_API_KEY:
    raise ValueError("Missing ANTHROPIC_API_KEY in .env file")

# Initialize Anthropic client
client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Load taxonomy
with open('docs/schema_taxonomy.yaml', 'r') as f:
    taxonomy = yaml.safe_load(f)

# ============================================
# Prompt Building
# ============================================

def build_classification_prompt(job_text: str) -> str:
    """
    Build classification prompt for Claude.
    
    NOTE: Agency detection is NOT included here - it's handled by Python
    pattern matching after Claude classification completes.
    """
    
    # Extract key enum values for the prompt
    seniority_levels = "\n".join([
        f"  - {item['code']}: {item['label']} - {item['description']}"
        for item in taxonomy['enums']['seniority_level']
    ])
    
    product_subfamilies = "\n".join([
        f"  - {item['code']}: {item['label']} - {item['description']}"
        for item in taxonomy['enums']['product_subfamily']
    ])
    
    data_subfamilies = "\n".join([
        f"  - {item['code']}: {item['label']} - {item['description']}"
        for item in taxonomy['enums']['data_subfamily']
    ])
    
    # Get classification guidance
    seniority_guidance = taxonomy['classification_guidance']['seniority']
    subfamily_guidance = taxonomy['classification_guidance']['job_subfamily']
    
    prompt = f"""You are a precise job posting classifier. Analyze the job posting below and return structured JSON.

# CRITICAL INSTRUCTIONS
1. Extract ONLY information explicitly stated in the posting - DO NOT infer or guess
2. For seniority: PRIORITIZE TITLE over years of experience
3. For skills: Extract ONLY skills explicitly mentioned by name (no inference from context)
4. Return valid JSON matching the exact schema provided below
5. Use null for any field where information is not explicitly stated

# SENIORITY CLASSIFICATION RULES

**Priority Order (FOLLOW THIS STRICTLY):**
{chr(10).join('- ' + rule for rule in seniority_guidance['priority_order'])}

**Year Boundaries (use only when title is ambiguous):**
{chr(10).join('- ' + rule for rule in seniority_guidance['year_boundary_rules'])}

**Title Priority Examples (STUDY THESE):**
{chr(10).join('- ' + example for example in seniority_guidance['title_priority_examples'])}

**Track Distinction (IMPORTANT):**
{chr(10).join('- ' + rule for rule in seniority_guidance['track_distinction'])}

**Valid Seniority Levels:**
{seniority_levels}

# JOB SUBFAMILY CLASSIFICATION

**Product Subfamilies:**
{product_subfamilies}

**Data Subfamilies:**
{data_subfamilies}

**Key Distinctions to Remember:**
{chr(10).join('- ' + rule for rule in subfamily_guidance['key_distinctions'])}

# REQUIRED OUTPUT SCHEMA

Return JSON with this EXACT structure:

{{
  "employer": {{
    "name": "string (required - exact company name)",
    "department": "product|data|null (only if explicitly stated)",
    "company_size_estimate": "startup|scaleup|enterprise|null (infer from context if clear)"
  }},
  "role": {{
    "title_display": "string (required - exact title from posting)",
    "job_family": "product|data|out_of_scope (required - MUST classify)",
    "job_subfamily": "string from subfamilies above (null only if out_of_scope)",
    "seniority": "junior|mid|senior|staff_principal|director_plus|null",
    "track": "ic|management|null",
    "position_type": "full_time|part_time|contract|internship (default: full_time)",
    "experience_range": "string or null (ONLY if explicitly stated, e.g. '5-7 years')"
  }},
  "location": {{
    "city_code": "lon|nyc|den (required - map using context)",
    "working_arrangement": "onsite|hybrid|remote|flexible (required - default: onsite if not stated)"
  }},
  "compensation": {{
    "currency": "gbp|usd|null",
    "base_salary_range": {{
      "min": number or null,
      "max": number or null
    }},
    "equity_eligible": true|false|null
  }},
  "skills": [
    {{"name": "Python", "family_code": "programming"}},
    {{"name": "SQL", "family_code": "programming"}}
  ]
}}

# LOCATION MAPPING GUIDANCE
- London, UK / London, England / Greater London → lon
- New York, NY / NYC / New York City / Manhattan / Brooklyn → nyc  
- Denver, CO / Denver Metro / Boulder, CO → den

# WORKING ARRANGEMENT GUIDANCE
- "Remote or hybrid" → flexible
- "Hybrid (2 days office)" → hybrid
- "Remote-first" → remote
- Nothing stated → onsite

# SKILLS EXTRACTION RULES
- ONLY extract skills explicitly named in the posting
- Match to family_code from taxonomy if possible (programming, deep_learning, warehouses_lakes, etc.)
- If skill family unclear, leave family_code as null
- DO NOT infer skills from job requirements (e.g., don't add "Python" because it's a data job)

# JOB POSTING TO CLASSIFY

{job_text}

Return ONLY valid JSON with no markdown formatting or explanations."""

    return prompt


# ============================================
# Classification Function
# ============================================

def classify_job_with_claude(job_text: str, verbose: bool = False) -> Dict:
    """
    Classify a job posting using Claude 3.5 Haiku.
    
    NOTE: This function does NOT populate is_agency or agency_confidence fields.
    Those are added by Python pattern matching after this function returns.
    
    Args:
        job_text: Full job posting text
        verbose: If True, print prompt and raw response
    
    Returns:
        Dictionary with classified job data matching schema
        (is_agency and agency_confidence will be null - added later by pattern matching)
    """
    prompt = build_classification_prompt(job_text)
    
    if verbose:
        print("\n" + "="*60)
        print("SENDING PROMPT TO CLAUDE")
        print("="*60)
        print(prompt[:500] + "...\n")
    
    try:
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=2000,
            temperature=0.1,  # Low temperature for consistency
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        # Extract text from Claude's response
        response_text = response.content[0].text
        
        if verbose:
            print("\n" + "="*60)
            print("RAW CLAUDE RESPONSE")
            print("="*60)
            print(response_text[:500] + "...\n")
        
        # Parse JSON (Claude should return clean JSON)
        # Strip any markdown code fences just in case
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        result = json.loads(response_text)
        
        # Ensure employer dict exists and add placeholder agency fields
        # (These will be overwritten by pattern matching in fetch script)
        if 'employer' not in result:
            result['employer'] = {}
        result['employer']['is_agency'] = None
        result['employer']['agency_confidence'] = None
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse Claude's response as JSON: {e}")
        print(f"Raw response: {response_text}")
        raise
    except Exception as e:
        print(f"[ERROR] Classification failed: {e}")
        raise


# ============================================
# Test Function
# ============================================

if __name__ == "__main__":
    # Simple test
    test_job = """
    Senior Data Scientist
    Acme Corp - London, UK
    Full-time • Hybrid
    
    We're looking for a Senior Data Scientist with 6-8 years experience.
    
    Requirements:
    - Python, SQL
    - PyTorch or TensorFlow
    - Experience with A/B testing
    
    Salary: £80,000 - £110,000
    """
    
    print("Testing Claude classification...")
    result = classify_job_with_claude(test_job, verbose=True)
    
    print("\n" + "="*60)
    print("CLASSIFICATION RESULT")
    print("="*60)
    print(json.dumps(result, indent=2))
    print("\n[WARNING] Note: is_agency and agency_confidence are null here")
    print("   They will be populated by pattern matching in fetch script")