import json, re
from typing import List
import pandas as pd
import mysql.connector
from gensim.models.doc2vec import Doc2Vec, TaggedDocument
import os
POSTS_TABLE = "reddit_posts"
RUNS = ["dm50", "dm100", "dm200"]

# Doc2Vec settings for each run
RUN_CONFIGS = {
    "dm50": dict(dm=1, vector_size=50, window=5,  min_count=2, epochs=80, negative=10, sample=1e-4, workers=4, seed=42),
    "dm100": dict(dm=1, vector_size=100, window=5,  min_count=2, epochs=80, negative=10, sample=1e-4, workers=4, seed=42),
    "dm200": dict(dm=1, vector_size=200, window=5,  min_count=3, epochs=80, negative=10, sample=1e-4, workers=4, seed=42)
}

SAVE_MODEL_FILES = True  

_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_TAG_RE = re.compile(r"<[^>]+>")

def ensure_tables(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reddit_embeddings_runs (
            id VARCHAR(20),
            run_name VARCHAR(64),
            embedding JSON,
            PRIMARY KEY (id, run_name)
        ) ENGINE=InnoDB
    """)
    conn.commit()
    cur.close()

def fetch_posts(conn) -> pd.DataFrame:
    q = f"""
        SELECT id, title, content, keywords, image_text
        FROM {POSTS_TABLE}
        ORDER BY timestamp ASC
    """
    df = pd.read_sql(q, conn)
    for col in ["title", "content", "keywords", "image_text"]:
        if col not in df.columns:
            df[col] = ""
    return df

def build_documents(df: pd.DataFrame) -> List[TaggedDocument]:
    docs = []
    for _id, title, content, keywords, img_text in df[["id","title","content","keywords","image_text"]].itertuples(index=False):
        parts = []
        for t in (title, content, keywords, img_text):
            if pd.notna(t) and str(t).strip():
                parts.append(str(t))
        if not parts:
            continue
        text = " ".join(parts)
        text = _URL_RE.sub(" ", text)
        text = _TAG_RE.sub(" ", text)
        words = text.split()
        docs.append(TaggedDocument(words=words, tags=[str(_id)]))
    return docs



def train_and_persist(conn, docs: List[TaggedDocument], run_name: str, cfg: dict):
    print(f"[+] Training Doc2Vec run={run_name} cfg={cfg}")
    model = Doc2Vec(**cfg)
    model.build_vocab(docs)
    model.train(docs, total_examples=len(docs), epochs=model.epochs)
    if SAVE_MODEL_FILES:
        model.save(f"doc2vec_{run_name}.model")
        print(f"    Saved model -> doc2vec_{run_name}.model")

    # Store embeddings per (id, run_name) in reddit_embeddings_runs
    cur = conn.cursor()
    rows = 0
    for doc in docs:
        tag = doc.tags[0]
        vec = model.dv[tag].tolist() if tag in model.dv else model.infer_vector(doc.words).tolist()
        cur.execute(
            """
            INSERT INTO reddit_embeddings_runs (id, run_name, embedding)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE embedding = VALUES(embedding)
            """,
            (tag, run_name, json.dumps(vec))
        )
        rows += 1

    conn.commit()
    cur.close()


    print(f"    Wrote {rows} embeddings into reddit_embeddings_runs for run={run_name}")

def main():
    conn = mysql.connector.connect(
    host = "localhost",
    user = "root",
    password = "",
    database = "reddit_tech"
    )

    ensure_tables(conn)
    df = fetch_posts(conn)

    if df.empty:
        print("No rows in reddit_posts. Exiting.")
        conn.close()
        return
    docs = build_documents(df)


    if not docs:
        print("No text available to train on. Exiting.")
        conn.close()
        return


    for rn in RUNS:
        if rn not in RUN_CONFIGS:
            print(f"[!] Unknown run '{rn}' (skipped). Valid: {list(RUN_CONFIGS.keys())}")
            continue
        train_and_persist(conn, docs, rn, RUN_CONFIGS[rn])

        
    conn.close()

if __name__ == "__main__":
    main()
