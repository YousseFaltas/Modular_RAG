import streamlit as st
import os
import sys
import uuid
from testing_pipeline import data_extractions, process_and_embed_chunks
from helpers.DB import ingest_to_postgres
from helpers.vector_db import insert_to_weaviate

st.set_page_config(page_title="RAG Chunker Bot", layout="wide")

st.title("🤖 RAG Document Processor & Chat")

# --- Sidebar: File Upload ---
with st.sidebar:
    st.header("Upload Documents")
    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
    
    if uploaded_file:
        # Save temp file for Docling to read
        temp_path = f"temp_{uploaded_file.name}"
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        if st.button("🚀 Process & Ingest"):
            with st.spinner("Extracting chunks with Docling..."):
                chunks = data_extractions(temp_path)
                
            with st.spinner("Embedding and Ingesting..."):
                ingestion_data = process_and_embed_chunks(docling_chunks=chunks)
                # Ingest into both DBs
                ingest_to_postgres(ingestion_data["chunks"])
                insert_to_weaviate(ingestion_data)
                
            st.success(f"Ingested {len(chunks)} chunks successfully!")
            os.remove(temp_path)

# --- Main Chat Interface ---
st.subheader("Chat with your Data")
if "messages" not in st.session_state:
    st.session_state.messages = []

try:
    from rag_generator import rag_answer_with_memory
except Exception as e:
    rag_answer_with_memory = None
    print(f"Warning: could not import rag_generator.rag_answer_with_memory: {e}")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask something about the documents..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # Use the generation module if available
        if rag_answer_with_memory:
            user_id = st.session_state.get("user_id")
            if not user_id:
                user_id = str(uuid.uuid4())
                st.session_state["user_id"] = user_id
            with st.spinner("Generating answer..."):
                try:
                    response = rag_answer_with_memory(prompt, user_id)
                except Exception as e:
                    response = f"❌ Error generating response: {e}"
        else:
            response = "I have indexed your document. (Retrieval logic goes here)"
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})