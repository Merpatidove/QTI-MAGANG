use anyhow::{Context, Result};
use fastembed::{EmbeddingModel, InitOptions, TextEmbedding};
use serde_json::json;
use std::fs;
use uuid::Uuid;

// With the tunnel running, localhost:6333 IS the cluster's Qdrant.
const QDRANT_URL: &str = "http://localhost:6333";
const COLLECTION: &str = "qti_knowledge_base";
const MAX_CHUNK_CHARS: usize = 500; // stay under MiniLM's 256-token window

// Pack paragraphs into ~max_chars chunks. A fenced ```bash block is one
// paragraph, so it never gets sliced mid-command.
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

// Read a "## Key: value" line if the SOP has it; else "unknown".
fn field(block: &str, key: &str) -> String {
    for line in block.lines() {
        if let Some(rest) = line.trim().strip_prefix(key) {
            return rest.trim_start_matches(':').trim().to_string();
        }
    }
    "unknown".to_string()
}

fn main() -> Result<()> {
    // ---- READ ----
    println!("📖 Reading RAG_Manual.md ...");
    let content = fs::read_to_string("RAG_Manual.md")
        .context("Failed to read RAG_Manual.md — run from inside data-pipeline/")?;
    let content = content.replace("\r\n", "\n"); // normalize Windows line endings

    let blocks: Vec<&str> = content.split("\n# SOP-").collect();
    let sops = &blocks[1..]; // block 0 is the intro before the first SOP
    println!("✅ Found {} SOP entries.", sops.len());

    // ---- EMBED ----
    println!("🧠 Loading all-MiniLM-L6-v2 (384-dim) — first run downloads the model (~80 MB), this is normal ...");
    let model = TextEmbedding::try_new(InitOptions::new(EmbeddingModel::AllMiniLML6V2))
        .context("Failed to init embedding model")?;

    let mut points = Vec::new();
    for block in sops {
        let first_line = block.lines().next().unwrap_or("");
        let (id, title) = match first_line.split_once(": ") {
            Some((i, t)) => (i.trim().to_string(), t.trim().to_string()),
            None => (first_line.trim().to_string(), "Untitled".to_string()),
        };
        let category = field(block, "## Category");
        let tier = field(block, "## Confidence Tier");

        let chunks = chunk_text(block, MAX_CHUNK_CHARS);
        // prefix each chunk with id+title so the vector carries that context
        let texts: Vec<String> = chunks.iter()
            .map(|c| format!("SOP-{} {}: {}", id, title, c)).collect();
        let embeddings = model.embed(texts.clone(), None).context("embed failed")?;

        for (txt, vec) in texts.iter().zip(embeddings.into_iter()) {
            points.push(json!({
                "id": Uuid::new_v4().to_string(),
                "vector": vec,
                "payload": {
                    "text": txt,
                    "sop_id": format!("SOP-{}", id),
                    "title": title,
                    "category": category,
                    "tier": tier
                }
            }));
        }
        println!("   SOP-{} → {} chunk(s)", id, chunks.len());
    }
    println!("✅ Built {} points total.", points.len());

    // ---- UPSERT ----
    println!("⬆️  Upserting to {} ...", QDRANT_URL);
    let resp = reqwest::blocking::Client::new()
        .put(format!("{}/collections/{}/points", QDRANT_URL, COLLECTION))
        .json(&json!({ "points": points }))
        .send()
        .context("upsert failed — is the tunnel window still open?")?;
    let status = resp.status();
    let body = resp.text().unwrap_or_default();
    if !status.is_success() { anyhow::bail!("Qdrant error ({}): {}", status, body); }
    println!("✅ Upsert OK: {}", body);
    Ok(())
}