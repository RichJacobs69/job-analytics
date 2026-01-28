# EPIC: LLM Classification Evaluation System

**Status:** Future Enhancement
**Created:** 2026-01-08
**Priority:** Medium-High
**Estimated Effort:** 2-3 weeks

## Overview

Build a comprehensive evaluation system for all LLM-powered classification in the job-analytics platform. This enables:
- Measuring classification accuracy against human-annotated ground truth
- Comparing model performance (Gemini 2.5 Flash-Lite vs Gemini 3.0 vs Claude)
- Regression testing when prompts or models change
- Quality assessment for subjective outputs (summaries, skills extraction)

## Current Classification Coverage

| Domain | Fields | Current Model | Future Model |
|--------|--------|---------------|--------------|
| **Job Classification** | job_family, job_subfamily, seniority, working_arrangement, track, position_type, skills, summary | Gemini 2.5 Flash-Lite | Gemini 3.0 (frontier) |
| **Employer Classification** | employer_industry (20 categories), company_size_estimate | Gemini 3.0 (frontier) | Gemini 3.0 (frontier) |

**Key Use Case:** Evals will enable comparison between Gemini 2.5 Flash-Lite and Gemini 3.0 for job classification to validate model upgrade.

## Problem Statement

Current evaluation (`tests/eval_gemini.py`) compares Gemini vs Claude Haiku, but:
1. Claude Haiku classifications are NOT validated ground truth
2. No human annotation to establish true accuracy
3. No evaluation of subjective quality (summary, skills completeness)
4. No systematic regression testing framework

## Architecture

```
                                +------------------------+
                                |   Gold Standard Set    |
                                |   (Human Annotated)    |
                                |   SQLite Database      |
                                +------------------------+
                                          |
          +-------------------------------+-------------------------------+
          |                               |                               |
          v                               v                               v
+-------------------+          +-------------------+          +-------------------+
|  Exact Match Eval |          | LLM-as-Judge Eval |          |  Streamlit App    |
|  (Classification) |          |   (Subjective)    |          | (Annotation Tool) |
+-------------------+          +-------------------+          +-------------------+
     |                              |                              |
     | - job_family                 | - summary quality            | - Human labeling
     | - job_subfamily              | - skills completeness        | - Disagreement resolution
     | - seniority                  | - edge case reasoning        | - Quality audit
     | - working_arrangement        |                              |
     | - employer_industry          |                              |
     +------------------------------+------------------------------+
                                    |
                                    v
                          +-------------------+
                          |   Eval Reports    |
                          |   & Regression    |
                          +-------------------+
```

## Components

### 1. Human Annotation System

**Streamlit Annotation App** (`evals/annotation/app.py`)
- Present job postings one at a time
- Dropdown/radio selections for each classification field
- Skills entry with autocomplete from taxonomy
- Summary quality rating
- Notes field for edge cases
- SQLite backend for persistence

**Gold Standard Schema:**
```sql
CREATE TABLE gold_jobs (
    id TEXT PRIMARY KEY,
    source_job_id INTEGER,
    source TEXT,
    title TEXT,
    company TEXT,
    raw_text TEXT,

    -- Gold labels
    gold_job_family TEXT,
    gold_job_subfamily TEXT,
    gold_seniority TEXT,
    gold_working_arrangement TEXT,
    gold_track TEXT,
    gold_position_type TEXT,
    gold_skills TEXT,  -- JSON array
    gold_summary TEXT,

    -- Metadata
    annotated_by TEXT,
    annotated_at TIMESTAMP,
    confidence TEXT,
    notes TEXT,

    -- Review status
    reviewed_by TEXT,
    reviewed_at TIMESTAMP
);

CREATE TABLE gold_employers (
    id TEXT PRIMARY KEY,
    canonical_name TEXT UNIQUE,
    display_name TEXT,
    gold_industry TEXT,
    gold_company_size TEXT,
    reasoning TEXT,
    annotated_by TEXT,
    annotated_at TIMESTAMP
);
```

**Target Dataset Size:**
- Initial: 100 jobs across all families/seniorities
- Phase 2: 250+ jobs with edge cases
- Employers: 50+ companies across industries

### 2. Exact Match Evaluation

For deterministic classification fields:

| Field | Target Accuracy | Notes |
|-------|-----------------|-------|
| job_family | >= 95% | Critical - gates all downstream |
| job_subfamily | >= 88% | Complex taxonomy |
| seniority | >= 80% | Ambiguous without years stated |
| working_arrangement | >= 85% | Often unstated |
| employer_industry | >= 85% | Subjective boundaries |

**Eval Runner:** `evals/runners/run_classification_eval.py`
- Load gold standard from SQLite
- Run classifier on each job
- Calculate accuracy, precision, recall per field
- Generate confusion matrices
- Output JSON report

### 3. LLM-as-Judge Evaluation

For subjective quality assessment:

**Summary Quality Judging:**
- Use Claude Sonnet as judge (stronger than classifier model)
- Score 1-5 on: accuracy, specificity, completeness, conciseness
- Target: average overall score >= 3.5

**Skills Completeness Judging:**
- Compare extracted skills vs gold skills
- Calculate precision (% extracted that are valid) and recall (% gold found)
- Target: recall >= 70%, precision >= 85%

**Judge Prompts:** `evals/prompts/judge_prompts.py`

### 4. Model Comparison Framework

Enable A/B comparison between models:

```python
# Compare Gemini 2.5 Flash-Lite vs Gemini 3.0 for job classification
python -m evals.runners.compare_models \
    --model-a gemini-2.5-flash-lite \
    --model-b gemini-3.0 \
    --dataset gold_jobs
```

Output:
- Side-by-side accuracy comparison
- Per-field performance delta
- Cost comparison (tokens, latency)
- Recommendation (upgrade/keep current)

### 5. Regression Testing

Automated checks before prompt or model changes:

```yaml
# evals/config/thresholds.yaml
thresholds:
  job_family: 0.95
  job_subfamily: 0.88
  seniority: 0.80
  working_arrangement: 0.85
  employer_industry: 0.85
  summary_overall: 3.5
  skills_recall: 0.70
```

Integration with CI/CD (optional future):
- Run evals on PR that modifies classifier.py
- Block merge if accuracy drops below threshold

## Directory Structure

```
evals/
+-- __init__.py
+-- config/
|   +-- thresholds.yaml           # Pass/fail thresholds
|   +-- taxonomy_snapshot.yaml    # Frozen taxonomy for consistency
|
+-- data/
|   +-- gold_standard.db          # SQLite database
|   +-- exports/                   # JSON exports for sharing
|
+-- annotation/
|   +-- app.py                    # Streamlit annotation tool
|   +-- extract_for_annotation.py # Pull jobs needing annotation
|
+-- metrics/
|   +-- classification.py         # Exact match metrics
|   +-- llm_judge.py             # LLM-as-judge scoring
|   +-- agreement.py             # Inter-annotator agreement (Cohen's Kappa)
|
+-- prompts/
|   +-- judge_prompts.py         # Summary/skills judge prompts
|
+-- runners/
|   +-- run_classification_eval.py
|   +-- run_summary_eval.py
|   +-- run_skills_eval.py
|   +-- run_employer_eval.py
|   +-- compare_models.py
|   +-- run_regression.py
|
+-- reports/
    +-- (generated JSON reports)
```

## Implementation Phases

### Phase 1: Foundation (3-4 days)
- [x] Create EPIC document
- [ ] Build Streamlit annotation app with SQLite
- [ ] Create extract_for_annotation.py script
- [ ] Annotate initial 50 jobs

### Phase 2: Core Evals (3-4 days)
- [ ] Implement exact-match eval runner
- [ ] Add confusion matrix generation
- [ ] Implement model comparison framework
- [ ] Annotate additional 50 jobs (total 100)

### Phase 3: LLM-as-Judge (2-3 days)
- [ ] Implement summary quality judge
- [ ] Implement skills completeness judge
- [ ] Add aggregate quality metrics

### Phase 4: Employer Evals (2 days)
- [ ] Add employer annotation to Streamlit app
- [ ] Implement employer industry eval
- [ ] Annotate 50 employers

### Phase 5: Automation (2-3 days)
- [ ] Regression test runner with thresholds
- [ ] JSON report generation
- [ ] (Optional) GitHub Actions integration

## Success Criteria

1. **Gold Standard Dataset:** 250+ annotated jobs, 50+ annotated employers
2. **Classification Accuracy:** Meet or exceed thresholds defined above
3. **Model Comparison:** Validated decision to upgrade job classifier to Gemini 3.0
4. **Regression Safety:** No prompt changes deployed without passing eval

## Dependencies

- Streamlit (`pip install streamlit`)
- SQLite (built-in Python)
- Anthropic SDK (for LLM-as-judge with Claude)
- Existing pipeline infrastructure

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Annotation fatigue | Start with 100 jobs, add incrementally |
| Annotator disagreement | Use 2-annotator review for edge cases |
| Taxonomy drift | Snapshot taxonomy version with gold set |
| Judge model changes | Pin judge model version in config |

## References

- `docs/schema_taxonomy.yaml` - Classification taxonomy
- `pipeline/classifier.py` - Current job classifier
- `pipeline/utilities/enrich_employer_metadata.py` - Employer classifier
- `tests/eval_gemini.py` - Existing (deprecated) eval approach

---

**Next Step:** Run `streamlit run evals/annotation/app.py` to start annotating jobs.
