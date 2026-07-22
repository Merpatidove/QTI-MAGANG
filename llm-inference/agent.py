import json
import re
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
from prompts import REACT_SYSTEM_PROMPT
from tools import search_sop, execute_safe_cli

app = FastAPI()

MAC_MINI_OLLAMA_URL = "http://192.168.100.35:11434/api/generate"
MODEL_NAME = "hf.co/stefancosma/Qwen2.5-Coder-7B-Instruct-Q4_K_M-GGUF:latest"

# Flexible Pydantic model to handle all ticket payload variations in the golden dataset
class Ticket(BaseModel):
    ticket_id: str
    raw_text: Optional[str] = None
    ticket_content: Optional[str] = None
    description: Optional[str] = None
    log: Optional[str] = None
    content_text: Optional[str] = Field(default=None, alias="content")

    @property
    def content(self) -> str:
        return (
            self.raw_text
            or self.ticket_content
            or self.description
            or self.log
            or self.content_text
            or ""
        )


def clean_and_parse_json(raw_str: str) -> dict:
    """Strips markdown fences and safely parses JSON, even with raw newlines/control chars."""
    if not raw_str:
        return {}

    # 1. Strip markdown fences
    cleaned = re.sub(r"```(?:json)?", "", raw_str)
    cleaned = cleaned.replace("```", "").strip()

    # 2. Extract outermost JSON object
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)

    # 3. Parse JSON (strict=False permits unescaped newlines inside string values)
    try:
        return json.loads(cleaned, strict=False)
    except Exception as e:
        return {
            "error": "JSON parse error",
            "raw_output": raw_str,
            "exception": str(e)
        }


def call_ollama(prompt: str) -> dict:
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }
    try:
        response = requests.post(MAC_MINI_OLLAMA_URL, json=payload, timeout=45)
        response.raise_for_status()
        raw_output = response.json().get("response", "")
        return clean_and_parse_json(raw_output)
    except Exception as e:
        return {
            "error": str(e),
            "5w1h_analysis": "Error parsing model response or connecting to Ollama.",
            "tool": None
        }


@app.post("/process-ticket")
def process_ticket(ticket: Ticket):
    ticket_text = ticket.content
    if not ticket_text:
        raise HTTPException(
            status_code=400, 
            detail="No ticket content provided (checked raw_text, ticket_content, description, log, content)."
        )

    # Step 1: 5W1H Analysis & Tool Choice
    initial_prompt = f"{REACT_SYSTEM_PROMPT}\n\nIncoming Syslog/Ticket:\n{ticket_text}"
    decision_data = call_ollama(initial_prompt)

    tool_name = decision_data.get("tool")
    
    # Defend against "params": null from LLM output
    params = decision_data.get("params")
    if not isinstance(params, dict):
        params = {}

    tool_output = None

    # Step 2: Execute Tool safely if requested
    if tool_name == "search_sop":
        query = params.get("query") or ticket_text
        try:
            tool_output = search_sop(query)
        except Exception as e:
            tool_output = f"Error executing search_sop: {str(e)}"

    elif tool_name == "execute_safe_cli":
        command = params.get("command") or ""
        try:
            tool_output = execute_safe_cli(command)
        except Exception as e:
            tool_output = f"Error executing execute_safe_cli: {str(e)}"

    # Step 3: Synthesis Phase if tool output was retrieved
    if tool_output and "Error" not in str(tool_output):
        synthesis_prompt = f"""
Given the ticket below and the retrieved SOP content, output the final JSON response.

Ticket: {ticket_text}
Retrieved SOP Context: {tool_output}

Return JSON with keys: 'ticket_id', '5w1h_analysis', 'action_taken', and 'result'.
"""
        final_response = call_ollama(synthesis_prompt)
    else:
        final_response = decision_data

    # Step 4: Fallback extraction for analysis payload
    analysis_output = (
        final_response.get("5w1h_analysis") 
        or final_response.get("5w1h_output")
        or final_response.get("analysis")
        or final_response
    )

    return {
        "ticket_id": ticket.ticket_id,
        "5w1h_output": analysis_output,
        "action_taken": str(tool_name) if tool_name else "none",
        "result": tool_output if tool_output else "No action taken."
    }