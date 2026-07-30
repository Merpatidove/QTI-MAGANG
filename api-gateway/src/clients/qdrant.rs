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
use reqwest::Client;
use serde::{Deserialize, Serialize};
use anyhow::{Result, Context};

// 2. QDRANT CONFIGURATION
// Read the URL from an environment variable so the SAME binary works
// in two places:
//   • On your laptop (tunnel):  QDRANT_URL=http://localhost:6333
//   • In the cluster (default): falls back to the in-cluster DNS below.
// This also partially ticks the "move QDRANT_URL to an env var" TODO (§2.4).
fn qdrant_url() -> String {
    std::env::var("QDRANT_URL")
        .unwrap_or_else(|_| "http://qdrant.qdrant.svc.cluster.local:6333".to_string())
}

const COLLECTION_NAME: &str = "qti_knowledge_base";

// 3. DATA STRUCTURES FOR QDRANT'S API
// What we send to Qdrant
#[derive(Serialize)]
struct SearchRequest {
    vector: Vec<f32>,
    limit: usize,
    with_payload: bool,
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
    text: Option<String>,
    sop_id: Option<String>,
    title: Option<String>,
}

// 4. THE SEARCH FUNCTION
// `pub` makes this visible to `routes/query.rs`.
// `async` is mandatory here because network requests take time.
pub async fn search_sop(query_vector: Vec<f32>) -> Result<String> {
    let client = Client::new();

    // Build the URL — now uses qdrant_url() instead of a hardcoded const
    let url = format!("{}/collections/{}/points/search", qdrant_url(), COLLECTION_NAME);

    let request_body = SearchRequest {
        vector: query_vector,
        limit: 1,
        with_payload: true,
    };

    // 🚨 CRITICAL CONCEPT: `.await` 🚨
    // `.send()` initiates the HTTP POST request.
    // `.await` tells Tokio: "Pause this function and let the CPU handle
    // other requests until Qdrant replies."
    let response = client
        .post(&url)
        .json(&request_body)
        .send()
        .await
        .context("❌ Failed to connect to Qdrant. Is the pod running?")?;

    if !response.status().is_success() {
        let error_text = response.text().await.unwrap_or_default();
        anyhow::bail!("❌ Qdrant returned an error: {}", error_text);
    }

    let qdrant_data: QdrantResponse = response
        .json()
        .await
        .context("❌ Failed to parse Qdrant's JSON response")?;

    if let Some(first_result) = qdrant_data.result.first() {
        if let Some(payload) = &first_result.payload {
            if let Some(text) = &payload.text {
                return Ok(text.clone());
            }
        }
    }

    Ok("No matching SOP found in the knowledge base.".to_string())
}