# HITE API Contract (JSON Schema)
**Version:** 2.0
**Status:** Locked for Initial Prototype (retrieval-only, 2026-08-02)

---

## Overview

This contract describes the **api-gateway** (Rust/Axum), which is **retrieval-only**: it accepts a ticket, embeds the text, searches the Qdrant knowledge base for the closest-matching SOP, and returns the retrieved SOP text as context.

It does **not** perform inference, generate a 5W1H triage, assign a confidence tier, or make routing decisions. Those belong to the DS Python agent (`llm-inference/agent.py`), which calls this gateway to obtain RAG context and then calls Ollama for generation. See `llm-inference/` for the agent's own output contract.

---

## 1. The Input Payload (Request)

The DS agent's `tools.search_sop` sends this payload to `POST /v1/query` on the gateway (NodePort 30082, `http://100.106.122.68:30082/v1/query`).

```json
{
  "ticket_id": "TKT-8492",
  "raw_text": "Getting a non-fast-forward error when trying to push to ResponsiPemweb_6_Bali main branch.",
  "project_tags": ["git", "version-control"]
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `ticket_id` | string | yes | Arbitrary identifier; echoed back in the response |
| `raw_text` | string | yes | The ticket/error text to embed and search against |
| `project_tags` | array of strings | yes | Currently unused by the gateway (reserved for future filtering) |

---

## 2. The Output Payload (Response)

The gateway returns the retrieved SOP text as context for the DS agent to ground its generation.

### 2.1 Success case (classification: `"retrieved"`)

```json
{
  "ticket_metadata": {
    "ticket_id": "TKT-8492",
    "classification": "retrieved"
  },
  "remediation_payload": {
    "proposed_fix": "SOP-GIT-003 Non-Fast-Forward Push: ## Context\nError Signature: `git push` rejected with `non-fast-forward`...",
    "requires_type_check": true
  }
}
```

| Field | Type | Notes |
|---|---|---|
| `ticket_metadata.ticket_id` | string | Echo of the request's `ticket_id` |
| `ticket_metadata.classification` | string | `"retrieved"` when a SOP was found; `"embed_error"` if embedding failed |
| `remediation_payload.proposed_fix` | string | The retrieved SOP text (prefixed `SOP-{id} {title}:`); or `"No matching SOP found in the knowledge base."` on no match |
| `remediation_payload.requires_type_check` | boolean | Always `true` for `"retrieved"` and `"embed_error"` responses |

### 2.2 Error case (classification: `"embed_error"`)

Returned when the embedding model fails (e.g. corrupted cache). The DS agent should treat this as ungrounded input.

```json
{
  "ticket_metadata": {
    "ticket_id": "TKT-8492",
    "classification": "embed_error"
  },
  "remediation_payload": {
    "proposed_fix": "Embedding failed: <error details>",
    "requires_type_check": true
  }
}
```

---

## 3. HTTP Contract

| Method | Path | Status Codes |
|---|---|---|
| `GET` | `/v1/health` | 200 — `{"status":"ok","version":"0.1.0"}` |
| `POST` | `/v1/query` | 200 (errors reported in body, not via HTTP status) |
| `GET` | `/metrics` | 200 — Prometheus text format |

A malformed JSON body on `/v1/query` returns **422 Unprocessable Entity** (Axum default).

---

## 4. What's NOT in this contract

The following fields from earlier drafts have been moved to the **DS agent's output** (the `5w1h_output` dict the agent returns on `/process-ticket`):

- ~~`cognitive_triage`~~ (fact_coverage_score, confidence_tier, qdrant_match_found)
- ~~`grounding_citations`~~
- ~~`routing_decision`~~

These are properties of the *generated* 5W1H answer, not of the retrieval step. The gateway has no visibility into them and must not be expected to emit them.

---

## 5. Version History

- **v1.0 (2026-07-14)** — initial draft; described a gateway that forwarded to inference and returned Tier/routing/citations. Never implemented.
- **v2.0 (2026-08-02)** — revised to match the retrieval-only decision. Gateway returns only the retrieved SOP text; inference and 5W1H generation live in the DS agent.