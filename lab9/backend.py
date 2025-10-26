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
from langchain_huggingface import HuggingFaceEmbeddings
import shutil

# Initialize FastAPI app
app = FastAPI(title="Chat with PDF Backend")

# CORS for frontend
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


# --- Routes ---
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Handle single PDF upload, clear old FAISS, and rebuild new one."""
    contents = await file.read()

    reader = PdfReader(io.BytesIO(contents))
    num_pages = len(reader.pages)
    text = "\n".join((reader.pages[i].extract_text() or "") for i in range(num_pages)).strip()

    if not text:
        return {"status": "error", "message": "Could not extract text from PDF."}

    if os.path.exists(VS_DIR):
        print(f"Removing old FAISS index at {VS_DIR}")
        shutil.rmtree(VS_DIR)
    os.makedirs(VS_DIR, exist_ok=True)

    text_chunks = get_text_chunks(text)
    print(f"Creating new FAISS index with {len(text_chunks)} chunks...")
    vectorstore = get_vectorstore(text_chunks)
    vectorstore.save_local(VS_DIR)

    conn = _init_mysql()
    _upsert_pdf_and_chunks(conn, file.filename, contents, text, num_pages, text_chunks)
    conn.close()

    # --- Step 5: Refresh the conversation chain ---
    global conversation_chain
    conversation_chain = get_conversation_chain(vectorstore)

    return {"status": "success", "message": f"{file.filename} processed and indexed successfully."}




class PromptRequest(BaseModel):
    prompt: str


@app.post("/prompt-input")
async def process_prompt(req: PromptRequest):
    global conversation_chain

    # Always reload FAISS before answering
    try:
        vectorstore = FAISS.load_local(VS_DIR, embeddings, allow_dangerous_deserialization=True)
    except Exception as e:
        return {"answer": f"Error loading FAISS index: {e}"}

    # Refresh conversation chain each time
    conversation_chain = get_conversation_chain(vectorstore)

    # Generate answer
    answer = conversation_chain.invoke(
        {"input": req.prompt},
        config={"configurable": {"session_id": session_id}},
    )

    if isinstance(answer, dict) and "output_text" in answer:
        answer = answer["output_text"]
    elif not isinstance(answer, str):
        answer = str(answer)

    return {"answer": answer.strip()}



@app.get("/")
def root():
    return {"message": "PDF QA backend running. Use /upload and /prompt-input."}


