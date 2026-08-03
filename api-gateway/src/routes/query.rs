use axum::Json;
use lazy_static::lazy_static;
use prometheus::{register_int_counter, register_int_counter_vec, register_histogram};
use anyhow::Result;
use fastembed::{EmbeddingModel, InitOptions, TextEmbedding};
use crate::models::{QueryRequest, QueryResponse, TicketMetadata, RemediationPayload};

lazy_static! {
    pub static ref QUERIES_TOTAL: prometheus::IntCounter = register_int_counter!(
        "queries_total",
        "Total number of RAG query requests received"
    ).unwrap();

    // NEW: did the Qdrant search return a usable SOP match?
    static ref QDRANT_MATCH_TOTAL: prometheus::IntCounterVec = register_int_counter_vec!(
        "qti_qdrant_match_total",
        "Whether the Qdrant search returned a usable SOP match",
        &["found"]
    ).unwrap();

    // NEW: /v1/query responses counted by classification
    static ref TICKET_CLASSIFICATION_TOTAL: prometheus::IntCounterVec = register_int_counter_vec!(
        "qti_ticket_classification_total",
        "Count of /v1/query responses by classification",
        &["classification"]
    ).unwrap();

    // NEW: end-to-end /v1/query latency in seconds
    static ref REQUEST_DURATION_SECONDS: prometheus::Histogram = register_histogram!(
        "qti_request_duration_seconds",
        "End-to-end latency of /v1/query in seconds"
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
    // NEW: start the latency timer. It records the duration automatically when
    // this function returns — on ANY path, including the early embed_error return.
    let _timer = REQUEST_DURATION_SECONDS.start_timer();
    println!("📨 Query for ticket {}", req.ticket_id);

    let vector = match embed_text(&req.raw_text) {
        Ok(v) => v,
        Err(e) => {
            tracing::error!("embed failed: {e}");
            // NEW: count the embed_error classification
            TICKET_CLASSIFICATION_TOTAL.with_label_values(&["embed_error"]).inc();
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

    // NEW: did we get a real SOP chunk back? Ingestion prefixes every stored
    // chunk with "SOP-{id} {title}:", so a real match starts with "SOP-";
    // the no-match / error fallback does not.
    let found = sop_text.starts_with("SOP-");
    QDRANT_MATCH_TOTAL.with_label_values(&[if found { "true" } else { "false" }]).inc();

    // NEW: count the retrieved classification
    TICKET_CLASSIFICATION_TOTAL.with_label_values(&["retrieved"]).inc();

    Json(QueryResponse {
        ticket_metadata: TicketMetadata { ticket_id: req.ticket_id, classification: "retrieved".into() },
        remediation_payload: RemediationPayload { proposed_fix: sop_text, requires_type_check: true },
    })
}