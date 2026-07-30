use axum::Json;
use lazy_static::lazy_static;
use prometheus::register_int_counter;
use anyhow::Result;
use fastembed::{EmbeddingModel, InitOptions, TextEmbedding};
use crate::models::{QueryRequest, QueryResponse, TicketMetadata, RemediationPayload};

lazy_static! {
    pub static ref QUERIES_TOTAL: prometheus::IntCounter = register_int_counter!(
        "queries_total",
        "Total number of RAG query requests received"
    ).unwrap();
}

// text -> 384-dim vector, same model as the pipeline.
// EMBED_CACHE_DIR (set only in the cluster image) tells fastembed to load the
// baked model instead of downloading (the cluster has no internet).
fn embed_text(text: &str) -> Result<Vec<f32>> {
    let mut opts = InitOptions::new(EmbeddingModel::AllMiniLML6V2);
    if let Ok(dir) = std::env::var("EMBED_CACHE_DIR") {
        opts.cache_dir = std::path::PathBuf::from(dir);
        // if this line errors with "expected Option<...>", wrap the right side in Some( ... )
    }
    let model = TextEmbedding::try_new(opts)?;
    let mut v = model.embed(vec![text.to_string()], None)?;
    Ok(v.remove(0))
}

// used later by the Docker build to pre-download the model
pub fn warm_embedder() -> Result<()> { embed_text("warmup").map(|_| ()) }

pub async fn query(Json(req): Json<QueryRequest>) -> Json<QueryResponse> {
    QUERIES_TOTAL.inc();
    println!("📨 Query for ticket {}", req.ticket_id);

    let vector = match embed_text(&req.raw_text) {
        Ok(v) => v,
        Err(e) => {
            tracing::error!("embed failed: {e}");
            return Json(QueryResponse {
                ticket_metadata: TicketMetadata { ticket_id: req.ticket_id, classification: "embed_error".into() },
                remediation_payload: RemediationPayload { proposed_fix: format!("Embedding failed: {e}"), requires_type_check: true },
            });
        }
    };
    let sop_text = match crate::clients::qdrant::search_sop(vector).await {
        Ok(t) => t,
        Err(e) => { tracing::error!("qdrant search failed: {e}"); "No matching SOP found in the knowledge base.".to_string() }
    };

    Json(QueryResponse {
        ticket_metadata: TicketMetadata { ticket_id: req.ticket_id, classification: "retrieved".into() },
        remediation_payload: RemediationPayload { proposed_fix: sop_text, requires_type_check: true },
    })
}