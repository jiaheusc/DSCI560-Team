import os
import io
import hashlib
from datetime import datetime
from typing import List, Tuple, Optional
from pathlib import Path
import sys

import streamlit as st
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter as CharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from sentence_transformers import SentenceTransformer
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import InMemoryChatMessageHistory
from operator import itemgetter
from htmlTemplates import css, bot_template, user_template
import mysql.connector
from pathlib import Path

DATA_DIR = os.path.abspath("./daton youra")
VS_DIR = os.path.join(DATA_DIR, "faiss_index")
os.makedirs(DATA_DIR, exist_ok=True)


CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100

MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASSWORD = "DSCI560&team"
MYSQL_DB = "lab9"


def _load_api_key_from_dotenv() -> Optional[str]:
    here = Path(__file__).parent
    load_dotenv(dotenv_path=here / ".env", override=True)
    load_dotenv(dotenv_path=here / ".env.txt", override=True)
    key = os.getenv("OPENAI_API_KEY")
    if key:
        os.environ["OPENAI_API_KEY"] = key
    return key


def get_pdf_text(pdf_docs):
    texts = []
    for f in pdf_docs:
        try:
            f.seek(0)
            reader = PdfReader(f)
            pages = len(reader.pages)
            buf = []
            for i in range(pages):
                try:
                    buf.append(reader.pages[i].extract_text() or "")
                except Exception:
                    buf.append("")
            texts.append("\n".join(buf))
        finally:
            # reset pointer for any downstream re-use
            try:
                f.seek(0)
            except Exception:
                pass
    return "\n".join(texts)


def get_text_chunks(text: str) -> List[str]:
    splitter = CharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
    )
    return splitter.split_text(text)



def get_vectorstore(text_chunks: List[str]):
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-MiniLM-L6-v2")
    return FAISS.from_texts(text_chunks, embeddings)

STORE = {}
def _get_session_history(session_id: str):
    if session_id not in STORE:
        STORE[session_id] = InMemoryChatMessageHistory()
    return STORE[session_id]



def _format_docs(docs):
    return "\n\n".join(d.page_content for d in docs)

from langchain_core.runnables import RunnableLambda

def get_conversation_chain(vectorstore):
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    def query_func(inputs):
        query = inputs["input"]
        docs = retriever.invoke(query)
        context = "\n\n".join(d.page_content for d in docs)
        return f"Top relevant context:\n{context}"

    runnable = RunnableLambda(query_func)
    return RunnableWithMessageHistory(
        runnable,
        _get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
        output_messages_key=None,
    )



def handle_userinput(user_question: str):
    if "session_id" not in st.session_state:
        st.session_state.session_id = "streamlit"

    chain = st.session_state.conversation
    answer = chain.invoke(
        {"input": user_question},
        config={"configurable": {"session_id": st.session_state.session_id}}
    )  # this is a plain string

    # Render full history
    history = _get_session_history(st.session_state.session_id).messages
    for msg in history:
        role = "🧑‍💻 You" if getattr(msg, "type", "") == "human" else "🤖 Bot"
        st.markdown(f"**{role}:** {msg.content}")

    # Also show the newest answer
    if answer:
        st.markdown(f"**🤖 Bot:** {answer}")



def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)


def _mysql_root_conn():
    return mysql.connector.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        autocommit=True,
        charset="utf8mb4",
        use_unicode=True,
    )


def _mysql_conn(dbname: str):
    return mysql.connector.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=dbname,
        autocommit=True,
        charset="utf8mb4",
        use_unicode=True,
    )


def _init_mysql():
    # Ensure DB exists
    root = _mysql_root_conn()
    cur = root.cursor()
    cur.execute(
        f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DB}` "
        "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    )
    cur.close()
    root.close()

    # Ensure tables exist
    conn = _mysql_conn(MYSQL_DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pdfs (
            id CHAR(40) PRIMARY KEY,             -- sha1(full text)
            filename VARCHAR(512) NOT NULL,
            num_pages INT NOT NULL,
            sha1 CHAR(40) NOT NULL,              -- sha1(raw bytes)
            text LONGTEXT NOT NULL,              -- full extracted text
            created_at DATETIME NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            pdf_id CHAR(40) NOT NULL,
            chunk_index INT NOT NULL,
            content LONGTEXT NOT NULL,
            CONSTRAINT fk_chunks_pdfs FOREIGN KEY (pdf_id)
                REFERENCES pdfs(id) ON DELETE CASCADE ON UPDATE CASCADE,
            KEY idx_chunks_pdf_id (pdf_id, chunk_index)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
    cur.close()
    return conn



def _sha1_bytes(b: bytes):
    h = hashlib.sha1()
    h.update(b)
    return h.hexdigest()


def _sha1_text(s: str):
    h = hashlib.sha1()
    h.update(s.encode("utf-8"))
    return h.hexdigest()


def _upsert_pdf_and_chunks(conn, filename: str, raw_bytes: bytes, text: str, num_pages: int, chunks: List[str]):
    pdf_id = _sha1_text(text)
    raw_sha1 = _sha1_bytes(raw_bytes)
    cur = conn.cursor()


    cur.execute(
        """
        INSERT INTO pdfs (id, filename, num_pages, sha1, text, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            filename = VALUES(filename),
            num_pages = VALUES(num_pages),
            sha1 = VALUES(sha1),
            text = VALUES(text)
        """,
        (pdf_id, filename, num_pages, raw_sha1, text, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
    )


    cur.execute("SELECT 1 FROM chunks WHERE pdf_id = %s LIMIT 1", (pdf_id,))
    has_chunks = cur.fetchone() is not None
    if not has_chunks:
        cur.executemany(
            "INSERT INTO chunks (pdf_id, chunk_index, content) VALUES (%s, %s, %s)",
            [(pdf_id, i, c) for i, c in enumerate(chunks)]
        )

    cur.close()



def run_cli_driver(vectorstore):
    chain = get_conversation_chain(vectorstore)
    session_id = "cli"
    print("CLI mode (OpenAI). Type 'exit' to quit.")
    while True:
        q = input("> ").strip()
        if q.lower() in {"exit", "quit"}:
            break
        ans = chain.invoke({"input": q}, config={"configurable": {"session_id": session_id}})
        print(ans)




def _load_vectorstore_for_cli_openai():
    index_dir = "./data/faiss_index"
    if not os.path.isdir(index_dir):
        return None
    mbeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-MiniLM-L6-v2")
    return FAISS.load_local(index_dir, embeddings, allow_dangerous_deserialization=True)

