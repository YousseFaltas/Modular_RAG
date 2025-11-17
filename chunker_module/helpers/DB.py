import json # <-- ADD THIS IMPORT
from typing import List, Dict, Any
from dotenv import load_dotenv
import os
import psycopg2
from psycopg2 import Error
import time


load_dotenv()

# --- PostgreSQL Connection Details ---
DB_HOST = os.getenv("POSTGRES_HOST") 
DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")   
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")
DB_PORT = os.getenv("POSTGRES_PORT") 

def get_postgres_connection():
    """This function connect to the postgress DB 

    Returns:
        DB object: the initialized cursor for DB communication
    """
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        conn.autocommit = False
        cursor = conn.cursor()
        print("✅ Successfully connected to PostgreSQL")
        return conn, cursor
    except Error as e:
        print(f"❌ Error connecting to PostgreSQL: {e}")
        return None, None
    
# --- Run Setup ---

MAX_RETRIES = 10
RETRY_INTERVAL = 3  # seconds

def wait_for_postgres():
    for attempt in range(MAX_RETRIES):
        try:
            print(f"Attempt {attempt + 1} to connect to PostgreSQL...")
            conn = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                port=DB_PORT
            )
            conn.close()
            print("PostgreSQL is available.")
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            time.sleep(RETRY_INTERVAL)
    print("PostgreSQL not available after multiple attempts.")
    return False

# --- INGESTION (REPLACED) ---
def ingest_to_postgres(data: List[Dict[str, Any]]):
    """
    Ingests a list of processed chunks into the PostgreSQL database.
    This function is idempotent and will not create duplicates
    based on the 'chunk_id' primary key.
    """
    
    # 1. Wait for the database to be ready
    if not wait_for_postgres():
        print("Exiting due to failed PostgreSQL connection.")
        return

    conn = None
    cursor = None
    
    try:
        # 2. Use your helper function to get the connection
        # (This already sets autocommit=False)
        conn, cursor = get_postgres_connection()
        
        if not conn or not cursor:
            # get_postgres_connection already printed the error
            return

        # 3. Prepare the data for insertion
        insert_data = [
            (
                str(d["chunk_id"]),
                d["doc_hash"],
                d["chunk_index"],
                d["filename"],
                json.dumps(d["page_numbers"]) if d["page_numbers"] else None,
                d["title"],
                d["text"],
                json.dumps(d["content_types"]) if d["content_types"] else None,
                json.dumps(d["bounding_boxes"]) if d["bounding_boxes"] else None,
            )
            for d in data
        ]
        
        if not insert_data:
            print("No data provided to ingest.")
            return

        # 4. Execute the batch insert as a single transaction
        print(f"Attempting to ingest {len(insert_data)} chunks into PostgreSQL...")
        
        cursor.executemany("""
        INSERT INTO chunks (
            chunk_id, doc_hash, chunk_index, filename, 
            page_numbers, title, text, content_types, bounding_boxes
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (chunk_id) DO NOTHING;
        """, insert_data)
        
        # 5. Commit the entire transaction
        conn.commit()
        
        # cursor.rowcount shows how many rows were *actually* inserted
        print(f"PostgreSQL batch insert successful. {cursor.rowcount} new rows inserted.")

    except Error as e:
        print(f"❌ ERROR: PostgreSQL transaction failed: {e}")
        # 6. Roll back the entire batch if anything went wrong
        if conn:
            conn.rollback()
    finally:
        # 7. Always close connections
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        print("PostgreSQL connection closed.")