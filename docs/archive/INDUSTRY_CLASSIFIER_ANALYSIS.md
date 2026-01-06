# Industry Classifier Analysis & Recommendations

**Date:** 2026-01-05
**Context:** Review of `pipeline/utilities/classify_employer_industry.py` output
**Issue:** Systematic misclassification, particularly over-assignment to `ai_ml`

---

## Problem Summary

The current industry classifier is biased by job titles rather than company identity. Since our dataset is filtered to **data, product, and delivery roles**, every company appears to be hiring ML/data talent, causing the LLM to over-classify as `ai_ml` or `data_infra`.

---

## Evidence: Misclassifications Observed

### ai_ml Over-Classification (Most Severe)

| Company | Assigned | Correct | Why Misclassified |
|---------|----------|---------|-------------------|
| greylock partners | ai_ml | financial_services | VC firm hiring data roles |
| medium | ai_ml | consumer | Publishing platform |
| oliver james | ai_ml | professional_services | Recruitment/staffing agency |
| huxley | ai_ml | professional_services | Staffing firm |
| cross river | ai_ml | fintech | Bank-as-a-service |
| accordion | ai_ml | professional_services | PE consulting |
| bse global | ai_ml | consumer | Sports/entertainment venue |
| mgma-acmpe | ai_ml | healthtech | Healthcare management assoc |
| diligent corporation | ai_ml | b2b_saas | GRC software |
| ursa major | ai_ml | hardware | Rocket propulsion company |
| greylock partners | ai_ml | financial_services | VC firm |
| jane street | ai_ml | financial_services | Quant trading firm |
| mozilla | ai_ml | consumer/devtools | Browser company |

### Staffing Agencies Systematically Misclassified

All staffing/recruiting agencies are being classified as `ai_ml` because they recruit for tech roles:
- oliver james
- huxley
- searchability
- huxley associates
- skillfinder international
- barrington james
- mason frank international
- many others...

### consumer Vertical Issues

Some legitimate, some questionable:

| Company | Assigned | Should Be | Notes |
|---------|----------|-----------|-------|
| SurveyMonkey | consumer | b2b_saas | Enterprise survey tool |
| Superhuman | consumer | b2b_saas | Business email client |
| compass | consumer | proptech | Real estate brokerage |
| Nooks | consumer | b2b_saas | Sales engagement platform |
| liftoff | consumer | martech | Mobile ad platform |

---

## Root Cause Analysis

### Current Classifier Input (Lines 114-139, 273-279)

```python
CLASSIFICATION_PROMPT = """...
COMPANY: {company_name}

SAMPLE JOB TITLES:
{job_titles}
...
"""

def get_sample_job_titles(canonical_name: str, limit: int = 5) -> List[str]:
    result = supabase.table("enriched_jobs").select(
        "title_display"
    ).eq("employer_name", canonical_name).limit(limit).execute()
    return [job["title_display"] for job in result.data]
```

### The Bias Mechanism

1. Our pipeline filters to data/product/delivery roles only
2. Classifier sees: Company X + ["Data Engineer", "ML Engineer", "Product Manager - AI"]
3. LLM infers: "This company does AI/ML work"
4. Reality: Company X is a bank/VC/staffing agency that just happens to hire these roles

---

## Recommendations

### Option 1: URL/Domain-Based Classification (Recommended)

Replace job titles with company domain. The LLM has training knowledge about what companies do based on their domains.

```python
CLASSIFICATION_PROMPT = """You are an industry classifier. Given a company name and domain, classify into ONE industry.

COMPANY: {company_name}
DOMAIN: {domain}

IMPORTANT: Classify based on the company's CORE PRODUCT/SERVICE, not who they hire.
- A VC firm hiring data engineers is still financial_services
- A staffing agency placing ML roles is still professional_services
- A bank with an AI team is still financial_services or fintech

INDUSTRY CATEGORIES:
{industry_list}

Return JSON: {{"industry": "...", "confidence": "...", "reasoning": "..."}}
"""
```

**Requires:** Adding `website` field to `employer_metadata` (may already exist or need sourcing)

### Option 2: Explicit Anti-Bias Rules

Add rule-based pre-classification for known categories:

```python
STAFFING_INDICATORS = [
    "staffing", "recruiting", "recruitment", "talent", "consultancy",
    "consulting", "partners", "associates", "group", "solutions"
]

VC_INDICATORS = ["ventures", "capital", "partners", "investment"]

BANK_INDICATORS = ["bank", "banking", "financial", "credit union"]

def pre_classify(company_name: str) -> Optional[str]:
    name_lower = company_name.lower()

    if any(ind in name_lower for ind in STAFFING_INDICATORS):
        return "professional_services"
    if any(ind in name_lower for ind in VC_INDICATORS):
        return "financial_services"
    if any(ind in name_lower for ind in BANK_INDICATORS):
        return "financial_services"

    return None  # Fall through to LLM
```

### Option 3: Hybrid Approach (Best)

Combine URL + explicit rules + fallback:

```python
def classify_employer(company_name: str, domain: Optional[str]) -> Dict:
    # 1. Rule-based pre-classification
    pre_result = pre_classify(company_name)
    if pre_result:
        return {"industry": pre_result, "confidence": "high", "reasoning": "Rule-based match"}

    # 2. LLM classification with domain (preferred) or name-only
    if domain:
        return llm_classify_with_domain(company_name, domain)
    else:
        return llm_classify_name_only(company_name)
```

### Option 4: Remove Job Titles, Keep Name Only

Simplest change - just remove job titles from the prompt:

```python
CLASSIFICATION_PROMPT = """You are an industry classifier. Given a company name, classify into ONE industry.

COMPANY: {company_name}

Classify based on your knowledge of this company. If unknown, make best inference from the name.
...
"""
```

**Pros:** Simple change, no new data needed
**Cons:** Less signal for obscure companies

---

## Additional Taxonomy Recommendations

### Consider Adding Verticals

| Proposed | Current Catch-All | Examples |
|----------|-------------------|----------|
| gaming | consumer | Riot Games, Epic, Take-Two, King |
| media_entertainment | consumer | Disney, Paramount, Warner, Netflix |
| social | consumer | Meta, Twitter/X, TikTok |

### Tighten ai_ml Definition

Current definition is too broad. Should be:
> "AI-first companies whose PRIMARY PRODUCT is AI/ML - foundation models, AI tools, ML platforms. NOT companies that USE AI."

Add explicit exclusions to prompt:
```
CLASSIFICATION RULES:
- ai_ml is ONLY for companies whose primary product IS AI/ML
- Companies that USE AI but sell something else go in their primary category
- Banks with ML teams = financial_services
- E-commerce with recommendation engines = ecommerce
```

---

## Implementation Priority

1. **Quick Win:** Remove job titles from prompt (Option 4) - immediate improvement
2. **Medium-term:** Add rule-based pre-classification for staffing/VC/banks (Option 2)
3. **Long-term:** Source company domains and implement URL-based classification (Option 1)

---

## Files to Modify

- `pipeline/utilities/classify_employer_industry.py` - Main classifier
- `docs/schema_taxonomy.yaml` - Taxonomy definitions (if adding verticals)
- `employer_metadata` table - Add `website` column if implementing URL approach

---

## Validation Approach

After implementing changes, re-run on a sample and spot-check:
1. All staffing agencies -> professional_services
2. All VC/PE firms -> financial_services
3. All banks -> financial_services or fintech
4. Gaming companies -> consumer (or gaming if added)
5. ai_ml count should drop significantly (currently over-represented)
