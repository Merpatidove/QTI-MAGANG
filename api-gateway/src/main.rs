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
// 🚨 CRITICAL RUST CONCEPT: THE MODULE SYSTEM 🚨
// Unlike Python or Node.js, Rust does NOT automatically scan your folders.
// If you create a file named `models.rs`, the compiler will ignore it 
// unless you explicitly declare it here using the `mod` keyword.
mod models;
mod routes;
mod clients;

// 2. IMPORTS
use axum::{routing::{get, post}, Router};
use prometheus::{Encoder, TextEncoder, register_int_counter};
use std::net::SocketAddr;
use lazy_static::lazy_static;

// 3. GLOBAL METRICS
// We track total HTTP requests for the Grafana dashboard.
lazy_static! {
    static ref HTTP_REQUESTS_TOTAL: prometheus::IntCounter = register_int_counter!(
        "http_requests_total",
        "Total number of HTTP requests across all endpoints"
    ).unwrap();
}

// 4. THE METRICS ENDPOINT
// Prometheus scrapes this endpoint every 15 seconds to feed Grafana.
async fn metrics() -> String {
    let encoder = TextEncoder::new();
    let mut buffer = String::new();
    let metric_families = prometheus::gather();
    encoder.encode_utf8(&metric_families, &mut buffer).unwrap();
    buffer
}

// 5. THE MAIN FUNCTION (BOOT SEQUENCE)
// `#[tokio::main]` is a macro that spins up the Tokio async runtime.
// Without this, `.await` keywords will not compile.
#[tokio::main]
async fn main() {
    // Initialize structured logging (visible in `kubectl logs`)
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info".into()),
        )
        .init();

    // 🚨 CRITICAL: WIRING THE ROUTER 🚨
    // We point the Axum router to our new modular files.
    // Notice how we use `routes::health::health` to reach into the folder.
    let app = Router::new()
        .route("/v1/health", get(routes::health::health))
        .route("/v1/query", post(routes::query::query))
        .route("/metrics", get(metrics));

    // Bind to port 8080 (as specified in the Infrastructure Report)
    // We use [0, 0, 0, 0] instead of [127, 0, 0, 1] so the Kubernetes 
    // cluster can reach the server from outside the container.
    let addr = SocketAddr::from(([0, 0, 0, 0], 8080));
    tracing::info!("🚀 API Gateway listening on {addr}");

    // Start the infinite event loop
    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}