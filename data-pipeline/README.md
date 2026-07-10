# /data-pipeline — Web Scraping & Qdrant Ingestion

## Owner
Data Engineering Team

## Purpose
This directory contains the **data pipeline** — scraping raw documents, chunking them, generating embeddings, and upserting them into the **Qdrant** vector database.

## Responsibilities
- Scrape and collect source documents (web pages, PDFs, DOCX)
- Clean and chunk text (target: ≤ 512 tokens per chunk)
- Generate 1024-dim embeddings using the agreed embedding model
- Upsert points into Qdrant collection `qti_knowledge_base` with the required payload schema
- Schedule and monitor recurring ingestion jobs

## Directory Layout (Planned)
```
data-pipeline/
├── scrapers/
│   ├── web_scraper.py       # HTTP/HTML scraping
│   └── pdf_parser.py        # PDF/DOCX extraction
├── processors/
│   ├── chunker.py           # Text chunking logic
│   └── embedder.py          # Embedding model wrapper
├── ingestion/
│   └── qdrant_upserter.py   # Qdrant client & upsert logic
├── schemas/
│   └── payload_schema.json  # Mirrors api_contract.md §4.2
├── tests/
│   └── test_chunker.py
├── requirements.txt
├── .env.example             # QDRANT_URL, QDRANT_API_KEY, etc.
└── README.md
```

## Qdrant Payload Schema
All upserted points must conform to the schema in [api_contract.md §4.2](../api_contract.md#42-qdrant-payload-schema-ingested-by-data-engineering).

**Collection name:** `qti_knowledge_base`  
**Vector dimensions:** `1024`  
**Distance metric:** `Cosine`

## Setup
> TODO: Add setup instructions once `requirements.txt` and Qdrant collection are initialized.
