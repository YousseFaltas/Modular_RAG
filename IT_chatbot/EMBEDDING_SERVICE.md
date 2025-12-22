# Embedding Service Microservice Architecture

## Overview

The embedding model logic has been separated from the main chatbot into an independent microservice. This allows:

- **Scalability**: Run embedding service independently and scale it separately
- **Modularity**: Embedding service can be deployed and updated without touching main app
- **Resource Isolation**: Heavy embedding computations don't affect chat interface responsiveness
- **Reusability**: Other services can use the embedding API without duplicating logic

## Architecture

### Services

1. **embedding-service** (NEW)
   - FastAPI microservice running on port 8001
   - Handles all embedding operations using SentenceTransformer
   - Provides REST API endpoints for text embedding
   - Dockerfile: `Dockerfile.embedding`
   - Requirements: `embedding_requirements.txt`

2. **streamlit-app**
   - Main chat interface
   - Calls embedding service via HTTP API
   - Uses `helpers.embedding_client.EmbeddingServiceClient`

3. **rag-service**
   - RAG query service
   - Also uses embedding service API

4. **db** (PostgreSQL)
5. **weaviate** (Vector Database)

## Files Added/Modified

### New Files
- `embedding_service.py` - FastAPI embedding service
- `Dockerfile.embedding` - Docker configuration for embedding service
- `embedding_requirements.txt` - Minimal dependencies for embedding service
- `helpers/embedding_client.py` - Python client for embedding service API

### Modified Files
- `docker-compose.yml` - Added embedding-service configuration
- `testing_pipeline.py` - Updated to use embedding service API
- `app.py` - Ready to use embedding service (no changes needed, uses testing_pipeline)
- `requirements.txt` - No changes needed, but can be cleaned up if desired

## Embedding Service API Endpoints

### Health Check
```
GET /health
Returns: {"status": "healthy", "model": "BAAI/bge-m3"}
```

### Single Text Embedding
```
POST /embed
Request: {"text": "Your text here"}
Response: {"text": "Your text here", "embedding": [0.123, ...]}
```

### Batch Embedding
```
POST /embed-batch
Request: {"texts": ["text1", "text2", ...]}
Response: {"embeddings": [{"text": "text1", "embedding": [...]}, ...]}
```

### Chunk Embedding (Recommended)
```
POST /embed-chunks
Request: {"chunks": [{"text": "...", "other_field": "..."}, ...]}
Response: {"chunks": [{"text": "...", "vector": [...], "other_field": "..."}, ...]}
```

### Model Information
```
GET /model-info
Returns: {
  "model_name": "BAAI/bge-m3",
  "embedding_dim": 384,
  "device": "cpu" or "cuda",
  "max_seq_length": 8192
}
```

## Using the Embedding Service

### In Python Code

```python
from helpers.embedding_client import get_embedding_client

# Get client instance
client = get_embedding_client()

# Or specify custom URL
client = get_embedding_client(base_url="http://embedding-service:8001")

# Embed single text
embedding = client.embed_single("Your text here")

# Embed multiple texts
embeddings = client.embed_batch(["text1", "text2", "text3"])

# Embed chunks (preserves all chunk data)
chunks_with_vectors = client.embed_chunks([
    {"text": "chunk1", "doc_id": "123"},
    {"text": "chunk2", "doc_id": "123"}
])

# Check service health
is_healthy = client.health_check()

# Get model info
info = client.get_model_info()
```

### From testing_pipeline.py

The updated `process_and_embed_chunks()` function now:
1. Creates chunk dictionaries with metadata
2. Sends them to the embedding service via API
3. Receives chunks with embedded vectors
4. Returns the data for database ingestion

```python
chunks = data_extractions(pdf_path)
ingestion_data = process_and_embed_chunks(chunks)  # Uses embedding service API
ingest_to_postgres(ingestion_data["chunks"])
insert_to_weaviate(ingestion_data)
```

## Running the Services

### With Docker Compose
```bash
docker-compose up -d
```

This will start:
- PostgreSQL (port 5432)
- Weaviate (port 8080)
- Embedding Service (port 8001)
- RAG Service (port 8000)
- Streamlit App (port 8501)

### Checking Embedding Service Status
```bash
# Health check
curl http://localhost:8001/health

# Model info
curl http://localhost:8001/model-info

# Test embedding
curl -X POST http://localhost:8001/embed \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world"}'
```

### Standalone Embedding Service
To run only the embedding service:

```bash
# Build image
docker build -f Dockerfile.embedding -t embedding-service .

# Run container
docker run -p 8001:8001 \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  embedding-service

# Or with Docker Compose
docker-compose up embedding-service
```

## Environment Variables

Required environment variables:
- `OPENAI_API_KEY` - OpenAI API key (used by other services, optional for embedding service)
- `EMBEDDING_SERVICE_URL` - URL to embedding service (default: `http://localhost:8001`)

Optional:
- `POSTGRES_HOST` - PostgreSQL host (default: `localhost`)
- `POSTGRES_USER` - PostgreSQL user
- `POSTGRES_PASSWORD` - PostgreSQL password
- `POSTGRES_DB` - PostgreSQL database name
- `WEAVIATE_HOST` - Weaviate host (default: `localhost`)
- `WEAVIATE_PORT` - Weaviate port (default: `8080`)

## Scaling & Deployment

### Multiple Embedding Service Instances
You can run multiple embedding service instances with a load balancer:

```yaml
# In docker-compose.yml
embedding-service-1:
  build:
    context: .
    dockerfile: Dockerfile.embedding
  ports:
    - "8001:8001"
  ...

embedding-service-2:
  build:
    context: .
    dockerfile: Dockerfile.embedding
  ports:
    - "8002:8001"  # Map to different port
  ...

# Use nginx or similar for load balancing
```

### Kubernetes Deployment
The embedding service is stateless and can be easily deployed to Kubernetes:
- No persistent storage needed
- Can scale horizontally with replicas
- Health checks already implemented

## Development Tips

### Testing the Embedding Service
```python
import requests

# Test the API directly
response = requests.post(
    "http://localhost:8001/embed-batch",
    json={"texts": ["Hello world", "Test embedding"]}
)
print(response.json())
```

### Monitoring
- Check service logs: `docker logs embedding-service`
- Monitor health: `curl http://localhost:8001/health`
- Performance: Measure embedding request latency and throughput

### Upgrading the Embedding Model
To use a different embedding model:
1. Update `EMBEDDING_MODEL` variable in `embedding_service.py`
2. Rebuild the embedding service Docker image
3. Restart the service

Example:
```python
# In embedding_service.py
EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"  # Different model
```

## Troubleshooting

### Embedding Service Not Responding
```bash
# Check if service is running
docker-compose ps | grep embedding

# View logs
docker-compose logs embedding-service

# Health check
curl http://localhost:8001/health
```

### Model Download Issues
The first startup may take time as the model is downloaded. Monitor with:
```bash
docker-compose logs -f embedding-service
```

### Connection Issues in Docker
Ensure your other services use `http://embedding-service:8001` (not `localhost`)
and that they're on the same network (`rag-network`).

## API Response Examples

### Successful Embedding Response
```json
{
  "text": "Hello world",
  "embedding": [0.123, 0.456, ..., 0.789]
}
```

### Error Response
```json
{
  "detail": "Embedding model not loaded"
}
```
HTTP Status: 503 (Service Unavailable)

### Batch Response
```json
{
  "embeddings": [
    {"text": "text1", "embedding": [...]},
    {"text": "text2", "embedding": [...]}
  ]
}
```

## Performance Considerations

- **Batch Processing**: Use `/embed-batch` or `/embed-chunks` for better throughput
- **Model Size**: BAAI/bge-m3 is ~1GB, ensure sufficient disk space
- **GPU Support**: Automatically uses CUDA if available, otherwise falls back to CPU
- **Timeout**: Default timeout is 5 minutes for batch operations

## Next Steps

1. Start all services: `docker-compose up -d`
2. Verify embedding service: `curl http://localhost:8001/health`
3. Upload documents via Streamlit app
4. Monitor service logs during ingestion
5. Test retrieval and chat functionality
