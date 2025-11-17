import uuid
from typing import List, Dict, Any

# # Your helper functions are now imported
from helpers.DB import ingest_to_postgres
from helpers.vector_db import insert_to_weaviate

# CHUNKING
from docling.chunking import HybridChunker
from dotenv import load_dotenv
from openai import OpenAI
import os
from pathlib import Path

from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
)
from docling.datamodel.settings import settings
from docling.document_converter import DocumentConverter, PdfFormatOption
from sentence_transformers import SentenceTransformer # <-- ADD THIS
import torch

# --- 1. SETUP ---
load_dotenv()

accelerator_options = AcceleratorOptions(
    num_threads=8, device=AcceleratorDevice.CPU
)
pipeline_options = PdfPipelineOptions()
pipeline_options.accelerator_options = accelerator_options
pipeline_options.do_ocr = True
pipeline_options.do_table_structure = True
pipeline_options.table_structure_options.do_cell_matching = True

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(
            pipeline_options=pipeline_options,
        )
    }
)
EMBEDDING_MODEL = "BAAI/bge-m3" 

# --- Load the local embedding model ---
# This will download the model the first time it's run
print(f"Loading embedding model: '{EMBEDDING_MODEL}'...")
try:
    device = "cpu" if torch.cuda.is_available() else "cpu"
    embedding_model = SentenceTransformer("BAAI/bge-m3", device=device)
    print("Embedding model loaded successfully.")
except Exception as e:
    print(f"ERROR: Could not load SentenceTransformer model: {e}")
    # In a real app, you'd exit here
    

PDF_PATH = "/home/youssef/github/Modular_RAG/PDFs/1H2025_Earnings_Release.pdf"

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- 2. DOCUMENT CONVERSION & CHUNKING ---
def data_extractions(pdf_path:str) -> any:
    print(f"Starting conversion for: {pdf_path}")
    result = converter.convert(pdf_path)
    print("Document conversion complete.")

    chunker = HybridChunker(
        tokenizer=embedding_model.tokenizer,           # <-- 2. Use the model's tokenizer
        max_tokens=embedding_model.max_seq_length,   # <-- 3. Use the model's max length
        merge_peers=True,
    )

    chunk_iter = chunker.chunk(dl_doc=result.document)
    chunks = list(chunk_iter)
    print(f"Document chunking complete. Found {len(chunks)} chunks.")
    return chunks


# --- 3. DATA PROCESSING & EMBEDDING  ---
def process_and_embed_chunks(docling_chunks: List[Any]) -> Dict[str, Any]:
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
            prov.bbox.model_dump_json()  # Or prov.bbox.json() for Pydantic V1
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
        # Call the local model's .encode() method
        for i, data in enumerate(processed_chunks):
            vector = embedding_model.encode(data['text'], normalize_embeddings=True).tolist()
            data["vector"] = vector
            
        print("Embeddings generated successfully.")
        return {"document": parent_document_data, "chunks": processed_chunks}

    except Exception as e:
        print(f"ERROR: Failed to generate embeddings: {e}")
       # --- 3. FIX RETURN VALUE ---
        return {"document": None, "chunks": []}


# --- 4. EXECUTION (UPDATED) ---

def main():
    chunks = data_extractions(PDF_PATH)
    
    if not chunks:
        print("No chunks were generated. Exiting.")
        return

    # 1. Process docling chunks and get embeddings
    ingestion_data = process_and_embed_chunks(docling_chunks=chunks)
    
    if not ingestion_data["chunks"]:
        print("Data processing or embedding failed. Exiting.")
        return

    # 2. Ingest into databases
    # Pass only the list of chunks to Postgres
    # ingest_to_postgres(ingestion_data["chunks"]) 
    
    # # Pass the full dictionary to Weaviate to build the graph
    insert_to_weaviate(ingestion_data)
    
    # print("\n--- Ingestion Complete ---")
    # print(f"Successfully processed and ingested {len(ingestion_data['chunks'])} chunks.")

if __name__ == "__main__":
    main()