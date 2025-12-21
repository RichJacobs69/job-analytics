"""
Job classification using Claude 3.5 Haiku
UPDATED: Removed agency detection from Claude prompt (handled by Python pattern matching)
UPDATED: Claude no longer classifies job_family - it's auto-derived from job_subfamily via strict mapping
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

def build_classification_prompt(job_text: str, structured_input: dict = None) -> str:
    """
    Build classification prompt for Claude.
    
    Args:
        job_text: Raw job description text (for backwards compatibility)
        structured_input: Optional dict with structured fields:
            - title: Job title (from API)
            - company: Company name (from API)
            - category: Job category (from Adzuna API, e.g., "IT Jobs")
            - location: Location string
            - salary_min: Minimum salary (if available)
            - salary_max: Maximum salary (if available)
            - description: Job description text
    
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

    # Build skills ontology for the prompt
    skills_sections = []
    skills_ontology = taxonomy.get('skills_ontology', {})

    for parent_category, families in skills_ontology.items():
        category_skills = []
        for family_info in families:
            family_code = family_info['family']['code']
            family_label = family_info['family']['label']
            skill_names = family_info.get('names', [])

            # Format as: family_code (Label): skill1, skill2, skill3, ...
            skills_list = ", ".join(skill_names[:10])  # Limit to first 10 to save tokens
            if len(skill_names) > 10:
                skills_list += f", ... ({len(skill_names)} total)"

            category_skills.append(f"  - {family_code} ({family_label}): {skills_list}")

        if category_skills:
            skills_sections.append(f"\n**{parent_category.upper()} Skills:**\n" + "\n".join(category_skills))

    skills_ontology_text = "\n".join(skills_sections)

    # Build the job input section based on whether we have structured input
    if structured_input:
        job_input_section = "# JOB TO CLASSIFY\n\n"
        job_input_section += f"**Job Title:** {structured_input.get('title', 'Unknown')}\n"
        job_input_section += f"**Company:** {structured_input.get('company', 'Unknown')}\n"
        
        if structured_input.get('category'):
            job_input_section += f"**Category:** {structured_input.get('category')}\n"
        
        if structured_input.get('location'):
            job_input_section += f"**Location:** {structured_input.get('location')}\n"
        
        if structured_input.get('salary_min') or structured_input.get('salary_max'):
            salary_min = structured_input.get('salary_min', 'N/A')
            salary_max = structured_input.get('salary_max', 'N/A')
            job_input_section += f"**Salary Range:** {salary_min} - {salary_max}\n"
        
        job_input_section += f"\n**Job Description:**\n{structured_input.get('description', job_text)}"
    else:
        job_input_section = f"# JOB POSTING TO CLASSIFY\n\n{job_text}"
    
    prompt = f"""You are a precise job posting classifier. Analyze the job posting below and return structured JSON.

# CRITICAL INSTRUCTIONS
1. **JOB TITLE IS THE PRIMARY SIGNAL** for job_family classification - use it first
2. For seniority: PRIORITIZE TITLE over years of experience
3. For skills: Extract ONLY skills explicitly mentioned by name (no inference from context)
4. Return valid JSON matching the exact schema provided below
5. Use null for any field where information is not explicitly stated in title OR description

# JOB FAMILY CLASSIFICATION (MOST IMPORTANT)

**How to classify job_family - USE THE JOB TITLE FIRST:**

→ **product** - Classify as 'product' if the job title contains:
  - "Product Manager", "PM", "Product Owner", "PO"
  - "Product Lead", "Head of Product", "VP Product", "CPO"
  - "Product Director", "Group Product Manager", "GPM"
  - "Technical Product Manager"
  - "Growth PM", "Platform PM", "AI PM", "ML PM"
  
→ **data** - Classify as 'data' if the job title contains:
  - "Data Scientist", "Data Engineer", "Data Analyst"
  - "Machine Learning Engineer", "ML Engineer", "MLE"
  - "Analytics Engineer", "Data Architect"
  - "Research Scientist", "AI Researcher"
  - "Product Analyst" (when focused on data/analytics)
  
→ **out_of_scope** - Classify as 'out_of_scope' ONLY if:
  - Title is clearly NOT product or data (e.g., "Software Engineer", "Marketing Manager", "Sales Rep")
  - Title contains: "Product Marketing", "Product Designer", "Product Support" (these are NOT PM roles)

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

**Classification Rules:**
- Data Analyst / Research Scientist / Applied Scientist titles → ALWAYS data family
- Applied Scientist = research_scientist_ml (ML research, not software eng)
- BI Engineer → analytics_engineer (data modeling focused)
{chr(10).join('- ' + rule for rule in subfamily_guidance['key_distinctions'])}

# REQUIRED OUTPUT SCHEMA

Return JSON with this EXACT structure:

{{
  "employer": {{
    "department": "product|data|null (only if explicitly stated)",
    "company_size_estimate": "startup|scaleup|enterprise|null (infer from context if clear)"
  }},
  "role": {{
    "job_subfamily": "string from subfamilies above (required - choose the most specific match, or 'out_of_scope' if none fit)",
    "seniority": "junior|mid|senior|staff_principal|director_plus|null",
    "track": "ic|management|null",
    "position_type": "full_time|part_time|contract|internship (default: full_time)",
    "experience_range": "string or null (ONLY if explicitly stated, e.g. '5-7 years')"
  }},
  "location": {{
    "working_arrangement": "onsite|hybrid|remote|flexible|unknown (required - use 'unknown' if not stated or unclear)"
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

# WORKING ARRANGEMENT GUIDANCE (location is extracted separately from source metadata)
- "Remote or hybrid" → flexible
- "Hybrid (2 days office)" → hybrid
- "Remote-first" → remote
- "Office-based" or "Onsite" explicitly stated → onsite
- Nothing stated or truncated text → unknown

# SKILLS ONTOLOGY - Use these family_codes when extracting skills
{skills_ontology_text}

# SKILLS EXTRACTION RULES
- ONLY extract skills explicitly named in the posting
- Match to family_code from the ontology above whenever possible
- Common examples: "Python" → programming, "AWS" → cloud, "Snowflake" → warehouses_lakes, "dbt" → data_modeling
- If skill doesn't match any family in ontology, use family_code: null
- DO NOT infer skills from job requirements (e.g., don't add "Python" just because it's a data job)

{job_input_section}

Return ONLY valid JSON with no markdown formatting or explanations."""

    return prompt


# ============================================
# Classification Function
# ============================================

def classify_job_with_claude(job_text: str, verbose: bool = False, structured_input: dict = None) -> Dict:
    """
    Classify a job posting using Claude 3.5 Haiku.
    
    NOTE: This function does NOT populate is_agency or agency_confidence fields.
    Those are added by Python pattern matching after this function returns.
    
    Args:
        job_text: Full job posting text (used if structured_input not provided)
        verbose: If True, print prompt and raw response
        structured_input: Optional dict with structured fields from API:
            - title: Job title (CRITICAL for job_family classification)
            - company: Company name
            - category: Job category (e.g., "IT Jobs" from Adzuna)
            - location: Location string
            - salary_min: Minimum salary
            - salary_max: Maximum salary
            - description: Job description text
    
    Returns:
        Dictionary with classified job data matching schema
        (is_agency and agency_confidence will be null - added later by pattern matching)
    """
    prompt = build_classification_prompt(job_text, structured_input=structured_input)
    
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

        # Extract actual token usage from API response
        usage = response.usage
        haiku_input_price = 0.80  # $0.80 per 1M input tokens
        haiku_output_price = 2.40  # $2.40 per 1M output tokens

        cost_data = {
            'input_tokens': usage.input_tokens,
            'output_tokens': usage.output_tokens,
            'input_cost': (usage.input_tokens / 1_000_000) * haiku_input_price,
            'output_cost': (usage.output_tokens / 1_000_000) * haiku_output_price,
            'total_cost': (usage.input_tokens / 1_000_000) * haiku_input_price +
                         (usage.output_tokens / 1_000_000) * haiku_output_price
        }

        # Extract text from Claude's response
        response_text = response.content[0].text

        if verbose:
            print("\n" + "="*60)
            print("RAW CLAUDE RESPONSE")
            print("="*60)
            print(response_text[:500] + "...\n")
            print(f"Token usage: {usage.input_tokens} input, {usage.output_tokens} output")
            print(f"Cost: ${cost_data['total_cost']:.6f}\n")

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

        # Automatically derive job_family from job_subfamily using strict mapping
        # Claude no longer classifies job_family - we determine it deterministically
        if 'role' in result and result['role'].get('job_subfamily'):
            job_subfamily = result['role']['job_subfamily']

            # Special case: out_of_scope means job_family should also be out_of_scope
            if job_subfamily == 'out_of_scope':
                result['role']['job_family'] = 'out_of_scope'
            else:
                # Get correct family from mapping
                from job_family_mapper import get_correct_job_family
                job_family = get_correct_job_family(job_subfamily)

                if job_family:
                    result['role']['job_family'] = job_family
                    if verbose:
                        print(f"[INFO] job_family auto-assigned: {job_subfamily} -> {job_family}")
                else:
                    # Subfamily not in mapping - shouldn't happen but handle gracefully
                    if verbose:
                        print(f"[WARNING] Unknown job_subfamily '{job_subfamily}' - no family mapping found")
                    result['role']['job_family'] = None
        else:
            # No subfamily provided
            result['role']['job_family'] = None

        # Enrich skills with family codes using deterministic mapping
        # Claude extracts skill names; Python assigns families
        if 'skills' in result and result['skills']:
            from skill_family_mapper import enrich_skills_with_families
            result['skills'] = enrich_skills_with_families(result['skills'])
            if verbose:
                mapped = sum(1 for s in result['skills'] if s.get('family_code'))
                print(f"[INFO] Skills enriched: {mapped}/{len(result['skills'])} mapped to families")

        # Attach actual cost data to the result for tracking
        result['_cost_data'] = cost_data

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