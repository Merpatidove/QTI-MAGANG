# HITE API Contract (JSON Schema)
**Version:** 1.0
**Status:** Locked for Initial Prototype


## 1. The Input Payload (Request)
This is the payload the API Gateway sends to the Python Inference Engine when a new ticket is submitted.

```json
{
  "ticket_id": "TKT-8492",
  "raw_text": "Getting a non-fast-forward error when trying toj push to ResponsiPemweb_6_Bali main branch.",
  "project_tags": ["git", "version-control"]
}

## 2. The Output Payload (Response)

```json
{
  "ticket_metadata": {
    "ticket_id": "TKT-8492",
    "timestamp": "2026-07-14T10:15:22Z",
    "classification": "Version Control Error"
  },
  "cognitive_triage": {
    "fact_coverage_score": 1.00,
    "confidence_tier": "A",
    "qdrant_match_found": true
  },
  "remediation_payload": {
    "proposed_fix": "```bash\ngit pull origin main --rebase\ngit push origin main\n```",
    "requires_type_check": false
  },
  "grounding_citations": [
    {
      "document_title": "Internal Git SOP",
      "version": "1.2",
      "last_updated": "2026-01-15",
      "passage_similarity_score": 0.94
    }
  ],
  "routing_decision": {
    "action": "AUTO_DELIVER",
    "escalation_target": null,
    "reason": "Fact coverage is 100%. Safe for developer review."
  }
}