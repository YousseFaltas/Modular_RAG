"""
Embedding Service API - Microservice for handling embeddings
Separates embedding logic into its own service to be deployed independently
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
import torch
from dotenv import load_dotenv
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Embedding Service API", version="1.0.0")

# Initialize embedding model
EMBEDDING_MODEL = "BAAI/bge-m3"
embedding_model = None

@app.on_event("startup")
async def startup_event():
    """Load embedding model on startup"""
    global embedding_model
    try:
        logger.info(f"Loading embedding model: '{EMBEDDING_MODEL}'...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        embedding_model = SentenceTransformer(EMBEDDING_MODEL, device=device)
        logger.info(f"Embedding model loaded successfully on device: {device}")
    except Exception as e:
        logger.error(f"ERROR: Could not load SentenceTransformer model: {e}")
        raise RuntimeError(f"Failed to load embedding model: {e}")

# ========================
# Request/Response Models
# ========================

class EmbedRequest(BaseModel):
    """Request model for embedding a single text"""
    text: str

class BatchEmbedRequest(BaseModel):
    """Request model for batch embedding texts"""
    texts: List[str]

class EmbedResponse(BaseModel):
    """Response model for single embedding"""
    text: str
    embedding: List[float]

class BatchEmbedResponse(BaseModel):
    """Response model for batch embeddings"""
    embeddings: List[Dict[str, Any]]

class EmbedChunksRequest(BaseModel):
    """Request model for embedding processed chunks"""
    chunks: List[Dict[str, Any]]

class EmbedChunksResponse(BaseModel):
    """Response model for chunk embeddings"""
    chunks: List[Dict[str, Any]]

# ========================
# Endpoints
# ========================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "model": EMBEDDING_MODEL}

@app.post("/embed", response_model=EmbedResponse)
async def embed_single(request: EmbedRequest):
    """
    Embed a single text string
    
    Args:
        request: EmbedRequest with text to embed
        
    Returns:
        EmbedResponse with text and embedding vector
    """
    if embedding_model is None:
        raise HTTPException(status_code=503, detail="Embedding model not loaded")
    
    try:
        vector = embedding_model.encode(request.text, normalize_embeddings=True).tolist()
        return EmbedResponse(text=request.text, embedding=vector)
    except Exception as e:
        logger.error(f"Error embedding text: {e}")
        raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}")

@app.post("/embed-batch", response_model=BatchEmbedResponse)
async def embed_batch(request: BatchEmbedRequest):
    """
    Embed multiple texts in batch
    
    Args:
        request: BatchEmbedRequest with list of texts to embed
        
    Returns:
        BatchEmbedResponse with list of embeddings
    """
    if embedding_model is None:
        raise HTTPException(status_code=503, detail="Embedding model not loaded")
    
    if not request.texts:
        raise HTTPException(status_code=400, detail="No texts provided")
    
    try:
        embeddings = []
        vectors = embedding_model.encode(request.texts, normalize_embeddings=True)
        
        for text, vector in zip(request.texts, vectors):
            embeddings.append({
                "text": text,
                "embedding": vector.tolist()
            })
        
        return BatchEmbedResponse(embeddings=embeddings)
    except Exception as e:
        logger.error(f"Error embedding batch: {e}")
        raise HTTPException(status_code=500, detail=f"Batch embedding failed: {str(e)}")

@app.post("/embed-chunks", response_model=EmbedChunksResponse)
async def embed_chunks(request: EmbedChunksRequest):
    """
    Embed chunks data structure
    Adds 'vector' field to each chunk with its embedding
    
    Args:
        request: EmbedChunksRequest with list of chunk dictionaries
        
    Returns:
        EmbedChunksResponse with chunks containing embeddings
    """
    if embedding_model is None:
        raise HTTPException(status_code=503, detail="Embedding model not loaded")
    
    if not request.chunks:
        raise HTTPException(status_code=400, detail="No chunks provided")
    
    try:
        # Extract texts from chunks
        texts_to_embed = [chunk.get("text", "") for chunk in request.chunks]
        
        # Generate embeddings
        vectors = embedding_model.encode(texts_to_embed, normalize_embeddings=True)
        
        # Add embeddings to chunks
        for i, chunk in enumerate(request.chunks):
            chunk["vector"] = vectors[i].tolist()
        
        logger.info(f"Successfully embedded {len(request.chunks)} chunks")
        return EmbedChunksResponse(chunks=request.chunks)
    except Exception as e:
        logger.error(f"Error embedding chunks: {e}")
        raise HTTPException(status_code=500, detail=f"Chunk embedding failed: {str(e)}")

@app.get("/model-info")
async def get_model_info():
    """Get information about the loaded embedding model"""
    if embedding_model is None:
        raise HTTPException(status_code=503, detail="Embedding model not loaded")
    
    return {
        "model_name": EMBEDDING_MODEL,
        "embedding_dim": embedding_model.get_sentence_embedding_dimension(),
        "device": embedding_model.device,
        "max_seq_length": embedding_model.get_max_seq_length()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
