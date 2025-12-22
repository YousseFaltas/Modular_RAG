# Deployment & Testing Checklist

## Pre-Deployment Checklist

### Code Review
- [ ] Review `embedding_service.py` for business logic correctness
- [ ] Check `helpers/embedding_client.py` for error handling
- [ ] Verify `testing_pipeline.py` properly calls embedding service
- [ ] Ensure `docker-compose.yml` has correct service ordering
- [ ] Check all new files are present:
  - [ ] `embedding_service.py`
  - [ ] `Dockerfile.embedding`
  - [ ] `embedding_requirements.txt`
  - [ ] `helpers/embedding_client.py`
  - [ ] Documentation files (4x .md files)

### Configuration
- [ ] `.env` file exists with required variables:
  - [ ] `POSTGRES_USER`
  - [ ] `POSTGRES_PASSWORD`
  - [ ] `POSTGRES_DB`
  - [ ] `OPENAI_API_KEY`
  - [ ] `EMBEDDING_SERVICE_URL` (optional, defaults to localhost:8001)
- [ ] Docker daemon is running
- [ ] Sufficient disk space (at least 10GB for models and containers)
- [ ] Ports are available:
  - [ ] 8001 (embedding service)
  - [ ] 8501 (streamlit)
  - [ ] 8000 (rag service)
  - [ ] 8080 (weaviate)
  - [ ] 5432 (postgres)

### Dependencies
- [ ] `requirements.txt` updated (embedding deps removed)
- [ ] `embedding_requirements.txt` created with correct packages
- [ ] Python version compatible (3.8+)
- [ ] Docker and docker-compose installed

## Deployment Steps

### Step 1: Build Images
```bash
# In project directory
docker-compose build

# Expected output:
# Successfully built embedding-service image
# Successfully built streamlit-app image
# Successfully built rag-service image
```

**Checklist:**
- [ ] No build errors
- [ ] Images are properly tagged
- [ ] Total image size reasonable

### Step 2: Start Services
```bash
docker-compose up -d

# Expected output:
# Creating network "IT_chatbot_rag-network" with driver "bridge"
# Creating IT_chatbot_db_1 ...
# Creating IT_chatbot_weaviate_1 ...
# Creating IT_chatbot_embedding-service_1 ...
# Creating IT_chatbot_rag-service_1 ...
# Creating IT_chatbot_streamlit-app_1 ...
```

**Checklist:**
- [ ] All services created successfully
- [ ] No port conflicts
- [ ] Services starting without errors

### Step 3: Verify Services Running
```bash
docker-compose ps

# Expected output:
# NAME                    STATUS              PORTS
# IT_chatbot_db_1         Up 2 minutes        0.0.0.0:5432->5432/tcp
# IT_chatbot_weaviate_1   Up 2 minutes        0.0.0.0:8080->8080/tcp
# IT_chatbot_embedding... Up 2 minutes        0.0.0.0:8001->8001/tcp
# IT_chatbot_rag-service  Up 2 minutes        0.0.0.0:8000->8000/tcp
# IT_chatbot_streamlit... Up 1 minute         0.0.0.0:8501->8501/tcp
```

**Checklist:**
- [ ] All services show "Up" status
- [ ] All ports properly mapped
- [ ] No services restarting repeatedly

## Health Checks

### Embedding Service Health
```bash
# Direct health check
curl http://localhost:8001/health

# Expected response (< 100ms):
# {"status":"healthy","model":"BAAI/bge-m3"}
```

**Checklist:**
- [ ] Returns HTTP 200
- [ ] Status is "healthy"
- [ ] Response time < 100ms

### Model Information
```bash
curl http://localhost:8001/model-info

# Expected response:
# {
#   "model_name": "BAAI/bge-m3",
#   "embedding_dim": 384,
#   "device": "cpu" or "cuda",
#   "max_seq_length": 8192
# }
```

**Checklist:**
- [ ] Returns HTTP 200
- [ ] Correct embedding dimension (384)
- [ ] Device properly detected

### PostgreSQL Health
```bash
# From inside Docker
docker-compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1"

# Expected response:
# ?column?
# --------
#        1
```

**Checklist:**
- [ ] Connection successful
- [ ] Database accessible

### Weaviate Health
```bash
curl http://localhost:8080/v1/.well-known/ready

# Expected response:
# {"ready":true}
```

**Checklist:**
- [ ] Returns HTTP 200
- [ ] Ready status true

### Streamlit App
```bash
# Open browser or curl
curl -I http://localhost:8501

# Expected response:
# HTTP/1.1 200 OK
```

**Checklist:**
- [ ] App loads at http://localhost:8501
- [ ] No JavaScript errors in browser console
- [ ] Sidebar visible with "Upload Documents"

## Functional Testing

### Test 1: Single Text Embedding
```bash
curl -X POST http://localhost:8001/embed \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world"}'

# Expected response (< 500ms):
# {
#   "text": "Hello world",
#   "embedding": [0.123, 0.456, ..., 0.789]
# }
```

**Checklist:**
- [ ] Returns HTTP 200
- [ ] Embedding vector has 384 dimensions
- [ ] Response time reasonable

### Test 2: Batch Embedding
```bash
curl -X POST http://localhost:8001/embed-batch \
  -H "Content-Type: application/json" \
  -d '{
    "texts": [
      "This is text one",
      "This is text two",
      "This is text three"
    ]
  }'

# Expected response:
# {
#   "embeddings": [
#     {"text": "...", "embedding": [...]},
#     {"text": "...", "embedding": [...]},
#     {"text": "...", "embedding": [...]}
#   ]
# }
```

**Checklist:**
- [ ] Returns HTTP 200
- [ ] All 3 embeddings returned
- [ ] Each has 384 dimensions

### Test 3: Chunk Embedding
```bash
curl -X POST http://localhost:8001/embed-chunks \
  -H "Content-Type: application/json" \
  -d '{
    "chunks": [
      {
        "text": "First chunk content",
        "doc_id": "doc123",
        "chunk_index": 0
      },
      {
        "text": "Second chunk content",
        "doc_id": "doc123",
        "chunk_index": 1
      }
    ]
  }'

# Expected response:
# {
#   "chunks": [
#     {
#       "text": "First chunk content",
#       "vector": [...384 dimensions...],
#       "doc_id": "doc123",
#       "chunk_index": 0
#     },
#     {...}
#   ]
# }
```

**Checklist:**
- [ ] Returns HTTP 200
- [ ] All metadata preserved (doc_id, chunk_index, etc.)
- [ ] Vector field added to each chunk
- [ ] Each vector has 384 dimensions

### Test 4: Document Upload & Embedding
1. Open http://localhost:8501
2. Upload a PDF file

**Checklist:**
- [ ] File upload succeeds
- [ ] "Process & Ingest" button appears
- [ ] Click button initiates processing
- [ ] Progress indicators show
- [ ] Success message appears: "Ingested X chunks successfully!"

### Test 5: Chat Functionality
1. After document upload, go to chat interface
2. Type a question: "What is in the document?"
3. Click send

**Checklist:**
- [ ] Message appears in chat
- [ ] "Generating answer..." spinner shows
- [ ] Response appears from assistant
- [ ] No error messages
- [ ] Response seems relevant to document

## Integration Testing

### Test 6: Full Pipeline
```bash
# Monitor all logs simultaneously
docker-compose logs -f embedding-service &
docker-compose logs -f streamlit-app &
docker-compose logs -f rag-service

# Then in browser:
# 1. Upload PDF
# 2. Watch logs for:
#    - Chunking progress
#    - Embedding service receiving requests
#    - Database inserts
#    - Weaviate inserts
```

**Checklist:**
- [ ] Chunking completes successfully
- [ ] Embedding service called 1+ times
- [ ] Embeddings returned with vectors
- [ ] Database receives insert commands
- [ ] Weaviate graph updated
- [ ] No errors in any service logs

### Test 7: Error Handling
```bash
# Stop embedding service
docker-compose stop embedding-service

# Try to embed
curl -X POST http://localhost:8001/embed \
  -H "Content-Type: application/json" \
  -d '{"text": "test"}'

# Expected: Connection refused or 503 Service Unavailable
```

**Checklist:**
- [ ] Error handled gracefully
- [ ] No crash or cascade failures
- [ ] Can restart service
- [ ] Recovery is automatic

### Test 8: Service Recovery
```bash
# Restart embedding service
docker-compose restart embedding-service

# Wait 30 seconds for startup
sleep 30

# Verify it's healthy
curl http://localhost:8001/health

# Try embedding again
curl -X POST http://localhost:8001/embed \
  -H "Content-Type: application/json" \
  -d '{"text": "test"}'
```

**Checklist:**
- [ ] Service restarts successfully
- [ ] Health check passes
- [ ] Embeddings work normally
- [ ] No data loss

## Performance Testing

### Test 9: Embedding Latency
```python
import time
import requests

url = "http://localhost:8001/embed"
text = "This is a test sentence for embedding performance."

times = []
for i in range(10):
    start = time.time()
    response = requests.post(url, json={"text": text})
    elapsed = time.time() - start
    times.append(elapsed * 1000)  # Convert to ms
    print(f"Request {i+1}: {elapsed*1000:.2f}ms")

avg = sum(times) / len(times)
print(f"\nAverage: {avg:.2f}ms")
print(f"Min: {min(times):.2f}ms")
print(f"Max: {max(times):.2f}ms")
```

**Expected Results:**
- [ ] Average < 200ms
- [ ] Min < 100ms (after warmup)
- [ ] Max < 500ms

### Test 10: Batch Throughput
```python
import time
import requests

url = "http://localhost:8001/embed-batch"
texts = ["Text sample"] * 100  # 100 texts

start = time.time()
response = requests.post(url, json={"texts": texts})
elapsed = time.time() - start

print(f"Embedded 100 texts in {elapsed:.2f}s")
print(f"Throughput: {100/elapsed:.1f} texts/second")
```

**Expected Results:**
- [ ] Total time < 5 seconds
- [ ] Throughput > 20 texts/second

### Test 11: Memory Usage
```bash
# While service is running
docker stats embedding-service --no-stream

# Expected output:
# CONTAINER ID   MEM USAGE / LIMIT
# ...            3-4GB / available memory

# Check for memory leaks over time
watch -n 1 'docker stats embedding-service --no-stream'
# Monitor for 5+ minutes - should be stable
```

**Checklist:**
- [ ] Memory usage stable (~3-4GB)
- [ ] No gradual memory increase
- [ ] No out-of-memory errors

## Cleanup & Documentation

### Test 12: Documentation Completeness
- [ ] README.md exists and is accurate
- [ ] QUICKSTART_MICROSERVICES.md is clear and complete
- [ ] EMBEDDING_SERVICE.md has all API documentation
- [ ] MIGRATION_GUIDE.md explains all changes
- [ ] ARCHITECTURE_DIAGRAMS.md shows system clearly
- [ ] IMPLEMENTATION_SUMMARY.md lists all changes
- [ ] Code is properly documented with docstrings

**Checklist:**
- [ ] All 6 documentation files exist
- [ ] No broken links in documentation
- [ ] Code examples are accurate and tested
- [ ] API examples are copy-pasteable

### Test 13: Cleanup Test
```bash
# Stop all services
docker-compose down

# Expected: All containers stopped

# Start again
docker-compose up -d

# Expected: Clean startup with no state issues
```

**Checklist:**
- [ ] Services stop cleanly
- [ ] No orphaned containers/volumes
- [ ] Restart is clean
- [ ] Data persists in volumes

## Regression Testing

### Test 14: Backward Compatibility
- [ ] Old app.py code still works (unchanged)
- [ ] Data ingestion produces same results
- [ ] Chat responses are comparable
- [ ] No breaking changes to APIs

**Checklist:**
- [ ] Upload same test PDF
- [ ] Compare embeddings (should be identical)
- [ ] Compare search results (should be identical)
- [ ] No migration needed for existing data

## Production Readiness

### Pre-Production Checklist
- [ ] All tests pass
- [ ] Performance within SLA
- [ ] Error handling tested
- [ ] Recovery tested
- [ ] Documentation complete
- [ ] Security reviewed
- [ ] Resource limits set appropriately

### Production Deployment
- [ ] Use production configuration
- [ ] Set resource limits in docker-compose
- [ ] Configure logging/monitoring
- [ ] Setup backup strategy
- [ ] Document troubleshooting steps
- [ ] Create runbook for on-call
- [ ] Plan for scaling strategy

### Monitoring (Post-Deployment)
- [ ] Health check dashboard
- [ ] Alert on service failures
- [ ] Track embedding latency
- [ ] Monitor resource usage
- [ ] Log aggregation setup
- [ ] Error rate tracking

## Sign-Off

- [ ] All tests passing
- [ ] Code review approved
- [ ] Documentation reviewed
- [ ] Performance acceptable
- [ ] Ready for production deployment

**Deployment Date:** ___________
**Deployed By:** ___________
**Reviewed By:** ___________

---

**Notes & Issues Found:**
```
[Record any issues found during testing and how they were resolved]




```

**Performance Metrics:**
```
Average Embedding Latency: _________ ms
Batch Throughput: _________ texts/second
Memory Usage: _________ GB
Service Uptime: _________%
```
