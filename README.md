# QTI RAG Pipeline — Shared Repository

> **Internal AI knowledge-base system for QTI.**  
> Combines a Mistral-7B LLM, Qdrant vector search, and an Axum API gateway deployed on K3s.

---

## Repository Structure

```
QTI-MAGANG/
├── api_contract.md        ← 📋 Single source of truth for all JSON schemas
│
├── inference/             ← 🤖 Inference Team
│   └── README.md             mistral.rs server on Mac Mini
│
├── api-gateway/           ← 🔧 DevOps Team
│   └── README.md             Axum gateway + K3s manifests
│
└── data-pipeline/         ← 📊 Data Engineering Team
    └── README.md             Scraping, chunking, Qdrant ingestion
```

---

## Where to Start

| I am... | I should read... |
|---------|-----------------|
| **New to the project** | This README, then `api_contract.md` |
| **Inference team** | `api_contract.md` §5, then `inference/README.md` |
| **DevOps team** | `api_contract.md` §3 & §4, then `api-gateway/README.md` |
| **Data Engineering team** | `api_contract.md` §4.2, then `data-pipeline/README.md` |

---

## The API Contract

**[`api_contract.md`](./api_contract.md)** is the canonical definition of every JSON payload in this system.  
**No team ships code that contradicts it.** All changes require a PR approved by all three team leads.

---

## Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Stable, reviewed code only |
| `feat/inference/*` | Inference team feature branches |
| `feat/gateway/*` | DevOps team feature branches |
| `feat/pipeline/*` | Data Engineering feature branches |

---

## Team Contacts

| Team | Lead | Slack |
|------|------|-------|
| Inference | TBD | TBD |
| DevOps / API-Gateway | TBD | TBD |
| Data Engineering | TBD | TBD |
