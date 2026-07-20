import json
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prompts import REACT_SYSTEM_PROMPT
from tools import search_sop, execute_safe_cli

app = FastAPI()

# Placeholder IP - Waskito/DevOps will give you the real Mac Mini IP
MAC_MINI_OLLAMA_URL = "http://qti@192.168.20.163:11434/api/generate"
class Ticket(BaseModel):
    ticket_id: str
    raw_text: str

@app.post("/process-ticket")
def process_ticket(ticket: Ticket):
    # 1. Combine your 5W1H rules with the raw syslog
    full_prompt = f"{REACT_SYSTEM_PROMPT}\n\nIncoming Syslog:\n{ticket.raw_text}"
    
    payload = {
        "model": "hf.co/stefancosma/Qwen2.5-Coder-7B-Instruct-Q4_K_M-GGUF:latest",
        "prompt": full_prompt,
        "stream": False,
        "format": "json" 
    }
    # 2. Send to Mac Mini
    try:
        ollama_response = requests.post(MAC_MINI_OLLAMA_URL, json=payload)
        ollama_response.raise_for_status()
        agent_decision = ollama_response.json().get("response", "")
        decision_data = json.loads(agent_decision)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to Mac Mini: {str(e)}")

    # 3. Execution Phase
    tool_name = decision_data.get("tool")
    params = decision_data.get("params", {})
    
    result = "No action taken."
    
    if tool_name == "search_sop":
        result = search_sop(params.get("query", ""))
    elif tool_name == "execute_safe_cli":
        result = execute_safe_cli(params.get("command", ""))
    elif decision_data.get("status") == "ESCALATE":
        result = "Ticket escalated to human operators."

    return {
        "ticket_id": ticket.ticket_id,
        "5w1h_analysis": decision_data.get("5w1h_analysis", "No analysis provided."),
        "action_taken": tool_name if tool_name else decision_data.get("status"),
        "result": result
    }