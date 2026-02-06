"""
Audit Skills Taxonomy
======================
Discovers unmapped skills, duplicate entries, orphaned families, and coverage gaps
in the skills taxonomy (domain -> family -> skill).

Queries all enriched_jobs, extracts unique skills, cross-references with
skill_family_mapping.yaml and skill_domain_mapping.yaml.

Usage:
    python pipeline/utilities/audit_skills_taxonomy.py
    python pipeline/utilities/audit_skills_taxonomy.py --output-csv

Options:
    --output-csv   Save report to docs/costs/skills_audit_report.csv
"""

import os
import sys
import csv
import argparse
from collections import Counter, defaultdict
from pathlib import Path

import yaml
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
SKILL_FAMILY_PATH = CONFIG_DIR / "skill_family_mapping.yaml"
SKILL_DOMAIN_PATH = CONFIG_DIR / "skill_domain_mapping.yaml"
SCHEMA_TAXONOMY_PATH = PROJECT_ROOT / "docs" / "schema_taxonomy.yaml"
CSV_OUTPUT_PATH = PROJECT_ROOT / "docs" / "costs" / "skills_audit_report.csv"


def get_supabase():
    """Initialize Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in environment")
    return create_client(url, key)


def load_skill_family_mapping() -> dict[str, str]:
    """Load skill -> family mapping (last-write-wins, same as mapper)."""
    with open(SKILL_FAMILY_PATH, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    mapping = {}
    for family_code, skill_list in raw.items():
        if not isinstance(skill_list, list):
            continue
        for skill in skill_list:
            mapping[skill.lower().strip()] = family_code
    return mapping


def detect_duplicates() -> list[dict]:
    """Detect skills that appear in multiple families (raw YAML parsing)."""
    with open(SKILL_FAMILY_PATH, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    # Track first-seen and all-seen families for each skill
    skill_families: dict[str, list[str]] = defaultdict(list)

    for family_code, skill_list in raw.items():
        if not isinstance(skill_list, list):
            continue
        for skill in skill_list:
            normalized = skill.lower().strip()
            skill_families[normalized].append(family_code)

    duplicates = []
    for skill, families in skill_families.items():
        if len(families) > 1:
            duplicates.append({
                "skill": skill,
                "families": families,
                "first_seen": families[0],
                "last_seen (wins)": families[-1],
            })

    return duplicates


def load_domain_mapping() -> dict[str, dict]:
    """Load family -> domain mapping."""
    with open(SKILL_DOMAIN_PATH, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    family_to_domain = {}
    for domain_code, domain_info in raw.items():
        label = domain_info.get("label", domain_code)
        for family in domain_info.get("families", []):
            family_to_domain[family] = {"domain": domain_code, "label": label}
    return family_to_domain


def load_schema_taxonomy_families() -> set[str]:
    """Load family codes from schema_taxonomy.yaml skills_ontology."""
    with open(SCHEMA_TAXONOMY_PATH, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    families = set()
    ontology = raw.get("skills_ontology", {})
    for category_families in ontology.values():
        if not isinstance(category_families, list):
            continue
        for entry in category_families:
            family_info = entry.get("family", {})
            if isinstance(family_info, dict) and "code" in family_info:
                families.add(family_info["code"])
    return families


def fetch_all_skills(supabase) -> list[dict]:
    """Fetch all jobs with skills from Supabase (paginated)."""
    all_records = []
    offset = 0
    page_size = 1000

    while True:
        result = (
            supabase.table("enriched_jobs")
            .select("id, skills")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        if not result.data:
            break
        all_records.extend(result.data)
        if len(result.data) < page_size:
            break
        offset += page_size

    return all_records


def analyze_skills(records: list[dict], skill_mapping: dict[str, str]):
    """Analyze skills from all records against the mapping."""
    # Count skill occurrences and track family_code status
    skill_counts = Counter()
    null_family_skills = Counter()
    mapped_family_skills = Counter()
    family_code_in_db = Counter()
    total_skill_mentions = 0
    records_with_skills = 0

    for record in records:
        skills = record.get("skills")
        if not skills or not isinstance(skills, list):
            continue
        records_with_skills += 1

        for skill in skills:
            name = skill.get("name") or ""
            name = name.strip()
            if not name:
                continue
            total_skill_mentions += 1
            skill_counts[name] += 1

            family_code = skill.get("family_code")
            if family_code:
                family_code_in_db[family_code] += 1
                mapped_family_skills[name] += 1
            else:
                null_family_skills[name] += 1

    # Cross-reference with current mapping
    unique_skills = set(skill_counts.keys())
    currently_mapped = set()
    currently_unmapped = set()

    for skill_name in unique_skills:
        normalized = skill_name.lower().strip()
        if normalized in skill_mapping:
            currently_mapped.add(skill_name)
        else:
            currently_unmapped.add(skill_name)

    # Skills that would change family on re-mapping
    stale_mappings = []
    for record in records:
        skills = record.get("skills")
        if not skills or not isinstance(skills, list):
            continue
        for skill in skills:
            name = skill.get("name") or ""
            name = name.strip()
            if not name:
                continue
            current_family = skill.get("family_code")
            new_family = skill_mapping.get(name.lower().strip())
            if current_family and new_family and current_family != new_family:
                stale_mappings.append({
                    "skill": name,
                    "current_family": current_family,
                    "new_family": new_family,
                })

    # Deduplicate stale mappings (keep unique skill+current+new combos)
    seen = set()
    unique_stale = []
    for s in stale_mappings:
        key = (s["skill"].lower(), s["current_family"], s["new_family"])
        if key not in seen:
            seen.add(key)
            unique_stale.append(s)

    return {
        "total_records": len(records),
        "records_with_skills": records_with_skills,
        "total_skill_mentions": total_skill_mentions,
        "unique_skills": len(unique_skills),
        "currently_mapped": len(currently_mapped),
        "currently_unmapped": len(currently_unmapped),
        "skill_counts": skill_counts,
        "null_family_skills": null_family_skills,
        "mapped_family_skills": mapped_family_skills,
        "family_code_in_db": family_code_in_db,
        "currently_unmapped_set": currently_unmapped,
        "stale_mappings": unique_stale,
    }


def cluster_unmapped_skills(unmapped_skills: set[str], skill_counts: Counter) -> dict[str, list]:
    """Group unmapped skills by keyword patterns to suggest new families."""
    # Define keyword patterns that might suggest new families
    keyword_patterns = {
        "networking": ["network", "networking", "tcp", "dns", "vpn", "firewall", "load balancer"],
        "compliance_regulation": ["compliance", "regulatory", "regulation", "audit", "sox", "aml", "kyc"],
        "data_mesh": ["data mesh", "data product", "data contract"],
        "robotics": ["robot", "robotics", "ros", "ros2", "motion planning", "slam"],
        "blockchain": ["blockchain", "web3", "defi", "smart contract", "ethereum", "solana"],
        "design_tools": ["figma", "sketch", "adobe", "photoshop", "illustrator", "invision"],
        "communication": ["communication", "presentation", "writing", "documentation"],
        "project_management": ["project management", "program management", "pmo", "prince2"],
        "low_code": ["low-code", "no-code", "power apps", "power automate", "appsheet"],
        "search_retrieval": ["search", "solr", "lucene", "opensearch", "meilisearch"],
    }

    clusters = defaultdict(list)
    for skill in unmapped_skills:
        skill_lower = skill.lower()
        for cluster_name, keywords in keyword_patterns.items():
            for keyword in keywords:
                if keyword in skill_lower:
                    clusters[cluster_name].append({
                        "skill": skill,
                        "count": skill_counts.get(skill, 0),
                    })
                    break  # Only match first pattern

    # Sort each cluster by count descending and filter to clusters with 2+ skills
    result = {}
    for cluster_name, skills in clusters.items():
        skills.sort(key=lambda x: -x["count"])
        if len(skills) >= 2:
            result[cluster_name] = skills

    return result


def print_report(analysis: dict, duplicates: list, family_to_domain: dict,
                 skill_mapping: dict, schema_families: set, output_csv: bool = False):
    """Print comprehensive audit report."""
    print("=" * 70)
    print("SKILLS TAXONOMY AUDIT REPORT")
    print("=" * 70)

    # -- Section 1: Summary Stats --
    print("\n1. SUMMARY STATISTICS")
    print("-" * 40)
    mapped_pct = (analysis["currently_mapped"] / analysis["unique_skills"] * 100
                  if analysis["unique_skills"] > 0 else 0)
    unmapped_pct = 100 - mapped_pct

    print(f"  Total records fetched:    {analysis['total_records']:,}")
    print(f"  Records with skills:      {analysis['records_with_skills']:,}")
    print(f"  Total skill mentions:     {analysis['total_skill_mentions']:,}")
    print(f"  Unique skills:            {analysis['unique_skills']:,}")
    print(f"  Mapped to a family:       {analysis['currently_mapped']:,} ({mapped_pct:.1f}%)")
    print(f"  Unmapped (null family):   {analysis['currently_unmapped']:,} ({unmapped_pct:.1f}%)")

    # Count null family mentions
    null_mentions = sum(analysis["null_family_skills"].values())
    total_mentions = analysis["total_skill_mentions"]
    null_mention_pct = null_mentions / total_mentions * 100 if total_mentions > 0 else 0
    print(f"  Null-family mentions:     {null_mentions:,} / {total_mentions:,} ({null_mention_pct:.1f}%)")

    # -- Section 2: Top Unmapped Skills --
    print(f"\n2. TOP UNMAPPED SKILLS BY FREQUENCY (top 40)")
    print("-" * 40)
    unmapped_with_counts = [
        (skill, analysis["skill_counts"][skill])
        for skill in analysis["currently_unmapped_set"]
    ]
    unmapped_with_counts.sort(key=lambda x: -x[1])

    for skill, count in unmapped_with_counts[:40]:
        print(f"  {count:>5}x  {skill}")

    # -- Section 3: Emergent Family Analysis --
    print(f"\n3. EMERGENT FAMILY ANALYSIS (clusters of unmapped skills)")
    print("-" * 40)
    clusters = cluster_unmapped_skills(
        analysis["currently_unmapped_set"], analysis["skill_counts"]
    )
    if clusters:
        for cluster_name, skills in sorted(clusters.items(),
                                            key=lambda x: -sum(s["count"] for s in x[1])):
            total = sum(s["count"] for s in skills)
            print(f"  [{cluster_name}] ({len(skills)} skills, {total} total mentions)")
            for s in skills[:8]:
                print(f"    {s['count']:>5}x  {s['skill']}")
    else:
        print("  No significant clusters detected in unmapped skills.")

    # -- Section 4: Stale Mappings --
    print(f"\n4. SKILLS THAT WOULD CHANGE FAMILY ON RE-MAPPING ({len(analysis['stale_mappings'])})")
    print("-" * 40)
    if analysis["stale_mappings"]:
        for s in sorted(analysis["stale_mappings"], key=lambda x: x["skill"].lower()):
            print(f"  {s['skill']}: {s['current_family']} -> {s['new_family']}")
    else:
        print("  None -- all DB family codes match current mapping.")

    # -- Section 5: Duplicate Entries --
    print(f"\n5. DUPLICATE ENTRIES ACROSS FAMILIES ({len(duplicates)})")
    print("-" * 40)
    if duplicates:
        for d in sorted(duplicates, key=lambda x: x["skill"]):
            families_str = " -> ".join(d["families"])
            print(f"  {d['skill']}: {families_str} (wins: {d['last_seen (wins)']})")
    else:
        print("  None -- no duplicates found.")

    # -- Section 6: Orphaned Families --
    print(f"\n6. FAMILY CODES IN DB WITH NO DOMAIN MAPPING")
    print("-" * 40)
    db_families = set(analysis["family_code_in_db"].keys())
    orphaned = db_families - set(family_to_domain.keys())
    if orphaned:
        for fam in sorted(orphaned):
            count = analysis["family_code_in_db"][fam]
            print(f"  {fam}: {count:,} mentions (no domain)")
    else:
        print("  None -- all DB family codes have a domain mapping.")

    # -- Section 7: Coverage Gaps --
    print(f"\n7. FAMILY COVERAGE GAPS")
    print("-" * 40)

    # Families in schema_taxonomy but not in skill_family_mapping
    mapping_families = set()
    with open(SKILL_FAMILY_PATH, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    for family_code, skill_list in raw.items():
        if isinstance(skill_list, list):
            mapping_families.add(family_code)

    in_schema_not_mapping = schema_families - mapping_families
    in_mapping_not_schema = mapping_families - schema_families
    in_domain_not_mapping = set(family_to_domain.keys()) - mapping_families
    in_mapping_not_domain = mapping_families - set(family_to_domain.keys())

    if in_schema_not_mapping:
        print("  In schema_taxonomy.yaml but NOT in skill_family_mapping.yaml:")
        for f in sorted(in_schema_not_mapping):
            print(f"    - {f}")

    if in_mapping_not_schema:
        print("  In skill_family_mapping.yaml but NOT in schema_taxonomy.yaml:")
        for f in sorted(in_mapping_not_schema):
            print(f"    - {f}")

    if in_domain_not_mapping:
        print("  In skill_domain_mapping.yaml but NOT in skill_family_mapping.yaml:")
        for f in sorted(in_domain_not_mapping):
            print(f"    - {f}")

    if in_mapping_not_domain:
        print("  In skill_family_mapping.yaml but NOT in skill_domain_mapping.yaml:")
        for f in sorted(in_mapping_not_domain):
            print(f"    - {f}")

    if not (in_schema_not_mapping or in_mapping_not_schema or
            in_domain_not_mapping or in_mapping_not_domain):
        print("  Full alignment across all config files.")

    print("\n" + "=" * 70)

    # -- Optional CSV output --
    if output_csv:
        _write_csv(analysis, duplicates, family_to_domain)


def _write_csv(analysis: dict, duplicates: list, family_to_domain: dict):
    """Write audit results to CSV."""
    CSV_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(CSV_OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Summary section
        writer.writerow(["Section", "Metric", "Value"])
        writer.writerow(["Summary", "Total records", analysis["total_records"]])
        writer.writerow(["Summary", "Records with skills", analysis["records_with_skills"]])
        writer.writerow(["Summary", "Total skill mentions", analysis["total_skill_mentions"]])
        writer.writerow(["Summary", "Unique skills", analysis["unique_skills"]])
        writer.writerow(["Summary", "Mapped skills", analysis["currently_mapped"]])
        writer.writerow(["Summary", "Unmapped skills", analysis["currently_unmapped"]])
        writer.writerow([])

        # Top unmapped
        writer.writerow(["Unmapped Skills", "Skill", "Count"])
        unmapped_with_counts = [
            (skill, analysis["skill_counts"][skill])
            for skill in analysis["currently_unmapped_set"]
        ]
        unmapped_with_counts.sort(key=lambda x: -x[1])
        for skill, count in unmapped_with_counts[:100]:
            writer.writerow(["Unmapped", skill, count])
        writer.writerow([])

        # Duplicates
        writer.writerow(["Duplicates", "Skill", "Families", "Winner"])
        for d in duplicates:
            writer.writerow(["Duplicate", d["skill"], " | ".join(d["families"]), d["last_seen (wins)"]])
        writer.writerow([])

        # Stale mappings
        writer.writerow(["Stale Mappings", "Skill", "Current Family", "New Family"])
        for s in analysis["stale_mappings"]:
            writer.writerow(["Stale", s["skill"], s["current_family"], s["new_family"]])

    print(f"\n[DONE] CSV saved to: {CSV_OUTPUT_PATH}")


def main():
    parser = argparse.ArgumentParser(description="Audit skills taxonomy")
    parser.add_argument("--output-csv", action="store_true",
                        help="Save report to CSV")
    args = parser.parse_args()

    print("Loading configuration files...")
    skill_mapping = load_skill_family_mapping()
    family_to_domain = load_domain_mapping()
    schema_families = load_schema_taxonomy_families()
    duplicates = detect_duplicates()

    print(f"  skill_family_mapping: {len(skill_mapping)} skills -> families")
    print(f"  skill_domain_mapping: {len(family_to_domain)} families -> domains")
    print(f"  schema_taxonomy families: {len(schema_families)}")
    print(f"  Duplicate entries: {len(duplicates)}")

    print("\nFetching all jobs with skills from Supabase...")
    supabase = get_supabase()
    records = fetch_all_skills(supabase)
    print(f"  Fetched {len(records):,} records")

    print("\nAnalyzing skills...")
    analysis = analyze_skills(records, skill_mapping)

    print_report(analysis, duplicates, family_to_domain, skill_mapping,
                 schema_families, output_csv=args.output_csv)


if __name__ == "__main__":
    main()
