use serde::{Deserialize, Serialize};

// 1. The Input Blueprint (What the AI Agent sends to us)
#[derive(Deserialize, Debug)]
pub struct QueryRequest {
    pub ticket_id: String,
    pub raw_text: String,
    pub project_tags: Vec<String>,
}

// 2. The Output Blueprint (What we send back to the Agent)
#[derive(Serialize)]
pub struct QueryResponse {
    pub ticket_metadata: TicketMetadata,
    pub remediation_payload: RemediationPayload,
}

// 3. Sub-struct for the Output
#[derive(Serialize)]
pub struct TicketMetadata {
    pub ticket_id: String,
    pub classification: String,
}

// 4. Sub-struct for the Output
#[derive(Serialize)]
pub struct RemediationPayload {
    pub proposed_fix: String,
    pub requires_type_check: bool,
}