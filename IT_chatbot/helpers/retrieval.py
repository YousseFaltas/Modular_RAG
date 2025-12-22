"""
Retrieval module for querying Weaviate vector database.
Uses Weaviate v4 collections API for consistency with vector_db.py
"""

import os
from typing import List, Optional
import weaviate
from weaviate.classes.query import MetadataQuery
import logging

logger = logging.getLogger(__name__)

DOCUMENT_COLLECTION = os.getenv("WEAVIATE_DOCUMENT_COLLECTION", "IT_Chatbot_Document")
CHUNK_COLLECTION = os.getenv("WEAVIATE_CHUNK_COLLECTION", "DocChunk")


def create_client() -> Optional[weaviate.WeaviateClient]:
    """Create a Weaviate client using environment variables.

    Falls back to Docker service defaults if env vars are not provided.
    Returns None if connection fails.
    """
    try:
        http_host = os.getenv("WEAVIATE_HOST", "weaviate")
        http_port = int(os.getenv("WEAVIATE_PORT", 8080))
        grpc_host = os.getenv("WEAVIATE_HOST", "weaviate")
        grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", 50051))

        client = weaviate.connect_to_custom(
            http_host=http_host,
            http_port=http_port,
            grpc_host=grpc_host,
            grpc_port=grpc_port
        )
        # quick health check
        if not client.is_ready():
            logger.warning("Weaviate client not ready")
            return None
        return client
    except Exception as e:
        logger.error(f"❌ Weaviate connection error: {e}")
        return None


def get_rag_context(search_query: str, lang: str = "en", top_k: int = 7) -> str:
    """Query Weaviate for the most relevant chunks and return a combined context string.

    Uses the Weaviate v4 collections API with hybrid search (text + vector).

    Args:
        search_query: The user-search query (already optimized).
        lang: Language code (not used currently, reserved for future filters).
        top_k: Number of chunks to retrieve.

    Returns:
        A single string containing concatenated chunk texts (suitable for prompt context).
    """
    client = create_client()
    if not client:
        return ""  # Empty context on failure

    try:
        # Get the chunk collection using v4 API
        chunk_collection = client.collections.get(CHUNK_COLLECTION)
        
        # Try hybrid search first (combines BM25 text search + vector similarity)
        try:
            results = chunk_collection.query.hybrid(
                query=search_query,
                alpha=0.5,  # Balance between keyword (0) and vector (1) search
                limit=top_k,
                return_metadata=MetadataQuery(score=True)
            )
        except Exception as hybrid_error:
            logger.warning(f"Hybrid search failed, falling back to near_text: {hybrid_error}")
            # Fallback to pure vector search if hybrid is not available
            try:
                results = chunk_collection.query.near_text(
                    query=search_query,
                    limit=top_k,
                    return_metadata=MetadataQuery(distance=True)
                )
            except Exception as vector_error:
                logger.error(f"Vector search also failed: {vector_error}")
                return ""

        # Process results
        items = []
        for obj in results.objects:
            props = obj.properties
            text = props.get("text") or ""
            title = props.get("title") or ""
            filename = props.get("filename") or ""
            chunk_index = props.get("chunk_index")
            
            # Build context prefix for traceability
            prefix = ""
            if filename or title or chunk_index is not None:
                prefix = f"[{filename} | {title} | chunk:{chunk_index}]\n"
            
            items.append(prefix + text)

        # Concatenate with separators
        context = "\n\n---\n\n".join(items)
        return context

    except Exception as e:
        logger.error(f"Error during retrieval: {e}")
        return ""
    finally:
        try:
            client.close()
        except Exception:
            pass


if __name__ == "__main__":
    # Simple sanity check
    logging.basicConfig(level=logging.INFO)
    c = create_client()
    if c:
        print("✅ Weaviate client ready")
        try:
            collections = c.collections.list_all()
            print(f"Available collections: {list(collections.keys())}")
        except Exception as e:
            print(f"Could not list collections: {e}")
        try:
            c.close()
        except Exception:
            pass
    else:
        print("❌ Failed to connect to Weaviate")