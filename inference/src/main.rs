mod types; // Tells main to look at your types.rs file

use axum::{
    routing::post,
    Json, Router,
};
use types::{InferenceRequest, InferenceResponse};

#[tokio::main]
async fn main() {
    // 1. Build the router (The exact URL from your API Contract)
    let app = Router::new()
        .route("/api/v1/generate", post(handle_inference));

    // 2. Define the server address (localhost:8080)
    let listener = tokio::net::TcpListener::bind("127.0.0.1:8080").await.unwrap();
    println!("🚀 Mac Mini Inference Engine listening on http://127.0.0.1:8080");

    // 3. Start the server
    axum::serve(listener, app).await.unwrap();
}

// 4. The function that triggers when data arrives
async fn handle_inference(
    Json(payload): Json<InferenceRequest>, // Axum automatically unpacks the JSON here!
) -> Json<InferenceResponse> {
    
    // Print to your local terminal to prove the data arrived safely
    println!("\n📥 [NEW TICKET RECEIVED]");
    println!("Symptom: {}", payload.user_symptom);
    println!("Diagnosis: {}", payload.diagnostic_flag);

    // TODO: We will add your AI Prompt Injection logic here in the next step!
    
    // For now, send a temporary success message back to DevOps
    let response = InferenceResponse {
        ai_response: "Hello from the Rust Engine! Data received perfectly.".to_string(),
        status: "success".to_string(),
    };

    Json(response)
}