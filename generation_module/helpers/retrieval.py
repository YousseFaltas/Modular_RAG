import weaviate
from weaviate.classes.init import Auth
from pprint import pprint
import os


DOCUMENT_COLLECTION = "Document"
CHUNK_COLLECTION = "DocChunk"

def create_client():
    print("Connecting to Weaviate to set up schema...")
    try:
        client = weaviate.connect_to_local()
        print("Weaviate connection successful.")
        return client
    except Exception as e:
        print(f"ERROR: Could not connect to weaviate: {e}")
        return None # Return None on failure
    
def main():
    client = create_client()

    if client:
        try :
            response = client.collections.list_all(simple=False)

            pprint(response)

        finally:
            client.close()
            print("Weaviate connection closed")

if __name__ == "__main__":
    main()