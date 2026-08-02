import json
import os
import time
import requests
from pathlib import Path

base_dir = Path(__file__).parent.parent
dataset_path = base_dir / "data-pipeline" / "golden_datasets.json"
results_path = Path(__file__).parent / "evaluation_results.json"

# The agent (agent.py) runs as a FastAPI service:  uvicorn agent:app --port 8000
# The real pipeline is test_run -> agent -> Ollama (NOT the gateway /v1/query).
AGENT_URL = os.environ.get("AGENT_URL", "http://127.0.0.1:8000")

with open(dataset_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# If the JSON is a dictionary containing a list of tickets, extract the list.
if isinstance(data, dict):
    tickets = data.get("tickets", [data])
else:
    tickets = data

evaluation_data = []

for index, ticket in enumerate(tickets):
    start_time = time.time()

    # Handle both dictionary objects and raw string inputs gracefully
    raw_payload = ticket if isinstance(ticket, dict) else {"ticket_content": ticket}
    ticket_id = raw_payload.get("ticket_id", f"TICKET_{index+1}")

    # The agent's Ticket model accepts ticket_id + raw_text (project_tags is ignored).
    payload = {
        "ticket_id": ticket_id,
        "raw_text": raw_payload.get("ticket_content", raw_payload.get("raw_text", "Unknown content")),
        "project_tags": raw_payload.get("project_tags", [])
    }

    status_code = 0
    w5h = {}
    error = None
    try:
        response = requests.post(f"{AGENT_URL}/process-ticket", json=payload, timeout=360)
        status_code = response.status_code
        if status_code == 200:
            agent_resp = response.json()
            # Extract the FLAT six-key 5W1H dict the grader expects.
            w5h = agent_resp.get("5w1h_output", agent_resp) if isinstance(agent_resp, dict) else {}
        else:
            error = f"HTTP {status_code}: {response.text[:200]}"
    except Exception as e:
        error = f"request error: {e}"

    process_time = round(time.time() - start_time, 2)

    result_entry = {
        "ticket_id": ticket_id,
        "inference_time_sec": process_time,
        "status_code": status_code,
        "5w1h_output": w5h,
    }
    if error:
        # Top-level error -> grade_result.py skips this ticket's valid-JSON count.
        result_entry["error"] = error

    evaluation_data.append(result_entry)
    tag = "OK" if error is None else f"ERR({error})"
    print(f"[{index+1}/{len(tickets)}] {ticket_id} in {process_time}s {tag}")

with open(results_path, "w", encoding="utf-8") as f:
    json.dump(evaluation_data, f, indent=2, ensure_ascii=False)

print(f"\nBatch processing complete. {len(evaluation_data)} tickets -> {results_path}")