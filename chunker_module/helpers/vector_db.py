import weaviate
from weaviate.classes.config import (
    Configure,
    Property,
    DataType,
    ReferenceProperty,
)
# --- ADD THIS IMPORT ---
import weaviate.classes as wvc

from weaviate.classes.data import DataObject
from weaviate.util import generate_uuid5
from typing import List, Dict, Any

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


def define_schema(client: weaviate.WeaviateClient):
    """
    Creates the 'Document' and 'DocChunk' collections in Weaviate.
    """
    if not client.collections.exists(DOCUMENT_COLLECTION):
        print("Creating 'Document' collection...")
        client.collections.create(
            name="Document",
            properties=[
                Property(
                    name="doc_hash", 
                    data_type=DataType.TEXT, 
                    tokenization="keyword",
                    index_filterable= True,
                    ),
                Property(
                    name="filename", 
                    data_type=DataType.TEXT,
                    index_filterable= True,
                    index_searchable=True
                    ),
                Property(
                    name="mimetype",
                    data_type=DataType.TEXT, 
                    tokenization="keyword"
                    )
            ],
            # This collection won't be vectorized, it's just a metadata node
            vector_config=wvc.config.Configure.Vectors.self_provided()
        )
    
    if not client.collections.exists(CHUNK_COLLECTION):
        print("Creating 'DocChunk' collection...")
        client.collections.create(
            name="DocChunk",
            properties=[
                # --- Content & Metadata ---
                Property(
                    name="text", 
                    data_type=DataType.TEXT,
                    index_searchable=True
                    ),
                Property(
                    name="chunk_index", 
                    data_type=DataType.INT,
                    index_filterable=True,
                    ),
                Property(
                    name="filename", 
                    data_type=DataType.TEXT,
                    index_filterable=True,
                    index_searchable=True
                    ),
                Property(
                    name="title", 
                    data_type=DataType.TEXT, 
                    skip_vectorization=True,
                    index_filterable=True,
                    index_searchable=True
                    ),
                
                # --- List/Array Properties ---
                Property(
                    name="page_numbers", 
                    data_type=DataType.INT_ARRAY,
                    index_filterable=True
                    ),
                Property(
                    name="content_types", 
                    data_type=DataType.TEXT_ARRAY, 
                    tokenization="keyword"
                    ),
                Property(name="bounding_boxes", data_type=DataType.TEXT_ARRAY), # Storing as JSON strings
                
                # --- Foreign Key (for Postgres) ---
                Property(name="chunk_id", data_type=DataType.UUID, skip_vectorization=True), 
            ],
            # --- Graph Link ---
            references=[
                ReferenceProperty(name="fromDocument", target_collection="Document")
            ],
            # --- Vector Config ---
            # Tell Weaviate we are providing our own vectors
            vector_config=wvc.config.Configure.Vectors.self_provided(),
            vector_index_config=Configure.VectorIndex.hnsw(
                distance_metric=weaviate.classes.config.VectorDistances.COSINE
            )
        )
    print("Schema is ready.")


def insert_to_weaviate(ingestion_data: Dict[str, Any]):
    """
    Ingests the parent document and its chunks into Weaviate (v4 syntax),
    creating a graph link between them.
    """
    client = None
    try:
        # --- 1. Connect and ensure schema ---
        client = weaviate.connect_to_local() 
        define_schema(client) 

        parent_doc_data = ingestion_data.get("document")
        chunks_data = ingestion_data.get("chunks")

        if not parent_doc_data or not chunks_data:
            print("ERROR: Ingestion data is missing 'document' or 'chunks'.")
            return

        parent_doc_uuid = parent_doc_data["uuid"]

        # --- 3. Insert Parent Document Node (v4 syntax) ---
        print(f"Ingesting 'Document' node: {parent_doc_data['filename']}")
        document_collection = client.collections.get("Document")
        
        try:
            # v4 syntax for inserting a single object
            document_collection.data.insert(
                properties={
                    "doc_hash": parent_doc_data["doc_hash"],
                    "filename": parent_doc_data["filename"],
                    "mimetype": parent_doc_data["mimetype"],
                },
                uuid=parent_doc_uuid
            )
        except Exception as e:
            if "already exists" in str(e):
                print(f"Document node {parent_doc_uuid} already exists. Skipping.")
            else:
                raise e

        # --- 4. Prepare & Batch Insert Chunks (v4 syntax) ---
        print(f"Preparing {len(chunks_data)} chunks for batch ingestion...")
        
        chunk_collection = client.collections.get("DocChunk")
        
        # v4 syntax for batch writing
        with chunk_collection.batch.fixed_size(batch_size=100) as batch:
            for chunk_props in chunks_data:
                
                vector = chunk_props.pop("vector", None)
                if vector is None:
                    print(f"Warning: Chunk {chunk_props['chunk_index']} has no vector. Skipping.")
                    continue
                
                # This UUID is for the Postgres link, remove it for Weaviate properties
                chunk_props.pop("parent_doc_uuid", None) 
                
                # Add object to batch with properties, vector, and reference
                batch.add_object(
                    properties=chunk_props,
                    vector=vector,
                    # v4 syntax for adding a cross-reference:
                    references={
                        "fromDocument": parent_doc_uuid
                    }
                )
        
        print(f"Successfully ingested {len(chunks_data)} chunks linked to document.")

    except Exception as e:
        print(f"ERROR during Weaviate ingestion: {e}")
    finally:
        if client:
            client.close()
            print("Weaviate connection closed.")