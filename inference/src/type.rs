use serde::{Deserialize, Serialize};

// This struct perfectly matches the JSON payload the DevOps team will send.
#[derive(Debug, Deserialize, Serialize)]
pub struct InferenceRequest {
    pub user_symptom: String,
    pub diagnostic_flag: String,
    pub retrieved_context: String,
}

// This struct is the final answer we will send back to the DevOps team.
#[derive(Debug, Serialize)]
pub struct InferenceResponse {
    pub ai_response: String,
    pub status: String,
}