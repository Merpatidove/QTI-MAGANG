use axum::Json;
// Pull the blueprints from the models file
use crate::models::{TicketRequest, InferenceResponse};

// The handler for POST /api/v1/ticket
pub async fn receive_ticket(Json(payload): Json<TicketRequest>) -> Json<InferenceResponse> {
    // 1. The Firewall automatically validated the JSON before this code even ran.
    println!("🛡️ FIREWALL PASSED: Ticket {} received.", payload.ticket_id);
    println!("   Tags: {:?}", payload.project_tags);

    // 2. For now, we just send a dummy success message back.
    // Later, this is where we will call Qdrant and Mistral.
    Json(InferenceResponse {
        status: "200 OK".to_string(),
        message: format!("Ticket {} logged by inference service.", payload.ticket_id),
    })
}