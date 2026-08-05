"""HITE 5W1H evaluation harness (client — does NOT start a server).

POSTs every ticket in the dataset to the agent's /process-ticket and writes
evaluation_results.json for grade_result.py to score.

Dataset switch: set DATASET to grade a different set, e.g.
    $env:DATASET = "..\data-pipeline\real_tickets.json"
Unset it to go back to the synthetic golden set.
"""

import json
import os
import time

import requests

AGENT_URL = os.environ.get("AGENT_URL", "http://127.0.0.1:8000")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATASET = os.path.join(SCRIPT_DIR, "..", "data-pipeline", "golden_datasets.json")
DATASET_PATH = os.environ.get("DATASET", DEFAULT_DATASET)
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "evaluation_results.json")

PLACEHOLDER_HOW = "Pending SOP search"


def load_tickets(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # Shape 1: flat array (real_tickets.json)
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        # Shape 2: object wrapping a list of tickets, e.g. {"tickets": [...]}
        for v in data.values():
            if isinstance(v, list) and v and all(isinstance(t, dict) for t in v):
                return v
        # Shape 3: object keyed by ticket id, values are ticket dicts
        tickets = [
            {**v, "ticket_id": v.get("ticket_id", k)}
            for k, v in data.items()
            if isinstance(v, dict)
            and ("raw_text" in v or "ticket_content" in v or "raw" in v)
        ]
        if tickets:
            return tickets

    raise SystemExit(
        f"{path}: unrecognized dataset shape. Expected a flat ticket array "
        "(real_tickets.json) or the wrapped form of golden_datasets.json."
    )


def ticket_text(t):
    # tolerate the field-name variants seen across datasets
    return (
        t.get("raw_text")
        or t.get("ticket_content")
        or t.get("ticket_text")
        or t.get("raw")
        or ""
    )


def is_grounded(how):
    how = (how or "").strip()
    return bool(how) and PLACEHOLDER_HOW.lower() not in how.lower()


def process_one(ticket):
    payload = {
        "ticket_id": ticket.get("ticket_id", ""),
        "raw_text": ticket_text(ticket),
        "project_tags": ticket.get("project_tags", []),
    }
    start = time.time()
    try:
        r = requests.post(f"{AGENT_URL}/process-ticket", json=payload, timeout=600)
        r.raise_for_status()
        resp = r.json()
        error = None
    except Exception as e:  # network / HTTP / JSON failure
        resp = {}
        error = f"{type(e).__name__}: {e}"
    elapsed = time.time() - start

    out5w1h = resp.get("5w1h_output") or {}
    how = out5w1h.get("how") or out5w1h.get("How") or ""

    return {
        "ticket_id": payload["ticket_id"],
        "5w1h_output": out5w1h,
        "action_taken": resp.get("action_taken"),
        "result_preview": (resp.get("result") or "")[:200],
        "grounded": is_grounded(how) and error is None,
        "inference_time_sec": round(elapsed, 2),
        **({"error": error} if error else {}),
    }


def main():
    tickets = load_tickets(DATASET_PATH)
    print(f"Dataset: {os.path.abspath(DATASET_PATH)} ({len(tickets)} tickets)")

    results = []
    for i, t in enumerate(tickets, 1):
        row = process_one(t)
        results.append(row)
        status = "OK" if "error" not in row else "ERR"
        print(
            f"[{i}/{len(tickets)}] {row['ticket_id']} "
            f"in {row['inference_time_sec']}s grounded={row['grounded']} {status}"
        )

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nBatch processing complete. {len(results)} tickets -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()