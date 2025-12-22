# setup_weaviate_schema.py

import weaviate
from weaviate.auth import AuthApiKey
import weaviate.classes as wvc
from weaviate.classes.config import (
    Configure, Property, DataType, ReferenceProperty  
)
from dotenv import load_dotenv
import os

# --- Load Config ---
load_dotenv()

DOCUMENT_COLLECTION = "Document"
CHUNK_COLLECTION = "DocChunk"

def create_client():
    print("Connecting to Weaviate to set up schema...")

    # --- THIS IS THE CORRECTED CONNECTION ---
    try:
        client = weaviate.connect_to_local()
        print("Weaviate connection successful.")
        return client
    
    except Exception as e:
        print(f"ERROR: Could not connect to weaviate: {e}")


def setup_weaviate_schema():
    """Ensures the Weaviate graph schema (Document -> DocChunk) exists."""
    client = create_client()

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
            vector_config=wvc.config.Configure.Vectors.self_provided()
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
            vector_config=wvc.config.Configure.Vectors.self_provided(),
            # Create the link *from* DocChunk *to* Document
            references=[
                ReferenceProperty(name="fromDocument", target_collection=DOCUMENT_COLLECTION)
            ]
        )
        print(f"'{CHUNK_COLLECTION}' collection created.")
    else:
        print(f"'{CHUNK_COLLECTION}' collection already exists.")

    if client:
        client.close()
        print("Weaviate connection closed.")

# --- Main execution block to run the setup ---
if __name__ == "__main__":
    # Run the schema setup
    setup_weaviate_schema()
    print("Schema setup complete.")