"""
Job classification using Gemini LLM.
Classifies job postings into structured taxonomy (subfamily, seniority, skills, etc.)

Key design decisions:
- job_family is auto-derived from job_subfamily via strict mapping (not LLM-classified)
- skill family_codes are assigned by Python (skill_family_mapper.py), not the LLM
- Agency detection is handled by Python pattern matching, not the LLM
- Sanitizes string "null" values to Python None for database compatibility
"""
import os
import json
import yaml
import time
from typing import Dict, Any
from dotenv import load_dotenv


def sanitize_null_strings(obj: Any) -> Any:
    """
    Recursively convert string "null" values to Python None.

    LLMs sometimes return "null" as a string instead of JSON null,
    which causes database constraint violations.
    """
    if isinstance(obj, dict):
        return {k: sanitize_null_strings(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_null_strings(item) for item in obj]
    elif isinstance(obj, str) and obj.lower() == "null":
        return None
    return obj

load_dotenv()

# ============================================
# Configuration
# ============================================

from google import genai
from google.genai import types

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("Missing GOOGLE_API_KEY in .env file")
gemini_client = genai.Client(api_key=GOOGLE_API_KEY)

# Gemini pricing (per 1M tokens)
PROVIDER_COSTS = {
    "gemini": {"input": 0.10, "output": 0.40},
}

# Source-specific model overrides (default is Gemini 3 Flash)
# Only list sources that need a different model
SOURCE_MODEL_CONFIG = {
    "greenhouse": "gemini-2.5-flash",          # Stable (avoids JSON errors on complex titles)
    "adzuna": "gemini-2.5-flash",              # Cost-effective for high volume
}

GEMINI_DEFAULT_MODEL = "gemini-3-flash-preview"
GEMINI_FALLBACK_MODEL = "gemini-2.5-flash-lite"

_gemini_generation_config = types.GenerateContentConfig(
    temperature=0.1,
    max_output_tokens=8000,
    response_mime_type="application/json"
)

def get_gemini_model_for_source(source: str = None) -> str:
    """Get the appropriate Gemini model name based on data source."""
    if source and source.lower() in SOURCE_MODEL_CONFIG:
        return SOURCE_MODEL_CONFIG[source.lower()]
    return GEMINI_DEFAULT_MODEL

# Default model name for legacy classify_job_with_gemini()
_default_model_name = get_gemini_model_for_source("greenhouse")

# Track fallbacks for reporting
_model_fallback_count = 0

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

    delivery_subfamilies = "\n".join([
        f"  - {item['code']}: {item['label']} - {item['description']}"
        for item in taxonomy['enums']['delivery_subfamily']
    ])

    # Get classification guidance
    seniority_guidance = taxonomy['classification_guidance']['seniority']
    subfamily_guidance = taxonomy['classification_guidance']['job_subfamily']
    delivery_guidance = taxonomy['classification_guidance'].get('delivery_subfamily', {})

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

    # Truncate very long descriptions to avoid token limit errors
    # Claude 3.5 Haiku has 200K token limit; ~4 chars per token = 50K chars safe limit for description
    MAX_DESCRIPTION_CHARS = 50000

    def truncate_text(text: str, max_chars: int) -> str:
        if not text or len(text) <= max_chars:
            return text
        return text[:max_chars] + "\n\n[DESCRIPTION TRUNCATED - exceeded maximum length]"

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

        description = truncate_text(structured_input.get('description', job_text), MAX_DESCRIPTION_CHARS)
        job_input_section += f"\n**Job Description:**\n{description}"
    else:
        truncated_text = truncate_text(job_text, MAX_DESCRIPTION_CHARS)
        job_input_section = f"# JOB POSTING TO CLASSIFY\n\n{truncated_text}"
    
    prompt = f"""You are a precise job posting classifier. Analyze the job posting below and return structured JSON.

# CRITICAL INSTRUCTIONS
1. **JOB TITLE IS THE PRIMARY SIGNAL** for job_family classification - use it first
2. For seniority: PRIORITIZE TITLE over years of experience
3. For skills: Extract ONLY skills explicitly mentioned by name (no inference from context)
4. Return valid JSON matching the exact schema provided below
5. Use null for any field where information is not explicitly stated in title OR description
6. For compensation: ONLY extract salary if a specific numeric salary or range is explicitly written in the description (e.g. "$120,000 - $150,000" or "70,000 GBP"). Return null if no salary figure is stated. Do NOT estimate or infer salary.

# JOB FAMILY CLASSIFICATION (MOST IMPORTANT)

**How to classify job_family - USE THE JOB TITLE FIRST:**

→ **product** - Classify as 'product' if the job title contains:
  - "Product Manager", "PM" (but NOT "Project Manager"), "Product Owner", "PO"
  - "Product Lead", "Head of Product", "VP Product", "CPO"
  - "Product Director", "Group Product Manager", "GPM"
  - "Technical Product Manager" (strategy-focused, NOT Technical Project Manager)
  - "Growth PM", "Platform PM", "AI PM", "ML PM"

→ **data** - Classify as 'data' if the job title contains:
  - "Data Scientist", "Data Engineer", "Data Analyst"
  - "Machine Learning Engineer", "ML Engineer", "MLE"
  - "Analytics Engineer", "Data Architect"
  - "Research Scientist", "AI Researcher"
  - "Product Analyst" (when focused on data/analytics)

→ **delivery** - Classify as 'delivery' if the job title contains:
  - "Delivery Manager", "Delivery Lead", "Agile Delivery Manager"
  - "Project Manager" (execution-focused, NOT "Product Manager")
  - "Technical Project Manager" (execution-focused, NOT "Technical Product Manager")
  - "Programme Manager", "Program Manager", "Technical Program Manager"
  - "Scrum Master", "Agile Coach", "Iteration Manager"
  - "Release Manager"
  - "PMO Manager", "PMO Director", "Head of PMO"

→ **out_of_scope** - Classify as 'out_of_scope' ONLY if:
  - Title is clearly NOT product, data, or delivery (e.g., "Software Engineer", "Marketing Manager", "Sales Rep")
  - Title contains: "Product Marketing", "Product Designer", "Product Support" (these are NOT PM roles)
  - Title contains: "Product Engineer" or "Platform Engineer" (these are SOFTWARE ENGINEERING roles, not PM roles)

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

**Delivery Subfamilies:**
{delivery_subfamilies}

**Classification Rules:**
- Data Analyst / Research Scientist / Applied Scientist titles → ALWAYS data family
- Applied Scientist = research_scientist_ml (ML research, not software eng)
- BI Engineer → analytics_engineer (data modeling focused)
- Project Manager / Programme Manager / Scrum Master → ALWAYS delivery family
- Technical Project Manager → delivery family (project_manager subfamily)
- Technical Product Manager → product family (technical_pm subfamily)
{chr(10).join('- ' + rule for rule in subfamily_guidance['key_distinctions'])}

# REQUIRED OUTPUT SCHEMA

Return JSON with this EXACT structure:

{{
  "employer": {{
    "department": "product|data|delivery|null (only if explicitly stated)"
  }},
  "role": {{
    "job_subfamily": "string from subfamilies above (required - choose the most specific match, or 'out_of_scope' if none fit)",
    "seniority": "junior|mid|senior|staff_principal|director_plus|null",
    "track": "ic|management|null",
    "position_type": "full_time|part_time|contract|internship (default: full_time)",
    "experience_range": "string or null (ONLY if explicitly stated, e.g. '5-7 years')"
  }},
  "location": {{
    "working_arrangement": "onsite|hybrid|remote|flexible|unknown"
  }},
  "compensation": {{
    "currency": "gbp|usd|null (ONLY if salary is explicitly stated)",
    "base_salary_range": {{
      "min": "number or null (ONLY if explicitly stated as a number in the posting)",
      "max": "number or null (ONLY if explicitly stated as a number in the posting)"
    }},
    "equity_eligible": true|false|null
  }},
  "skills": [
    {{"name": "Python", "family_code": "programming"}},
    {{"name": "SQL", "family_code": "programming"}}
  ],
  "summary": "2-3 sentence summary of day-to-day responsibilities (required)"
}}

# SUMMARY GENERATION RULES
- Write 2-3 concise sentences describing what the person will do day-to-day
- Focus on key responsibilities, team context, and product/domain if mentioned
- Avoid generic phrases like "exciting opportunity" or "fast-paced environment"
- Be specific and actionable (e.g., "Build data pipelines" not "Work with data")
- Maximum 50 words

# WORKING ARRANGEMENT
- onsite: Must be in office full-time (e.g. "5 days in office", "on-site", "office-based", no WFH option mentioned)
- hybrid: Mix of office and remote with a fixed expectation (e.g. "3 days in office", "hybrid 2 days/week")
- remote: Fully remote, no office requirement (e.g. "remote", "work from anywhere", "remote-first")
- flexible: Arrangement varies or is employee's choice (e.g. "remote or hybrid", "WFH but may vary by team", "flexible work arrangement")
- unknown: Nothing stated or text is unclear about arrangement

# SKILLS ONTOLOGY - Use these family_codes when extracting skills
{skills_ontology_text}

# SKILLS EXTRACTION RULES - CRITICAL
- Extract ONLY skills that are EXPLICITLY NAMED in the job posting text
- DO NOT list skills from the ontology that aren't mentioned in the posting
- Use standard casing for skill names: "Python" not "python", "SQL" not "sql", "JIRA" not "Jira". Match the casing shown in the skills ontology above
- Match to family_code from the ontology above whenever possible
- Common examples: "Python" → programming, "AWS" → cloud, "Snowflake" → warehouses_lakes
- If skill doesn't match any family in ontology, use family_code: null
- DO NOT infer skills (e.g., don't add "Python" just because it's a data job)

{job_input_section}

Return ONLY valid JSON with no markdown formatting or explanations."""

    return prompt


# ============================================
# Gemini Prompt Adaptation
# ============================================

def adapt_prompt_for_gemini(prompt: str) -> str:
    """
    Modify the classification prompt for Gemini-specific requirements:
    1. Years-First seniority logic (more normalized across companies)
    2. Consistent null handling (use JSON null, not string "null")
    3. Reinforce Product Manager title -> product family rule
    """
    # ===========================================
    # 1. SENIORITY: Years-First Logic
    # ===========================================
    old_priority = """**Priority Order (FOLLOW THIS STRICTLY):**
- **Title is primary signal**: If title explicitly states level (Junior, Senior, Staff, Principal, Director), use that as primary classification
- **Years as secondary signal**: Use experience years only when title is ambiguous (e.g., 'Data Scientist' without level qualifier)
- **When both present**: If title and years conflict, prioritize title unless conflict is extreme (e.g., 'Junior' with 15 years)"""

    new_priority = """**Priority Order (FOLLOW THIS STRICTLY):**
- **Years of experience is PRIMARY signal**: Use explicitly stated years to determine seniority level
- **Title is SECONDARY signal**: Only use title (Senior, Staff, etc.) when years are NOT stated
- **When both present**: Prioritize years over title for normalized cross-company comparison
- **When neither present**: Return null for seniority"""

    prompt = prompt.replace(old_priority, new_priority)

    old_examples = """**Title Priority Examples (STUDY THESE):**
- 'Senior Data Scientist, 4 years' -> senior (title wins over years)
- 'Staff Engineer, 8 years' -> staff_principal (title wins)
- 'Director of Data, 7 years' -> director_plus (title wins)
- 'Data Scientist, 7 years' -> senior (years guide when no level in title)
- 'Lead Data Scientist' -> senior (Lead = senior level)
- 'Principal PM, 9 years' -> staff_principal (title wins despite years suggesting senior)"""

    new_examples = """**Seniority Examples (STUDY THESE - Years First):**
- 'Senior Data Scientist, 4 years' -> mid (4 years = mid, ignore title)
- 'Data Scientist, 7 years' -> senior (7 years = senior)
- 'Staff Engineer, 8 years' -> senior (8 years = senior, not staff_principal)
- 'Data Scientist, 12 years' -> staff_principal (12 years = staff_principal)
- 'Director of Data, 7 years' -> director_plus (Director title = management track)
- 'Senior Data Scientist' (no years stated) -> senior (fall back to title)
- 'Data Scientist' (no years, no level) -> null (insufficient signal)"""

    prompt = prompt.replace(old_examples, new_examples)

    # ===========================================
    # 2. NULL HANDLING & PRODUCT MANAGER RULE
    # ===========================================
    extra_instructions = """
**CRITICAL RULES - READ BEFORE CLASSIFYING:**

1. **NULL VALUES**: When a field is unknown or not stated, use JSON null (not the string "null").
   - Correct: "seniority": null
   - Wrong: "seniority": "null"

2. **PRODUCT MANAGER TITLE RULE**: If the job title contains "Product Manager", "PM", or "GPM",
   it is ALWAYS a product subfamily, regardless of any qualifier words like "Data", "Technical", "Growth".
   - "Data Product Manager" -> job_subfamily: core_pm (NOT data family)
   - "Senior Data Product Manager, GTM" -> job_subfamily: core_pm
   - "Technical Product Manager" -> job_subfamily: technical_pm
   - "Growth PM" -> job_subfamily: growth_pm
   - "AI/ML PM" -> job_subfamily: ai_ml_pm
   - "Product Manager" (generic) -> job_subfamily: core_pm
   The word "Product Manager" in the title is the deciding factor.

   IMPORTANT: Use ONLY these exact product subfamily codes: core_pm, platform_pm, technical_pm, growth_pm, ai_ml_pm
   Do NOT invent new codes like "product_pm" - use "core_pm" for general PM roles.

3. **COMPENSATION**: Only return salary values if a specific number appears in the job description text (e.g. "$120,000", "70,000 GBP", "100k-130k"). If no salary is mentioned, return null for currency, base_salary_range.min, and base_salary_range.max. Never estimate or guess.

"""
    prompt = prompt.replace(
        "# REQUIRED OUTPUT SCHEMA",
        extra_instructions + "# REQUIRED OUTPUT SCHEMA"
    )

    return prompt


# ============================================
# V2 Prompt Builder (Tightened, Gemini-native)
# ============================================

def build_classification_prompt_v2(job_text: str, structured_input: dict = None) -> str:
    """
    Build a tightened classification prompt for Gemini.

    Compared to V1 + adapt_prompt_for_gemini():
    - Bakes in Years-First seniority, PM routing, null handling directly
    - Removes employer.department (unused downstream)
    - Removes family_code from skills output (Python overwrites via skill_family_mapper)
    - Removes skills ontology section (~50 lines saved)
    - Removes redundant instructions (skills rules stated once, compensation once)
    - Trims seniority examples from 11 to 4 genuinely ambiguous cases
    - No separate job_family section (family auto-derived from subfamily)

    Args:
        job_text: Raw job description text
        structured_input: Optional dict with structured fields from API
    """
    # Extract subfamilies from taxonomy
    product_subfamilies = "\n".join([
        f"    {item['code']}: {item['description']}"
        for item in taxonomy['enums']['product_subfamily']
    ])

    data_subfamilies = "\n".join([
        f"    {item['code']}: {item['description']}"
        for item in taxonomy['enums']['data_subfamily']
    ])

    delivery_subfamilies = "\n".join([
        f"    {item['code']}: {item['description']}"
        for item in taxonomy['enums']['delivery_subfamily']
    ])

    # Truncate very long descriptions
    MAX_DESCRIPTION_CHARS = 50000

    def truncate_text(text: str, max_chars: int) -> str:
        if not text or len(text) <= max_chars:
            return text
        return text[:max_chars] + "\n\n[DESCRIPTION TRUNCATED]"

    # Build job input section
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

        description = truncate_text(structured_input.get('description', job_text), MAX_DESCRIPTION_CHARS)
        job_input_section += f"\n**Job Description:**\n{description}"
    else:
        truncated_text = truncate_text(job_text, MAX_DESCRIPTION_CHARS)
        job_input_section = f"# JOB POSTING TO CLASSIFY\n\n{truncated_text}"

    prompt = f"""You are a precise job posting classifier. Return structured JSON.

# INSTRUCTIONS
1. Use the JOB TITLE as primary signal for subfamily classification.
2. Use YEARS OF EXPERIENCE as primary signal for seniority (title is secondary).
3. Extract ONLY skills explicitly named in the posting text.
4. Use JSON null (not the string "null") for unknown/unstated fields.

# ROLE CLASSIFICATION

Pick the most specific subfamily below. Family (product/data/delivery) is derived automatically from your subfamily choice.

**Product subfamilies** (title contains Product Manager, PM, GPM, Product Owner, PO):
{product_subfamilies}

**Data subfamilies** (title contains Data, ML, Analytics, Research Scientist):
{data_subfamilies}

**Delivery subfamilies** (title contains Project Manager, Programme Manager, Delivery Manager, Scrum Master):
{delivery_subfamilies}

**out_of_scope**: Title is clearly NOT product, data, or delivery (e.g. Software Engineer, Marketing Manager, Product Designer, Product Engineer).

**Key routing rules:**
- "Product Manager" / "PM" / "GPM" in title -> ALWAYS product subfamily, even with qualifiers like "Data", "Technical", "Growth".
  - "Data Product Manager" -> core_pm (NOT data family)
  - "Technical Product Manager" -> technical_pm
  - "Growth PM" -> growth_pm
  - "AI/ML PM" -> ai_ml_pm
  - Generic "Product Manager" -> core_pm (never invent codes like "product_pm")
- "Technical Project Manager" -> delivery: project_manager (NOT product)
- "Project Manager" / "Programme Manager" / "Scrum Master" -> ALWAYS delivery
- "Data Analyst" / "Research Scientist" / "Applied Scientist" -> ALWAYS data
- Applied Scientist -> research_scientist_ml
- BI Engineer -> analytics_engineer
- "Product Engineer" / "Platform Engineer" -> out_of_scope (software engineering, not PM)
- "AI Engineer" -> out_of_scope UNLESS description involves training/fine-tuning models or MLOps
- Product Analytics vs Data Analyst: product_analytics = product metrics, user behavior, experiments; data_analyst = business reporting, dashboards, BI
- ML Engineer includes both classical ML AND GenAI/LLM work when focused on model development

# SENIORITY

**Years-First logic (use years as primary signal, title as fallback):**
- 0-2 years -> junior
- 3-5 years -> mid
- 6-10 years -> senior
- 11+ years -> staff_principal
- Staff/Principal/Distinguished title -> staff_principal (title signal, ignore years)
- Director/VP/Head of/C-level title -> director_plus (management track, ignore years)
- No years AND no level in title -> null

**Examples:**
- "Senior Data Scientist, 4 years" -> mid (4 years = mid, years override title)
- "Data Scientist, 7 years" -> senior (7 years = senior)
- "Staff Product Manager, 5 years" -> staff_principal (Staff in title = staff_principal, ignore years)
- "Senior Data Scientist" (no years stated) -> senior (fall back to title)

**Track:**
- ic = individual contributor (includes tech leads, PMs, Scrum Masters -- they manage work, not people)
- management = explicit people management (direct reports, hiring, performance reviews)
- PM/Programme Manager/Project Manager/Delivery Manager/Scrum Master default to ic unless description explicitly states people management

**Delivery seniority:** PM/Programme Manager/Project Manager without level qualifier (Senior, Staff, Director, Head) -> mid

# OUTPUT SCHEMA

Return JSON with this exact structure:

{{
  "role": {{
    "job_subfamily": "string (required -- from subfamilies above, or out_of_scope)",
    "seniority": "junior|mid|senior|staff_principal|director_plus|null",
    "track": "ic|management|null",
    "position_type": "full_time|part_time|contract|internship",
    "experience_range": "string or null (e.g. '5-7 years', only if explicitly stated)"
  }},
  "location": {{
    "working_arrangement": "onsite|hybrid|remote|flexible|unknown"
  }},
  "compensation": {{
    "currency": "gbp|usd|eur|sgd|null",
    "base_salary_range": {{
      "min": null,
      "max": null
    }},
    "equity_eligible": null
  }},
  "skills": [
    {{"name": "Python"}},
    {{"name": "SQL"}}
  ],
  "summary": "2-3 sentence summary"
}}

# FIELD NOTES
- position_type: default full_time if not stated
- working_arrangement:
  - onsite: full-time in office ("5 days in office", "office-based", no WFH option)
  - hybrid: fixed mix of office + remote ("3 days in office", "hybrid 2 days/week")
  - remote: fully remote, no office requirement ("remote", "work from anywhere", "remote-first")
  - flexible: varies or employee choice ("remote or hybrid", "WFH but may vary by team")
  - unknown: nothing stated or unclear
- compensation: ONLY extract if a specific number appears (e.g. "$120,000", "70k GBP"). Never estimate. Return null fields if no salary mentioned.
- equity_eligible: true if equity/stock mentioned, null otherwise

# SUMMARY
- 2-3 concise sentences on day-to-day responsibilities
- Focus on key duties, team context, product/domain
- No generic phrases ("exciting opportunity"). Be specific ("Build data pipelines").
- Maximum 50 words

# SKILLS
- Extract ONLY technical skills, tools, frameworks, methodologies, and domain techniques explicitly named in the posting text
- DO NOT infer skills from job type (don't add "Python" just because it's a data job)
- DO NOT extract: spoken languages (English, French, Japanese), department names (Engineering, Design), or job titles
- Use standard casing: "Python" not "python", "SQL" not "sql", "JIRA" not "Jira"

{job_input_section}

Return ONLY valid JSON."""

    return prompt


# ============================================
# Classification Functions
# ============================================

def classify_job_with_gemini(job_text: str, verbose: bool = False, structured_input: dict = None) -> Dict:
    """
    Classify a job posting using Gemini (legacy non-retry path).

    Production callers should use classify_job() which goes through
    classify_job_with_gemini_retry() for fallback support.
    """
    prompt = build_classification_prompt_v2(job_text, structured_input=structured_input)

    if verbose:
        print("\n" + "="*60)
        print("SENDING PROMPT TO GEMINI 2.5 FLASH")
        print("="*60)
        print(prompt[:500] + "...\n")

    try:
        start_time = time.time()
        response = gemini_client.models.generate_content(
            model=_default_model_name,
            contents=prompt,
            config=_gemini_generation_config
        )
        latency_ms = (time.time() - start_time) * 1000

        # Extract token counts
        usage = response.usage_metadata
        input_tokens = usage.prompt_token_count if usage else 0
        output_tokens = usage.candidates_token_count if usage else 0

        # Calculate cost
        costs = PROVIDER_COSTS["gemini"]
        input_cost = (input_tokens / 1_000_000) * costs["input"]
        output_cost = (output_tokens / 1_000_000) * costs["output"]
        total_cost = input_cost + output_cost

        cost_data = {
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'input_cost': input_cost,
            'output_cost': output_cost,
            'total_cost': total_cost,
            'latency_ms': latency_ms,
            'provider': 'gemini'
        }

        # Extract text from response
        response_text = response.text

        if verbose:
            print("\n" + "="*60)
            print("RAW GEMINI RESPONSE")
            print("="*60)
            print(response_text[:500] + "...\n")
            print(f"Token usage: {input_tokens} input, {output_tokens} output")
            print(f"Cost: ${total_cost:.6f} | Latency: {latency_ms:.0f}ms\n")

        # Clean response text
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        result = json.loads(response_text)

        # Sanitize string "null" values to Python None
        result = sanitize_null_strings(result)

        # Handle list responses (Gemini sometimes returns array for malformed input)
        if isinstance(result, list):
            if len(result) > 0 and isinstance(result[0], dict):
                result = result[0]
            else:
                raise ValueError("Expected dict, got empty or invalid list")

        # Validate result structure
        if not isinstance(result, dict):
            raise ValueError(f"Expected dict, got {type(result).__name__}")

        # Ensure employer dict exists and add placeholder agency fields
        if 'employer' not in result:
            result['employer'] = {}
        result['employer']['is_agency'] = None
        result['employer']['agency_confidence'] = None

        # Auto-derive job_family from job_subfamily
        role = result.get('role', {})
        if isinstance(role, dict) and role.get('job_subfamily'):
            job_subfamily = role['job_subfamily']

            if job_subfamily == 'out_of_scope':
                result['role']['job_family'] = 'out_of_scope'
            else:
                try:
                    from pipeline.job_family_mapper import get_correct_job_family
                except ImportError:
                    from job_family_mapper import get_correct_job_family
                job_family = get_correct_job_family(job_subfamily)

                if job_family:
                    result['role']['job_family'] = job_family
                    if verbose:
                        print(f"[INFO] job_family auto-assigned: {job_subfamily} -> {job_family}")
                else:
                    if verbose:
                        print(f"[WARNING] Unknown job_subfamily '{job_subfamily}' - no family mapping found")
                    result['role']['job_family'] = None
        else:
            if 'role' not in result:
                result['role'] = {}
            result['role']['job_family'] = None

        # Enrich skills with family codes
        if 'skills' in result and result['skills']:
            try:
                from pipeline.skill_family_mapper import enrich_skills_with_families
            except ImportError:
                from skill_family_mapper import enrich_skills_with_families
            result['skills'] = enrich_skills_with_families(result['skills'])
            if verbose:
                mapped = sum(1 for s in result['skills'] if s.get('family_code'))
                print(f"[INFO] Skills enriched: {mapped}/{len(result['skills'])} mapped to families")

        # Attach cost data
        result['_cost_data'] = cost_data

        return result

    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse Gemini response as JSON: {e}")
        print(f"Raw response: {response_text if 'response_text' in locals() else 'N/A'}")
        # Try to extract job_subfamily from partial JSON (truncated responses)
        import re
        if 'response_text' in locals():
            match = re.search(r'"job_subfamily":\s*"([^"]+)"', response_text)
            if match:
                subfamily = match.group(1)
                print(f"[INFO] Recovered job_subfamily from partial JSON: {subfamily}")
                # Return minimal result with recovered subfamily
                return {
                    'role': {'job_subfamily': subfamily},
                    '_partial': True,
                    '_cost_data': cost_data if 'cost_data' in locals() else None
                }
        raise
    except Exception as e:
        print(f"[ERROR] Gemini classification failed: {e}")
        raise


def classify_job_with_gemini_retry(job_text: str, verbose: bool = False, structured_input: dict = None, max_retries: int = 2, source: str = None, _use_fallback: bool = False) -> Dict:
    """
    Wrapper around classify_job_with_gemini that retries if summary is missing.
    Falls back to gemini-2.5-flash-lite if source-specific model fails.

    Args:
        job_text: Job posting text
        verbose: Enable verbose logging
        structured_input: Structured fields from API
        max_retries: Maximum attempts (default 2 = 1 initial + 1 retry)
        source: Data source (greenhouse, lever, ashby, workable, adzuna)
        _use_fallback: Internal flag to use fallback model

    Returns:
        Classification result with summary (or best attempt)
    """
    global _model_fallback_count

    total_cost_data = {
        'input_tokens': 0,
        'output_tokens': 0,
        'input_cost': 0.0,
        'output_cost': 0.0,
        'total_cost': 0.0,
        'latency_ms': 0.0,
        'provider': 'gemini',
        'attempts': 0
    }

    # Select model based on source and fallback flag
    if _use_fallback:
        model_name = GEMINI_FALLBACK_MODEL
    else:
        model_name = get_gemini_model_for_source(source)

    for attempt in range(max_retries):
        total_cost_data['attempts'] += 1

        try:
            result = _classify_job_with_model(job_text, model_name, verbose=verbose, structured_input=structured_input)
        except Exception as e:
            title = structured_input.get('title', 'Unknown') if structured_input else 'Unknown'
            print(f"[ERROR] Classification failed for '{title[:40]}': {e}")

            # If primary model failed and not already using fallback, try fallback
            if not _use_fallback:
                _model_fallback_count += 1
                print(f"[INFO] Falling back to {GEMINI_FALLBACK_MODEL}...")
                return classify_job_with_gemini_retry(
                    job_text, verbose=verbose, structured_input=structured_input,
                    max_retries=max_retries, source=source, _use_fallback=True
                )
            raise

        # Accumulate costs
        if '_cost_data' in result:
            cost = result['_cost_data']
            total_cost_data['input_tokens'] += cost.get('input_tokens', 0)
            total_cost_data['output_tokens'] += cost.get('output_tokens', 0)
            total_cost_data['input_cost'] += cost.get('input_cost', 0)
            total_cost_data['output_cost'] += cost.get('output_cost', 0)
            total_cost_data['total_cost'] += cost.get('total_cost', 0)
            total_cost_data['latency_ms'] += cost.get('latency_ms', 0)

        # Check if summary is present and non-empty
        summary = result.get('summary')
        if summary and isinstance(summary, str) and len(summary.strip()) > 10:
            # Success - attach accumulated cost data
            result['_cost_data'] = total_cost_data
            if _use_fallback:
                result['_used_fallback'] = True
            return result

        # Summary missing - log and retry
        if attempt < max_retries - 1:
            title = structured_input.get('title', 'Unknown') if structured_input else 'Unknown'
            print(f"[RETRY] Summary missing for '{title[:40]}' - retrying ({attempt + 2}/{max_retries})")

    # All retries exhausted - return best result with warning
    title = structured_input.get('title', 'Unknown') if structured_input else 'Unknown'
    print(f"[WARNING] Summary still missing after {max_retries} attempts for '{title[:40]}'")
    result['_cost_data'] = total_cost_data
    return result


def _classify_job_with_model(job_text: str, model_name: str, verbose: bool = False, structured_input: dict = None) -> Dict:
    """Internal function that classifies using a specific model."""
    prompt = build_classification_prompt_v2(job_text, structured_input=structured_input)

    if verbose:
        print("\n" + "="*60)
        print(f"SENDING PROMPT TO {model_name.upper()}")
        print("="*60)
        print(prompt[:500] + "...\n")

    start_time = time.time()
    response = gemini_client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=_gemini_generation_config
    )
    latency_ms = (time.time() - start_time) * 1000

    # Extract token counts
    usage = response.usage_metadata
    input_tokens = usage.prompt_token_count if usage else 0
    output_tokens = usage.candidates_token_count if usage else 0

    # Calculate cost
    costs = PROVIDER_COSTS["gemini"]
    input_cost = (input_tokens / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]
    total_cost = input_cost + output_cost

    cost_data = {
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'input_cost': input_cost,
        'output_cost': output_cost,
        'total_cost': total_cost,
        'latency_ms': latency_ms,
        'provider': 'gemini',
        'model': model_name
    }

    # Extract text from response
    response_text = response.text

    if verbose:
        print("RAW RESPONSE")
        print("="*60)
        print(response_text[:1000] + "...\n" if len(response_text) > 1000 else response_text)

    # Parse JSON
    result = json.loads(response_text)
    result = sanitize_null_strings(result)

    # Handle list responses
    if isinstance(result, list):
        result = result[0] if result else {}

    # Agency fields
    if 'employer' not in result:
        result['employer'] = {}
    result['employer']['is_agency'] = None
    result['employer']['agency_confidence'] = None

    # Auto-derive job_family from job_subfamily
    role = result.get('role', {})
    if isinstance(role, dict) and role.get('job_subfamily'):
        job_subfamily = role['job_subfamily']
        if job_subfamily == 'out_of_scope':
            result['role']['job_family'] = 'out_of_scope'
        else:
            try:
                from pipeline.job_family_mapper import get_correct_job_family
            except ImportError:
                from job_family_mapper import get_correct_job_family
            job_family = get_correct_job_family(job_subfamily)
            if job_family:
                result['role']['job_family'] = job_family
            else:
                result['role']['job_family'] = None
    else:
        if 'role' not in result:
            result['role'] = {}
        result['role']['job_family'] = None

    # Enrich skills
    if 'skills' in result and result['skills']:
        try:
            from pipeline.skill_family_mapper import enrich_skills_with_families
        except ImportError:
            from skill_family_mapper import enrich_skills_with_families
        result['skills'] = enrich_skills_with_families(result['skills'])

    result['_cost_data'] = cost_data
    return result


# ============================================
# Main Classification Function
# ============================================

def classify_job(job_text: str, verbose: bool = False, structured_input: dict = None, source: str = None) -> Dict:
    """
    Classify a job posting using Gemini.

    Uses source-specific models for optimal quality/cost balance.

    Args:
        job_text: Full job posting text
        verbose: If True, print prompt and raw response
        structured_input: Optional dict with structured fields from API
        source: Data source (greenhouse, lever, ashby, workable, adzuna) for model selection

    Returns:
        Dictionary with classified job data matching schema
    """
    return classify_job_with_gemini_retry(job_text, verbose=verbose, structured_input=structured_input, source=source)


# ============================================
# Fallback Tracking Helpers
# ============================================

def get_model_fallback_count() -> int:
    """Get the number of times classification fell back from primary to fallback model."""
    return _model_fallback_count


def reset_model_fallback_count():
    """Reset the fallback counter."""
    global _model_fallback_count
    _model_fallback_count = 0


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

    print("Testing classification with Gemini...")
    result = classify_job(test_job, verbose=True)

    print("\n" + "="*60)
    print("CLASSIFICATION RESULT")
    print("="*60)
    print(json.dumps(result, indent=2))
    print("\n[INFO] Model used:", result.get('_cost_data', {}).get('model', 'unknown'))
    print("[WARNING] Note: is_agency and agency_confidence are null here")
    print("   They will be populated by pattern matching in fetch script")