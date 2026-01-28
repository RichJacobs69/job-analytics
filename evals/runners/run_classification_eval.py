"""
Classification Evaluation Runner

Compares LLM classifications against gold standard annotations.

Usage:
    python -m evals.runners.run_classification_eval
    python -m evals.runners.run_classification_eval --sample 20
    python -m evals.runners.run_classification_eval --export results.json
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import argparse
import json
from datetime import datetime
from typing import Dict, List
from collections import defaultdict

from evals.annotation.db import get_all_annotations
from pipeline.classifier import classify_job

CLASSIFICATION_FIELDS = [
    "job_family",
    "job_subfamily",
    "seniority",
    "working_arrangement",
    "track",
    "position_type"
]


def run_eval(sample_size: int = None, verbose: bool = False) -> Dict:
    """Run classification eval against gold standard."""

    # Load gold annotations
    annotations = get_all_annotations()

    if not annotations:
        print("[ERROR] No gold standard annotations found.")
        print("Run the annotation app first: streamlit run evals/annotation/app.py")
        return {}

    if sample_size:
        annotations = annotations[:sample_size]

    print(f"Evaluating {len(annotations)} gold standard jobs...")
    print()

    results = {
        "run_at": datetime.now().isoformat(),
        "total": len(annotations),
        "by_field": {
            field: {"correct": 0, "incorrect": 0, "errors": []}
            for field in CLASSIFICATION_FIELDS
        },
        "overall_correct": 0,
        "overall_incorrect": 0,
        "cost_total": 0.0
    }

    for i, ann in enumerate(annotations):
        title = ann.get("title", "Unknown")[:40]
        print(f"[{i+1}/{len(annotations)}] {title}...", end=" ", flush=True)

        try:
            # Classify with current model
            prediction = classify_job(ann["raw_text"])

            cost = prediction.get("_cost_data", {}).get("total_cost", 0)
            results["cost_total"] += cost

            # Extract predicted values
            pred_role = prediction.get("role", {})
            pred_location = prediction.get("location", {})

            pred_values = {
                "job_family": pred_role.get("job_family"),
                "job_subfamily": pred_role.get("job_subfamily"),
                "seniority": pred_role.get("seniority"),
                "working_arrangement": pred_location.get("working_arrangement"),
                "track": pred_role.get("track"),
                "position_type": pred_role.get("position_type"),
            }

            # Gold values
            gold_values = {
                "job_family": ann.get("gold_job_family"),
                "job_subfamily": ann.get("gold_job_subfamily"),
                "seniority": ann.get("gold_seniority"),
                "working_arrangement": ann.get("gold_working_arrangement"),
                "track": ann.get("gold_track"),
                "position_type": ann.get("gold_position_type"),
            }

            # Compare each field
            all_match = True
            for field in CLASSIFICATION_FIELDS:
                gold = gold_values[field]
                pred = pred_values[field]

                if gold == pred:
                    results["by_field"][field]["correct"] += 1
                else:
                    all_match = False
                    results["by_field"][field]["incorrect"] += 1
                    results["by_field"][field]["errors"].append({
                        "job_id": ann["id"],
                        "title": ann.get("title"),
                        "gold": gold,
                        "predicted": pred
                    })

            if all_match:
                results["overall_correct"] += 1
                print("OK")
            else:
                results["overall_incorrect"] += 1
                print("MISMATCH")

                if verbose:
                    for field in CLASSIFICATION_FIELDS:
                        g = gold_values[field]
                        p = pred_values[field]
                        if g != p:
                            print(f"    {field}: {g} -> {p}")

        except Exception as e:
            print(f"ERROR: {e}")
            results["overall_incorrect"] += 1

    # Calculate metrics
    for field in CLASSIFICATION_FIELDS:
        data = results["by_field"][field]
        total = data["correct"] + data["incorrect"]
        data["accuracy"] = data["correct"] / total if total > 0 else 0
        data["total"] = total

    results["overall_accuracy"] = (
        results["overall_correct"] / results["total"]
        if results["total"] > 0 else 0
    )

    return results


def print_report(results: Dict):
    """Print evaluation report."""
    print()
    print("=" * 60)
    print("CLASSIFICATION EVAL REPORT")
    print("=" * 60)
    print(f"Run at: {results.get('run_at', 'N/A')}")
    print(f"Total jobs evaluated: {results['total']}")
    print(f"Total LLM cost: ${results.get('cost_total', 0):.4f}")
    print()

    print("ACCURACY BY FIELD:")
    print("-" * 50)
    for field in CLASSIFICATION_FIELDS:
        data = results["by_field"][field]
        acc = data["accuracy"] * 100
        status = "[PASS]" if acc >= 80 else "[FAIL]"
        print(f"  {status} {field:<25} {acc:>5.1f}%  ({data['correct']}/{data['total']})")

    print("-" * 50)
    overall_acc = results["overall_accuracy"] * 100
    print(f"  Overall (all fields match): {overall_acc:.1f}%")
    print()

    # Top errors per field
    print("TOP ERRORS BY FIELD:")
    print("-" * 50)
    for field in CLASSIFICATION_FIELDS:
        errors = results["by_field"][field]["errors"]
        if errors:
            print(f"\n{field} ({len(errors)} errors):")
            for err in errors[:3]:
                print(f"  - {err['title'][:35]}: {err['gold']} -> {err['predicted']}")


def main():
    parser = argparse.ArgumentParser(description="Run classification eval")
    parser.add_argument("--sample", type=int, help="Sample size")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--export", type=str, help="Export results to JSON")
    args = parser.parse_args()

    results = run_eval(sample_size=args.sample, verbose=args.verbose)

    if results:
        print_report(results)

        if args.export:
            # Remove error details for cleaner export
            export_results = {**results}
            for field in CLASSIFICATION_FIELDS:
                export_results["by_field"][field]["errors"] = (
                    export_results["by_field"][field]["errors"][:10]
                )

            with open(args.export, "w") as f:
                json.dump(export_results, f, indent=2)
            print(f"\nResults exported to: {args.export}")


if __name__ == "__main__":
    main()
