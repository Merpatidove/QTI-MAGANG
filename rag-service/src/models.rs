use serde::{Deserialize, Serialize};

// The Input Blueprint (What the API Gateway sends us)
#[derive(Deserialize, Debug)]
pub struct TicketRequest {
    pub ticket_id: String,
    pub raw_text: String,
    pub project_tags: Vec<String>,
}

// The Output Blueprint (What we send back)
#[derive(Serialize)]
pub struct InferenceResponse {
    pub status: String,
    pub message: String,
}