import json, os, re, time
import requests
from typing import List
from fastapi import FastAPI
from fastapi.responses import Response
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

OLLAMA_URL   = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "hf.co/stefancosma/Qwen2.5-Coder-7B-Instruct-Q4_K_M-GGUF:latest")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300"))
TEMP = float(os.getenv("OLLAMA_TEMPERATURE", "0.8"))     
SEED = os.getenv("OLLAMA_SEED")                          
QTI_API_URL = os.getenv("QTI_API_URL", "http://100.106.122.68:30082")
MAX_SYNTH_RETRIES = int(os.getenv("OLLAMA_SYNTH_RETRIES", "2"))   

PLACEHOLDER_HOW = "Pending SOP search"
SIX_KEYS = ["Who", "What", "When", "Where", "Why", "How"]

LLM_LAT  = Histogram("qti_llm_request_duration_seconds", "LLM latency by phase", ["phase"], buckets=(1,5,15,30,60,120,300))
TOKENS   = Counter("qti_llm_tokens_total", "Tokens by type", ["type"])
PARSE_ERR= Counter("qti_agent_parse_errors_total", "JSON decode failures")
OLLAMA_TO= Counter("qti_agent_ollama_timeouts_total", "Ollama request timeouts")
EMPTY_RET= Counter("qti_agent_empty_retrieval_total", "search_sop with no actionable SOP")

app = FastAPI(title="HITE DS agent")

class Ticket(BaseModel):
    ticket_id: str
    raw_text: str
    project_tags: List[str] = []

ANALYSIS_PROMPT = """You are HITE, an IT-support triage engine.
Read the ticket and reply with a STRICT JSON object with exactly these keys:
"Who","What","When","Where","Why","How","action"
- The six 5W1H keys hold your preliminary analysis (short strings).
- "action" MUST be one of: "search_sop", "none", "execute_safe_cli". Choose "search_sop" unless the ticket is benign.
Ticket:
{raw_text}
Project tags: {tags}
Reply with ONLY the JSON object. No prose, no code fences."""

SYNTHESIS_PROMPT = """You are HITE, an IT-support triage engine.
Ticket:
{raw_text}
Retrieved SOP context (grounding source):
{sop_text}
Rewrite the final triage as a STRICT JSON object with EXACTLY six keys:
"Who","What","When","Where","Why","How".
- Ground "Why" and "How" in the retrieved SOP context above.
- If the SOP context is empty or unusable, set "How" to exactly "{placeholder}".
Reply with ONLY the JSON object. No prose, no code fences."""

def call_ollama(prompt: str, phase: str) -> str:
    opts = {"temperature": TEMP, "num_predict": 1024}
    if SEED: opts["seed"] = int(SEED)
    t0 = time.time()
    try:
        r = requests.post(f"{OLLAMA_URL}/api/generate",
                          json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "options": opts},
                          timeout=OLLAMA_TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.Timeout:
        OLLAMA_TO.inc(); raise
    finally:
        LLM_LAT.labels(phase=phase).observe(time.time() - t0)
    TOKENS.labels(type="prompt").inc(float(data.get("prompt_eval_count", 0)))
    TOKENS.labels(type="completion").inc(float(data.get("eval_count", 0)))
    return data.get("response", "")

def _strip_fences(s: str) -> str:
    return s.replace("```json", "").replace("```", "").strip()

def _parse_json_obj(raw: str) -> dict:
    text = _strip_fences(raw)
    try:
        v = json.loads(text)
        if isinstance(v, dict): return v
    except json.JSONDecodeError:
        pass
    
    m = re.search(r"\{.*\}", text, re.DOTALL)          
    if m:
        try:
            v = json.loads(m.group(0))
            if isinstance(v, dict): return v
        except json.JSONDecodeError:
            pass
            
    raise ValueError("no JSON object in model output")

def synthesize(prompt: str) -> dict:
    last = None
    for attempt in range(MAX_SYNTH_RETRIES + 1):
        raw = call_ollama(prompt, phase="synthesis")
        try:
            return _parse_json_obj(raw)
        except Exception as e:
            last = e
            PARSE_ERR.inc()
            if attempt < MAX_SYNTH_RETRIES:
                prompt = (prompt + "\n\nYour previous reply was NOT valid JSON:\n" + raw[:400]
                          + "\nError: " + str(e)
                          + "\nReply with ONLY the JSON object — no prose, no code fences.")
    raise last

def _is_err(payload) -> bool:      
    if not isinstance(payload, dict) or not payload: return True
    fix = str(payload.get("proposed_fix") or "").strip()
    return (not fix) or fix.lower() in {"none", "null", "n/a", "placeholder"}

def search_sop(t: Ticket):
    try:
        r = requests.post(f"{QTI_API_URL}/v1/query",
                          json={"ticket_id": t.ticket_id, "raw_text": t.raw_text, "project_tags": t.project_tags},
                          timeout=30)
        r.raise_for_status()
        payload = r.json().get("remediation_payload", {}) or {}
    except Exception:
        payload = {}
    if _is_err(payload):
        EMPTY_RET.inc(); return None
    return payload

def _norm(d: dict) -> dict:
    out = {}
    for k in SIX_KEYS:
        hit = next((x for x in d if x.strip().lower() == k.lower()), None)
        v = d.get(hit) if hit else None
        out[k] = str(v).strip() if v not in (None, "") else ""
    return out

def _complete(d: dict) -> bool:
    return all(d.get(k) for k in SIX_KEYS)

@app.post("/process-ticket")
def process_ticket(t: Ticket):
    action, sop, analysis = "search_sop", None, {}
    try:
        analysis = _parse_json_obj(call_ollama(
            ANALYSIS_PROMPT.format(raw_text=t.raw_text, tags=", ".join(t.project_tags)), phase="analysis"))
        action = str(analysis.get("action", "search_sop")).strip().lower()
    except Exception:
        PARSE_ERR.inc(); action = "search_sop"

    if action == "search_sop":
        sop = search_sop(t)

    final, grounded = None, False
    if sop is not None:
        try:
            final = _norm(synthesize(SYNTHESIS_PROMPT.format(
                raw_text=t.raw_text, sop_text=json.dumps(sop), placeholder=PLACEHOLDER_HOW)))
            grounded = _complete(final) and final["How"] != PLACEHOLDER_HOW
        except Exception:
            final = None

    if final is None:                      
        final = _norm(analysis)
        for k in SIX_KEYS:
            if not final[k]:
                final[k] = PLACEHOLDER_HOW if k == "How" else (t.raw_text[:80] if k == "What" else "unknown")
        grounded = False

    complete = _complete(final)
    tier = "A" if (complete and grounded) else "B" if complete else "C"
    return {"ticket_id": t.ticket_id, "5w1h_output": final, "action_taken": action,
            "result_preview": (json.dumps(sop)[:200] if sop else ""),
            "grounded": grounded, "confidence_tier": tier}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)