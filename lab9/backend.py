import os
import io
import hashlib
from datetime import datetime
from typing import List

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PyPDF2 import PdfReader

from app import (
    get_pdf_text,
    get_text_chunks,
    get_vectorstore,
    _init_mysql,
    _upsert_pdf_and_chunks,
    VS_DIR,
    DATA_DIR,
    get_conversation_chain,
    _load_api_key_from_dotenv,
)

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

# Initialize FastAPI app
app = FastAPI(title="Chat with PDF Backend")

# CORS for frontend (http://localhost or similar)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow frontend to call this backend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global conversation object
conversation_chain = None
session_id = "api"
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-MiniLM-L6-v2")

# Ensure FAISS + data folder exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(VS_DIR, exist_ok=True)

_load_api_key_from_dotenv()


# --- Utility: Load FAISS if exists ---
def load_or_create_faiss():
    if os.path.exists(VS_DIR):
        try:
            print(f"Loading existing FAISS index from {VS_DIR}")
            return FAISS.load_local(VS_DIR, embeddings, allow_dangerous_deserialization=True)
        except Exception as e:
            print("FAISS load failed:", e)
    print("Creating new FAISS index...")
    return None


# --- Routes ---

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Handle single PDF upload, process, and update FAISS + MySQL."""
    contents = await file.read()

    # Parse PDF text
    reader = PdfReader(io.BytesIO(contents))
    num_pages = len(reader.pages)
    text = "\n".join((reader.pages[i].extract_text() or "") for i in range(num_pages)).strip()

    if not text:
        return {"status": "error", "message": "Could not extract text from PDF."}

    # Split into chunks
    text_chunks = get_text_chunks(text)

    # Load or create FAISS vector store
    vectorstore = load_or_create_faiss()
    if vectorstore:
        # Add new text embeddings to existing FAISS
        vectorstore.add_texts(text_chunks)
    else:
        vectorstore = get_vectorstore(text_chunks)

    # Save updated FAISS
    vectorstore.save_local(VS_DIR)

    # Save to MySQL
    conn = _init_mysql()
    _upsert_pdf_and_chunks(conn, file.filename, contents, text, num_pages, text_chunks)

    # Update global conversation chain
    global conversation_chain
    conversation_chain = get_conversation_chain(vectorstore)

    return {"status": "success", "message": f"{file.filename} processed successfully."}


class PromptRequest(BaseModel):
    prompt: str


@app.post("/prompt-input")
async def process_prompt(req: PromptRequest):
    """Handle chat prompts and return answers."""
    global conversation_chain
    if conversation_chain is None:
        # Load FAISS from disk
        vectorstore = load_or_create_faiss()
        if vectorstore is None:
            return {"answer": "No documents indexed yet. Please upload a PDF first."}
        conversation_chain = get_conversation_chain(vectorstore)

    # Run retrieval + response
    answer = conversation_chain.invoke(
        {"input": req.prompt},
        config={"configurable": {"session_id": session_id}},
    )

    return {"answer": answer}


@app.get("/")
def root():
    return {"message": "PDF QA backend running. Use /upload and /prompt-input."}


# --- Run with: uvicorn backend:app --reload ---

