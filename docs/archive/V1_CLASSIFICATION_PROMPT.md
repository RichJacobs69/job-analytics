# V1 Classification Prompt (Archived 2026-02-14)

Replaced by V2 native Gemini prompt (`build_classification_prompt_v2`).

## Why V2

- **~51% fewer input tokens** (V2 is Gemini-native, no adaptation layer)
- **5x fewer JSON parse errors** on gemini-3-flash-preview (V1: 46%, V2: 10%)
- **Fewer fallbacks to gemini-2.5-flash-lite** in production (V1: 46%, V2: 10%)
- Agreement rates on 50-job eval with fallback enabled: subfamily 88%, family 96%, seniority 76%, arrangement 94%, track 98%
- Seniority diffs driven by V1 running on weaker fallback model vs V2 on primary

## V1 Architecture

V1 was a two-stage prompt:
1. `build_classification_prompt()` -- Claude-era base prompt with full skills ontology, verbose seniority examples, employer.department field
2. `adapt_prompt_for_gemini()` -- string-replacement layer that patched in Years-First seniority logic, null handling, and PM routing rules

V2 (`build_classification_prompt_v2()`) bakes everything into a single function, removing ~50 lines of skills ontology, redundant instructions, and the employer.department field.

---

## V1 Base Prompt: `build_classification_prompt()`

```python
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
            skills_list = ", ".join(skill_names[:10])
            if len(skill_names) > 10:
                skills_list += f", ... ({len(skill_names)} total)"
            category_skills.append(f"  - {family_code} ({family_label}): {skills_list}")

        if category_skills:
            skills_sections.append(f"\n**{parent_category.upper()} Skills:**\n" + "\n".join(category_skills))

    skills_ontology_text = "\n".join(skills_sections)

    MAX_DESCRIPTION_CHARS = 50000

    def truncate_text(text: str, max_chars: int) -> str:
        if not text or len(text) <= max_chars:
            return text
        return text[:max_chars] + "\n\n[DESCRIPTION TRUNCATED - exceeded maximum length]"

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

> **product** - Classify as 'product' if the job title contains:
  - "Product Manager", "PM" (but NOT "Project Manager"), "Product Owner", "PO"
  - "Product Lead", "Head of Product", "VP Product", "CPO"
  - "Product Director", "Group Product Manager", "GPM"
  - "Technical Product Manager" (strategy-focused, NOT Technical Project Manager)
  - "Growth PM", "Platform PM", "AI PM", "ML PM"

> **data** - Classify as 'data' if the job title contains:
  - "Data Scientist", "Data Engineer", "Data Analyst"
  - "Machine Learning Engineer", "ML Engineer", "MLE"
  - "Analytics Engineer", "Data Architect"
  - "Research Scientist", "AI Researcher"
  - "Product Analyst" (when focused on data/analytics)

> **delivery** - Classify as 'delivery' if the job title contains:
  - "Delivery Manager", "Delivery Lead", "Agile Delivery Manager"
  - "Project Manager" (execution-focused, NOT "Product Manager")
  - "Technical Project Manager" (execution-focused, NOT "Technical Product Manager")
  - "Programme Manager", "Program Manager", "Technical Program Manager"
  - "Scrum Master", "Agile Coach", "Iteration Manager"
  - "Release Manager"
  - "PMO Manager", "PMO Director", "Head of PMO"

> **out_of_scope** - Classify as 'out_of_scope' ONLY if:
  - Title is clearly NOT product, data, or delivery (e.g., "Software Engineer", "Marketing Manager", "Sales Rep")
  - Title contains: "Product Marketing", "Product Designer", "Product Support" (these are NOT PM roles)
  - Title contains: "Product Engineer" or "Platform Engineer" (these are SOFTWARE ENGINEERING roles, not PM roles)

# SENIORITY CLASSIFICATION RULES

**Priority Order (FOLLOW THIS STRICTLY):**
[from taxonomy['classification_guidance']['seniority']['priority_order']]

**Year Boundaries (use only when title is ambiguous):**
[from taxonomy['classification_guidance']['seniority']['year_boundary_rules']]

**Title Priority Examples (STUDY THESE):**
[from taxonomy['classification_guidance']['seniority']['title_priority_examples']]

**Track Distinction (IMPORTANT):**
[from taxonomy['classification_guidance']['seniority']['track_distinction']]

**Valid Seniority Levels:**
[from taxonomy['enums']['seniority_level']]

# JOB SUBFAMILY CLASSIFICATION

**Product Subfamilies:**
[from taxonomy['enums']['product_subfamily']]

**Data Subfamilies:**
[from taxonomy['enums']['data_subfamily']]

**Delivery Subfamilies:**
[from taxonomy['enums']['delivery_subfamily']]

**Classification Rules:**
- Data Analyst / Research Scientist / Applied Scientist titles -> ALWAYS data family
- Applied Scientist = research_scientist_ml (ML research, not software eng)
- BI Engineer -> analytics_engineer (data modeling focused)
- Project Manager / Programme Manager / Scrum Master -> ALWAYS delivery family
- Technical Project Manager -> delivery family (project_manager subfamily)
- Technical Product Manager -> product family (technical_pm subfamily)
[from taxonomy['classification_guidance']['job_subfamily']['key_distinctions']]

# REQUIRED OUTPUT SCHEMA

Return JSON with this EXACT structure:

{{
  "employer": {{
    "department": "product|data|delivery|null (only if explicitly stated)"
  }},
  "role": {{
    "job_subfamily": "string from subfamilies above",
    "seniority": "junior|mid|senior|staff_principal|director_plus|null",
    "track": "ic|management|null",
    "position_type": "full_time|part_time|contract|internship",
    "experience_range": "string or null"
  }},
  "location": {{
    "working_arrangement": "onsite|hybrid|remote|flexible|unknown"
  }},
  "compensation": {{
    "currency": "gbp|usd|null",
    "base_salary_range": {{
      "min": "number or null",
      "max": "number or null"
    }},
    "equity_eligible": true|false|null
  }},
  "skills": [
    {{"name": "Python", "family_code": "programming"}},
    {{"name": "SQL", "family_code": "programming"}}
  ],
  "summary": "2-3 sentence summary of day-to-day responsibilities"
}}

# SUMMARY GENERATION RULES
- Write 2-3 concise sentences describing what the person will do day-to-day
- Focus on key responsibilities, team context, and product/domain if mentioned
- Avoid generic phrases like "exciting opportunity" or "fast-paced environment"
- Be specific and actionable (e.g., "Build data pipelines" not "Work with data")
- Maximum 50 words

# WORKING ARRANGEMENT
- onsite: Must be in office full-time
- hybrid: Mix of office and remote with a fixed expectation
- remote: Fully remote, no office requirement
- flexible: Arrangement varies or is employee's choice
- unknown: Nothing stated or text is unclear about arrangement

# SKILLS ONTOLOGY - Use these family_codes when extracting skills
[~50 lines of skills ontology from taxonomy YAML]

# SKILLS EXTRACTION RULES - CRITICAL
- Extract ONLY skills that are EXPLICITLY NAMED in the job posting text
- DO NOT list skills from the ontology that aren't mentioned in the posting
- Use standard casing for skill names
- Match to family_code from the ontology above whenever possible
- If skill doesn't match any family in ontology, use family_code: null
- DO NOT infer skills

[JOB INPUT SECTION]

Return ONLY valid JSON with no markdown formatting or explanations."""

    return prompt
```

---

## V1 Gemini Adaptation Layer: `adapt_prompt_for_gemini()`

Applied as string replacements on top of the base prompt:

```python
def adapt_prompt_for_gemini(prompt: str) -> str:
    """
    Modify the classification prompt for Gemini-specific requirements:
    1. Years-First seniority logic (more normalized across companies)
    2. Consistent null handling (use JSON null, not string "null")
    3. Reinforce Product Manager title -> product family rule
    """

    # 1. SENIORITY: Replace Title-First with Years-First

    # Replaced priority order:
    # FROM: "Title is primary signal" / "Years as secondary signal"
    # TO:   "Years of experience is PRIMARY signal" / "Title is SECONDARY signal"

    # Replaced examples:
    # FROM: "Senior Data Scientist, 4 years -> senior (title wins)"
    # TO:   "Senior Data Scientist, 4 years -> mid (4 years = mid, ignore title)"
    #
    # FROM: "Staff Engineer, 8 years -> staff_principal (title wins)"
    # TO:   "Staff Engineer, 8 years -> senior (8 years = senior)"

    # 2. NULL HANDLING & PM ROUTING: Injected before output schema
    # - JSON null not string "null"
    # - PM title always -> product family
    # - Only core_pm/platform_pm/technical_pm/growth_pm/ai_ml_pm codes
    # - Compensation only if explicit number in text

    return prompt
```

---

## Key Differences: V1 vs V2

| Aspect | V1 (base + adapt) | V2 (native) |
|--------|-------------------|-------------|
| Skills ontology | ~50 lines in prompt | Removed (Python-side mapper handles family_code) |
| family_code in skills output | Yes (LLM assigns) | No (Python overwrites anyway) |
| employer.department | Included | Removed (unused downstream) |
| Seniority examples | 6-7 verbose examples | 4 genuinely ambiguous cases |
| Staff/Principal in title | Overridden by years | Honored as title signal (ignore years) |
| Prompt construction | Two functions + string replace | Single function |
| Avg input tokens | ~5,500 | ~2,700 |
