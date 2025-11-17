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

def create_database_schema():
    conn = None
    cursor = None
    try:
        if not wait_for_postgres():
            print("Exiting due to failed PostgreSQL connection.")
            return

        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        conn.autocommit = True
        cursor = conn.cursor()

        print(f"Successfully connected to PostgreSQL database '{DB_NAME}'.")
        print("Attempting to create database schema...")

        sql_script = """
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
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            
            -- Index for linking chunks to documents
            CREATE INDEX IF NOT EXISTS idx_chunks_doc_hash ON chunks (doc_hash);
            -- Index for finding chunks by filename
            CREATE INDEX IF NOT EXISTS idx_chunks_filename ON chunks (filename);
            """

        cursor.execute(sql_script)
        print("Database schema created successfully!")

    except Error as e:
        print(f"Error creating database schema: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        print("PostgreSQL connection closed.")


if __name__ == "__main__":
    create_database_schema() 