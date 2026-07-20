import requests

def search_sop(query: str) -> str:
    payload = {"query": query}
    # This points to Farrel's Qdrant vector search API
    response = requests.post("http://rag-service:8000/search", json=payload)
    return response.json().get("sop_text", "")

def execute_safe_cli(command: str) -> str:
    payload = {"cmd": command}
    # This points to Waskito's Docker execution sandbox
    response = requests.post("http://sandbox:8081/run", json=payload)
    return response.text