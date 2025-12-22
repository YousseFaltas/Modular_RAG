from dotenv import load_dotenv
import os
import psycopg2
from psycopg2 import Error, sql
import time

load_dotenv()

# --- PostgreSQL Connection Details ---
DB_HOST = os.getenv("POSTGRES_HOST") 
DB_NAME = os.getenv("POSTGRES_DB")  # The DB you want to create
DB_USER = os.getenv("POSTGRES_USER")   
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")
DB_PORT = os.getenv("POSTGRES_PORT") 

MAX_RETRIES = 10
RETRY_INTERVAL = 3

def connect_with_retry(target_db):
    """Helper to connect to a specific database with retries."""
    for attempt in range(MAX_RETRIES):
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                database=target_db,
                user=DB_USER,
                password=DB_PASSWORD,
                port=DB_PORT
            )
            return conn
        except Exception as e:
            print(f"Attempt {attempt + 1}: Could not connect to {target_db}. Retrying...")
            time.sleep(RETRY_INTERVAL)
    return None

def create_database_if_not_exists():
    """Connects to 'postgres' default DB to create the target DB."""
    conn = connect_with_retry("postgres")
    if not conn:
        print("Could not connect to PostgreSQL server.")
        return False

    conn.autocommit = True
    cursor = conn.cursor()

    try:
        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (DB_NAME,))
        exists = cursor.fetchone()
        
        if not exists:
            print(f"Database '{DB_NAME}' does not exist. Creating...")
            # Use sql.Identifier to safely handle the DB name
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_NAME)))
            print(f"Database '{DB_NAME}' created successfully.")
        else:
            print(f"Database '{DB_NAME}' already exists.")
        
        return True
    except Error as e:
        print(f"Error during database creation: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def create_database_schema():
    # 1. First, ensure the database itself exists
    if not create_database_if_not_exists():
        print("Failed to ensure database existence. Exiting.")
        return

    # 2. Now connect to the actual target database to create tables
    print(f"Connecting to '{DB_NAME}' to create schema...")
    conn = connect_with_retry(DB_NAME)
    if not conn:
        return

    try:
        conn.autocommit = True
        cursor = conn.cursor()

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
            
            CREATE INDEX IF NOT EXISTS idx_chunks_doc_hash ON chunks (doc_hash);
            CREATE INDEX IF NOT EXISTS idx_chunks_filename ON chunks (filename);
        """

        cursor.execute(sql_script)
        print("Schema (tables and indexes) created successfully!")

    except Error as e:
        print(f"Error creating schema: {e}")
    finally:
        if conn:
            conn.close()
            print("PostgreSQL connection closed.")

if __name__ == "__main__":
    create_database_schema()