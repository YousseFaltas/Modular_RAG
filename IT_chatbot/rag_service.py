import os
import sys
import uuid
from typing import Optional


from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="RAG Service")

try:
    from rag_generator import rag_answer_with_memory
except Exception as e:
    rag_answer_with_memory = None
    print(f"Warning: could not import rag_generator.rag_answer_with_memory: {e}")


class QueryRequest(BaseModel):
    question: str
    user_id: Optional[str] = None
    top_k: Optional[int] = 7


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/answer")
async def answer(req: QueryRequest):
    if rag_answer_with_memory is None:
        return {"error": "RAG generation module not available on import."}

    user_id = req.user_id or str(uuid.uuid4())
    try:
        resp = rag_answer_with_memory(req.question, user_id, top_k=req.top_k)
        return {"answer": resp, "user_id": user_id}
    except Exception as e:
        return {"error": str(e)}
