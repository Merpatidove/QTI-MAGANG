// =====================================================================
// FILE PURPOSE:
// This file defines the `/v1/query` POST endpoint.
// This is the core business logic of the API gateway. It receives error 
// logs from the AI Agent, searches the Qdrant database for solutions, 
// and returns the best match.
// =====================================================================

// 1. IMPORTS
use axum::Json;
use lazy_static::lazy_static;
use prometheus::register_int_counter;

// Import the data blueprints we defined in models.rs
// `crate::` means "start looking from the root of the project"
use crate::models::{QueryRequest, QueryResponse, TicketMetadata, RemediationPayload};

// 2. METRICS SETUP
// We create a global counter to track how many real queries the AI Agent sends us.
lazy_static! {
    pub static ref QUERIES_TOTAL: prometheus::IntCounter = register_int_counter!(
        "queries_total",
        "Total number of RAG query requests received"
    ).unwrap();
}

// 3. THE HANDLER FUNCTION
// `pub` makes it visible to main.rs.
// `async` allows it to handle network I/O without blocking.
//
// 🚨 CRITICAL CONCEPT: THE EXTRACTOR 🚨
// `Json(req): Json<QueryRequest>` is an "Extractor".
// It tells Axum: "Read the HTTP body, parse it as JSON, and if it matches
// the QueryRequest blueprint, give me the data in a variable named `req`."
// If the JSON is invalid or missing fields, Axum automatically rejects it
// with a 422 error before this code even runs. This is your "Data Firewall".
pub async fn query(Json(req): Json<QueryRequest>) -> Json<QueryResponse> {
    
    // Increment the Prometheus counter
    QUERIES_TOTAL.inc();

    // Log that we received a request
    println!("📨 Received query for ticket: {}", req.ticket_id);

    // TODO: In Phase 2, we will replace this placeholder logic
    // with a real call to `clients::qdrant::search()`.

    // For now, we just construct a dummy response that matches our Output Blueprint.
    // This proves to the CI/CD pipeline that our JSON structure is correct.
    Json(QueryResponse {
        ticket_metadata: TicketMetadata {
            ticket_id: req.ticket_id,
            classification: "placeholder_classification".to_string(),
        },
        remediation_payload: RemediationPayload {
            proposed_fix: "Rust backend is not yet connected to Qdrant.".to_string(),
            requires_type_check: false,
        },
    })
}