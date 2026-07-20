import requests
import json

mock_ticket = {
    "ticket_id": "TEST-101",
    "raw_text": "SQLSTATE[HY000]: General error: 1205 Lock wait timeout exceeded"
}

print("Sending ticket to SRE Agent...")
response = requests.post("http://127.0.0.1:8000/process-ticket", json=mock_ticket)
print(json.dumps(response.json(), indent=2))