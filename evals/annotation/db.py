"""
SQLite Database for Gold Standard Annotations

Handles all database operations for the annotation system.
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "gold_standard.db"


def get_connection() -> sqlite3.Connection:
    """Get database connection with row factory."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database schema."""
    conn = get_connection()
    cursor = conn.cursor()

    # Gold standard jobs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gold_jobs (
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
            gold_skills TEXT,
            gold_summary TEXT,

            -- Metadata
            annotated_by TEXT,
            annotated_at TIMESTAMP,
            confidence TEXT,
            notes TEXT,

            -- Review status
            reviewed_by TEXT,
            reviewed_at TIMESTAMP,
            review_status TEXT DEFAULT 'pending'
        )
    """)

    # Gold standard employers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gold_employers (
            id TEXT PRIMARY KEY,
            canonical_name TEXT UNIQUE,
            display_name TEXT,
            gold_industry TEXT,
            gold_company_size TEXT,
            reasoning TEXT,
            annotated_by TEXT,
            annotated_at TIMESTAMP,
            confidence TEXT
        )
    """)

    # Pending jobs queue (jobs to annotate)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_jobs (
            id TEXT PRIMARY KEY,
            source_job_id INTEGER,
            source TEXT,
            title TEXT,
            company TEXT,
            raw_text TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            priority INTEGER DEFAULT 0
        )
    """)

    # Annotation sessions (for tracking progress)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS annotation_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            annotator TEXT,
            started_at TIMESTAMP,
            ended_at TIMESTAMP,
            jobs_annotated INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


def add_pending_job(
    job_id: str,
    source_job_id: int,
    source: str,
    title: str,
    company: str,
    raw_text: str,
    priority: int = 0
) -> bool:
    """Add a job to the pending queue."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT OR IGNORE INTO pending_jobs
            (id, source_job_id, source, title, company, raw_text, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (job_id, source_job_id, source, title, company, raw_text, priority))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_next_pending_job() -> Optional[Dict]:
    """Get the next job to annotate (highest priority first)."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT * FROM pending_jobs
            ORDER BY priority DESC, added_at ASC
            LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def get_pending_count() -> int:
    """Get count of pending jobs."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM pending_jobs")
        return cursor.fetchone()[0]
    finally:
        conn.close()


def get_annotated_count() -> int:
    """Get count of annotated jobs."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM gold_jobs")
        return cursor.fetchone()[0]
    finally:
        conn.close()


def save_annotation(
    job_id: str,
    source_job_id: int,
    source: str,
    title: str,
    company: str,
    raw_text: str,
    gold_job_family: str,
    gold_job_subfamily: str,
    gold_seniority: Optional[str],
    gold_working_arrangement: str,
    gold_track: Optional[str],
    gold_position_type: str,
    gold_skills: List[Dict],
    gold_summary: str,
    annotated_by: str,
    confidence: str,
    notes: str
) -> bool:
    """Save an annotation to the gold standard."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Insert into gold_jobs
        cursor.execute("""
            INSERT OR REPLACE INTO gold_jobs
            (id, source_job_id, source, title, company, raw_text,
             gold_job_family, gold_job_subfamily, gold_seniority,
             gold_working_arrangement, gold_track, gold_position_type,
             gold_skills, gold_summary, annotated_by, annotated_at,
             confidence, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id, source_job_id, source, title, company, raw_text,
            gold_job_family, gold_job_subfamily, gold_seniority,
            gold_working_arrangement, gold_track, gold_position_type,
            json.dumps(gold_skills), gold_summary, annotated_by,
            datetime.now().isoformat(), confidence, notes
        ))

        # Remove from pending queue
        cursor.execute("DELETE FROM pending_jobs WHERE id = ?", (job_id,))

        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving annotation: {e}")
        return False
    finally:
        conn.close()


def skip_job(job_id: str) -> bool:
    """Remove a job from pending without annotating."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM pending_jobs WHERE id = ?", (job_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_all_annotations() -> List[Dict]:
    """Get all gold standard annotations."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM gold_jobs ORDER BY annotated_at DESC")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_annotation_stats() -> Dict:
    """Get annotation statistics."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        stats = {}

        # Total counts
        cursor.execute("SELECT COUNT(*) FROM gold_jobs")
        stats["total_annotated"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM pending_jobs")
        stats["pending"] = cursor.fetchone()[0]

        # By job family
        cursor.execute("""
            SELECT gold_job_family, COUNT(*) as count
            FROM gold_jobs
            GROUP BY gold_job_family
        """)
        stats["by_family"] = {row[0]: row[1] for row in cursor.fetchall()}

        # By source
        cursor.execute("""
            SELECT source, COUNT(*) as count
            FROM gold_jobs
            GROUP BY source
        """)
        stats["by_source"] = {row[0]: row[1] for row in cursor.fetchall()}

        # By seniority
        cursor.execute("""
            SELECT gold_seniority, COUNT(*) as count
            FROM gold_jobs
            GROUP BY gold_seniority
        """)
        stats["by_seniority"] = {row[0] or "null": row[1] for row in cursor.fetchall()}

        return stats
    finally:
        conn.close()


def export_to_json(output_path: str) -> int:
    """Export gold standard to JSON file."""
    annotations = get_all_annotations()

    # Parse skills JSON
    for ann in annotations:
        if ann.get("gold_skills"):
            ann["gold_skills"] = json.loads(ann["gold_skills"])

    output = {
        "version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "count": len(annotations),
        "jobs": annotations
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return len(annotations)


# Initialize database on import
init_db()
