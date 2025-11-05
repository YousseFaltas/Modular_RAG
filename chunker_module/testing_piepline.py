import os
import uuid
import json  # <-- ADD THIS IMPORT
from typing import List, Dict, Any

# Your helper functions are now imported
from helpers.DB import ingest_to_postgres
from helpers.weaviate import ingest_to_weaviate

# DOCUMENT EXTRACTION
from docling.document_converter import DocumentConverter
# CHUNKING
from docling.chunking import HybridChunker
from dotenv import load_dotenv
from openai import OpenAI
from utils.tokenizer import TikTokenWrapper

# --- 1. SETUP ---
load_dotenv()
converter = DocumentConverter()

EMBEDDING_MODEL = "text-embedding-3-large"
PDF_PATH = "/home/youssef/github/Modular_RAG/PDFs/1H2025_Earnings_Release.pdf"

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Load custom tokenizer
tokenizer = TikTokenWrapper(model_name=EMBEDDING_MODEL)
MAX_TOKENS = 8191

# --- 2. DOCUMENT CONVERSION & CHUNKING ---

print(f"Starting conversion for: {PDF_PATH}")
result = converter.convert(PDF_PATH)
document = result.document
print("Document conversion complete.")

chunker = HybridChunker(
    tokenizer=tokenizer,
    max_tokens=MAX_TOKENS,
    merge_peers=True,
)

chunk_iter = chunker.chunk(dl_doc=result.document)
chunks = list(chunk_iter)
print(f"Document chunking complete. Found {len(chunks)} chunks.")


# --- 3. DATA PROCESSING & EMBEDDING (REPLACED) ---

def process_and_embed_chunks(
    docling_chunks: List[Any], 
    openai_client: OpenAI, 
    model: str
) -> Dict[str, Any]:
    """
    Processes chunks and returns a dictionary with:
    1. A single 'document' object.
    2. A list of 'chunks' objects.
    """
    processed_chunks = []
    texts_to_embed = []
    
    # We only need the *first* chunk to get the parent doc info
    if not docling_chunks:
        return {"document": None, "chunks": []}
        
    first_meta = docling_chunks[0].meta
    doc_hash = str(first_meta.origin.binary_hash)
    
    # Use the hash to create a stable UUID for the parent Document
    parent_doc_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, doc_hash)

    parent_document_data = {
        "doc_hash": doc_hash,
        "filename": first_meta.origin.filename,
        "mimetype": first_meta.origin.mimetype,
        "uuid": parent_doc_uuid
    }
    
    print(f"Processing {len(docling_chunks)} chunks for document: {first_meta.origin.filename}")

    for i, chunk in enumerate(docling_chunks):
        chunk_id = uuid.uuid4() # This is the Postgres Primary Key
        meta = chunk.meta
        
        # --- Extract Rich Metadata ---
        page_nos = list(sorted(set(
            prov.page_no for item in meta.doc_items for prov in item.prov
        )))
        
        title = meta.headings[0] if meta.headings else None
        
        content_types = list(set(
            item.label.name.lower() for item in meta.doc_items
        ))
        
        # Store bboxes as a list of JSON strings
        bounding_boxes = [
            json.dumps(prov.bbox.to_dict())
            for item in meta.doc_items for prov in item.prov
        ]
        
        processed_chunks.append({
            "chunk_id": chunk_id,
            "doc_hash": doc_hash, # Foreign key for Postgres
            "chunk_index": i,
            "text": chunk.text,
            "filename": meta.origin.filename,
            "page_numbers": page_nos,
            "title": title,
            "content_types": content_types,
            "bounding_boxes": bounding_boxes,
            "parent_doc_uuid": parent_doc_uuid # The link for Weaviate
        })
        texts_to_embed.append(chunk.text)

    # --- Batch Embedding ---
    print(f"Generating embeddings for {len(texts_to_embed)} chunks...")
    try:
        response = openai_client.embeddings.create(
            input=texts_to_embed,
            model=model
        )
        embeddings = [e.embedding for e in response.data]
        
        for i, data in enumerate(processed_chunks):
            data["vector"] = embeddings[i]
            
        print("Embeddings generated successfully.")
        
        return {
            "document": parent_document_data,
            "chunks": processed_chunks
        }

    except Exception as e:
        print(f"ERROR: Failed to generate embeddings: {e}")
        return {"document": None, "chunks": []}


# --- 4. EXECUTION (UPDATED) ---

def main():
    if not chunks:
        print("No chunks were generated. Exiting.")
        return

    # 1. Process docling chunks and get embeddings
    ingestion_data = process_and_embed_chunks(
        docling_chunks=chunks,
        openai_client=client,
        model=EMBEDDING_MODEL
    )
    
    if not ingestion_data["chunks"]:
        print("Data processing or embedding failed. Exiting.")
        return

    # 2. Ingest into databases
    # Pass only the list of chunks to Postgres
    ingest_to_postgres(ingestion_data["chunks"]) 
    
    # Pass the full dictionary to Weaviate to build the graph
    ingest_to_weaviate(ingestion_data)
    
    print("\n--- Ingestion Complete ---")
    print(f"Successfully processed and ingested {len(ingestion_data['chunks'])} chunks.")

if __name__ == "__main__":
    main()