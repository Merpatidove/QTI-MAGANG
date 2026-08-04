import json
import os
import time
from typing import List, Optional

import requests
from fastapi import FastAPI
from fastapi.responses import Response
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

import tools

OLLAMA_URL   = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "hf.co/stefancosma/Qwen2.5-Coder-7B-Instruct-Q4_K_M-GGUF:latest")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "120"))
PLACEHOLDER_HOW = "Pending SOP search"

app = FastAPI(title="HITE 5W1H Triage Agent")

# ---------------- Prometheus metrics (Jep's action item) ----------------
LLM_DURATION    = Histogram("qti_llm_request_duration_seconds", "Ollama latency by phase", ["phase"])
LLM_TOKENS      = Counter("qti_llm_tokens_total", "Tokens used by type", ["type"])
PARSE_ERRORS    = Counter("qti_agent_parse_errors_total", "JSON decode failures from the model")
OLLAMA_TIMEOUTS = Counter("qti_agent_ollama_timeouts_total", "Ollama request timeouts")
EMPTY_RETRIEVALS= Counter("qti_agent_empty_retrieval_total", "search_sop calls with no usable SOP")


class Ticket(BaseModel):
    ticket_id: str = ""
    raw_text: str
    project_tags: List[str] = []


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
async def health():
    return {"status": "ok"}


def call_ollama(prompt: str, phase: str) -> str:
    t0 = time.perf_counter()
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=OLLAMA_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        LLM_TOKENS.labels(type="prompt").inc(data.get("prompt_eval_count", 0) or 0)
        LLM_TOKENS.labels(type="completion").inc(data.get("eval_count", 0) or 0)
        return data.get("response", "")
    except requests.exceptions.Timeout:
        OLLAMA_TIMEOUTS.inc()
        return ""
    except requests.exceptions.RequestException:
        return ""
    finally:
        LLM_DURATION.labels(phase=phase).observe(time.perf_counter() - t0)


def parse_json(text: str) -> Optional[dict]:
    try:
        s, e = text.find("{"), text.rfind("}")
        if s == -1 or e == -1:
            raise ValueError("no braces")
        return json.loads(text[s:e + 1])
    except Exception:
        PARSE_ERRORS.inc()
        return None


def analysis_prompt(t: Ticket) -> str:
    return (
        "You are an IT operations triage assistant. Read the ticket and reply with ONLY a JSON object "
        'with exactly these keys: "what","where","when","who","why","how","action".\n'
        '- Fill the 5W1H from the ticket; use "" if unknown.\n'
        f'- "how" must be "{PLACEHOLDER_HOW}" for now.\n'
        '- "action" is one of: "search_sop","execute_safe_cli","none". Use "search_sop" for any error/failure/remediation ticket.\n'
        f"Ticket:\n{t.raw_text}\nReply with JSON only."
    )


def synthesis_prompt(t: Ticket, analysis: dict, tool_output) -> str:
    prior = json.dumps({k: analysis.get(k, "") for k in ("what", "where", "when", "who")})
    return (
        "You are an IT operations triage assistant. Using the retrieved SOP, finalize the triage. "
        'Reply with ONLY a JSON object with keys "what","where","when","who","why","how".\n'
        f'Ground "why" and "how" in the SOP. "how" must be a concrete remediation (never "{PLACEHOLDER_HOW}").\n'
        f"Ticket:\n{t.raw_text}\nRetrieved SOP:\n{tool_output}\nPrior analysis:\n{prior}\nReply with JSON only."
    )


@app.post("/process-ticket")
async def process_ticket(ticket: Ticket):
    # Step 1: analysis
    analysis = parse_json(call_ollama(analysis_prompt(ticket), phase="analysis")) or {}
    action = str(analysis.get("action", "none")).strip()
    if action not in ("search_sop", "execute_safe_cli", "none"):
        action = "none"

    five = {k: str(analysis.get(k, "") or "") for k in ("what", "where", "when", "who", "why")}
    five["how"] = str(analysis.get("how", "") or PLACEHOLDER_HOW)

    # Step 2: tool dispatch
    tool_output = None
    if action == "search_sop":
        tool_output = tools.search_sop(ticket.raw_text)
        if tool_output is None or not str(tool_output).strip() or str(tool_output).lstrip().startswith("Error"):
            EMPTY_RETRIEVALS.inc()
    elif action == "execute_safe_cli":
        try:
            tool_output = tools.execute_safe_cli(ticket.raw_text)
        except Exception:
            tool_output = None

    # Step 3: synthesis gate (the _is_err fix that raised grounding to 96.4%)
    _is_err = (
        tool_output is None
        or (isinstance(tool_output, dict) and bool(tool_output.get("error")))
        or str(tool_output).lstrip().startswith("Error")
    )
    if not _is_err:
        synth = parse_json(call_ollama(synthesis_prompt(ticket, analysis, tool_output), phase="synthesis"))
        if synth:
            for k in ("what", "where", "when", "who", "why", "how"):
                if str(synth.get(k, "") or "").strip():
                    five[k] = str(synth.get(k)).strip()

    return {"ticket_id": ticket.ticket_id, "action_taken": action, "result": tool_output, "5w1h_output": five}