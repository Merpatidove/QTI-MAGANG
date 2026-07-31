import json
import os
import time
import requests
from pathlib import Path

base_dir = Path(__file__).parent.parent
dataset_path = base_dir / "data-pipeline" / "golden_datasets.json"
results_path = Path(__file__).parent / "evaluation_results.json"

with open(dataset_path, "r") as f:
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
    
    # ✅ FIX 1: Map the dataset fields to the Rust backend's strict QueryRequest schema
    rust_payload = {
        "ticket_id": ticket_id,
        "raw_text": raw_payload.get("ticket_content", raw_payload.get("raw_text", "Unknown content")),
        "project_tags": raw_payload.get("project_tags", [])
    }
    
    # ✅ FIX 2: Point to the API Gateway NodePort (Tailscale worker-2) /v1/query.
    # Override with QTI_API_URL env var if needed (e.g. a local SSH tunnel).
    api_url = os.environ.get("QTI_API_URL", "http://100.106.122.68:30082/v1/query")
    response = requests.post(
        api_url,
        json=rust_payload
    )
    
    process_time = round(time.time() - start_time, 2)
    
    result_entry = {
        "ticket_id": ticket_id,
        "inference_time_sec": process_time,
        "status_code": response.status_code,
        "5w1h_output": response.json() if response.status_code == 200 else response.text
    }
    
    print(f"Processed {ticket_id} in {process_time}s (Status: {response.status_code})")
    evaluation_data.append(result_entry)

with open(results_path, "w") as f:
    json.dump(evaluation_data, f, indent=2)

print("Batch processing complete. Results saved to evaluation_results.json")