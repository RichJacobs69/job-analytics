# Epic: Semantic Search & Natural Language Interface

**Status:** Planning
**Created:** 2025-12-25
**Priority:** Medium-High (Enables new capabilities)

## Problem Statement

Current job search relies on structured filters (job_family, city, seniority) and exact keyword matching. This limits our ability to answer nuanced questions like:

- "Show me product roles that sound more like project management"
- "Find data science roles that emphasize experimentation over modeling"
- "Which companies have PM roles requiring strong technical backgrounds?"

These require **semantic understanding** of job descriptions, not just structured fields.

### User's Original Use Case

Detect project management patterns appearing in product manager roles:
- Project manager qualifications (PMP, delivery focus, stakeholder management)
- Output/delivery language vs outcome/impact language
- Waterfall/Agile process ownership vs product discovery

### Marketplace Questions This Enables

From `docs/marketplace_questions.md`, semantic search unlocks or enhances:

| ID | Question | Why Semantic Helps |
|----|----------|-------------------|
| MDS004 | "Is demand for my skill increasing?" | Skill mentions in context, not just keyword matches |
| TLC001 | "Which alternate titles describe similar work?" | Semantic similarity between job descriptions |
| SGU001-004 | Skills gap questions | Understanding skill context and co-occurrence |
| PT001-002 | "Do our job ads specify clear requirements?" | Semantic clarity scoring |
| CP002 | "Which skill combinations are competitors standardizing on?" | Semantic clustering of requirements |

## Scope Decisions

Based on data quality analysis (2025-12-25):

| Source | Avg Text Length | Job Count | Decision |
|--------|-----------------|-----------|----------|
| Greenhouse | 11,820 chars (9,538 after cleaning) | 2,910 | [INCLUDE] Full descriptions |
| Lever | 4,310 chars | 395 | [INCLUDE] Full descriptions |
| Adzuna | 504 chars | - | [EXCLUDE] Truncated by API, low semantic value |

**Current corpus:** 3,305 jobs from Greenhouse + Lever (as of 2025-12-25)

## Architecture

### Phase 1: Embedding Infrastructure (pgvector)

```
                                     Supabase PostgreSQL
                                    +-------------------+
                                    |                   |
raw_jobs ─────────────────────────> | raw_jobs          |
                                    |   - raw_text      |
                                    |                   |
                                    | job_embeddings    | <── NEW TABLE
                                    |   - raw_job_id    |
                                    |   - embedding     | (vector 1536)
                                    |   - text_hash     |
                                    |   - model_version |
                                    |                   |
enriched_jobs ───────────────────>  | enriched_jobs     |
                                    |                   |
                                    +-------------------+

Embedding Generation:
+----------------+     +------------------+     +----------------+
| raw_jobs       | --> | Text Preprocessor| --> | OpenAI API     |
| (greenhouse,   |     | - Strip forms    |     | text-embedding |
|  lever only)   |     | - Clean HTML     |     | -3-small       |
+----------------+     | - Normalize      |     +----------------+
                       +------------------+            |
                                                       v
                                              +----------------+
                                              | job_embeddings |
                                              +----------------+
```

### Phase 2: Smart Search

```
User Query: "PM roles with technical depth"
                    |
                    v
            +---------------+
            | Query Parser  |
            | - Extract     |
            |   filters     |
            | - Semantic    |
            |   component   |
            +---------------+
                    |
        +-----------+-----------+
        |                       |
        v                       v
+---------------+       +---------------+
| Structured    |       | Semantic      |
| Filter        |       | Search        |
| (SQL)         |       | (pgvector)    |
+---------------+       +---------------+
        |                       |
        v                       v
        +-----------+-----------+
                    |
                    v
            +---------------+
            | Result Ranker |
            | - Combine     |
            |   scores      |
            +---------------+
                    |
                    v
            [Ranked Job Results]
```

### Phase 3: Conversational Interface (RAG)

```
User: "What skills are trending in AI PM roles in London?"
                    |
                    v
            +-------------------+
            | Intent Detection  |
            | (Claude)          |
            +-------------------+
                    |
                    v
            +-------------------+
            | Hybrid Retrieval  |
            | - SQL filters     |
            | - Vector search   |
            +-------------------+
                    |
                    v
            +-------------------+
            | Response Gen      |
            | (Claude + context)|
            +-------------------+
                    |
                    v
            "Based on 47 AI PM roles in London,
             the most requested skills are..."
```

## Data Quality: Text Preprocessing

### Current Issues

1. **Greenhouse boilerplate**: Application forms, country dropdowns, legal text
2. **HTML artifacts**: Some descriptions contain markup
3. **Duplicate content**: Header/footer repeated across jobs

### Preprocessing Pipeline

```python
def preprocess_job_text(raw_text: str, source: str) -> str:
    """
    Clean job description for embedding.

    Steps:
    1. Strip HTML tags
    2. Remove application form boilerplate
    3. Remove phone/country picker lists
    4. Normalize whitespace
    5. Truncate to ~8000 tokens (embedding model limit)
    """
    # Source-specific cleaning
    if source == 'greenhouse':
        text = remove_greenhouse_boilerplate(text)
    elif source == 'lever':
        text = remove_lever_boilerplate(text)

    # Common cleaning
    text = strip_html(text)
    text = normalize_whitespace(text)
    text = truncate_to_token_limit(text, max_tokens=8000)

    return text
```

### Greenhouse Boilerplate Patterns to Remove

```
- "Create a Job Alert..."
- "Autofill with MyGreenhouse"
- "First Name*Last Name*Email*Phone..."
- Country/phone picker lists
- "Apply for this job*indicates a required field"
- Cookie consent text
- "Equal Opportunity Employer" standard blocks
```

### Quality Metrics

Track preprocessing effectiveness:
- `avg_text_length_before` vs `avg_text_length_after`
- `boilerplate_ratio` (% removed)
- `embedding_coverage` (% of jobs with valid embeddings)

## Implementation Plan

### Phase 1: Infrastructure (pgvector + Embeddings)

#### 1.1 Enable pgvector extension

```sql
-- Run in Supabase SQL editor
CREATE EXTENSION IF NOT EXISTS vector;
```

#### 1.2 Create job_embeddings table

```sql
CREATE TABLE job_embeddings (
    id SERIAL PRIMARY KEY,
    raw_job_id INTEGER NOT NULL REFERENCES raw_jobs(id),
    embedding vector(1536),  -- OpenAI text-embedding-3-small dimension
    text_hash TEXT NOT NULL,  -- MD5 of preprocessed text (for change detection)
    model_version TEXT NOT NULL DEFAULT 'text-embedding-3-small',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(raw_job_id)
);

-- Index for vector similarity search
CREATE INDEX ON job_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Index for joining with enriched_jobs
CREATE INDEX ON job_embeddings(raw_job_id);
```

#### 1.3 Create text preprocessor module

**File:** `pipeline/text_preprocessor.py`

```python
"""
Text preprocessing for semantic search embeddings.
"""
import re
import hashlib
from typing import Optional

# Greenhouse boilerplate patterns
GREENHOUSE_PATTERNS = [
    r'Create a Job Alert.*?Create alert',
    r'Apply for this job\*indicates a required field',
    r'Autofill with MyGreenhouse',
    r'First Name\*Last Name\*Email\*Phone.*?(?=\n\n|\Z)',
    r'\+\d{1,4}[A-Za-z\s&]+\+\d{1,4}',  # Phone country codes
]

def preprocess_for_embedding(raw_text: str, source: str) -> str:
    """Clean job text for embedding generation."""
    if not raw_text:
        return ""

    text = raw_text

    # Source-specific cleaning
    if source == 'greenhouse':
        for pattern in GREENHOUSE_PATTERNS:
            text = re.sub(pattern, '', text, flags=re.DOTALL | re.IGNORECASE)

    # Strip HTML
    text = re.sub(r'<[^>]+>', ' ', text)

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Truncate (OpenAI limit is 8191 tokens, ~32k chars conservative)
    if len(text) > 30000:
        text = text[:30000]

    return text

def compute_text_hash(text: str) -> str:
    """Generate hash for change detection."""
    return hashlib.md5(text.encode()).hexdigest()
```

#### 1.4 Create embedding generator

**File:** `pipeline/embedding_generator.py`

```python
"""
Generate embeddings for job descriptions using OpenAI API.
"""
import os
from typing import List, Dict, Optional
from openai import OpenAI
from pipeline.db_connection import supabase
from pipeline.text_preprocessor import preprocess_for_embedding, compute_text_hash

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "text-embedding-3-small"
BATCH_SIZE = 100  # OpenAI batch limit

def generate_embedding(text: str) -> List[float]:
    """Generate embedding for a single text."""
    response = client.embeddings.create(
        input=text,
        model=MODEL
    )
    return response.data[0].embedding

def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple texts."""
    response = client.embeddings.create(
        input=texts,
        model=MODEL
    )
    return [item.embedding for item in response.data]

def backfill_embeddings(
    sources: List[str] = ['greenhouse', 'lever'],
    batch_size: int = 50,
    dry_run: bool = False
) -> Dict:
    """
    Generate embeddings for all jobs from specified sources.

    Skips jobs that already have embeddings with matching text_hash.
    """
    stats = {
        'processed': 0,
        'skipped_existing': 0,
        'skipped_empty': 0,
        'errors': 0,
        'cost_estimate': 0.0
    }

    # Fetch jobs needing embeddings
    # ... implementation details ...

    return stats
```

#### 1.5 Create semantic search function

**File:** `pipeline/semantic_search.py`

```python
"""
Semantic search using pgvector.
"""
from typing import List, Dict, Optional
from pipeline.db_connection import supabase
from pipeline.embedding_generator import generate_embedding

def semantic_search(
    query: str,
    limit: int = 20,
    filters: Optional[Dict] = None,
    similarity_threshold: float = 0.3
) -> List[Dict]:
    """
    Search jobs by semantic similarity.

    Args:
        query: Natural language search query
        limit: Max results to return
        filters: Optional structured filters (job_family, city, etc.)
        similarity_threshold: Minimum similarity score (0-1)

    Returns:
        List of matching jobs with similarity scores
    """
    # Generate query embedding
    query_embedding = generate_embedding(query)

    # Build RPC call for hybrid search
    result = supabase.rpc('semantic_job_search', {
        'query_embedding': query_embedding,
        'match_threshold': similarity_threshold,
        'match_count': limit,
        'filter_job_family': filters.get('job_family') if filters else None,
        'filter_city': filters.get('city') if filters else None
    }).execute()

    return result.data

# SQL function for Supabase
SEMANTIC_SEARCH_SQL = """
CREATE OR REPLACE FUNCTION semantic_job_search(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.3,
    match_count int DEFAULT 20,
    filter_job_family text DEFAULT NULL,
    filter_city text DEFAULT NULL
)
RETURNS TABLE (
    enriched_job_id int,
    raw_job_id int,
    employer_name text,
    title_display text,
    job_family text,
    city_code text,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.id as enriched_job_id,
        e.raw_job_id,
        e.employer_name,
        e.title_display,
        e.job_family,
        e.city_code,
        1 - (emb.embedding <=> query_embedding) as similarity
    FROM job_embeddings emb
    JOIN enriched_jobs e ON e.raw_job_id = emb.raw_job_id
    WHERE
        1 - (emb.embedding <=> query_embedding) > match_threshold
        AND (filter_job_family IS NULL OR e.job_family = filter_job_family)
        AND (filter_city IS NULL OR e.city_code = filter_city)
    ORDER BY emb.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
"""
```

### Phase 2: Smart Search API

#### 2.1 Query parser

Parse user queries to extract structured filters + semantic component:

```python
def parse_search_query(query: str) -> Dict:
    """
    Parse natural language query into structured + semantic parts.

    Examples:
        "PM roles in London" ->
            {filters: {city: 'lon'}, semantic: 'PM roles'}

        "Data science with experimentation focus" ->
            {filters: {job_family: 'Data & Analytics'},
             semantic: 'experimentation focus'}
    """
    # Use Claude to extract structured filters
    # Return remaining text as semantic query
```

#### 2.2 Search endpoint

```python
from fastapi import FastAPI, Query

app = FastAPI()

@app.get("/search")
async def search_jobs(
    q: str = Query(..., description="Search query"),
    job_family: Optional[str] = None,
    city: Optional[str] = None,
    limit: int = 20
):
    """
    Hybrid search: structured filters + semantic similarity.
    """
    # Parse query
    parsed = parse_search_query(q)

    # Merge explicit filters with parsed filters
    filters = {**parsed['filters']}
    if job_family:
        filters['job_family'] = job_family
    if city:
        filters['city'] = city

    # Execute hybrid search
    results = semantic_search(
        query=parsed['semantic'],
        filters=filters,
        limit=limit
    )

    return {"results": results, "query": parsed}
```

### Phase 3: Conversational Interface

#### 3.1 RAG pipeline

```python
async def answer_question(question: str) -> str:
    """
    Answer natural language questions about job market.

    Uses RAG pattern:
    1. Parse intent and extract context requirements
    2. Retrieve relevant jobs via hybrid search
    3. Generate response with Claude
    """
    # Step 1: Parse intent
    intent = await parse_intent(question)

    # Step 2: Retrieve context
    if intent['requires_job_data']:
        jobs = semantic_search(
            query=intent['semantic_query'],
            filters=intent['filters'],
            limit=30
        )
        context = format_jobs_for_context(jobs)
    else:
        context = ""

    # Step 3: Generate response
    response = await claude.messages.create(
        model="claude-3-5-haiku-20241022",
        messages=[
            {"role": "system", "content": RAG_SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}
        ]
    )

    return response.content[0].text
```

## Cost Analysis

### Current Corpus (Measured 2025-12-25)

| Source | Job Count | Avg Tokens/Job | Total Tokens |
|--------|-----------|----------------|--------------|
| Greenhouse | 2,910 | 2,385 | 6.9M |
| Lever | 395 | 1,077 | 0.4M |
| **Total** | **3,305** | **2,228** | **7.4M** |

### Embedding Generation Costs (text-embedding-3-small)

| Scenario | Jobs | Tokens | Cost |
|----------|------|--------|------|
| Current corpus | 3,305 | 7.4M | **$0.15** |
| 10,000 jobs | 10,000 | 22.3M | **$0.45** |
| 20,000 jobs | 20,000 | 44.6M | **$0.89** |

**Rate:** $0.00002 per 1K tokens ($0.02 per 1M tokens)

### Ongoing Costs

| Activity | Est. Monthly Volume | Cost |
|----------|---------------------|------|
| New job embeddings | 500-1000 jobs | $0.02-0.04 |
| Search query embeddings | 1000 queries | $0.0004 |
| Claude RAG calls (Haiku) | 500 queries | $0.50-1.50 |
| **Total monthly** | - | **~$1-2** |

Note: The primary ongoing cost is Claude RAG calls, not embeddings.

### Storage (Supabase)

| Item | Size |
|------|------|
| 1536-dim vector | ~6KB per job |
| 10,000 jobs | ~60MB |
| Supabase free tier | 500MB included |

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `pipeline/text_preprocessor.py` | Create | Text cleaning for embeddings |
| `pipeline/embedding_generator.py` | Create | OpenAI embedding API client |
| `pipeline/semantic_search.py` | Create | pgvector search functions |
| `pipeline/rag_interface.py` | Create | Conversational interface |
| `wrappers/backfill_embeddings.py` | Create | One-time embedding generation |
| `wrappers/search_cli.py` | Create | CLI for testing search |
| `.env` | Modify | Add OPENAI_API_KEY |

## Dependencies

### Python Packages

```
openai>=1.0.0        # Embedding generation
pgvector             # Vector operations (if using Python client)
```

### Environment Variables

```
OPENAI_API_KEY=sk-...  # For embeddings (text-embedding-3-small)
```

## Testing Plan

### Phase 1 Tests

1. **Text preprocessor**: Verify boilerplate removal
2. **Embedding generation**: Verify vector dimensions, API calls
3. **pgvector queries**: Verify similarity search works

### Phase 2 Tests

1. **Query parser**: Test structured filter extraction
2. **Hybrid search**: Verify filter + semantic combination
3. **Relevance testing**: Manual evaluation of search results

### Phase 3 Tests

1. **RAG accuracy**: Test against marketplace questions
2. **PM vs Product Manager detection**: Original use case validation

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Embedding coverage | >95% of Greenhouse/Lever jobs | % with valid embeddings |
| Search relevance | Top-5 results contain answer | Manual evaluation |
| PM detection accuracy | >80% | Labeled test set |
| Query latency | <500ms | p95 response time |

## Rollout Plan

1. **Phase 1** (Infrastructure)
   - Enable pgvector
   - Create tables and indexes
   - Build text preprocessor
   - Generate embeddings for existing jobs

2. **Phase 2** (Smart Search)
   - Build query parser
   - Implement hybrid search
   - Create CLI for testing
   - Validate with sample queries

3. **Phase 3** (Conversational)
   - Build RAG pipeline
   - Create chat interface
   - Test against marketplace questions
   - Deploy to dashboard (future)

## Future Considerations

1. **Adzuna enrichment**: If we add full-text scraping for Adzuna, include those jobs
2. **Multi-modal**: Add company logos, charts to embeddings
3. **Fine-tuned embeddings**: Train custom model on job-specific semantics
4. **Real-time updates**: Embed new jobs as they're scraped
5. **Feedback loop**: Use search clicks to improve ranking

## Risks

| Risk | Mitigation |
|------|------------|
| OpenAI API costs spike | Set budget alerts, use caching |
| pgvector performance | Start with IVFFlat, upgrade to HNSW if needed |
| Text preprocessing removes important content | Manual review of sample preprocessed texts |
| Embedding model changes | Store model_version, support re-embedding |

## Open Questions

1. Should we expose search API publicly or keep internal?
2. How to handle jobs with very short descriptions after preprocessing?
3. Should we create reference embeddings for PM vs Product patterns as baselines?

## Sign-off

- [ ] Phase 1 complete (pgvector + embeddings)
- [ ] Phase 2 complete (smart search)
- [ ] Phase 3 complete (conversational interface)
- [ ] Deployed to production
