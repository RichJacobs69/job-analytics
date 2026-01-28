# LLM Classification Evaluation System

Human annotation and evaluation framework for job/employer classification quality.

## Quick Start

### 1. Install Dependencies

```bash
pip install streamlit
```

### 2. Extract Jobs for Annotation

```bash
# Extract 50 stratified jobs
python evals/annotation/extract_for_annotation.py --count 50

# Prioritize edge cases (ambiguous titles)
python evals/annotation/extract_for_annotation.py --count 50 --edge-cases

# Filter by source or family
python evals/annotation/extract_for_annotation.py --count 30 --source greenhouse
python evals/annotation/extract_for_annotation.py --count 20 --family data
```

### 3. Start Annotation App

```bash
streamlit run evals/annotation/app.py
```

Open http://localhost:8501 in your browser.

### 4. Export Gold Standard

Use the "Export to JSON" button in the app sidebar, or:

```python
from evals.annotation.db import export_to_json
export_to_json("evals/data/exports/gold_standard.json")
```

## Directory Structure

```
evals/
+-- annotation/
|   +-- app.py                    # Streamlit annotation UI
|   +-- db.py                     # SQLite database operations
|   +-- extract_for_annotation.py # Pull jobs from Supabase
|
+-- config/
|   +-- thresholds.yaml           # Pass/fail thresholds for regression
|
+-- data/
|   +-- gold_standard.db          # SQLite database (created automatically)
|   +-- exports/                   # JSON exports
|
+-- metrics/                       # (future) Evaluation metrics
+-- runners/                       # (future) Eval runners
+-- reports/                       # (future) Generated reports
```

## Database Schema

### gold_jobs
Human-annotated job classifications:
- `gold_job_family`: product, data, delivery, out_of_scope
- `gold_job_subfamily`: specific role type
- `gold_seniority`: junior, mid, senior, staff_principal, director_plus
- `gold_working_arrangement`: onsite, hybrid, remote, flexible, unknown
- `gold_track`: ic, management
- `gold_position_type`: full_time, part_time, contract, internship
- `gold_skills`: JSON array of skills
- `gold_summary`: ideal 2-3 sentence summary

### pending_jobs
Queue of jobs waiting to be annotated.

## Annotation Guidelines

1. **Job Family is Primary**: Title determines family, not description
2. **Seniority from Title First**: Use title markers (Senior, Staff, Director) before years
3. **Unknown is OK**: Use null/unknown when genuinely unclear
4. **Skills Must Be Explicit**: Only mark skills actually mentioned in posting
5. **Note Edge Cases**: Use the notes field for ambiguous situations

## Edge Cases to Watch

| Title Pattern | Correct Classification |
|--------------|----------------------|
| Data Product Manager | product / core_pm |
| Technical Project Manager | delivery / project_manager |
| Product Analyst | data / product_analytics or data_analyst |
| AI Engineer | Usually out_of_scope (SWE) |
| Applied Scientist | data / research_scientist_ml |
| Platform Engineer | out_of_scope (SWE) |
| Scrum Master | delivery / scrum_master |

## See Also

- `docs/architecture/Future Ideas/EPIC_LLM_CLASSIFICATION_EVALS.md` - Full epic
- `docs/schema_taxonomy.yaml` - Classification taxonomy
- `pipeline/classifier.py` - Current job classifier
