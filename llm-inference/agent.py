import json
import os
import time

import requests
from fastapi import FastAPI, Response
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

import tools

# ------------------------------------------------------------------ config
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get(
    "OLLAMA_MODEL",
    "hf.co/stefancosma/Qwen2.5-Coder-7B-Instruct-Q4_K_M-GGUF:latest",
)
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "300"))
# Balanced option: low-but-nonzero temperature + fixed seed (near-reproducible,
# without greedy lock-in). Env-overridable per run.
OLLAMA_TEMPERATURE = float(os.environ.get("OLLAMA_TEMPERATURE", "0.1"))
OLLAMA_SEED = int(os.environ.get("OLLAMA_SEED", "42"))

SIX_KEYS = ["what", "where", "when", "who", "why", "how"]
PLACEHOLDER_HOW = "Pending SOP search"

# ------------------------------------------------------------------ metrics
LLM_DURATION = Histogram(
    "qti_llm_request_duration_seconds", "LLM request duration by phase", ["phase"]
)
LLM_TOKENS = Counter("qti_llm_tokens_total", "LLM tokens by type", ["type"])
PARSE_ERRORS = Counter("qti_agent_parse_errors_total", "JSON decode failures")
OLLAMA_TIMEOUTS = Counter("qti_agent_ollama_timeouts_total", "Ollama request timeouts")
EMPTY_RETRIEVAL = Counter(
    "qti_agent_empty_retrieval_total", "search_sop calls with no actionable SOP"
)

app = FastAPI(title="HITE 5W1H agent")


class Ticket(BaseModel):
    ticket_id: str
    raw_text: str
    project_tags: list = []


# ------------------------------------------------------------------ prompts
ANALYSIS_SYSTEM = (
    "You are an IT ticket triage agent. Analyze the ticket and reply with STRICT JSON only "
    "(no markdown) with exactly these lowercase keys: "
    '"what", "where", "when", "who", "why", "how", "action". '
    "Fill what/where/when/who from the ticket (empty string if unknown). Set \"why\" to a "
    'brief hypothesis. Set "how" to the exact placeholder "Pending SOP search" for now. '
    '"action" must be exactly one of: "search_sop", "execute_safe_cli", "none".'
)


def synthesis_prompt(ticket_text: str, sop_context: str) -> str:
    return (
        "You are an IT ticket triage agent. Using the retrieved SOP context below, produce the "
        'final triage as STRICT JSON (no markdown) with exactly the six keys "what", "where", '
        '"when", "who", "why", "how". Ground "why" and "how" in the SOP; "how" must be the '
        "SOP's concrete remediation steps (never the placeholder).\n"
        f"Retrieved SOP context:\n{sop_context}\n\nTicket:\n{ticket_text}"
    )


# ------------------------------------------------------------------ helpers
def parse_json(text: str) -> dict:
    if not text:
        return {}
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        lo, hi = t.find("{"), t.rfind("}")
        if lo != -1 and hi > lo:
            try:
                return json.loads(t[lo : hi + 1])
            except json.JSONDecodeError:
                pass
        PARSE_ERRORS.inc()
        return {}


def call_ollama(prompt: str, phase: str = "analysis") -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "temperature": OLLAMA_TEMPERATURE,
        "seed": OLLAMA_SEED,
    }
    start = time.time()
    try:
        r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=OLLAMA_TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.Timeout:
        OLLAMA_TIMEOUTS.inc()
        return ""
    except requests.exceptions.RequestException:
        return ""
    finally:
        LLM_DURATION.labels(phase=phase).observe(time.time() - start)
    LLM_TOKENS.labels(type="prompt").inc(data.get("prompt_eval_count") or 0)
    LLM_TOKENS.labels(type="completion").inc(data.get("eval_count") or 0)
    return data.get("response", "")


def _is_err(tool_output) -> bool:
    """Structured error check (replaces the old '"Error" not in str(...)' substring veto)."""
    if tool_output is None:
        return True
    if isinstance(tool_output, dict):
        return "error" in tool_output
    if isinstance(tool_output, str):
        s = tool_output.strip()
        return (not s) or s.startswith("Error")
    return True


# ------------------------------------------------------------------ routes
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/process-ticket")
def process_ticket(ticket: Ticket):
    # 1) analysis: 5W1H + tool choice
    parsed = parse_json(
        call_ollama(f"{ANALYSIS_SYSTEM}\n\nTicket:\n{ticket.raw_text}", phase="analysis")
    )
    five = {k: str(parsed.get(k) or "") for k in SIX_KEYS}
    if not five["how"]:
        five["how"] = PLACEHOLDER_HOW
    action = parsed.get("action", "none")
    action_taken = action if action in ("search_sop", "execute_safe_cli", "none") else "none"

    # 2) tool dispatch
    tool_output = None
    if action_taken == "search_sop":
        try:
            tool_output = tools.search_sop(ticket.raw_text)
        except Exception:
            tool_output = None
        if _is_err(tool_output):
            EMPTY_RETRIEVAL.inc()
    elif action_taken == "execute_safe_cli":
        fn = getattr(tools, "execute_safe_cli", None)
        try:
            tool_output = fn(ticket.raw_text) if fn else None
        except Exception:
            tool_output = None

    # 3) synthesis: ground why/how in the retrieved SOP (only if retrieval succeeded)
    if action_taken == "search_sop" and not _is_err(tool_output):
        sparsed = parse_json(
            call_ollama(synthesis_prompt(ticket.raw_text, tool_output), phase="synthesis")
        )
        if sparsed:
            for k in SIX_KEYS:
                if sparsed.get(k):
                    five[k] = str(sparsed[k])

    return {
        "ticket_id": ticket.ticket_id,
        "action_taken": action_taken,
        "result": str(tool_output) if tool_output is not None else "",
        "5w1h_output": five,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)