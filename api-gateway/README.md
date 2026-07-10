# /api-gateway — Axum API Gateway & K3s Manifests

## Owner
DevOps Team

## Purpose
This directory contains the **Axum** (Rust) HTTP API gateway and all **K3s** (Kubernetes) deployment manifests.

## Responsibilities
- Receive and validate client requests (`POST /v1/query`)
- Embed the user query and query **Qdrant** for relevant chunks (Boundary B)
- Forward the query + chunks to the **Mac Mini inference server** (Boundary C)
- Aggregate results and return the standard JSON envelope to the client
- Manage health checks, authentication, rate limiting, and observability

## Directory Layout (Planned)
```
api-gateway/
├── src/
│   ├── main.rs          # Axum server entrypoint
│   ├── routes/
│   │   ├── query.rs     # POST /v1/query handler
│   │   └── health.rs    # GET /v1/health handler
│   ├── clients/
│   │   ├── qdrant.rs    # Qdrant HTTP client
│   │   └── inference.rs # Mac Mini inference client
│   └── models.rs        # Shared request/response structs (matches api_contract.md)
├── k8s/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   └── secrets.yaml     # (gitignored values, template provided)
├── Cargo.toml
└── README.md
```

## Interface Contract
- Client-facing: [api_contract.md §3 — Boundary A](../api_contract.md#3-boundary-a--client--api-gateway)
- Qdrant calls: [api_contract.md §4 — Boundary B](../api_contract.md#4-boundary-b--api-gateway--qdrant)
- Inference calls: [api_contract.md §5 — Boundary C](../api_contract.md#5-boundary-c--api-gateway--inference-mac-mini)

## Setup
> TODO: Add setup instructions once Cargo.toml and K3s cluster are initialized.
