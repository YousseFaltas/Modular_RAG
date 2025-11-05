import weaviate
import psycopg
import uuid
from psycopg.rows import dict_row
from weaviate.auth import AuthApiKey
from weaviate.classes.config import Configure, Property, DataType
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer # <-- ADD THIS

# --- 1. CONFIGURATION & CLIENT INITIALIZATION ---
# (Assumes your tokenizer and 'chunks' list are already loaded)

# --- Database & Weaviate Settings (Use Environment Variables!) ---
# Use the Hugging Face model name for BGE M3
EMBEDDING_MODEL = "BAAI/bge-m3" 
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY", "your-weaviate-api-key")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/rag_db")

# Weaviate Collection (Class) Name
WEAVIATE_COLLECTION = "DocChunk"

# --- Load the local embedding model ---
# This will download the model the first time it's run
print(f"Loading embedding model: '{EMBEDDING_MODEL}'...")
try:
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    print("Embedding model loaded successfully.")
except Exception as e:
    print(f"ERROR: Could not load SentenceTransformer model: {e}")
    # In a real app, you'd exit here
    
# --- Connect to Weaviate ---
print("Connecting to Weaviate...")
try:
    weaviate_client = weaviate.connect_to_custom(
        http_host=WEAVIATE_URL.replace("http://", ""),  # Remove protocol for host
        http_secure=WEAVIATE_URL.startswith("https"),
        grpc_host=WEAVIATE_URL.replace("http://", "").split(":")[0], # Assumes gRPC on default port or same host
        grpc_secure=WEAVIATE_URL.startswith("https"),
        auth_credentials=AuthApiKey(WEAVIATE_API_KEY),
    )
    weaviate_client.is_ready()
    print("Weaviate connection successful.")
except Exception as e:
    print(f"ERROR: Could not connect to Weaviate: {e}")
    
# --- Connect to PostgreSQL ---
print("Connecting to PostgreSQL...")
try:
    # Use a context manager for robust connection handling
    with psycopg.connect(DATABASE_URL) as pg_conn:
        with pg_conn.cursor() as cur:
            cur.execute("SELECT 1")
            print("PostgreSQL connection successful.")
except Exception as e:
    print(f"ERROR: Could not connect to PostgreSQL: {e}")


# --- 2. SCHEMA SETUP (IDEMPOTENT) ---

def setup_weaviate_schema(client: weaviate.WeaviateClient, collection_name: str):
    """Ensures the Weaviate collection exists with the correct schema."""
    if client.collections.exists(collection_name):
        print(f"Weaviate collection '{collection_name}' already exists.")
        return
    
    print(f"Creating Weaviate collection '{collection_name}'...")
    client.collections.create(
        name=collection_name,
        properties=[
            Property(name="postgres_id", data_type=DataType.TEXT),
        ],
        vectorizer_config=Configure.None_(),
    )
    print("Weaviate collection created.")

def setup_postgres_schema(conn_string: str):
    """Ensures the PostgreSQL 'chunks' table exists."""
    with psycopg.connect(conn_string) as conn:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id UUID PRIMARY KEY,
                filename TEXT,
                page_numbers JSONB,
                title TEXT,
                text TEXT NOT NULL,
                created_at TIMESTZ DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_chunks_filename ON chunks (filename);
            """)
            conn.commit()
    print("PostgreSQL 'chunks' table is ready.")

# --- Run Schema Setups ---
setup_weaviate_schema(weaviate_client, WEAVIATE_COLLECTION)
setup_postgres_schema(DATABASE_URL)


# --- 3. DATA PROCESSING & EMBEDDING (MODIFIED) ---

def process_and_embed_chunks(
    docling_chunks: List[Any], 
    model: SentenceTransformer
) -> List[Dict[str, Any]]:
    """
    Processes docling chunks, generates UUIDs, and fetches embeddings
    locally using the provided SentenceTransformer model.
    """
    print(f"Processing {len(docling_chunks)} chunks for ingestion...")
    processed_data = []
    texts_to_embed = []

    for chunk in docling_chunks:
        chunk_id = uuid.uuid4()
        
        page_nos = [
            page_no
            for page_no in sorted(
                set(
                    prov.page_no
                    for item in chunk.meta.doc_items
                    for prov in item.prov
                )
            )
        ] or None
        
        title = chunk.meta.headings[0] if chunk.meta.headings else None
        filename = chunk.meta.origin.filename if chunk.meta.origin else None
        
        processed_data.append({
            "chunk_id": chunk_id,
            "text": chunk.text,
            "filename": filename,
            "page_numbers": page_nos,
            "title": title,
        })
        texts_to_embed.append(chunk.text)

    # --- Batch Embedding (MODIFIED) ---
    print(f"Generating embeddings for {len(texts_to_embed)} chunks locally...")
    try:
        # Call the local model's .encode() method
        embeddings = model.encode(
            texts_to_embed,
            batch_size=32, # Adjust batch size based on your VRAM
            show_progress_bar=True
        )
        
        # Add the embeddings back to our processed data
        for i, data in enumerate(processed_data):
            # Convert numpy array to list for JSON/DB compatibility
            data["vector"] = embeddings[i].tolist() 
            
        print("Embeddings generated successfully.")
        return processed_data

    except Exception as e:
        print(f"ERROR: Failed to generate embeddings: {e}")
        return []

# --- 4. BATCH INGESTION (Unchanged) ---

def ingest_to_postgres(data: List[Dict[str, Any]], conn_string: str):
    """Batch-inserts structured chunk data into PostgreSQL."""
    print(f"Batch inserting {len(data)} records into PostgreSQL...")
    
    insert_data = [
        (
            d["chunk_id"],
            d["filename"],
            d["page_numbers"],
            d["title"],
            d["text"]
        )
        for d in data
    ]
    
    try:
        with psycopg.connect(conn_string) as conn:
            with conn.cursor() as cur:
                cur.executemany("""
                INSERT INTO chunks (chunk_id, filename, page_numbers, title, text)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (chunk_id) DO NOTHING;
                """, insert_data)
                conn.commit()
        print("PostgreSQL batch insert successful.")
    except Exception as e:
        print(f"ERROR: PostgreSQL batch insert failed: {e}")

def ingest_to_weaviate(
    data: List[Dict[str, Any]], 
    client: weaviate.WeaviateClient, 
    collection_name: str
):
    """Batch-inserts vectors and their linking IDs into Weaviate."""
    print(f"Batch inserting {len(data)} vectors into Weaviate...")
    
    try:
        with client.batch.dynamic() as batch:
            for d in data:
                properties = {
                    "postgres_id": str(d["chunk_id"])
                }
                
                batch.add_object(
                    collection=collection_name,
                    properties=properties,
                    vector=d["vector"],
                    uuid=uuid.uuid5(uuid.NAMESPACE_DNS, str(d["chunk_id"]))
                )
        
        if client.batch.failed_objects:
            print(f"WARNING: {len(client.batch.failed_objects)} objects failed to import into Weaviate.")
        
        print("Weaviate batch insert successful.")
            
    except Exception as e:
        print(f"ERROR: Weaviate batch insert failed: {e}")

# --- 5. EXECUTION (MODIFIED) ---

def main():
    if not chunks:
        print("No chunks were generated. Exiting.")
        return

    # 1. Process docling chunks and get embeddings
    ingestion_data = process_and_embed_chunks(
        docling_chunks=chunks,
        model=embedding_model  # Pass the loaded SBERT model
    )
    
    if not ingestion_data:
        print("Data processing or embedding failed. Exiting.")
        return

    # 2. Ingest into databases
    ingest_to_postgres(ingestion_data, DATABASE_URL)
    ingest_to_weaviate(ingestion_data, weaviate_client, WEAVIATE_COLLECTION)
    
    print("\n--- Ingestion Complete ---")
    print(f"Successfully processed and ingested {len(ingestion_data)} chunks.")

try:
    main()
finally:
    # Always close the Weaviate client
    if 'weaviate_client' in locals() and weaviate_client.is_connected():
        weaviate_client.close()
        print("Weaviate connection closed.")