"""
Streamlit Annotation App for Gold Standard Dataset

Usage:
    streamlit run evals/annotation/app.py

Features:
- Present job postings for annotation
- Dropdown/radio selections for classification fields
- Skills entry
- Summary review
- SQLite persistence
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import json
from datetime import datetime

from evals.annotation.db import (
    get_next_pending_job,
    get_pending_count,
    get_annotated_count,
    save_annotation,
    skip_job,
    get_annotation_stats,
    export_to_json
)

# ============================================
# Taxonomy Options (from schema_taxonomy.yaml)
# ============================================

JOB_FAMILIES = ["product", "data", "delivery", "out_of_scope"]

PRODUCT_SUBFAMILIES = ["core_pm", "growth_pm", "platform_pm", "technical_pm", "ai_ml_pm"]
DATA_SUBFAMILIES = ["product_analytics", "data_analyst", "analytics_engineer", "data_engineer",
                    "ml_engineer", "data_scientist", "research_scientist_ml", "data_architect"]
DELIVERY_SUBFAMILIES = ["delivery_manager", "project_manager", "programme_manager", "scrum_master"]

SUBFAMILY_MAP = {
    "product": PRODUCT_SUBFAMILIES,
    "data": DATA_SUBFAMILIES,
    "delivery": DELIVERY_SUBFAMILIES,
    "out_of_scope": []
}

SENIORITY_LEVELS = [None, "junior", "mid", "senior", "staff_principal", "director_plus"]
WORKING_ARRANGEMENTS = ["onsite", "hybrid", "remote", "flexible", "unknown"]
TRACKS = [None, "ic", "management"]
POSITION_TYPES = ["full_time", "part_time", "contract", "internship"]
CONFIDENCE_LEVELS = ["high", "medium", "low"]

# Common skills for autocomplete
COMMON_SKILLS = [
    "Python", "SQL", "R", "Scala", "Java",
    "PyTorch", "TensorFlow", "Scikit-learn", "XGBoost",
    "Spark", "Airflow", "dbt", "Kafka",
    "AWS", "GCP", "Azure", "Snowflake", "BigQuery", "Databricks",
    "Tableau", "Looker", "Power BI",
    "A/B Testing", "Statistics", "Machine Learning",
    "Product Strategy", "Roadmapping", "Agile", "Scrum",
    "JIRA", "Confluence", "Figma", "Notion",
    "LLMs", "RAG", "Prompt Engineering", "LangChain",
    "Docker", "Kubernetes", "Git", "CI/CD"
]

# ============================================
# Streamlit App
# ============================================

st.set_page_config(
    page_title="Job Classification Annotator",
    page_icon="[TAG]",
    layout="wide"
)

def main():
    st.title("[TAG] Job Classification Annotator")

    # Sidebar with stats and navigation
    with st.sidebar:
        st.header("Progress")

        stats = get_annotation_stats()
        annotated = stats["total_annotated"]
        pending = stats["pending"]

        col1, col2 = st.columns(2)
        col1.metric("Annotated", annotated)
        col2.metric("Pending", pending)

        if annotated > 0:
            st.progress(annotated / (annotated + pending) if (annotated + pending) > 0 else 0)

        st.divider()

        # Annotator name
        annotator = st.text_input("Your Name", value=st.session_state.get("annotator", ""))
        if annotator:
            st.session_state["annotator"] = annotator

        st.divider()

        # Stats breakdown
        if annotated > 0:
            st.subheader("By Job Family")
            for family, count in stats.get("by_family", {}).items():
                st.text(f"  {family}: {count}")

            st.subheader("By Source")
            for source, count in stats.get("by_source", {}).items():
                st.text(f"  {source}: {count}")

        st.divider()

        # Export button
        if st.button("Export to JSON"):
            output_path = "evals/data/exports/gold_standard_export.json"
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            count = export_to_json(output_path)
            st.success(f"Exported {count} annotations to {output_path}")

    # Main content
    job = get_next_pending_job()

    if not job:
        st.info("No pending jobs to annotate. Use extract_for_annotation.py to add jobs.")
        st.markdown("""
        ### Getting Started

        1. Run the extraction script to add jobs:
        ```bash
        python evals/annotation/extract_for_annotation.py --count 50
        ```

        2. Refresh this page to start annotating
        """)
        return

    # Display job information
    st.subheader(f"{job['title']}")
    st.caption(f"Company: {job['company']} | Source: {job['source']} | ID: {job['source_job_id']}")

    # Job description in expandable section
    with st.expander("Job Description", expanded=True):
        # Limit display length for readability
        raw_text = job["raw_text"]
        if len(raw_text) > 5000:
            st.text_area("", raw_text[:5000] + "\n\n[TRUNCATED - full text available]", height=400, disabled=True)
        else:
            st.text_area("", raw_text, height=400, disabled=True)

    st.divider()

    # Annotation form
    st.subheader("Classification Labels")

    col1, col2 = st.columns(2)

    with col1:
        # Job Family
        job_family = st.selectbox(
            "Job Family *",
            options=JOB_FAMILIES,
            index=0,
            help="Primary classification category"
        )

        # Job Subfamily (filtered by family)
        subfamily_options = SUBFAMILY_MAP.get(job_family, [])
        if subfamily_options:
            job_subfamily = st.selectbox(
                "Job Subfamily *",
                options=subfamily_options,
                help="Specific role type within the family"
            )
        else:
            job_subfamily = None
            if job_family == "out_of_scope":
                st.info("out_of_scope jobs have no subfamily")

        # Seniority
        seniority = st.selectbox(
            "Seniority",
            options=SENIORITY_LEVELS,
            format_func=lambda x: x if x else "(unknown)",
            help="Level based on title/years. Use None if unclear."
        )

        # Track
        track = st.selectbox(
            "Track",
            options=TRACKS,
            format_func=lambda x: x if x else "(unknown)",
            help="IC = individual contributor, Management = people manager"
        )

    with col2:
        # Working Arrangement
        working_arrangement = st.selectbox(
            "Working Arrangement *",
            options=WORKING_ARRANGEMENTS,
            index=4,  # Default to 'unknown'
            help="Remote, hybrid, onsite, flexible, or unknown"
        )

        # Position Type
        position_type = st.selectbox(
            "Position Type *",
            options=POSITION_TYPES,
            index=0,  # Default to full_time
            help="Employment type"
        )

        # Confidence
        confidence = st.selectbox(
            "Annotation Confidence",
            options=CONFIDENCE_LEVELS,
            index=0,
            help="How confident are you in this annotation?"
        )

    st.divider()

    # Skills
    st.subheader("Skills")

    skills_input = st.text_area(
        "Enter skills (comma-separated)",
        placeholder="Python, SQL, A/B Testing, Snowflake",
        help="Enter skills explicitly mentioned in the job posting"
    )

    # Quick add common skills
    st.caption("Quick add:")
    skill_cols = st.columns(8)
    quick_skills = []
    for i, skill in enumerate(COMMON_SKILLS[:16]):
        with skill_cols[i % 8]:
            if st.checkbox(skill, key=f"skill_{skill}"):
                quick_skills.append(skill)

    # Combine skills
    entered_skills = [s.strip() for s in skills_input.split(",") if s.strip()]
    all_skills = list(set(entered_skills + quick_skills))

    if all_skills:
        st.caption(f"Skills to save: {', '.join(all_skills)}")

    st.divider()

    # Summary (optional - for review)
    st.subheader("Summary (Optional)")
    gold_summary = st.text_area(
        "Gold standard summary",
        placeholder="2-3 sentence summary of day-to-day responsibilities...",
        help="Write an ideal summary or leave blank to skip",
        height=100
    )

    st.divider()

    # Notes
    notes = st.text_area(
        "Annotator Notes",
        placeholder="Any edge cases, ambiguities, or reasoning...",
        height=80
    )

    st.divider()

    # Action buttons
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        if st.button("Save Annotation", type="primary", use_container_width=True):
            # Validate
            if not st.session_state.get("annotator"):
                st.error("Please enter your name in the sidebar")
                return

            if job_family != "out_of_scope" and not job_subfamily:
                st.error("Please select a job subfamily")
                return

            # Format skills
            formatted_skills = [{"name": s, "family_code": None} for s in all_skills]

            # Save
            success = save_annotation(
                job_id=job["id"],
                source_job_id=job["source_job_id"],
                source=job["source"],
                title=job["title"],
                company=job["company"],
                raw_text=job["raw_text"],
                gold_job_family=job_family,
                gold_job_subfamily=job_subfamily,
                gold_seniority=seniority,
                gold_working_arrangement=working_arrangement,
                gold_track=track,
                gold_position_type=position_type,
                gold_skills=formatted_skills,
                gold_summary=gold_summary or "",
                annotated_by=st.session_state["annotator"],
                confidence=confidence,
                notes=notes
            )

            if success:
                st.success("Annotation saved!")
                st.rerun()
            else:
                st.error("Failed to save annotation")

    with col2:
        if st.button("Skip", use_container_width=True):
            skip_job(job["id"])
            st.rerun()

    with col3:
        if st.button("Skip (Bad Data)", use_container_width=True):
            # Skip with a note that data quality is poor
            skip_job(job["id"])
            st.rerun()


if __name__ == "__main__":
    main()
