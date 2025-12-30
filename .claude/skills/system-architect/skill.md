---
name: system-architect
description: System architecture reviewer focused on simplicity, scalability, and productization readiness. Use when planning new features, reviewing architecture decisions, evaluating abstraction opportunities, or preparing for scale.
---

# System Architect

Review and guide architectural decisions with a focus on simplicity now, scalability later. Help navigate the balance between "good enough" and "production-ready".

## When to Use This Skill

Trigger when user asks to:
- Plan a new epic or major feature
- Review current architecture
- Decide whether to abstract or keep simple
- Evaluate frontend vs backend responsibilities
- Plan for productization or scaling
- Choose between technical approaches
- Review database schema changes
- Design API contracts

## Architecture Philosophy

**Guiding principles:**

1. **YAGNI (You Aren't Gonna Need It)** - Don't build for hypothetical futures
2. **Make it work, make it right, make it fast** - In that order
3. **Complexity is debt** - Every abstraction has maintenance cost
4. **Explicit over implicit** - Clarity beats cleverness
5. **Data flows downhill** - Clear input -> process -> output paths

## Current System Context

### Architecture Overview

```
Data Sources                    Pipeline                      Storage              Frontend
+------------+                 +------------------+          +----------+         +------------+
| Adzuna API |----+            |                  |          |          |         |            |
+------------+    |            | unified_job_     |          | Supabase |         | Next.js    |
                  +----------->| ingester.py      |--------->| Postgres |-------->| Dashboard  |
+------------+    |            |                  |          |          |         | (Vercel)   |
| Greenhouse |----+            | classifier.py    |          +----------+         +------------+
| Scraper    |    |            | (Gemini LLM)     |
+------------+    |            +------------------+
                  |
+------------+    |
| Lever      |----+
| Fetcher    |
+------------+
```

### Key Components

| Component | Location | Responsibility |
|-----------|----------|----------------|
| Scrapers | `scrapers/` | Fetch raw job data from sources |
| Ingester | `pipeline/unified_job_ingester.py` | Merge, dedupe, normalize |
| Classifier | `pipeline/classifier.py` | LLM enrichment (Gemini) |
| DB Layer | `pipeline/db_connection.py` | Supabase CRUD operations |
| API | `portfolio-site/app/api/` | Next.js API routes |
| Dashboard | `portfolio-site/` | React visualization |

### Data Flow

```
Raw Job -> Deduplication -> Title Filter -> Location Filter -> Agency Filter
    -> LLM Classification -> Enriched Job -> Supabase -> API -> Dashboard
```

## Architecture Review Checklist

### 1. Separation of Concerns

**Questions to evaluate:**
- Is each module doing one thing well?
- Are there modules with too many responsibilities?
- Is business logic leaking into data access layers?
- Are scrapers independent of each other?

**Current concerns:**
| Module | Primary Concern | Watch For |
|--------|-----------------|-----------|
| `classifier.py` | LLM interaction | Don't add DB logic here |
| `db_connection.py` | Data persistence | Don't add business rules |
| `unified_job_ingester.py` | Data merging | Getting too large? |
| Scrapers | Data extraction | Source-specific only |

### 2. Abstraction Decisions

**When to abstract:**
- Pattern used in 3+ places
- Clear interface boundary exists
- Abstraction simplifies calling code
- Team will maintain it long-term

**When NOT to abstract:**
- Only 1-2 uses (wait for third)
- "Might need it someday"
- Abstraction adds more code than it saves
- You're the only user

**Current abstraction candidates:**
| Pattern | Occurrences | Recommendation |
|---------|-------------|----------------|
| Supabase client setup | Multiple files | [DONE] db_connection.py |
| Retry logic | Scrapers + API calls | Consider shared utility |
| Config loading | Per-source | Keep separate (different schemas) |
| Logging setup | Each module | Consider shared logger config |

### 3. Frontend/Backend Boundary

**Current split:**
- **Backend (job-analytics):** Data pipeline, classification, storage
- **Frontend (portfolio-site):** API routes, visualization, user interaction

**Questions to evaluate:**
- Are API routes doing too much computation?
- Should any frontend logic move to backend?
- Is data transformation happening in the right place?

**Principles:**
| Do in Backend | Do in Frontend |
|---------------|----------------|
| Heavy computation | UI state management |
| Data aggregation | User interactions |
| LLM calls | Filtering/sorting cached data |
| Scheduled jobs | Real-time updates |
| Sensitive operations | Presentation logic |

### 4. Database Schema

**Current tables:**
- `raw_jobs` - Unprocessed job data
- `enriched_jobs` - LLM-classified jobs

**Schema review questions:**
- Are indexes appropriate for query patterns?
- Is denormalization justified by read patterns?
- Are there missing constraints?
- Is JSONB being used appropriately?

**Schema change principles:**
1. Additive changes preferred (new columns nullable)
2. Migrations must be reversible
3. Document breaking changes
4. Consider API compatibility

### 5. Scaling Considerations

**Current scale:**
- ~6,000 jobs
- 302 Greenhouse + 61 Lever companies
- 5 cities
- Single-user dashboard

**Scaling questions to consider (NOT implement yet):**
| If... | Then consider... |
|-------|------------------|
| 50K+ jobs | Pagination, caching, indexes |
| Multi-tenant | Row-level security, tenant isolation |
| Real-time updates | WebSockets, Supabase realtime |
| Heavy traffic | CDN, edge caching, read replicas |
| Multiple pipelines | Queue system, job scheduling |

**IMPORTANT:** Don't build these until needed. Document the path, don't walk it prematurely.

### 6. API Design

**Current API pattern:** Next.js API routes at `/api/hiring-market/*`

**API review questions:**
- Are endpoints RESTful and predictable?
- Is error handling consistent?
- Are responses appropriately sized?
- Is there unnecessary data being sent?

**API design principles:**
| Do | Don't |
|----|-------|
| Return only needed fields | Return entire DB rows |
| Use consistent error format | Mix error formats |
| Document query parameters | Surprise consumers |
| Version if breaking changes | Change contracts silently |

### 7. Security Considerations

**Review for:**
- API keys in code (should be env vars)
- SQL injection risks (use parameterized queries)
- Exposed internal errors (sanitize error messages)
- Rate limiting on public endpoints

### 8. Observability

**Current state:**
- Pipeline logging to stdout
- GHA logs for scheduled runs
- No centralized monitoring

**Questions:**
- Can we diagnose issues from logs alone?
- Are errors actionable?
- Do we know when things fail?

## Future Architecture Planning

### Planned Features (from `docs/architecture/Future Ideas/`)

| Epic | Architecture Impact |
|------|---------------------|
| Semantic Search | Vector DB, embeddings pipeline |
| Job Feed | Subscription system, notifications |
| Competencies Framework | Taxonomy expansion, UI changes |
| Enriched Dedup | Algorithm changes, backfill |

### Productization Checklist

If/when moving toward a product:

- [ ] Multi-tenant data isolation
- [ ] User authentication
- [ ] Rate limiting
- [ ] Usage tracking/billing
- [ ] SLA monitoring
- [ ] Backup/recovery procedures
- [ ] Documentation for operators

## Output Format

When reviewing architecture, produce:

```markdown
## Architecture Review

**Date:** [Date]
**Scope:** [What was reviewed]

### Current State Assessment

| Aspect | Status | Notes |
|--------|--------|-------|
| Separation of Concerns | Good/Fair/Poor | [notes] |
| Appropriate Abstraction | Good/Fair/Poor | [notes] |
| F/E - B/E Boundary | Good/Fair/Poor | [notes] |
| Schema Design | Good/Fair/Poor | [notes] |
| Scaling Readiness | Good/Fair/Poor | [notes] |

### Recommendations

#### Do Now (Blocking Issues)
1. [Issue and fix]

#### Do Soon (Technical Debt)
1. [Issue and fix]

#### Do Later (Future-Proofing)
1. [Consideration for when scale demands]

### Decision Log

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| [Choice made] | [Why] | [What else was considered] |

### Architecture Diagram Updates

[If structure has changed, provide updated diagram]
```

## Key Files to Reference

- `docs/architecture/MULTI_SOURCE_PIPELINE.md` - Pipeline architecture
- `docs/architecture/Future Ideas/` - Planned features
- `docs/REPOSITORY_STRUCTURE.md` - Directory organization
- `pipeline/unified_job_ingester.py` - Core orchestration
- `pipeline/db_connection.py` - Data layer patterns
