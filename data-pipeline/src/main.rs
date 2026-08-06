use anyhow::{Context, Result};
use fastembed::{EmbeddingModel, InitOptions, TextEmbedding};
use serde_json::json;
use std::fs;
use uuid::Uuid;

const QDRANT_URL: &str = "http://localhost:6333";
const COLLECTION: &str = "qti_knowledge_base";
const MAX_CHUNK_CHARS: usize = 500;

fn chunk_text(body: &str, max_chars: usize) -> Vec<String> {
    let mut chunks = Vec::new();
    let mut current = String::new();
    for para in body.split("\n\n") {
        let para = para.trim();
        if para.is_empty() { continue; }
        if current.len() + para.len() + 2 > max_chars && !current.is_empty() {
            chunks.push(std::mem::take(&mut current));
        }
        if !current.is_empty() { current.push_str("\n\n"); }
        current.push_str(para);
    }
    if !current.is_empty() { chunks.push(current); }
    if chunks.is_empty() { chunks.push(body.trim().to_string()); }
    chunks
}

fn field(block: &str, key: &str) -> String {
    for line in block.lines() {
        if let Some(rest) = line.trim().strip_prefix(key) {
            return rest.trim_start_matches(':').trim().to_string();
        }
    }
    "unknown".to_string()
}

fn main() -> Result<()> {
    println!("📖 Reading RAG_Manual.md ...");
    let content = fs::read_to_string("RAG_Manual.md")
        .context("Failed to read RAG_Manual.md — run from inside data-pipeline/")?;
    let content = content.replace("\r\n", "\n");

    let mut sops = Vec::new();
    let mut current_block = String::new();
    let mut in_fence = false;

    for line in content.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with("```") { in_fence = !in_fence; }

        if !in_fence && line.starts_with("# SOP-") {
            if !current_block.is_empty() { sops.push(current_block); }
            current_block = line.trim_start_matches("# SOP-").to_string();
        } else if !in_fence && line.starts_with("# ") && !line.starts_with("## ") {
            if !current_block.is_empty() { sops.push(current_block); current_block = String::new(); }
        } else if !in_fence && trimmed == "---" {
            if !current_block.is_empty() { sops.push(current_block); current_block = String::new(); }
        } else if !current_block.is_empty() {
            current_block.push('\n');
            current_block.push_str(line);
        }
    }
    if !current_block.is_empty() { sops.push(current_block); }

    println!("✅ Found {} SOP entries.", sops.len());

    println!("🧠 Loading all-MiniLM-L6-v2 (384-dim) ...");
    let model = TextEmbedding::try_new(InitOptions::new(EmbeddingModel::AllMiniLML6V2))
        .context("Failed to init embedding model")?;

    let mut points = Vec::new();
    for block in &sops {
        let first_line = block.lines().next().unwrap_or("");
        let sop_id_meta = field(block, "SOP_ID");
        let category = field(block, "Category");
        let tier = field(block, "Confidence_Tier");
        let tags_str = field(block, "Tags");

        let (fallback_id, title) = match first_line.split_once(": ") {
            Some((i, t)) => (format!("SOP-{}", i.trim()), t.trim().to_string()),
            None => (first_line.trim().to_string(), "Untitled".to_string()),
        };
        let final_sop_id = if sop_id_meta != "unknown" { sop_id_meta } else { fallback_id };
        let final_category = if category != "unknown" { category } else { "unknown".to_string() };
        let final_tier = if tier != "unknown" { tier } else { "unknown".to_string() };
        let final_tags: Vec<String> = if tags_str != "unknown" {
            tags_str.split(',').map(|s| s.trim().to_string()).collect()
        } else { vec![] };

        let chunks = chunk_text(block, MAX_CHUNK_CHARS);
        let texts: Vec<String> = chunks.iter()
            .map(|c| format!("{} {}: {}", final_sop_id, title, c)).collect();
        let embeddings = model.embed(texts.clone(), None).context("embed failed")?;

        for (txt, vec) in texts.iter().zip(embeddings.into_iter()) {
            points.push(json!({
                "id": Uuid::new_v4().to_string(),
                "vector": vec,
                "payload": {
                    "text": txt, "sop_id": final_sop_id, "title": title,
                    "category": final_category, "tier": final_tier, "tags": final_tags
                }
            }));
        }
        println!("   {} ({}) [Tier {}] → {} chunk(s)", final_sop_id, final_category, final_tier, chunks.len());
    }
    println!("✅ Built {} points total.", points.len());

    let client = reqwest::blocking::Client::new();

    // ---- SMART RESET: only reset if the collection actually has data ----
    let mut state = "missing";
    if let Ok(resp) = client.get(format!("{}/collections/{}", QDRANT_URL, COLLECTION)).send() {
        if resp.status().is_success() {
            let body = resp.text().unwrap_or_default();
            if let Ok(v) = serde_json::from_str::<serde_json::Value>(&body) {
                let c = v["result"]["points_count"].as_u64().unwrap_or(0);
                state = if c > 0 { "hasdata" } else { "empty" };
            }
        }
    }
    println!("🔎 Collection state: {}.", state);

    if state == "hasdata" {
        println!("🗑️  Collection has data — resetting ...");
        let _ = client.delete(format!("{}/collections/{}", QDRANT_URL, COLLECTION)).send();
        std::thread::sleep(std::time::Duration::from_secs(3));
        state = "missing";
    }
    if state == "missing" {
        println!("🏗️  Creating collection ...");
        let create_resp = client
            .put(format!("{}/collections/{}", QDRANT_URL, COLLECTION))
            .json(&json!({ "vectors": { "size": 384, "distance": "Cosine" } }))
            .send()
            .context("failed to create collection")?;
        if !create_resp.status().is_success() {
            anyhow::bail!("Failed to create collection: {}", create_resp.text().unwrap_or_default());
        }
        println!("✅ Collection ready (384-dim, Cosine).");
    } else {
        println!("✅ Collection exists and is empty — skipping the heavy reset, upserting directly.");
    }

    println!("⬆️  Upserting to {} in batches ...", QDRANT_URL);
    let batch_size = 32;
    for (i, batch) in points.chunks(batch_size).enumerate() {
        let resp = client
            .put(format!("{}/collections/{}/points", QDRANT_URL, COLLECTION))
            .json(&json!({ "points": batch }))
            .send()
            .with_context(|| format!("upsert batch {} failed — is the tunnel window still open?", i))?;
        let status = resp.status();
        let body = resp.text().unwrap_or_default();
        if !status.is_success() { anyhow::bail!("Qdrant error on batch {} ({}): {}", i, status, body); }
        println!("   ✅ Batch {} OK ({} points)", i + 1, batch.len());
    }
    println!("✅ All upserts OK.");
    Ok(())
}