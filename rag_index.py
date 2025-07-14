# rag_index.py
import os
import logging
import psycopg2
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# in-memory index
rag_index: FAISS | None = None

def reload_rag_index():
    """Rebuild the in-memory FAISS index from the Postgres embeddings table."""
    global rag_index
    conn = psycopg2.connect(DATABASE_URL)
    cur  = conn.cursor()
    cur.execute("SELECT chunk_text FROM embeddings")
    docs = [Document(page_content=row[0]) for row in cur.fetchall()]
    cur.close()
    conn.close()

    embeddings = OpenAIEmbeddings()
    rag_index = FAISS.from_documents(docs, embeddings)
    logging.info(f"RAG index reloaded with {len(docs)} chunks")

async def _rag_search(question: str) -> str:
    """Similarity search against the live FAISS RAG index."""
    global rag_index
    if rag_index is None:
        reload_rag_index()
    hits = rag_index.similarity_search(question, k=3)
    return "\n\n".join(d.page_content for d in hits)
