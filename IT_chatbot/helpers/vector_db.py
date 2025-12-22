import weaviate
from weaviate.classes.config import (
    Configure,
    Property,
    DataType,
    ReferenceProperty,
)
import weaviate.classes as wvc

from weaviate.classes.data import DataObject
from weaviate.util import generate_uuid5
from typing import List, Dict, Any
import os 

DOCUMENT_COLLECTION = "IT_Chatbot_Document"
CHUNK_COLLECTION = "DocChunk"

def create_client():
    """Connects to Weaviate using Docker service names."""
    try:
        client = weaviate.connect_to_custom(
            http_host=os.getenv("WEAVIATE_HOST", "weaviate"),
            http_port=int(os.getenv("WEAVIATE_PORT", 8080)),
            grpc_host=os.getenv("WEAVIATE_HOST", "weaviate"),
            grpc_port=int(os.getenv("WEAVIATE_GRPC_PORT", 50051))
        )
        return client
    except Exception as e:
        print(f"❌ Weaviate Connection Error: {e}")
        return None

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
    client = create_client()
    if not client: return

    try:
        # 1. Ensure schema exists using your existing logic
        define_schema(client) 

        parent_doc_data = ingestion_data.get("document")
        chunks_data = ingestion_data.get("chunks")
        parent_doc_uuid = parent_doc_data["uuid"]

        # 2. Insert Document
        doc_coll = client.collections.get(DOCUMENT_COLLECTION)
        doc_coll.data.insert(
            properties={
                "doc_hash": parent_doc_data["doc_hash"],
                "filename": parent_doc_data["filename"],
                "mimetype": parent_doc_data["mimetype"],
            },
            uuid=parent_doc_uuid
        )

        # 3. Batch Insert Chunks
        chunk_coll = client.collections.get(CHUNK_COLLECTION)
        with chunk_coll.batch.fixed_size(batch_size=50) as batch:
            for c in chunks_data:
                vector = c.pop("vector", None)
                c.pop("parent_doc_uuid", None)
                batch.add_object(
                    properties=c,
                    vector=vector,
                    references={"fromDocument": parent_doc_uuid}
                )
        print("✅ Weaviate ingestion complete.")
    finally:
        client.close()