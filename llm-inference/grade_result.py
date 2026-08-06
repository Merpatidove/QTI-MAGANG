"""
grade_result.py — single source of truth for the two 5W1H metrics (guidebook §1.6):
  1. Complete 5W1H Schema — all six keys present (shape)
  2. Grounded            — 'how' backed by a real retrieved SOP, not the placeholder

CI gate (handed to Ferdi for ci.yml, guidebook §1.4):
  Set CI_SCHEMA_MIN / CI_GROUNDED_MIN (percentages) to activate a failing gate.
  Example GitHub Actions env: CI_SCHEMA_MIN=100.0  CI_GROUNDED_MIN=80.0
  Locally (env unset) the gate stays OFF and behavior is unchanged.
"""
import json
import os
import sys
from pathlib import Path

# A 'how' that still holds the prompt's placeholder example is NOT grounded in a SOP.
# Keep this string in sync with the `grounded` flag in test_run.py.
PLACEHOLDER_HOW = "pending sop search"
REQUIRED_KEYS = {"Who", "What", "When", "Where", "Why", "How"}


def evaluate_results():
    results_path = Path("evaluation_results.json")
    if not results_path.exists():
        print("Error: evaluation_results.json not found! Run test_run.py first.")
        sys.exit(1)

    with open(results_path, 'r', encoding='utf-8') as f:
        try:
            results = json.load(f)
        except json.JSONDecodeError:
            print("Error: evaluation_results.json is corrupted or not valid JSON.")
            sys.exit(1)

    if not results:
        print("evaluation_results.json is empty. No tests to grade.")
        return

    total = len(results)
    valid_json = 0
    complete_5w1h = 0
    grounded = 0
    tier_a = tier_b = tier_c = 0

    for item in results:
        output = item.get("5w1h_output", {})          # Fix A: the real key
        if not (isinstance(output, dict) and not item.get("error")):
            tier_c += 1                               # unusable output = schema-incomplete
            continue
        valid_json += 1

        # Schema completeness: all six keys present (capitalize matches lowercase emit)
        extracted = {str(k).capitalize() for k in output.keys()}
        is_complete = REQUIRED_KEYS.issubset(extracted)
        if is_complete:
            complete_5w1h += 1

        # Grounding: 'how' holds real SOP steps, not the placeholder / not empty
        how = output.get("how") or output.get("How") or ""
        is_grounded = isinstance(how, str) and bool(how.strip()) and PLACEHOLDER_HOW not in how.lower()
        if is_grounded:
            grounded += 1

        # Tier mapping (§1.6): A = complete + grounded · B = complete, ungrounded · C = incomplete
        if is_complete and is_grounded:
            tier_a += 1
        elif is_complete:
            tier_b += 1
        else:
            tier_c += 1

    def pct(n): return (n / total) * 100 if total else 0

    print("==========================================")
    print("   📊 5W1H Baseline Evaluation Results    ")
    print("==========================================")
    print(f"Total Test Cases Run:       {total}")
    print(f"Valid JSON Responses:       {valid_json}/{total} ({pct(valid_json):.1f}%)")
    print(f"Complete 5W1H Schema:       {complete_5w1h}/{total} ({pct(complete_5w1h):.1f}%)")
    print(f"Grounded (how != pending):  {grounded}/{total} ({pct(grounded):.1f}%)")
    print("------------------------------------------")
    print(f"Tier A (complete+grounded): {tier_a}")
    print(f"Tier B (complete, ungrounded): {tier_b}")
    print(f"Tier C (incomplete):        {tier_c}")
    print("==========================================")
    print("Schema  = does the 6-key structure exist?")
    print("Grounded= is 'how' backed by a real retrieved SOP?")
    print("Tier A = schema-complete AND grounded | Tier B = complete but ungrounded")

    # ------------------------------------------------------------------
    # CI gate — active only when thresholds are set via env (e.g. ci.yml).
    #   CI_SCHEMA_MIN  : hard gate, schema must reach this % (use 100.0)
    #   CI_GROUNDED_MIN: floor, grounding ≥ this % (use 80.0 ≈ 44/55;
    #                    grounding is stochastic, so don't gate it high)
    # Exits 1 on breach so the CI step fails; exits 0 otherwise.
    # ------------------------------------------------------------------
    if "CI_SCHEMA_MIN" in os.environ or "CI_GROUNDED_MIN" in os.environ:
        schema_min = float(os.environ.get("CI_SCHEMA_MIN", "0"))
        grounded_min = float(os.environ.get("CI_GROUNDED_MIN", "0"))
        schema_pct, grounded_pct = pct(complete_5w1h), pct(grounded)

        failures = []
        if schema_pct < schema_min:
            failures.append(f"schema {schema_pct:.1f}% < required {schema_min:.1f}%")
        if grounded_pct < grounded_min:
            failures.append(f"grounded {grounded_pct:.1f}% < required {grounded_min:.1f}%")

        if failures:
            print("[ci-gate] FAIL — " + "; ".join(failures))
            sys.exit(1)
        print(f"[ci-gate] PASS — schema {schema_pct:.1f}% (min {schema_min:.1f}%), "
              f"grounded {grounded_pct:.1f}% (min {grounded_min:.1f}%)")


if __name__ == "__main__":
    evaluate_results()