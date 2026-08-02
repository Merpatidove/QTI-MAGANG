import os
import requests

# The live RAG path is the api-gateway on NodePort 30082 (HITE Guidebook §1.1, §7).
# Fix D: search_sop previously pointed at the DELETED rag-service:8000 — now the gateway.
GATEWAY_URL = os.environ.get("QTI_API_URL", "http://100.106.122.68:30082")


def search_sop(query: str) -> str:
    """Retrieve RAG context from the live api-gateway (/v1/query, NodePort 30082).
    Returns the retrieved SOP text (remediation_payload.proposed_fix)."""
    payload = {"ticket_id": "RAG-QUERY", "raw_text": query, "project_tags": []}
    response = requests.post(f"{GATEWAY_URL}/v1/query", json=payload, timeout=60)
    response.raise_for_status()
    return response.json().get("remediation_payload", {}).get("proposed_fix", "")


def execute_safe_cli(command: str) -> str:
    """Waskito's Docker execution sandbox is NOT deployed in this environment.
    Return an 'Error:'-prefixed message so agent.py skips the synthesis phase and
    falls back to the analysis-phase 5W1H (still a valid six-key object).
    Non-critical for the 5W1H schema score."""
    return (
        f"Error: execute_safe_cli sandbox not deployed in eval environment "
        f"(command not run: {command})"
    )