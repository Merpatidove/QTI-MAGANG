import json
from pathlib import Path

# A 'how' that still holds the prompt's placeholder example is NOT grounded in a SOP.
# Keep this string in sync with the `grounded` flag in test_run.py.
PLACEHOLDER_HOW = "pending sop search"
REQUIRED_KEYS = {"Who", "What", "When", "Where", "Why", "How"}


def evaluate_results():
    results_path = Path("evaluation_results.json")
    if not results_path.exists():
        print("Error: evaluation_results.json not found! Run test_run.py first.")
        exit(1)

    with open(results_path, 'r', encoding='utf-8') as f:
        try:
            results = json.load(f)
        except json.JSONDecodeError:
            print("Error: evaluation_results.json is corrupted or not valid JSON.")
            exit(1)

    if not results:
        print("evaluation_results.json is empty. No tests to grade.")
        return

    total = len(results)
    valid_json = 0
    complete_5w1h = 0
    grounded = 0

    for item in results:
        output = item.get("5w1h_output", {})          # Fix A: the real key
        if not (isinstance(output, dict) and not item.get("error")):
            continue
        valid_json += 1

        # Schema completeness: all six keys present (capitalize matches lowercase emit)
        extracted = {str(k).capitalize() for k in output.keys()}
        if REQUIRED_KEYS.issubset(extracted):
            complete_5w1h += 1

        # Grounding: 'how' holds real SOP steps, not the placeholder / not empty
        how = output.get("how") or output.get("How") or ""
        if isinstance(how, str) and how.strip() and PLACEHOLDER_HOW not in how.lower():
            grounded += 1

    def pct(n): return (n / total) * 100 if total else 0

    print("==========================================")
    print("   📊 5W1H Baseline Evaluation Results    ")
    print("==========================================")
    print(f"Total Test Cases Run:      {total}")
    print(f"Valid JSON Responses:      {valid_json}/{total} ({pct(valid_json):.1f}%)")
    print(f"Complete 5W1H Schema:      {complete_5w1h}/{total} ({pct(complete_5w1h):.1f}%)")
    print(f"Grounded (how != pending): {grounded}/{total} ({pct(grounded):.1f}%)")
    print("==========================================")
    print("Schema  = does the 6-key structure exist?")
    print("Grounded= is 'how' backed by a real retrieved SOP?")
    print("Tier A = schema-complete AND grounded | Tier B = complete but ungrounded")


if __name__ == "__main__":
    evaluate_results()