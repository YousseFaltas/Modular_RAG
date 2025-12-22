import os
from typing import List
import weaviate


DOCUMENT_COLLECTION = os.getenv("WEAVIATE_DOCUMENT_COLLECTION", "IT_Chatbot_Document")
CHUNK_COLLECTION = os.getenv("WEAVIATE_CHUNK_COLLECTION", "DocChunk")


def create_client():
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
        _ = client.is_ready()
        return client
    except Exception as e:
        print(f"❌ Weaviate connection error: {e}")
        return None


def get_rag_context(search_query: str, lang: str = "en", top_k: int = 7) -> str:
    """Query Weaviate for the most relevant chunks and return a combined context string.

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
        # Prefer hybrid search (text + vector) when available in Weaviate
        try:
            query_builder = client.query.get(CHUNK_COLLECTION, ["text", "title", "filename", "chunk_index"]).with_limit(top_k)
            # try hybrid (text+vector) search first
            try:
                query = query_builder.with_hybrid({"query": search_query, "alpha": 0.5})
                result = query.do()
            except Exception:
                # fallback to near_text vector search
                query = query_builder.with_near_text({"concepts": [search_query]})
                result = query.do()
        except Exception:
            # Generic fallback for client variations
            result = client.query.get(CHUNK_COLLECTION, ["text", "title", "filename", "chunk_index"]).with_near_text({"concepts": [search_query]}).with_limit(top_k).do()

        items = []
        hits = result.get("data", {}).get("Get", {}).get(CHUNK_COLLECTION, [])
        for h in hits:
            # each h expected to be a dict with properties
            text = h.get("text") or ""
            title = h.get("title") or ""
            filename = h.get("filename") or ""
            chunk_index = h.get("chunk_index")
            prefix = f"[{filename} | {title} | chunk:{chunk_index}]\n" if filename or title or chunk_index is not None else ""
            items.append(prefix + text)

        # Concatenate with separators
        context = "\n\n---\n\n".join(items)
        return context
    finally:
        try:
            client.close()
        except Exception:
            pass


if __name__ == "__main__":
    # simple sanity check
    c = create_client()
    if c:
        print("Weaviate client ready")
        try:
            print("Available collections (may vary depending on client):")
            print(c.schema.get())
        except Exception:
            pass
        try:
            c.close()
        except Exception:
            pass