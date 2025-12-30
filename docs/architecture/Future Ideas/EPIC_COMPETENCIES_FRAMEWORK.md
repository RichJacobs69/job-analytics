# Epic: Competencies Framework for Senior Roles

**Status:** Planning
**Created:** 2025-12-28
**Priority:** Medium (Enhances classification quality for senior roles)

## Problem Statement

The current skills ontology focuses on **tools, technologies, and methodologies** (Python, SQL, JIRA, Agile, PMP). This works well for technical roles and junior-mid positions where specific tool proficiency is emphasized.

However, senior roles (staff_principal, director_plus) emphasize **competencies** - soft skills, leadership qualities, and strategic capabilities. Job descriptions for these roles often contain language like:

- "Influence senior stakeholders across the organization"
- "Define and communicate product vision to executives"
- "Thrive in ambiguous environments with minimal direction"
- "Build and mentor high-performing teams"

These competencies are currently **not captured** in our classification, leading to senior PM/PgM roles showing "no skills found" even when the job description is rich with competency requirements.

### Example: Monzo Lead PM (raw_job_id 26298)

The job description mentions:
- "You'll be working closely with senior stakeholders"
- "Drive the vision and strategy"
- "Lead cross-functional teams"

But extracts **zero skills** because:
- No specific tools mentioned (no JIRA, no SQL)
- No methodologies mentioned (no Agile, no Scrum)
- Competencies not in the ontology

## Scope

### In Scope

- Define competencies ontology parallel to skills ontology
- Universal competencies (apply across job families)
- Job family-specific competencies (Product, Data, Delivery)
- Extraction patterns for LLM classifier
- Storage in enriched_jobs table

### Out of Scope (Future Work)

- Competency-based job matching/recommendations
- Competency gap analysis for candidates
- Seniority inference from competency patterns

## Proposed Architecture

### Competencies vs Skills

| Aspect | Skills (Current) | Competencies (Proposed) |
|--------|-----------------|------------------------|
| Focus | Tools, technologies, methodologies | Soft skills, leadership, mindsets |
| Detection | Explicit keyword matching | Pattern/phrase inference |
| Examples | Python, SQL, JIRA, Agile | Strategic thinking, stakeholder influence |
| Seniority relevance | All levels | Primarily senior+ |
| Extraction confidence | High (explicit mention) | Medium (inferred from language) |

### Storage Format

Same structure as skills for consistency:

```json
{
  "competencies": [
    {"code": "exec_communication", "family_code": "leadership"},
    {"code": "vision_setting", "family_code": "strategic"},
    {"code": "cross_functional", "family_code": "leadership"}
  ]
}
```

### Schema Addition

```yaml
competencies:
  items:
    type: array
    extraction_note: "Extract competencies from language patterns - see competencies_ontology"
    items:
      type: object
      properties:
        code:
          type: string
          extraction_note: "Competency code from ontology (e.g., 'exec_communication')"
        family_code:
          type: string
          extraction_note: "Parent family code (e.g., 'leadership', 'strategic')"
```

## Proposed Competencies Ontology

### Universal Competencies (All Job Families)

```yaml
universal:
  - family: {code: leadership, label: "Leadership & Influence"}
    competencies:
      - code: exec_communication
        label: "Executive Communication"
        description: "Presents to C-suite, board-level narratives, senior stakeholders"
        patterns: ["executive presentation", "board-level", "C-suite", "senior stakeholders", "leadership team"]

      - code: stakeholder_influence
        label: "Stakeholder Influence"
        description: "Influence without authority, coalition building, alignment"
        patterns: ["influence without authority", "build consensus", "align stakeholders", "drive alignment", "cross-org influence"]

      - code: cross_functional
        label: "Cross-Functional Leadership"
        description: "Leads across engineering, design, ops, multiple teams"
        patterns: ["cross-functional", "work across", "partner with engineering", "collaborate with design", "multiple teams"]

      - code: mentoring
        label: "Mentoring & Coaching"
        description: "Develops junior talent, team building, coaching"
        patterns: ["mentor", "coach", "develop team", "grow talent", "build team", "nurture"]

  - family: {code: strategic, label: "Strategic Thinking"}
    competencies:
      - code: vision_setting
        label: "Vision Setting"
        description: "Defines long-term direction, north stars, multi-year strategy"
        patterns: ["define vision", "set direction", "north star", "long-term strategy", "multi-year", "3-5 year"]

      - code: ambiguity_tolerance
        label: "Ambiguity Tolerance"
        description: "Thrives in undefined problem spaces, minimal direction"
        patterns: ["ambiguous", "undefined", "greenfield", "minimal direction", "figure it out", "uncharted"]

      - code: business_acumen
        label: "Business Acumen"
        description: "P&L awareness, commercial understanding, revenue impact"
        patterns: ["P&L", "revenue", "commercial", "business impact", "unit economics", "market dynamics"]

      - code: zero_to_one
        label: "0-to-1 Experience"
        description: "Built new products/capabilities from scratch"
        patterns: ["0 to 1", "zero to one", "from scratch", "greenfield", "build new", "launch new"]

  - family: {code: execution, label: "Execution Excellence"}
    competencies:
      - code: prioritization
        label: "Prioritization"
        description: "Trade-off decisions, ruthless focus, saying no"
        patterns: ["prioritize", "trade-offs", "ruthless", "focus", "say no", "what not to do"]

      - code: decision_making
        label: "Decision-Making"
        description: "Makes calls with incomplete information, owns decisions"
        patterns: ["make decisions", "incomplete information", "own the decision", "decisive", "judgment calls"]

      - code: change_management
        label: "Change Management"
        description: "Drives org change, transformation, process improvement"
        patterns: ["change management", "transformation", "org change", "process improvement", "drive change"]
```

### Product-Specific Competencies

```yaml
product:
  - family: {code: customer_insight, label: "Customer Insight"}
    competencies:
      - code: customer_empathy
        label: "Customer Empathy"
        description: "Deep user understanding, voice of customer, user advocacy"
        patterns: ["customer empathy", "user-centric", "voice of customer", "user advocate", "customer obsessed"]

      - code: market_awareness
        label: "Market Awareness"
        description: "Competitive landscape, industry trends, market positioning"
        patterns: ["competitive landscape", "market trends", "industry dynamics", "market positioning", "competitive analysis"]

      - code: product_intuition
        label: "Product Intuition"
        description: "Taste, design sensibility, UX judgment, product sense"
        patterns: ["product sense", "product intuition", "design sensibility", "taste", "UX judgment"]

  - family: {code: product_craft, label: "Product Craft"}
    competencies:
      - code: roadmap_ownership
        label: "Roadmap Ownership"
        description: "End-to-end roadmap accountability, prioritization authority"
        patterns: ["own the roadmap", "roadmap accountability", "prioritization", "product direction"]

      - code: gtm_strategy
        label: "GTM Strategy"
        description: "Go-to-market, launch strategy, adoption, distribution"
        patterns: ["go-to-market", "GTM", "launch strategy", "adoption", "distribution", "market entry"]

      - code: data_informed
        label: "Data-Informed Decisions"
        description: "Balances data + intuition, metrics-driven with judgment"
        patterns: ["data-informed", "data-driven", "metrics", "balance data", "quantitative + qualitative"]
```

### Data-Specific Competencies

```yaml
data:
  - family: {code: analytical_thinking, label: "Analytical Thinking"}
    competencies:
      - code: problem_decomposition
        label: "Problem Decomposition"
        description: "Breaks complex problems into solvable parts"
        patterns: ["break down", "decompose", "structure problems", "complex to simple", "first principles"]

      - code: intellectual_curiosity
        label: "Intellectual Curiosity"
        description: "Deep-dives, root cause analysis, always learning"
        patterns: ["curious", "deep dive", "root cause", "why behind", "continuous learning"]

      - code: experimentation_mindset
        label: "Experimentation Mindset"
        description: "Hypothesis-driven, test-and-learn, scientific method"
        patterns: ["hypothesis", "experiment", "test and learn", "scientific", "iterate"]

  - family: {code: translation, label: "Business Translation"}
    competencies:
      - code: technical_communication
        label: "Technical Communication"
        description: "Explains complex concepts to non-technical audiences"
        patterns: ["explain to non-technical", "translate", "simplify", "communicate findings", "storytelling with data"]

      - code: insight_to_action
        label: "Insight to Action"
        description: "Converts analysis into business decisions and recommendations"
        patterns: ["actionable insights", "recommendations", "drive decisions", "so what", "business impact"]

      - code: scalable_thinking
        label: "Scalable Thinking"
        description: "Designs for scale, future-proofing, systematic approaches"
        patterns: ["scale", "systematic", "repeatable", "future-proof", "sustainable"]
```

### Delivery-Specific Competencies

```yaml
delivery:
  - family: {code: facilitation, label: "Facilitation & Coordination"}
    competencies:
      - code: conflict_resolution
        label: "Conflict Resolution"
        description: "Mediates disagreements, finds consensus, navigates tensions"
        patterns: ["resolve conflict", "mediate", "consensus", "navigate tensions", "difficult conversations"]

      - code: negotiation
        label: "Negotiation"
        description: "Scope, timeline, resource negotiation, trade-off discussions"
        patterns: ["negotiate", "scope discussions", "trade-off", "resource allocation", "timeline negotiation"]

      - code: team_empowerment
        label: "Team Empowerment"
        description: "Removes blockers, enables autonomy, servant leadership"
        patterns: ["remove blockers", "empower", "servant leader", "enable teams", "autonomy"]

  - family: {code: delivery_excellence, label: "Delivery Excellence"}
    competencies:
      - code: risk_management
        label: "Risk Management"
        description: "Identifies, mitigates, escalates risks proactively"
        patterns: ["risk management", "mitigate risk", "escalate", "RAID", "risk register"]

      - code: process_improvement
        label: "Process Improvement"
        description: "Retrospectives, continuous improvement, efficiency gains"
        patterns: ["retrospective", "continuous improvement", "process improvement", "optimize", "efficiency"]

      - code: deadline_orientation
        label: "Deadline Orientation"
        description: "Urgency, milestone accountability, delivery focus"
        patterns: ["deadline", "milestone", "on-time", "delivery-focused", "urgency", "ship"]
```

## Implementation Plan

### Phase 1: Ontology Refinement [ACTION REQUIRED]

**[TODO] Thorough Ontology Review:**

Before implementation, conduct a comprehensive review of the competencies ontology:

1. **Pattern validation**: Test extraction patterns against 50+ real job descriptions across seniority levels
2. **Coverage analysis**: Ensure all common competency language in senior roles is captured
3. **False positive check**: Verify patterns don't over-extract at junior levels
4. **Family boundaries**: Confirm competencies are correctly categorized by family
5. **Cross-family overlap**: Identify and resolve any competencies that span families
6. **Seniority correlation**: Determine which competencies correlate with which seniority levels

**Deliverable**: Updated competencies_ontology in schema_taxonomy.yaml with validated patterns

### Phase 2: Schema & Database

1. Add `competencies` column to enriched_jobs (JSONB array)
2. Update schema_taxonomy.yaml with competencies_ontology
3. Create competencies validation rules

### Phase 3: Classifier Integration

1. Update classifier.py prompt to extract competencies
2. Add extraction patterns for each competency
3. Test with sample job descriptions
4. Validate extraction quality

### Phase 4: Backfill & Dashboard

1. Re-classify existing jobs to extract competencies
2. Add competencies to dashboard views (if desired)
3. Create competencies distribution charts

## Key Design Decisions

### 1. Extraction Approach

Unlike skills (explicit keyword matching), competencies require **pattern inference**:

```python
# Skills: explicit match
"Python" in text -> skill: Python

# Competencies: pattern inference
"influence senior stakeholders across the organization" -> competency: stakeholder_influence
```

### 2. Confidence Levels

Consider adding confidence levels to competency extraction:

```json
{
  "code": "exec_communication",
  "family_code": "leadership",
  "confidence": "high"  # high/medium/low
}
```

### 3. Seniority Correlation

Some competencies correlate strongly with seniority:

| Competency | Typical Seniority |
|------------|------------------|
| exec_communication | staff_principal, director_plus |
| mentoring | senior+ |
| vision_setting | director_plus |
| cross_functional | mid+ |

This could be used for:
- Validation (flag if junior role has exec_communication)
- Seniority inference (future feature)

### 4. Overlap with Skills

Some concepts appear in both ontologies:

| Current Skill | Proposed Competency | Resolution |
|---------------|---------------------|------------|
| Stakeholder management (product skill) | stakeholder_influence | Keep both - skill is tactical, competency is strategic |
| Cross-functional collaboration (product skill) | cross_functional | Merge into competency only |

## Testing Plan

1. **Pattern coverage**: Extract competencies from 100 senior role descriptions
2. **Precision check**: Manual review of extracted competencies for accuracy
3. **Recall check**: Identify missed competencies in sample descriptions
4. **Seniority correlation**: Verify senior roles have more competencies than junior

## Success Metrics

| Metric | Target |
|--------|--------|
| Senior roles with competencies extracted | >80% |
| Competency extraction precision | >85% |
| False positive rate (junior roles) | <10% |

## Dependencies

- schema_taxonomy.yaml update
- classifier.py modification
- enriched_jobs schema change (add competencies column)

## Open Questions

1. Should competencies be extractable from all seniority levels or gated to senior+?
2. Should we weight competencies differently by job family?
3. How do we handle competencies that appear in company "about us" sections vs role requirements?
4. Should competency extraction trigger re-classification of existing jobs?

## References

- Original discussion: Monzo Lead PM (raw_job_id 26298) had no skills extracted
- Related: EPIC_SEMANTIC_SEARCH.md (semantic patterns complement competency extraction)

## Sign-off

- [ ] Ontology review complete (Phase 1)
- [ ] Schema updated
- [ ] Classifier integration complete
- [ ] Backfill complete
- [ ] Dashboard updated (optional)
