import json
from pathlib import Path

def evaluate_results():
    # Define paths based on your current directory structure
    results_path = Path("evaluation_results.json")
    
    # Safety check (matches the error you saw earlier!)
    if not results_path.exists():
        print("Error: evaluation_results.json not found! Run test_run.py first.")
        exit(1)

    # Load the LLM inference results
    with open(results_path, 'r', encoding='utf-8') as f:
        try:
            results = json.load(f)
        except json.JSONDecodeError:
            print("Error: evaluation_results.json is corrupted or not valid JSON.")
            exit(1)

    if not results:
        print("evaluation_results.json is empty. No tests to grade.")
        return

    total_tests = len(results)
    valid_json_count = 0
    complete_5w1h_count = 0

    # The exact 5W1H schema keys the agent is expected to extract
    required_keys = {"Who", "What", "When", "Where", "Why", "How"}

    for item in results:
        # Assuming your test_run.py saves the parsed dictionary under 'output' or 'response'
        output = item.get("output", {})
        
        # 1. Evaluate JSON Decode Stability
        if isinstance(output, dict) and not item.get("error"):
            valid_json_count += 1
            
            # 2. Evaluate Schema Completeness (Did it extract all 6 elements?)
            # We convert the keys to uppercase/lowercase standard to ensure strict matching
            extracted_keys = {str(k).capitalize() for k in output.keys()}
            
            if required_keys.issubset(extracted_keys):
                complete_5w1h_count += 1

    # Calculate percentages
    json_success_rate = (valid_json_count / total_tests) * 100 if total_tests > 0 else 0
    schema_success_rate = (complete_5w1h_count / total_tests) * 100 if total_tests > 0 else 0

    # Print out the Baseline Evaluation Metrics
    print("==========================================")
    print("   📊 5W1H Baseline Evaluation Results    ")
    print("==========================================")
    print(f"Total Test Cases Run:   {total_tests}")
    print(f"Valid JSON Responses:   {valid_json_count}/{total_tests} ({json_success_rate:.1f}%)")
    print(f"Complete 5W1H Schema:   {complete_5w1h_count}/{total_tests} ({schema_success_rate:.1f}%)")
    print("==========================================")

    # Optional: Grade against golden_datasets.json if you want to check accuracy of the answers later
    # golden_path = Path("../golden_datasets.json")
    # if golden_path.exists():
    #    ... load golden data and compare values ...

if __name__ == "__main__":
    evaluate_results()