# System Architecture Diagrams

## Microservice Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                      Docker Network (rag-network)                 │
│                                                                    │
│  ┌──────────────────────┐    ┌──────────────────────────────────┐ │
│  │  Streamlit Chat App  │    │  Embedding Service (FastAPI)     │ │
│  │  Port: 8501          │    │  Port: 8001                      │ │
│  │                      │    │                                  │ │
│  │  • File upload       │    │  • Load SentenceTransformer      │ │
│  │  • Chat interface    │    │  • Embed texts                   │ │
│  │  • Vector search     │◄───┤  • Batch operations              │ │
│  │                      │ (HTTP REST API)  • Health checks      │ │
│  └──────────────────────┘    └──────────────────────────────────┘ │
│           │ │                                                       │
│           │ └────────────────────────────────────────┐              │
│           │                                          │              │
│           └──────────────────┐                       │              │
│                              │                       │              │
│  ┌────────────────────────────▼─────┐  ┌────────────▼──────────┐  │
│  │   PostgreSQL (Port 5432)         │  │   Weaviate (Port 8080)│  │
│  │                                  │  │                       │  │
│  │   • Document metadata            │  │   • Vector storage    │  │
│  │   • Chunk data                   │  │   • Vector search     │  │
│  │   • Relationships                │  │   • Graph DB          │  │
│  └──────────────────────────────────┘  └───────────────────────┘  │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

## Data Flow: Document Processing

```
Step 1: Upload Document (Streamlit)
         │
         ▼
┌────────────────────┐
│  app.py            │
│  file_uploader()   │
└────────────────────┘
         │
         ▼
Step 2: Extract & Chunk (Docling)
┌────────────────────┐
│  testing_pipeline  │
│  data_extractions()│
│  Uses Docling      │
└────────────────────┘
         │
         ▼
Step 3: Embed (via API)
┌────────────────────────────────────┐
│  testing_pipeline                  │
│  process_and_embed_chunks()        │
│  ├─ Create chunk objects           │
│  └─ Call embedding_client.py       │
└────────────────────────────────────┘
         │
         ▼ HTTP POST /embed-chunks
┌────────────────────────────────────┐
│  embedding_service.py              │
│  POST /embed-chunks endpoint       │
│  ├─ Receives chunks                │
│  ├─ Encodes with SentenceTransformer
│  └─ Returns chunks with vectors    │
└────────────────────────────────────┘
         │
         ▼ Return vectors
┌────────────────────────────────────┐
│  testing_pipeline (continued)      │
│  Receives embedded chunks          │
└────────────────────────────────────┘
         │
         ├─────────────┬──────────────┐
         │             │              │
    Step 4a        Step 4b        Step 5
    Metadata       Metadata       Vectors
         │             │              │
         ▼             ▼              ▼
    ┌────────┐   ┌────────┐   ┌──────────┐
    │  DB    │   │  DB    │   │ Weaviate │
    │ Insert │   │ Insert │   │  Insert  │
    └────────┘   └────────┘   └──────────┘
```

## Request-Response Flow

### Embedding Service - Single Text
```
Client Application
        │
        │ POST /embed
        │ {"text": "Hello world"}
        ▼
┌─────────────────────────────────┐
│  embedding_service.py           │
│                                 │
│  @app.post("/embed")            │
│  async def embed_single():      │
│    • Receive text               │
│    • Encode with model          │
│    • Normalize embeddings       │
│    • Return vector              │
└─────────────────────────────────┘
        │
        │ 200 OK
        │ {"text": "...", "embedding": [...]}
        ▼
Client Receives Vector
```

### Embedding Service - Batch with Chunks
```
Python Client (testing_pipeline.py)
        │
        │ POST /embed-chunks
        │ {
        │   "chunks": [
        │     {"text": "...", "doc_id": "123", ...},
        │     {"text": "...", "doc_id": "456", ...}
        │   ]
        │ }
        ▼
┌─────────────────────────────────────┐
│  embedding_service.py               │
│                                     │
│  @app.post("/embed-chunks")         │
│  async def embed_chunks():          │
│    • Receive chunks                 │
│    • Extract texts                  │
│    • Batch encode                   │
│    • Add "vector" to each chunk     │
│    • Return enriched chunks         │
└─────────────────────────────────────┘
        │
        │ 200 OK
        │ {
        │   "chunks": [
        │     {
        │       "text": "...",
        │       "vector": [...],
        │       "doc_id": "123",
        │       ... all original fields ...
        │     },
        │     ...
        │   ]
        │ }
        ▼
Client Processes Data
```

## Service Dependencies

```
┌─────────────────────────────────────────┐
│          Docker Compose Stack           │
│                                         │
│  ┌──────────────────────────────────┐   │
│  │  streamlit-app                   │   │
│  │  • depends_on: [db, weaviate]    │   │
│  │  • depends_on: [embedding-srv]   │   │
│  └──────────────────────────────────┘   │
│           ▲         ▲          ▲         │
│           │         │          │         │
│      ┌────┴─┐  ┌───┴─┐   ┌───┴──┐      │
│      │      │  │     │   │      │      │
│  ┌───▼──┐ ┌─▼──▼─┐ ┌──▼──────────┐   │
│  │  db  │ │weavi │ │ embedding-  │   │
│  │      │ │ ate  │ │ service     │   │
│  └──────┘ └──────┘ └─────────────┘   │
│                                         │
│  All services on "rag-network"         │
│  Automatic DNS resolution within net   │
└─────────────────────────────────────────┘
```

## API Endpoint Diagram

```
┌──────────────────────────────────────────────────────────┐
│         Embedding Service API (Port 8001)                │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  Health & Monitoring                                     │
├──────────────────────────────────────────────────────────┤
│  GET /health                                             │
│  └─ Returns: {"status": "healthy", "model": "..."}      │
│                                                          │
│  GET /model-info                                         │
│  └─ Returns: {embedding_dim, device, model_name, ...}  │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  Embedding Endpoints                                     │
├──────────────────────────────────────────────────────────┤
│  POST /embed                                             │
│  Request: {"text": "string"}                             │
│  Response: {"text": "...", "embedding": [float, ...]}   │
│  Use for: Single text embeddings                        │
│                                                          │
│  POST /embed-batch                                       │
│  Request: {"texts": ["str1", "str2", ...]}             │
│  Response: {"embeddings": [{text, embedding}, ...]}    │
│  Use for: Multiple texts, better throughput             │
│                                                          │
│  POST /embed-chunks                                      │
│  Request: {"chunks": [{text, doc_id, ...}, ...]}       │
│  Response: {"chunks": [{..., vector, ...}, ...]}       │
│  Use for: Document chunks, preserves metadata           │
└──────────────────────────────────────────────────────────┘
```

## Model Architecture (BAAI/bge-m3)

```
┌──────────────────────────────────────────────┐
│   Input Text                                  │
│   "Your text here..."                         │
└────────────────┬─────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────┐
│   Tokenization                                │
│   [CLS] token_1 token_2 ... token_n [SEP]   │
└────────────────┬─────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────┐
│   BERT Transformer Layers                     │
│   • 12 layers                                 │
│   • 768 hidden dimensions                     │
│   • Attention mechanisms                      │
└────────────────┬─────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────┐
│   Mean Pooling                                │
│   Pool [CLS] and all token representations   │
└────────────────┬─────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────┐
│   L2 Normalization                            │
│   Normalize vector to unit length             │
└────────────────┬─────────────────────────────┘
                 │
└────────────────▼─────────────────────────────┘
           Output Embedding
        384-dimensional vector
        Cosine similarity ready
    [0.123, 0.456, 0.789, ..., 0.234]
```

## Docker Image Layers

### Before (Monolithic)
```
streamlit-app Docker Image (3.5GB)
├── Base: python:3.10-slim
├── Dependencies
│   ├── docling (OCR, chunking)
│   ├── sentence-transformers (MODEL)
│   ├── torch (MODEL)
│   ├── weaviate-client
│   ├── psycopg2
│   └── streamlit, fastapi, etc.
└── Application code
    ├── app.py
    ├── testing_pipeline.py
    ├── helpers/
    └── ...

Total: 1 large image with everything
```

### After (Microservices)
```
streamlit-app Image (2.8GB)              embedding-service Image (3.2GB)
├── Base: python:3.10-slim               ├── Base: python:3.10-slim
├── Dependencies                         ├── Dependencies
│   ├── docling                          │   ├── sentence-transformers
│   ├── weaviate-client                  │   ├── torch (MODEL)
│   ├── psycopg2                         │   ├── fastapi
│   ├── streamlit                        │   ├── uvicorn
│   ├── fastapi                          │   └── pydantic
│   └── ...                              │
├── Application code                     └── Application code
│   ├── app.py                               ├── embedding_service.py
│   ├── testing_pipeline.py                 └── ...
│   ├── helpers/
│   └── ...                              Separate, focused image

Total: 2 focused images
```

## Traffic Flow in Docker Network

```
Internet (localhost)
    │
    ├─── :8501 ──────────┐
    │                    │
    ├─── :8001 ──────────┤
    │                    │
    ├─── :8000 ──────────┤
    │                    │
    ├─── :8080 ──────────┤
    │                    │
    └─── :5432 ──────────┤
                         │
                    Internal Docker Network (rag-network)
                    ┌────┴────────────────────────────────┐
                    │                                     │
            ┌───────▼──────┐                  ┌──────────▼─────┐
            │ streamlit:   │                  │ embedding-     │
            │   8501       │ ◄────HTTP───────│  service:      │
            │              │    (REST API)    │    8001        │
            │ + calls      │                  │                │
            │ postgresql   │                  │ Returns vectors│
            │ + writes to  │                  │                │
            │ weaviate     │                  └────────────────┘
            └───────┬──────┘
                    │
         ┌──────────┼──────────┐
         │          │          │
    ┌────▼──┐  ┌───▼───┐  ┌──▼──────┐
    │ db    │  │weaviate│  │ rag-    │
    │ :5432 │  │ :8080  │  │service  │
    │       │  │        │  │ :8000   │
    └───────┘  └────────┘  └─────────┘
```

## State Transitions

```
Embedding Service Lifecycle
└─ Startup
   ├─ Load FastAPI app
   ├─ Start @app.on_event("startup")
   ├─ Load SentenceTransformer model (30-40s)
   │  └─ Downloaded from HuggingFace
   ├─ Ready to serve requests
   └─ Health endpoint returns "healthy"
      │
      ├─ Service Running
      │  ├─ /health checks pass
      │  ├─ API endpoints respond
      │  ├─ Accept /embed requests
      │  └─ Return vectors within latency SLA
      │
      └─ Shutdown
         ├─ Graceful shutdown
         ├─ Wait for in-flight requests
         └─ Clean up resources
```

---

These diagrams illustrate the complete architecture, data flows, and service interactions in the microservices-based RAG chatbot system.
