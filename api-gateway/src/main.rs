use axum::{routing::{get, post}, Json, Router};
use prometheus::{Encoder, TextEncoder, register_int_counter, register_int_gauge};
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

lazy_static::lazy_static! {
    static ref HTTP_REQUESTS_TOTAL: prometheus::IntCounter = register_int_counter!(
        "http_requests_total",
        "Total number of HTTP requests"
    ).unwrap();
    static ref HEALTH_CHECKS_TOTAL: prometheus::IntCounter = register_int_counter!(
        "health_checks_total",
        "Total number of health check requests"
    ).unwrap();
    static ref QUERIES_TOTAL: prometheus::IntCounter = register_int_counter!(
        "queries_total",
        "Total number of query requests"
    ).unwrap();
}

async fn health() -> Json<serde_json::Value> {
    HEALTH_CHECKS_TOTAL.inc();
    Json(serde_json::json!({
        "status": "ok",
        "version": env!("CARGO_PKG_VERSION")
    }))
}

async fn metrics() -> String {
    let encoder = TextEncoder::new();
    let mut buffer = String::new();
    let metric_families = prometheus::gather();
    encoder.encode_utf8(&metric_families, &mut buffer).unwrap();
    buffer
}

async fn query(Json(req): Json<QueryRequest>) -> Json<QueryResponse> {
    QUERIES_TOTAL.inc();
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
        .route("/v1/query", post(query))
        .route("/metrics", get(metrics));

    let addr = SocketAddr::from(([0, 0, 0, 0], 8080));
    tracing::info!("listening on {addr}");

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
