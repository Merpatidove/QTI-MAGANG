use axum::{routing::{get, post}, Json, Router};
use serde::{Deserialize, Serialize};
use std::net::SocketAddr;

#[derive(Deserialize)]
struct QueryRequest {
    ticket_id: String,
    raw_text: String,
    project_tags: Vec<String>,
}

#[derive(Serialize)]
struct QueryResponse {
    ticket_metadata: TicketMetadata,
    remediation_payload: RemediationPayload,
}

#[derive(Serialize)]
struct TicketMetadata {
    ticket_id: String,
    classification: String,
}

#[derive(Serialize)]
struct RemediationPayload {
    proposed_fix: String,
    requires_type_check: bool,
}

async fn health() -> Json<serde_json::Value> {
    Json(serde_json::json!({
        "status": "ok",
        "version": env!("CARGO_PKG_VERSION")
    }))
}

async fn query(Json(req): Json<QueryRequest>) -> Json<QueryResponse> {
    Json(QueryResponse {
        ticket_metadata: TicketMetadata {
            ticket_id: req.ticket_id,
            classification: "placeholder".to_string(),
        },
        remediation_payload: RemediationPayload {
            proposed_fix: "Not yet implemented".to_string(),
            requires_type_check: false,
        },
    })
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info".into()),
        )
        .init();

    let app = Router::new()
        .route("/v1/health", get(health))
        .route("/v1/query", post(query));

    let addr = SocketAddr::from(([0, 0, 0, 0], 8080));
    tracing::info!("listening on {addr}");

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
