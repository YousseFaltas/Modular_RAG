import psycopg
import uuid
import json # <-- ADD THIS IMPORT
from psycopg.rows import dict_row
from typing import List, Dict, Any
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/rag_db")

# --- Connect to PostgreSQL ---
print("Connecting to PostgreSQL...")
try:
    with psycopg.connect(DATABASE_URL) as pg_conn:
        with pg_conn.cursor() as cur:
            cur.execute("SELECT 1")
            print("PostgreSQL connection successful.")
except Exception as e:
    print(f"ERROR: Could not connect to PostgreSQL: {e}")

# --- SCHEMA (REPLACED) ---
def setup_postgres_schema(conn_string: str):
    """Ensures the PostgreSQL 'chunks' table exists with the full schema."""
    with psycopg.connect(conn_string) as conn:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id UUID PRIMARY KEY,
                doc_hash TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                filename TEXT,
                page_numbers JSONB,
                title TEXT,
                text TEXT NOT NULL,
                content_types JSONB,
                bounding_boxes JSONB,
                created_at TIMESTZ DEFAULT NOW()
            );
            
            -- Index for linking chunks to documents
            CREATE INDEX IF NOT EXISTS idx_chunks_doc_hash ON chunks (doc_hash);
            -- Index for finding chunks by filename
            CREATE INDEX IF NOT EXISTS idx_chunks_filename ON chunks (filename);
            """)
            conn.commit()
    print("PostgreSQL 'chunks' table is ready.")

# --- Run Setup ---
setup_postgres_schema(DATABASE_URL)

# --- INGESTION (REPLACED) ---
def ingest_to_postgres(data: List[Dict[str, Any]], conn_string: str = DATABASE_URL):
    """Batch-inserts structured chunk data into PostgreSQL."""
    print(f"Batch inserting {len(data)} records into PostgreSQL...")
    
    insert_data = [
        (
            d["chunk_id"],
            d["doc_hash"],
            d["chunk_index"],
            d["filename"],
            json.dumps(d["page_numbers"]) if d["page_numbers"] else None, # Ensure JSONB
            d["title"],
            d["text"],
            json.dumps(d["content_types"]) if d["content_types"] else None, # Ensure JSONB
            json.dumps(d["bounding_boxes"]) if d["bounding_boxes"] else None, # Ensure JSONB
        )
        for d in data
    ]
    
    try:
        with psycopg.connect(conn_string) as conn:
            with conn.cursor() as cur:
                cur.executemany("""
                INSERT INTO chunks (
                    chunk_id, doc_hash, chunk_index, filename, 
                    page_numbers, title, text, content_types, bounding_boxes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (chunk_id) DO NOTHING;
                """, insert_data)
                
                conn.commit()
        print("PostgreSQL batch insert successful.")
    except Exception as e:
        print(f"ERROR: PostgreSQL batch insert failed: {e}")