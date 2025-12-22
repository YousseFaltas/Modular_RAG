# Quick Start Guide - Microservice Architecture

## Summary of Changes

Your RAG chatbot has been refactored with a **separated embedding microservice**. This provides:

✅ Independent scaling of embedding service  
✅ Faster iteration on main chatbot  
✅ Better resource isolation  
✅ Reusable embedding API for other services  

## New Components

| Component | Role | Port |
|-----------|------|------|
| `embedding-service` | FastAPI microservice for embeddings | 8001 |
| `streamlit-app` | Chat interface (calls embedding service) | 8501 |
| `rag-service` | RAG queries (calls embedding service) | 8000 |
| `db` | PostgreSQL | 5432 |
| `weaviate` | Vector database | 8080 |

## Quick Start

### 1. Start All Services
```bash
docker-compose up -d
```

### 2. Verify Embedding Service
```bash
# Check health
curl http://localhost:8001/health

# Expected response:
# {"status": "healthy", "model": "BAAI/bge-m3"}
```

### 3. Access the Apps
- **Chat Interface**: http://localhost:8501
- **Embedding Service API**: http://localhost:8001/docs (Swagger UI)
- **RAG Service**: http://localhost:8000/docs
- **Weaviate**: http://localhost:8080
- **PostgreSQL**: localhost:5432

## Key Files Changed

### New Files
```
embedding_service.py              # FastAPI embedding microservice
Dockerfile.embedding              # Docker config for embedding service
embedding_requirements.txt        # Minimal dependencies
helpers/embedding_client.py       # Python client for the API
EMBEDDING_SERVICE.md              # Detailed documentation
```

### Modified Files
```
docker-compose.yml                # Added embedding-service configuration
testing_pipeline.py               # Now uses embedding service API
requirements.txt                  # Removed embedding dependencies
```

## How It Works

### Previous Architecture (Monolithic)
```
Streamlit App
    ↓
Direct embedding model (SentenceTransformer)
    ↓
Weaviate & PostgreSQL
```

### New Architecture (Microservices)
```
Streamlit App
    ↓ (HTTP REST API)
Embedding Service (FastAPI)
    ↓ (returns vectors)
Streamlit App
    ↓
Weaviate & PostgreSQL
```

## Using the Embedding Service

### In Python Code
```python
from helpers.embedding_client import get_embedding_client

client = get_embedding_client()

# Single embedding
vector = client.embed_single("Your text here")

# Batch embeddings
vectors = client.embed_batch(["text1", "text2", "text3"])

# Embed chunks (recommended)
chunks_with_vectors = client.embed_chunks([
    {"text": "content1", "doc_id": "123"},
    {"text": "content2", "doc_id": "123"}
])
```

### Direct API Calls
```bash
# Single embedding
curl -X POST http://localhost:8001/embed \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world"}'

# Batch embeddings
curl -X POST http://localhost:8001/embed-batch \
  -H "Content-Type: application/json" \
  -d '{"texts": ["text1", "text2"]}'

# Model info
curl http://localhost:8001/model-info
```

## Document Upload & Ingestion Flow

1. Upload PDF via Streamlit app
2. `data_extractions()` → Chunks document using Docling
3. `process_and_embed_chunks()` → Calls embedding service API
4. Embedding service returns vectors
5. Data ingested into:
   - PostgreSQL (metadata)
   - Weaviate (vectors)

## Scaling the Embedding Service

### Run Multiple Instances
```bash
# Terminal 1: Original service
docker-compose up embedding-service

# Terminal 2: Second instance on different port
docker run -p 8002:8001 -f Dockerfile.embedding embedding-service

# Use nginx/load balancer to distribute requests
```

### Monitor Service
```bash
# View logs
docker-compose logs -f embedding-service

# Check resource usage
docker stats embedding-service

# Health check
while true; do curl http://localhost:8001/health; sleep 5; done
```

## Troubleshooting

### Embedding Service Not Starting
```bash
# Check logs
docker-compose logs embedding-service

# Likely issues:
# 1. Model download timeout (first run)
# 2. Out of disk space
# 3. Port already in use
```

### Connection Error in Chat
Ensure environment variable is set:
```bash
export EMBEDDING_SERVICE_URL=http://localhost:8001
# or in .env file:
EMBEDDING_SERVICE_URL=http://embedding-service:8001
```

### Slow Embeddings
- First request takes longer (model warmup)
- Use batch API for multiple embeddings
- Consider GPU acceleration for production

## Environment Variables

Create `.env` file:
```bash
# Database
POSTGRES_USER=chatbot_user
POSTGRES_PASSWORD=secure_password
POSTGRES_DB=rag_chatbot

# API Keys
OPENAI_API_KEY=your_key_here

# Service URLs (Docker Compose automatically resolves these)
EMBEDDING_SERVICE_URL=http://embedding-service:8001
POSTGRES_HOST=db
WEAVIATE_HOST=weaviate
```

## Development Tips

### Test Locally Without Docker
```bash
# Terminal 1: Start embedding service
python -m uvicorn embedding_service:app --reload --port 8001

# Terminal 2: Use your client
python -c "from helpers.embedding_client import get_embedding_client; \
           client = get_embedding_client(); \
           print(client.embed_single('test'))"
```

### Add Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
```

### Performance Testing
```python
import time
from helpers.embedding_client import get_embedding_client

client = get_embedding_client()

# Single vs batch
start = time.time()
client.embed_single("text")
print(f"Single: {time.time() - start:.2f}s")

start = time.time()
client.embed_batch(["text"] * 10)
print(f"Batch 10: {time.time() - start:.2f}s")
```

## Next Steps

1. ✅ Run `docker-compose up -d`
2. ✅ Verify services: `curl http://localhost:8001/health`
3. ✅ Upload a document through the UI
4. ✅ Monitor embedding service: `docker logs embedding-service`
5. ✅ Test chat functionality
6. ✅ Check Weaviate console at http://localhost:8080

## Production Deployment

### Docker Image Build
```bash
# Build embedding service image
docker build -f Dockerfile.embedding -t my-registry/embedding-service:latest .
docker push my-registry/embedding-service:latest
```

### Kubernetes Deployment
See `EMBEDDING_SERVICE.md` for Kubernetes examples.

### Performance Optimization
- Use GPU-enabled instances for embedding service
- Increase batch size for throughput
- Use CDN/caching for common queries
- Monitor with Prometheus/Grafana

## Support & Debugging

Check `EMBEDDING_SERVICE.md` for:
- Complete API documentation
- Detailed architecture explanation
- Advanced configuration options
- Performance tuning guide
- Kubernetes deployment guide

---

**Questions?** Review the generated documentation:
- `EMBEDDING_SERVICE.md` - Complete reference
- `embedding_service.py` - Service implementation
- `helpers/embedding_client.py` - Client library
