// =====================================================================
// FILE PURPOSE:
// This file defines the client used to search the Qdrant Vector Database.
// 
// ARCHITECTURE NOTE:
// The AI Agent will send us an error log. We will convert that log into 
// a mathematical vector (numbers). We pass those numbers to the function 
// in this file. This function sends an HTTP POST request to the Qdrant 
// database (running in the K3s cluster) to find the closest matching SOP.
// =====================================================================

// 1. IMPORTS
// `reqwest` is the industry-standard HTTP client for Rust. DevOps already 
// added it to our Cargo.toml. We use it to make outbound network requests.
// `serde` is used to parse the JSON response that Qdrant sends back to us.
// `anyhow::Result` is a convenient error-handling type that lets us easily 
// bubble up errors if the network request fails.
use reqwest::Client;
use serde::{Deserialize, Serialize};
use anyhow::{Result, Context};

// 2. QDRANT CONFIGURATION
// The Infrastructure Report states Qdrant is running at this internal cluster URL.
// In a production app, we would read this from an Environment Variable (K8s Secret),
// but for now, we hardcode the internal cluster DNS name DevOps set up.
const QDRANT_URL: &str = "http://qdrant.qdrant.svc.cluster.local:6333";
const COLLECTION_NAME: &str = "qti_knowledge_base";

// 3. DATA STRUCTURES FOR QDRANT'S API
// We need to define the exact shape of the JSON we send TO Qdrant, 
// and the exact shape of the JSON Qdrant sends BACK to us.

// What we send to Qdrant
#[derive(Serialize)]
struct SearchRequest {
    vector: Vec<f32>,   // The mathematical representation of the error log
    limit: usize,       // How many results we want back (we only need the top 1)
    with_payload: bool, // Tell Qdrant to send back the original text, not just the math
}

// What Qdrant sends back to us
#[derive(Deserialize)]
struct QdrantResponse {
    result: Vec<SearchResult>,
}

#[derive(Deserialize)]
struct SearchResult {
    payload: Option<Payload>,
}

#[derive(Deserialize)]
struct Payload {
    text: Option<String>,      // The actual SOP instructions
    sop_id: Option<String>,    // Example: "SOP-DB-001"
    title: Option<String>,     // Example: "MySQL Connection Timeout"
}

// 4. THE SEARCH FUNCTION
// `pub` makes this visible to `routes/query.rs`.
// `async` is mandatory here because network requests take time. This allows 
// the server to handle other users while waiting for Qdrant to respond.
pub async fn search_sop(query_vector: Vec<f32>) -> Result<String> {
    
    // Initialize the HTTP client
    let client = Client::new();

    // Build the URL for the Qdrant search endpoint
    let url = format!("{}/collections/{}/points/search", QDRANT_URL, COLLECTION_NAME);

    // Build the JSON payload we are going to send
    let request_body = SearchRequest {
        vector: query_vector,
        limit: 1,
        with_payload: true,
    };

    // 🚨 CRITICAL CONCEPT: `.await` 🚨
    // `.send()` initiates the HTTP POST request. 
    // `.await` tells the Tokio engine: "I am waiting for the network. Pause this 
    // function and let the CPU go handle other web requests until Qdrant replies."
    let response = client
        .post(&url)
        .json(&request_body)
        .send()
        .await
        .context("❌ Failed to connect to Qdrant. Is the pod running?")?;

    // Check if Qdrant returned a success status code (200 OK)
    if !response.status().is_success() {
        let error_text = response.text().await.unwrap_or_default();
        anyhow::bail!("❌ Qdrant returned an error: {}", error_text);
    }

    // Parse the JSON response from Qdrant into our Rust structs
    let qdrant_data: QdrantResponse = response
        .json()
        .await
        .context("❌ Failed to parse Qdrant's JSON response")?;

    // Extract the text from the first (and only) result
    if let Some(first_result) = qdrant_data.result.first() {
        if let Some(payload) = &first_result.payload {
            if let Some(text) = &payload.text {
                return Ok(text.clone());
            }
        }
    }

    // If we get here, Qdrant didn't find a close enough match
    Ok("No matching SOP found in the knowledge base.".to_string())
}