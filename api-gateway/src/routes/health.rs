// =====================================================================
// FILE PURPOSE:
// This file defines the `/v1/health` GET endpoint. 
// Kubernetes and our CI/CD pipeline ping this URL to verify the server 
// is alive. If this fails, the cluster will restart our pod.
// =====================================================================

// 1. IMPORTS
// `Json` is an Axum tool that automatically converts Rust data into JSON HTTP responses.
// `lazy_static` allows us to create global variables that are initialized only once.
// `register_int_counter` creates a metric that Prometheus can scrape for Grafana dashboards.
use axum::Json;
use lazy_static::lazy_static;
use prometheus::register_int_counter;

// 2. METRICS SETUP
// We create a global counter to track how many times Kubernetes pings us.
// `lazy_static!` ensures this counter is safely created in memory exactly 
// once when the server boots up, and survives across thousands of requests.
lazy_static! {
    pub static ref HEALTH_CHECKS_TOTAL: prometheus::IntCounter = register_int_counter!(
        "health_checks_total",
        "Total number of health check requests received by the server"
    ).unwrap(); // .unwrap() is safe here; if metrics fail to register, the server shouldn't start.
}

// 3. THE HANDLER FUNCTION
// `pub` makes this function visible to `main.rs` so the router can use it.
// `async` tells Rust this function handles network I/O without blocking the CPU.
pub async fn health() -> Json<serde_json::Value> {
    
    // Increment the Prometheus counter by 1 every time this endpoint is hit
    HEALTH_CHECKS_TOTAL.inc();

    // Build and return the JSON response.
    // Axum automatically wraps this in an HTTP 200 OK response and sets 
    // the `Content-Type: application/json` header for us.
    Json(serde_json::json!({
        "status": "ok",
        "version": env!("CARGO_PKG_VERSION") // Grabs the version number directly from Cargo.toml
    }))
}