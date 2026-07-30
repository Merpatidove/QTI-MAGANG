// =====================================================================
// FILE PURPOSE:
// This is the entry point of the application. It acts as the "Orchestrator".
//
// ARCHITECTURE NOTE:
// This file contains ZERO business logic. It does not parse JSON, it does
// not query databases, and it does not format responses. Its sole purpose
// is to wire the isolated modules (`models`, `routes`, `clients`) together,
// allocate the network port, and hand control over to the Axum event loop.
// =====================================================================

// 1. MODULE DECLARATIONS
mod models;
mod routes;
mod clients;

// 2. IMPORTS
use axum::{routing::{get, post}, Router};
use prometheus::{TextEncoder, register_int_counter};
use std::net::SocketAddr;
use lazy_static::lazy_static;

// 3. GLOBAL METRICS
lazy_static! {
    static ref HTTP_REQUESTS_TOTAL: prometheus::IntCounter = register_int_counter!(
        "http_requests_total",
        "Total number of HTTP requests across all endpoints"
    ).unwrap();
}

// 4. THE METRICS ENDPOINT
async fn metrics() -> String {
    let encoder = TextEncoder::new();
    let mut buffer = String::new();
    let metric_families = prometheus::gather();
    encoder.encode_utf8(&metric_families, &mut buffer).unwrap();
    buffer
}

// 5. THE MAIN FUNCTION (BOOT SEQUENCE)
#[tokio::main]
async fn main() {
    // 🚨 NEW: --download-only guard 🚨
    // The Docker build step runs the binary with this flag so that
    // fastembed downloads the embedding model into the image at BUILD
    // time (the build machine has internet). At RUNTIME in the air-gapped
    // cluster, the model is already baked in — no download needed.
    // This guard inits the model, prints a confirmation, and exits
    // WITHOUT starting the HTTP server.
    if std::env::args().any(|a| a == "--download-only") {
        match routes::query::warm_embedder() {
            Ok(_) => {
                println!("✅ embedding model ready in cache");
                std::process::exit(0);
            }
            Err(e) => {
                eprintln!("warmup failed: {e}");
                std::process::exit(1);
            }
        }
    }

    // Initialize structured logging (visible in `kubectl logs`)
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info".into()),
        )
        .init();

    // Wire the Axum router to our modular files
    let app = Router::new()
        .route("/v1/health", get(routes::health::health))
        .route("/v1/query", post(routes::query::query))
        .route("/metrics", get(metrics));

    // Bind to 0.0.0.0:8080 so the cluster can reach the server
    let addr = SocketAddr::from(([0, 0, 0, 0], 8080));
    tracing::info!("🚀 API Gateway listening on {addr}");

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}