# /inference — Mistral.rs Inference Server

## Owner
Inference Team

## Purpose
This directory contains everything needed to run the **mistral.rs**-based LLM inference server on the Mac Mini.

## Responsibilities
- Load and serve the Mistral-7B-Instruct model via `mistral.rs`
- Expose `POST /infer` HTTP endpoint (see [`api_contract.md`](../api_contract.md) §5)
- Format the RAG prompt from retrieved chunks + user query
- Return structured JSON with `answer`, `resolution_steps`, and token usage

## Directory Layout (Planned)
```
inference/
├── src/
│   └── main.rs          # mistral.rs HTTP wrapper
├── scripts/
│   └── start.sh         # Launch script for Mac Mini
├── models/              # (gitignored) Local model weights
├── Cargo.toml
└── README.md
```

## Interface Contract
See [api_contract.md §5 — Boundary C](../api_contract.md#5-boundary-c--api-gateway--inference-mac-mini)

## Setup
> TODO: Add setup instructions once Cargo.toml is initialized.
