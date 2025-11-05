import weaviate
import json # <-- ADD THIS IMPORT
import uuid
from weaviate.auth import AuthApiKey
from weaviate.classes.config import (
    Configure, Property, DataType, ReferenceProperty
)
from typing import List, Dict, Any
from dotenv import load_dotenv
import os

load_dotenv()
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY", "your-weaviate-api-key")

# Define our new collection names
DOCUMENT_COLLECTION = "Document"
CHUNK_COLLECTION = "DocChunk"

# --- Connect to Weaviate ---
print("Connecting to Weaviate...")
try:
    weaviate_client = weaviate.connect_to_custom(
        http_host=WEAVIATE_URL.replace("http://", ""),
        http_secure=WEAVIATE_URL.startswith("https"),
        grpc_host=WEAVIATE_URL.replace("http://", "").split(":")[0],
        grpc_secure=WEAVIATE_URL.startswith("https"),
        auth_credentials=AuthApiKey(WEAVIATE_API_KEY),
    )
    weaviate_client.is_ready()
    print("Weaviate connection successful.")
except Exception as e:
    print(f"ERROR: Could not connect to Weaviate: {e}")
    

# --- 2. SCHEMA SETUP (REPLACED) ---

def setup_weaviate_schema(client: weaviate.WeaviateClient):
    """Ensures the Weaviate graph schema (Document -> DocChunk) exists."""
    
    # 1. Create Parent "Document" class
    if not client.collections.exists(DOCUMENT_COLLECTION):
        print(f"Creating Weaviate collection '{DOCUMENT_COLLECTION}'...")
        client.collections.create(
            name=DOCUMENT_COLLECTION,
            properties=[
                Property(name="doc_hash", data_type=DataType.TEXT),
                Property(name="filename", data_type=DataType.TEXT),
                Property(name="mimetype", data_type=DataType.TEXT),
            ],
            vectorizer_config=Configure.None_(),
        )
        print(f"'{DOCUMENT_COLLECTION}' collection created.")
    else:
        print(f"'{DOCUMENT_COLLECTION}' collection already exists.")

    # 2. Create "DocChunk" class
    if not client.collections.exists(CHUNK_COLLECTION):
        print(f"Creating Weaviate collection '{CHUNK_COLLECTION}'...")
        client.collections.create(
            name=CHUNK_COLLECTION,
            properties=[
                Property(name="postgres_id", data_type=DataType.UUID),
                Property(name="chunk_index", data_type=DataType.NUMBER),
                Property(name="text", data_type=DataType.TEXT),
                Property(name="title", data_type=DataType.TEXT),
                Property(name="page_numbers", data_type=DataType.NUMBER_ARRAY),
                Property(name="content_types", data_type=DataType.TEXT_ARRAY),
                Property(name="bounding_boxes", data_type=DataType.TEXT_ARRAY),
            ],
            vectorizer_config=Configure.None_(),
            # Create the link *from* DocChunk *to* Document
            references=[
                ReferenceProperty(name="fromDocument", target_collection=DOCUMENT_COLLECTION)
            ]
        )
        print(f"'{CHUNK_COLLECTION}' collection created.")
    else:
        print(f"'{CHUNK_COLLECTION}' collection already exists.")


# --- Run Schema Setups ---
setup_weaviate_schema(weaviate_client)


# --- 4. BATCH INGESTION (REPLACED) ---

def ingest_to_weaviate(
    data: Dict[str, Any], # <-- Accepts the full dictionary
    client: weaviate.WeaviateClient = weaviate_client
):
    """
    Batch-inserts the parent Document and all DocChunks into Weaviate.
    """
    document_data = data.get("document")
    chunk_data_list = data.get("chunks", [])

    if not document_data or not chunk_data_list:
        print("No document or chunk data found to ingest into Weaviate.")
        return

    # --- 1. Add the Parent Document (Idempotent) ---
    print(f"Ingesting parent document: {document_data['filename']}")
    try:
        # Weaviate's `insert` is idempotent if `uuid` is provided
        client.data_object.create(
            class_name=DOCUMENT_COLLECTION,
            data_object={
                "doc_hash": document_data["doc_hash"],
                "filename": document_data["filename"],
                "mimetype": document_data["mimetype"],
            },
            uuid=document_data["uuid"],
        )
    except Exception as e:
        # This can happen if the object already exists, which is fine
        print(f"Note: Could not create parent document (may already exist): {e}")


    # --- 2. Batch Insert Chunks ---
    print(f"Batch inserting {len(chunk_data_list)} vectors into Weaviate...")
    try:
        with client.batch.dynamic() as batch:
            for chunk_data in chunk_data_list:
                
                properties = {
                    "postgres_id": chunk_data["chunk_id"],
                    "chunk_index": chunk_data["chunk_index"],
                    "text": chunk_data["text"],
                    "title": chunk_data["title"],
                    "page_numbers": chunk_data["page_numbers"],
                    "content_types": chunk_data["content_types"],
                    "bounding_boxes": chunk_data["bounding_boxes"],
                    
                    # This is the "link" to the parent Document
                    "fromDocument": [document_data["uuid"]] # Link using the parent's UUID
                }
                
                batch.add_object(
                    collection=CHUNK_COLLECTION,
                    properties=properties,
                    vector=chunk_data["vector"],
                    # Create a stable UUID for the chunk object itself
                    uuid=uuid.uuid5(uuid.NAMESPACE_DNS, str(chunk_data["chunk_id"]))
                )
        
        if client.batch.failed_objects:
            print(f"WARNING: {len(client.batch.failed_objects)} objects failed to import into Weaviate.")
        
        print("Weaviate batch insert successful.")
            
    except Exception as e:
        print(f"ERROR: Weaviate batch insert failed: {e}")
    finally:
        # Always close the Weaviate client at the end of the script
        if 'weaviate_client' in locals() and client.is_connected():
            client.close()
            print("Weaviate connection closed.")