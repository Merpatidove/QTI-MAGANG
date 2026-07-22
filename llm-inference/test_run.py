import json
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
    payload = ticket if isinstance(ticket, dict) else {"ticket_content": ticket}
    ticket_id = payload.get("ticket_id", f"TICKET_{index+1}")
    
    response = requests.post(
        "http://127.0.0.1:8000/process-ticket", 
        json=payload
    )
    
    process_time = round(time.time() - start_time, 2)
    
    result_entry = {
        "ticket_id": ticket_id,
        "inference_time_sec": process_time,
        "status_code": response.status_code,
        "5w1h_output": response.json() if response.status_code == 200 else response.text
    }
    
    print(f"Processed {ticket_id} in {process_time}s")
    evaluation_data.append(result_entry)

with open(results_path, "w") as f:
    json.dump(evaluation_data, f, indent=2)

print("Batch processing complete. Results saved to evaluation_results.json")