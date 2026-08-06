# HITE Data Science Methodology — 5W1H Triage Evaluation
### Document No. DS-METH-001 · Version 1.0 · Owner: Johan (Data Scientist) · 2026-08-05

---

## 1. Purpose

This document defines how the HITE (Hybrid IT Triage Engine) Data Science lane measures whether the LLM triage agent produces **correct, complete, and knowledge-grounded** incident analyses. It is the reference for the evaluation harness (`test_run.py` + `grade_result.py`), the two-stage maturity model, and the metric definitions handed to DevOps for dashboards and CI gating.

## 2. System Under Test

```
ticket (raw_text + project_tags)
  → agent.py (FastAPI ReAct orchestrator, :8000 /process-ticket)
      → Analysis phase   : Ollama (Qwen2.5-Coder-7B) picks a tool + drafts 5W1H
      → Retrieval phase  : tools.search_sop → gateway /v1/query → Qdrant (qti_knowledge_base)
      → Synthesis phase  : Ollama rewrites 5W1H, grounding Why/How in the retrieved SOP
  → structured 5W1H JSON (Who, What, When, Where, Why, How) + confidence tier
```

Generation lives in the DS agent; the gateway is **retrieval-only** (architecture locked 2026-08-02, §1.3.5).

## 3. Two-Stage Maturity Model

| Stage | Goal | Dataset | Answers |
|---|---|---|---|
| **Stage 1 — Synthetic validation** | Prove the pipeline works end-to-end and the schema is stable | `golden_datasets.json` (55 tickets) | "Can the agent produce a complete, grounded 5W1H at all?" |
| **Stage 2 — Real-data validation** | Prove it works on production-shaped errors and find knowledge gaps | `real_tickets.json` (8 tickets, curated from real incidents) | "Does it ground in the *right* SOP for real failures?" |

Stage 1 is a necessary but not sufficient condition: every synthetic ticket has a matching SOP, so Stage 1 **cannot** exercise the wrong-SOP-grounding failure mode that Stage 2 exposes.

## 4. Metric Definitions

| Metric | Definition | Source of truth |
|---|---|---|
| **Valid JSON** | Agent output parses as JSON | `test_run.py` |
| **Schema completeness** | All six 5W1H keys present and non-empty | `grade_result.py` |
| **Grounding (naive)** | `how` ≠ `"Pending SOP search"` placeholder | `grade_result.py` |
| **Grounding (honest)** | Grounded **and** the retrieved SOP actually matches the ticket's root cause | human review (see §7) |
| **Confidence tier** | **A** = complete + grounded · **B** = complete, ungrounded · **C** = incomplete/escape | `grade_result.py` |

## 5. Stage 1 — Synthetic Validation Results

| Run (2026) | Schema | Grounded | Note |
|---|---|---|---|
| Baseline, 08-02 | 55/55 | 24/55 (43.6%) | First real grounding measurement (Fix A) |
| Control band, 08-03 | 55/55 | 24–28/55 (43.6–50.9%) | Pre-fix |
| Treatment (`_is_err` synthesis gate), 08-03 | 55/55 | **52–53/55 (94.5–96.4%)** | Winning fix; HEAD=52, archived `3a03a55`=53 |
| Reproducibility, 08-05 | 55/55 | band 52–54/55 | ~11 "fragile" tickets rotate per draw |

**Reproducibility policy:** Qwen2.5-Coder on Apple Metal is non-deterministic even at fixed seed. Ablations: `temp 0.1` degenerates synthesis JSON (45/55); `seed 42 @ temp 0.8` = 49→48 across repeats. Therefore results are reported as a **band / mean ± range**, never a single point. Knobs: `OLLAMA_TEMPERATURE`, `OLLAMA_SEED` (set in the agent's terminal before uvicorn).

**Remaining Stage 1 loss:** ~7 synthesis JSON decode failures → remediation = **synthesis retry-on-parse-failure** (in progress).

## 6. Stage 2 — Real-Data Validation

### 6.1 Error→eval pipeline (manual curation)
Raw error logs → `collected_error_logs.json` (provenance) → flattened into `real_tickets.json` (same schema as golden: `ticket_id`, `raw_text`, `project_tags`).

**Curation rules:**
1. One ticket per **root cause** (dedupe repeated log lines).
2. Info-level / benign noise ≠ incidents (no ticket).
3. Sources: Loki log mining (Grafana Explore, error-level filters per namespace) + manual debugging sessions.

### 6.2 Real ticket set (8 tickets)
| Ticket | Root cause | Expected SOP |
|---|---|---|
| REAL-001 | Ollama unreachable over WireGuard | SOP-INF-003 |
| REAL-002 | Loki datasource unreachable | SOP-INF-004 |
| REAL-003 | nginx bind() port in use | SOP-DOC-002 |
| REAL-004 | VolumeSnapshot CRDs missing (csi-snapshotter) | SOP-INF-005 |
| REAL-005 | Loki querier context-canceled bursts | SOP-INF-004 |
| REAL-006 | Worker lost route to control plane | SOP-INF-006 |
| REAL-007 | etcd request timeout (leader election) | SOP-INF-007 |
| REAL-008 | Argo CD Redis unreachable | SOP-INF-008 |

### 6.3 Coverage-gap finding (the key Stage 2 result)
Retrieval always returns a **nearest neighbor**, never nothing. So a ticket with no matching SOP still yields `grounded=True` — backed by an **irrelevant** SOP. Initial real run: 3/3 returned `grounded=True`, but only REAL-003 matched its real SOP; REAL-001/002 grounded in SOP-KIT-002 / SOP-DB-001. **Honest read: 1/3 correctly grounded.**

### 6.4 Remediation loop
Author missing SOPs (SOP-INF-003..008) → append to `RAG_Manual.md` (18 → **24 SOPs**) → Farrel re-ingests (384-dim/Cosine, 83 → ~110+ points) → re-eval.

**Current status:** grounding on the real set raised to **75% (6/8 tickets)**; RAG_Manual updated and committed; awaiting Farrel re-ingest, after which REAL-001..008 will be re-evaluated against the expanded KB (post-ingest numbers to be recorded below).

| Measurement | Grounded | Note |
|---|---|---|
| Pre-expansion, honest (3 tickets) | 1/3 | §6.3 coverage-gap finding |
| Post-SOP-authoring, real set (8 tickets) | **6/8 (75%)** | current |
| Post-ingest re-eval | _pending_ | run after Farrel re-ingests |

**Current status:** grounding raised to **75%** `[CONFIRM: real set 6/8 or synthetic?]`; RAG_Manual updated; awaiting Farrel re-ingest to re-eval REAL-001..008 against the expanded KB.

## 7. Key Lesson — Naive Grounding Is Blind to Retrieval Correctness

The naive check (`how != placeholder`) counts wrong-SOP grounding as grounded. Real-data grounding therefore needs a **retrieval-correctness signal or human review**, not just the placeholder test. This is why the honest metric (§4) exists and why SOP expansion is the actual remediation for coverage gaps.

## 8. Generalization Caveat

Once SOP-INF-003..008 are ingested, REAL-001..008 become **"seen"** data — re-evaluating them measures recall of known knowledge, not generalization. Future generalization tests must use **fresh, unseen tickets**. The long-term fix is the automated error→eval curator.

## 9. Limitations & Future Work

1. **Automated Loki → eval curator** (§4.2) — still PROPOSED; curation is manual today.
2. **Retrieval-correctness signal** — replace/augment the naive grounding check so the grader can distinguish right-SOP from wrong-SOP grounding automatically.
3. **Synthesis retry-on-parse-failure** — recover the ~7 decode failures (Stage 1).
4. **CI gate** — wire `grade_result.py` into CI with a threshold (e.g. `grounded ≥ 45/55`).
5. **Tier metrics** — instrument `qti_confidence_tier_total`, `qti_routing_decision_total`, `qti_fact_coverage_score` on the agent (owner: DS, per §1.4 re-scope).

## 10. References
- HITE Master Guidebook §1.3–§1.6 (DS pipeline), §4.2 (observability), §8 (this doc's origin)
- `llm-inference/test_run.py`, `grade_result.py`, `agent.py`
- Archives: `evaluation_results_real_0804.json`, `evaluation_results_seed42_0805.json`, `treatment2_errorgate_0803.json`