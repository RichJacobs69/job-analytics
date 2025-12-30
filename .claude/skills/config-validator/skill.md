---
name: config-validator
description: Validate and maintain YAML/JSON configuration files. Use when asked to check config consistency, add new mappings, update blocklists, or ensure configuration integrity.
---

# Config Validator

Ensure configuration files are valid, consistent, and complete. Manage mappings for job families, skills, agencies, and locations.

## When to Use This Skill

Trigger when user asks to:
- Validate configuration files
- Add new skill mappings
- Update the agency blocklist
- Add location patterns
- Check for config inconsistencies
- Debug classification issues related to config
- Ensure all subfamilies/skills are mapped

## Configuration Inventory

### Config Files

| File | Purpose | Format |
|------|---------|--------|
| `config/job_family_mapping.yaml` | Subfamily -> Family mapping | YAML |
| `config/skill_family_mapping.yaml` | Skill -> Family mapping | YAML |
| `config/agency_blacklist.yaml` | Recruitment agency blocklist | YAML |
| `config/location_mapping.yaml` | Location patterns and city codes | YAML |
| `config/greenhouse/title_patterns.yaml` | Title include/exclude patterns | YAML |
| `config/greenhouse/location_patterns.yaml` | Location filters for Greenhouse | YAML |
| `config/lever/title_patterns.yaml` | Title include/exclude patterns | YAML |
| `config/lever/location_patterns.yaml` | Location filters for Lever | YAML |
| `config/greenhouse/company_ats_mapping.json` | Company -> Slug mapping | JSON |
| `config/lever/company_mapping.json` | Company -> Slug mapping | JSON |

## Validation Checks

### 1. Job Family Mapping

**File:** `config/job_family_mapping.yaml`

**Structure:**
```yaml
subfamilies:
  core_de: data
  analytics_eng: data
  ml_eng: data
  data_sci: data
  bi_analyst: data
  core_pm: product
  technical_pm: product
  growth_pm: product
  ai_ml_pm: product
  platform_pm: product
```

**Validation rules:**
- All subfamilies used by classifier must be mapped
- All families must be valid: `data`, `product`, `delivery`, `out_of_scope`
- No duplicate subfamily keys

**Check for issues:**
```python
# Find unmapped subfamilies in database
SELECT DISTINCT job_subfamily
FROM enriched_jobs
WHERE job_subfamily NOT IN (
    'core_de', 'analytics_eng', 'ml_eng', 'data_sci', 'bi_analyst',
    'core_pm', 'technical_pm', 'growth_pm', 'ai_ml_pm', 'platform_pm'
);
```

### 2. Skill Family Mapping

**File:** `config/skill_family_mapping.yaml`

**Structure:**
```yaml
skills:
  python:
    family_code: programming
    domain: technical
  sql:
    family_code: data_query
    domain: technical
  # ... 800+ skills
```

**Validation rules:**
- All skills should have `family_code` and `domain`
- `family_code` should be from valid set
- `domain` should be from valid set (8 domains)
- No duplicate skill names (case-insensitive)

**Valid domains:**
- `technical`
- `data_platforms`
- `business`
- `methodology`
- `soft_skills`
- `industry`
- `tools`
- `cloud`

**Check for unmapped skills:**
```python
# From GHA logs, look for:
# "family_code: null" patterns
# These indicate skills the LLM extracted but aren't in mapping

# Or query database:
SELECT skill->>'name' as skill_name, COUNT(*) as occurrences
FROM enriched_jobs, jsonb_array_elements(skills) as skill
WHERE skill->>'family_code' IS NULL
GROUP BY skill->>'name'
ORDER BY occurrences DESC
LIMIT 20;
```

### 3. Agency Blocklist

**File:** `config/agency_blacklist.yaml`

**Structure:**
```yaml
agencies:
  # Exact matches (company name)
  - "Robert Half"
  - "Hays"
  - "Michael Page"

  # Pattern matches (for detection)
patterns:
  - "recruitment"
  - "staffing"
  - "talent acquisition"
```

**Validation rules:**
- No duplicate entries
- Entries should be lowercase for consistent matching
- Patterns should not be too broad (avoid false positives)

**Check effectiveness:**
```python
# Look for agency jobs that slipped through
SELECT employer_name, COUNT(*) as jobs
FROM enriched_jobs
WHERE LOWER(employer_name) LIKE '%recruit%'
   OR LOWER(employer_name) LIKE '%staffing%'
   OR LOWER(employer_name) LIKE '%talent%'
GROUP BY employer_name
ORDER BY jobs DESC;
```

### 4. Location Mapping

**File:** `config/location_mapping.yaml`

**Structure:**
```yaml
cities:
  london:
    code: lon
    country: GB
    patterns:
      - "london"
      - "uk"
      - "united kingdom"
    aliases:
      - "ldn"

  new_york:
    code: nyc
    country: US
    patterns:
      - "new york"
      - "nyc"
      - "manhattan"
      - "brooklyn"
```

**Validation rules:**
- All city codes used in DB should be mapped
- Patterns should be lowercase
- No overlapping patterns between cities
- Country codes should be valid ISO 2-letter codes

**Check for unmapped locations:**
```sql
-- Find jobs with unknown city codes
SELECT city_code, COUNT(*) as jobs
FROM enriched_jobs
WHERE city_code = 'unk' OR city_code IS NULL
GROUP BY city_code;

-- Find location text that failed to parse
SELECT location_raw, COUNT(*) as occurrences
FROM raw_jobs
WHERE id NOT IN (
    SELECT raw_job_id FROM enriched_jobs WHERE city_code != 'unk'
)
GROUP BY location_raw
ORDER BY occurrences DESC
LIMIT 20;
```

### 5. Title Patterns

**Files:** `config/greenhouse/title_patterns.yaml`, `config/lever/title_patterns.yaml`

**Structure:**
```yaml
include_patterns:
  - "data engineer"
  - "data scientist"
  - "product manager"
  - "machine learning"

exclude_patterns:
  - "intern"
  - "student"
  - "assistant"

exclude_exact:
  - "Recruiter"
  - "HR Manager"
```

**Validation rules:**
- Patterns should be lowercase (matching is case-insensitive)
- Include patterns should not be too broad
- Exclude patterns should not block valid roles
- No contradictory patterns (same pattern in include and exclude)

**Check effectiveness:**
```bash
# Review GHA logs for:
# "Filtered by title:" patterns
# Check if legitimate roles are being filtered out
```

## Adding New Mappings

### Adding a New Skill

```yaml
# In config/skill_family_mapping.yaml
skills:
  # Add new skill:
  dbt:
    family_code: data_transformation
    domain: data_platforms
```

**Before adding, check:**
1. Is this skill appearing frequently in jobs?
2. What family does it logically belong to?
3. Is there an existing similar skill? (e.g., "dbt" vs "dbt Core")

### Adding a New Agency

```yaml
# In config/agency_blacklist.yaml
agencies:
  - "New Recruitment Agency"
```

**Before adding, check:**
1. Is this definitely an agency, not a product company?
2. Are there variations of the name? (e.g., "ABC Recruiting" vs "ABC Recruitment")

### Adding a New Location Pattern

```yaml
# In config/location_mapping.yaml
cities:
  san_francisco:
    patterns:
      - "san francisco"
      - "sf"
      - "bay area"  # Add new pattern
```

**Before adding, check:**
1. Could this pattern match other cities?
2. Is it specific enough?
3. Test with existing data before deploying

## Validation Script

Create or run validation:

```python
"""Validate all configuration files."""
import yaml
import json
from pathlib import Path

def validate_job_family_mapping():
    """Check job family mapping completeness."""
    with open('config/job_family_mapping.yaml') as f:
        config = yaml.safe_load(f)

    valid_families = {'data', 'product', 'delivery', 'out_of_scope'}

    for subfamily, family in config['subfamilies'].items():
        if family not in valid_families:
            print(f"[ERROR] Invalid family '{family}' for subfamily '{subfamily}'")

    print(f"[OK] {len(config['subfamilies'])} subfamilies mapped")

def validate_skill_mapping():
    """Check skill mapping completeness."""
    with open('config/skill_family_mapping.yaml') as f:
        config = yaml.safe_load(f)

    skills = config.get('skills', {})
    missing_family = [s for s, v in skills.items() if not v.get('family_code')]
    missing_domain = [s for s, v in skills.items() if not v.get('domain')]

    if missing_family:
        print(f"[WARN] Skills missing family_code: {missing_family[:5]}...")
    if missing_domain:
        print(f"[WARN] Skills missing domain: {missing_domain[:5]}...")

    print(f"[OK] {len(skills)} skills mapped")

def validate_agency_blocklist():
    """Check agency blocklist."""
    with open('config/agency_blacklist.yaml') as f:
        config = yaml.safe_load(f)

    agencies = config.get('agencies', [])
    duplicates = [a for a in agencies if agencies.count(a) > 1]

    if duplicates:
        print(f"[WARN] Duplicate agencies: {set(duplicates)}")

    print(f"[OK] {len(agencies)} agencies in blocklist")

def validate_json_configs():
    """Validate JSON config files."""
    json_files = [
        'config/greenhouse/company_ats_mapping.json',
        'config/lever/company_mapping.json'
    ]

    for filepath in json_files:
        try:
            with open(filepath) as f:
                data = json.load(f)
            print(f"[OK] {filepath}: {len(data)} entries")
        except json.JSONDecodeError as e:
            print(f"[ERROR] {filepath}: Invalid JSON - {e}")

if __name__ == '__main__':
    validate_job_family_mapping()
    validate_skill_mapping()
    validate_agency_blocklist()
    validate_json_configs()
```

## Output Format

When validating configs, produce:

```markdown
## Config Validation Report

**Date:** [Date]
**Files Checked:** [Count]

### Validation Summary

| Config File | Status | Issues |
|-------------|--------|--------|
| job_family_mapping.yaml | OK/WARN/ERROR | [count] |
| skill_family_mapping.yaml | OK/WARN/ERROR | [count] |
| agency_blacklist.yaml | OK/WARN/ERROR | [count] |
| location_mapping.yaml | OK/WARN/ERROR | [count] |
| title_patterns.yaml | OK/WARN/ERROR | [count] |

### Issues Found

#### Critical (Blocks Pipeline)
- [Issue description and fix]

#### Warnings (Data Quality Impact)
- [Issue description and fix]

#### Info (Optimization Opportunities)
- [Suggestion]

### Recommended Changes

```yaml
# Add to skill_family_mapping.yaml:
new_skill:
  family_code: [family]
  domain: [domain]

# Add to agency_blacklist.yaml:
- "New Agency Name"
```

### Unmapped Items from Logs

| Type | Item | Occurrences | Suggested Mapping |
|------|------|-------------|-------------------|
| Skill | [name] | [count] | [family_code] |
| Location | [text] | [count] | [city_code] |
```

## Key Files to Reference

- `config/job_family_mapping.yaml` - Subfamily -> family
- `config/skill_family_mapping.yaml` - Skill -> family/domain
- `config/agency_blacklist.yaml` - Agency blocklist
- `config/location_mapping.yaml` - Location patterns
- `pipeline/job_family_mapper.py` - Uses job family config
- `pipeline/skill_family_mapper.py` - Uses skill config
- `pipeline/agency_detection.py` - Uses agency blocklist
- `pipeline/location_extractor.py` - Uses location config
