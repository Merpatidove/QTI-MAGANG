# API Contract — QTI RAG Pipeline
**Version:** 1.0.0  
**Status:** DRAFT — Requires sign-off from all three teams  
**Last Updated:** 2026-07-10  
**Owners:** Inference Team · DevOps / API-Gateway Team · Data Engineering Team

---

## Table of Contents
1. [Overview & System Topology](#1-overview--system-topology)
2. [Shared Conventions](#2-shared-conventions)
3. [Boundary A — Client → API Gateway](#3-boundary-a--client--api-gateway)
4. [Boundary B — API Gateway → Qdrant](#4-boundary-b--api-gateway--qdrant)
5. [Boundary C — API Gateway → Inference (Mac Mini)](#5-boundary-c--api-gateway--inference-mac-mini)
6. [Error Envelope Reference](#6-error-envelope-reference)
7. [HTTP Status Code Matrix](#7-http-status-code-matrix)
8. [Versioning & Change Policy](#8-versioning--change-policy)
9. [Sign-off](#9-sign-off)

---

## 1. Overview & System Topology

```
 ┌──────────┐   (A)   ┌─────────────────┐   (B)  ┌────────┐
 │  Client  │────────▶│  Axum API GW    │───────▶│ Qdrant │
 └──────────┘         │  (K3s / DevOps) │        └────────┘
                      │                 │   (C)  ┌──────────────┐
                      │                 │───────▶│  Inference   │
                      └─────────────────┘        │  Mac Mini    │
                                                  │ (mistral.rs) │
                                                  └──────────────┘
```

| Boundary | Parties | Transport | Auth |
|----------|---------|-----------|------|
| A | Client ↔ API Gateway | HTTPS / REST | Bearer JWT (TBD) |
| B | API Gateway ↔ Qdrant | HTTP (internal K3s) | Qdrant API Key |
| C | API Gateway ↔ Inference | HTTP (internal LAN) | Pre-shared secret header |

---

## 2. Shared Conventions

- All payloads are **`application/json`** (UTF-8).
- All timestamps use **ISO 8601 UTC** format: `"2026-07-10T03:00:00Z"`.
- Field names use **`snake_case`**.
- Arrays are always present (never omitted); use `[]` for empty.
- Nullable fields are explicitly typed as `string | null`.
- Every response — success or error — is wrapped in the [standard envelope](#6-error-envelope-reference).

---

## 3. Boundary A — Client → API Gateway

### `POST /v1/query`
Submit a user question and receive an AI-generated answer with source citations.

#### 3.1 Request

```json
{
  "user_message": "string",
  "session_id":   "string | null",
  "top_k":        "integer | null",
  "filters": {
    "tags":       "string[]",
    "date_from":  "string | null",
    "date_to":    "string | null"
  }
}
```

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| `user_message` | string | ✅ | — | 1–2048 characters |
| `session_id` | string\|null | ❌ | null | UUID v4, for conversation history |
| `top_k` | integer\|null | ❌ | 5 | 1–20 |
| `filters.tags` | string[] | ❌ | [] | Max 10 items, each ≤ 64 chars |
| `filters.date_from` | string\|null | ❌ | null | ISO 8601 date `YYYY-MM-DD` |
| `filters.date_to` | string\|null | ❌ | null | ISO 8601 date `YYYY-MM-DD` |

**Example Request:**
```json
{
  "user_message": "What is the standard lead time for procurement under the QTI framework?",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "top_k": 5,
  "filters": {
    "tags": ["procurement", "logistics"],
    "date_from": "2025-01-01",
    "date_to":   null
  }
}
```

---

#### 3.2 Success Response — `200 OK`

```json
{
  "success": true,
  "data": {
    "answer":           "string",
    "session_id":       "string",
    "resolution_steps": "string[]",
    "sources": [
      {
        "document_id":   "string",
        "title":         "string",
        "excerpt":       "string",
        "score":         "float",
        "url":           "string | null"
      }
    ],
    "model":            "string",
    "latency_ms":       "integer"
  },
  "error": null,
  "request_id": "string",
  "timestamp":  "string"
}
```

| Field | Description |
|-------|-------------|
| `answer` | Full natural-language answer from the LLM |
| `session_id` | Echo of request `session_id` or newly generated UUID |
| `resolution_steps` | Ordered list of actionable steps extracted from the answer |
| `sources[].document_id` | Internal Qdrant point UUID |
| `sources[].score` | Cosine similarity score (0.0–1.0) |
| `sources[].excerpt` | Relevant chunk of text (≤ 512 chars) |
| `model` | Model identifier used (e.g., `"mistral-7b-instruct-v0.3"`) |
| `latency_ms` | End-to-end server-side latency in milliseconds |

**Example Response:**
```json
{
  "success": true,
  "data": {
    "answer": "Under the QTI framework, standard lead time for procurement is 14 business days from purchase order issuance, as outlined in Section 4.2 of the Procurement Policy 2025.",
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "resolution_steps": [
      "Issue a Purchase Order via the procurement portal.",
      "Coordinate with the supplier for acknowledgment within 2 business days.",
      "Track delivery through the logistics dashboard."
    ],
    "sources": [
      {
        "document_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "title":       "QTI Procurement Policy 2025",
        "excerpt":     "Standard lead time is defined as 14 business days from the date of PO issuance...",
        "score":       0.92,
        "url":         "https://internal.qti.id/docs/procurement-policy-2025"
      }
    ],
    "model":      "mistral-7b-instruct-v0.3",
    "latency_ms": 1240
  },
  "error":      null,
  "request_id": "req_01J5XKPQ7M3NBVWZ8R9T4GHFC",
  "timestamp":  "2026-07-10T03:00:01Z"
}
```

---

### `GET /v1/health`
Liveness probe for the API Gateway.

#### Response — `200 OK`
```json
{
  "success": true,
  "data": {
    "status":             "healthy",
    "qdrant_status":      "healthy",
    "inference_status":   "healthy",
    "version":            "1.0.0",
    "uptime_seconds":     3600
  },
  "error":      null,
  "request_id": "string",
  "timestamp":  "string"
}
```

---

## 4. Boundary B — API Gateway → Qdrant

> **Owner:** DevOps team  
> **Note:** Uses the Qdrant REST API. The contract below documents the exact subset this system uses.

### 4.1 Vector Search — `POST /collections/{collection_name}/points/search`

**Collection name:** `qti_knowledge_base` (agreed by Data Engineering team)

#### Request (sent by API Gateway to Qdrant)
```json
{
  "vector":         "[float, ...]",
  "limit":          "integer",
  "with_payload":   true,
  "with_vectors":   false,
  "filter": {
    "must": [
      {
        "key":   "string",
        "match": { "value": "string" }
      }
    ],
    "range": {
      "key": "indexed_at",
      "gte": "string | null",
      "lte": "string | null"
    }
  },
  "score_threshold": "float | null"
}
```

| Field | Description |
|-------|-------------|
| `vector` | 1024-dim embedding from the embedding model |
| `limit` | Maps from `top_k` in the client request |
| `score_threshold` | Default `0.70` — discard low-relevance chunks |

#### Expected Qdrant Response (subset)
```json
{
  "result": [
    {
      "id":    "string",
      "score": "float",
      "payload": {
        "document_id": "string",
        "title":       "string",
        "chunk_text":  "string",
        "url":         "string | null",
        "tags":        "string[]",
        "indexed_at":  "string"
      }
    }
  ]
}
```

### 4.2 Qdrant Payload Schema (ingested by Data Engineering)

Every point upserted into Qdrant **must** include the following payload fields:

```json
{
  "document_id": "string",
  "title":       "string",
  "chunk_text":  "string",
  "chunk_index": "integer",
  "url":         "string | null",
  "tags":        "string[]",
  "source_type": "string",
  "indexed_at":  "string"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `document_id` | string | UUID of the parent document |
| `title` | string | Human-readable document title |
| `chunk_text` | string | Raw text of this chunk (≤ 512 tokens) |
| `chunk_index` | integer | 0-based index of chunk within document |
| `url` | string\|null | Source URL (if web-scraped) |
| `tags` | string[] | Category labels for filtering |
| `source_type` | string | One of: `"web"`, `"pdf"`, `"docx"`, `"manual"` |
| `indexed_at` | string | ISO 8601 UTC timestamp of ingestion |

---

## 5. Boundary C — API Gateway → Inference (Mac Mini)

> **Owner:** Inference team  
> **Transport:** HTTP POST over local LAN / VPN tunnel  
> **Auth Header:** `X-Inference-Secret: <pre-shared-key>` (stored in K3s Secret)

### `POST /infer`

#### 5.1 Request (sent by API Gateway to Mac Mini)

```json
{
  "prompt":           "string",
  "retrieved_chunks": [
    {
      "document_id": "string",
      "title":       "string",
      "chunk_text":  "string",
      "score":       "float"
    }
  ],
  "session_id":       "string | null",
  "generation_config": {
    "max_new_tokens":  "integer",
    "temperature":     "float",
    "top_p":           "float",
    "repeat_penalty":  "float"
  }
}
```

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| `prompt` | string | ✅ | — | Raw user message text |
| `retrieved_chunks` | object[] | ✅ | — | Min 1, Max 20 chunks |
| `session_id` | string\|null | ❌ | null | For multi-turn context (future) |
| `generation_config.max_new_tokens` | integer | ❌ | 512 | 64–2048 |
| `generation_config.temperature` | float | ❌ | 0.7 | 0.0–2.0 |
| `generation_config.top_p` | float | ❌ | 0.9 | 0.0–1.0 |
| `generation_config.repeat_penalty` | float | ❌ | 1.1 | 1.0–2.0 |

**Example Request:**
```json
{
  "prompt": "What is the standard lead time for procurement under the QTI framework?",
  "retrieved_chunks": [
    {
      "document_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "title":       "QTI Procurement Policy 2025",
      "chunk_text":  "Standard lead time is defined as 14 business days from the date of PO issuance...",
      "score":       0.92
    }
  ],
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "generation_config": {
    "max_new_tokens": 512,
    "temperature":    0.7,
    "top_p":          0.9,
    "repeat_penalty": 1.1
  }
}
```

---

#### 5.2 Success Response — `200 OK`

```json
{
  "success": true,
  "data": {
    "answer":           "string",
    "resolution_steps": "string[]",
    "model":            "string",
    "tokens_used": {
      "prompt_tokens":     "integer",
      "completion_tokens": "integer",
      "total_tokens":      "integer"
    },
    "latency_ms": "integer"
  },
  "error":      null,
  "request_id": "string",
  "timestamp":  "string"
}
```

**Example Response:**
```json
{
  "success": true,
  "data": {
    "answer": "Under the QTI framework, standard lead time for procurement is 14 business days from purchase order issuance, as outlined in Section 4.2 of the Procurement Policy 2025.",
    "resolution_steps": [
      "Issue a Purchase Order via the procurement portal.",
      "Coordinate with the supplier for acknowledgment within 2 business days.",
      "Track delivery through the logistics dashboard."
    ],
    "model": "mistral-7b-instruct-v0.3",
    "tokens_used": {
      "prompt_tokens":     384,
      "completion_tokens": 128,
      "total_tokens":      512
    },
    "latency_ms": 980
  },
  "error":      null,
  "request_id": "req_01J5XKPQ7M3NBVWZ8R9T4GHFC",
  "timestamp":  "2026-07-10T03:00:01Z"
}
```

---

## 6. Error Envelope Reference

All error responses share this structure:

```json
{
  "success":    false,
  "data":       null,
  "error": {
    "error_code": "string",
    "message":    "string",
    "details":    "string | null"
  },
  "request_id": "string",
  "timestamp":  "string"
}
```

### Error Code Registry

| `error_code` | HTTP Status | Description | Owner |
|--------------|-------------|-------------|-------|
| `VALIDATION_ERROR` | 400 | Request payload failed schema validation | DevOps |
| `INVALID_SESSION` | 400 | Provided `session_id` format is invalid | DevOps |
| `UNAUTHORIZED` | 401 | Missing or invalid auth token | DevOps |
| `FORBIDDEN` | 403 | Authenticated but not permitted | DevOps |
| `QUERY_TOO_LONG` | 422 | `user_message` exceeds 2048 characters | DevOps |
| `NO_RESULTS_FOUND` | 404 | Qdrant returned zero results above threshold | DevOps |
| `QDRANT_UNAVAILABLE` | 503 | Cannot reach Qdrant cluster | DevOps |
| `INFERENCE_UNAVAILABLE` | 503 | Cannot reach Mac Mini inference server | DevOps |
| `INFERENCE_TIMEOUT` | 504 | Mac Mini exceeded response deadline (30s) | DevOps |
| `MODEL_ERROR` | 500 | mistral.rs returned an internal error | Inference |
| `EMBEDDING_ERROR` | 500 | Embedding model failed to encode query | DevOps |
| `INTERNAL_ERROR` | 500 | Unhandled server-side exception | DevOps |

**Example Error Response:**
```json
{
  "success": false,
  "data":    null,
  "error": {
    "error_code": "INFERENCE_TIMEOUT",
    "message":    "The inference server did not respond within the 30-second deadline.",
    "details":    "Upstream host: 192.168.1.50:8080, timeout: 30000ms"
  },
  "request_id": "req_01J5XKPQ7M3NBVWZ8R9T4GHFC",
  "timestamp":  "2026-07-10T03:00:31Z"
}
```

---

## 7. HTTP Status Code Matrix

| Scenario | Client ← Gateway | Gateway ← Inference | Gateway ← Qdrant |
|----------|:-----------------:|:-------------------:|:----------------:|
| All systems nominal | 200 | 200 | 200 |
| Bad client payload | 400 | N/A | N/A |
| Unauthenticated | 401 | N/A | N/A |
| Message too long | 422 | N/A | N/A |
| No relevant docs found | 404 | N/A | N/A |
| Qdrant down | 503 | N/A | 503 |
| Inference down | 503 | 503 | N/A |
| Inference slow | 504 | timeout | N/A |
| LLM crash | 500 | 500 | N/A |
| Gateway crash | 500 | N/A | N/A |

---

## 8. Versioning & Change Policy

1. This contract is versioned via Git tags (e.g., `contract-v1.0.0`).
2. **Backward-incompatible changes** (removing/renaming fields) require:
   - A 2-week deprecation notice posted in this file.
   - A new `/v2/` endpoint — the old one must remain functional for 30 days.
3. **Backward-compatible changes** (adding optional fields) require:
   - A PR with approval from all three team leads.
4. The `api_contract.md` in the `main` branch is the **single source of truth**.

---

## 9. Sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Inference Team Lead | | | ☐ |
| DevOps / API-Gateway Team Lead | | | ☐ |
| Data Engineering Team Lead | | | ☐ |

> **Next Review Date:** 2026-08-10  
> To propose changes, open a PR and request reviews from all three leads.
