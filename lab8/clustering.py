import json
import numpy as np
import pandas as pd
import mysql.connector

from sklearn.preprocessing import Normalizer
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score


POSTS_TABLE = "reddit_posts"

# Which runs to process: "ALL" or list like ["dm50", "dbow100"]
RUNS = "ALL"

K_MIN = 2
K_MAX = 8
RANDOM_STATE = 42



def ensure_tables(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS clusters_assignments_runs (
            post_id    VARCHAR(20),
            run_name   VARCHAR(64),
            cluster_id INT,
            title      TEXT,
            content    TEXT,
            PRIMARY KEY (post_id, run_name)
        ) ENGINE=InnoDB
    """)
    conn.commit()
    cur.close()

def available_runs(conn) -> list:
    q = "SELECT DISTINCT run_name FROM reddit_embeddings_runs ORDER BY run_name"
    return pd.read_sql(q, conn)["run_name"].tolist()


def load_run_df(conn, run_name: str) -> pd.DataFrame:
    q = f"""
        SELECT p.id, p.title, p.content, r.embedding
        FROM {POSTS_TABLE} AS p
        JOIN reddit_embeddings_runs AS r ON p.id = r.id
        WHERE r.run_name = %s
    """
    df = pd.read_sql(q, conn, params=[run_name])
    if df.empty:
        return df
    df["embedding_list"] = df["embedding"].apply(lambda s: [float(x) for x in json.loads(s)])
    return df



def choose_k_by_silhouette(Xn, kmin=2, kmax=20, random_state=42):
    n = Xn.shape[0]
    # silhouette requires at least 2 clusters and n_samples > n_clusters
    max_k_allowed = max(2, min(kmax, n - 1))
    candidate_ks = [k for k in range(max(kmin, 2), max_k_allowed + 1)]
    if not candidate_ks:
        # fallback to single cluster when not enough samples
        return 1, [], []
    scores = []
    for k in candidate_ks:
        km = KMeans(n_clusters=k, init='k-means++', random_state=random_state, n_init=10)
        labels = km.fit_predict(Xn)
        try:
            sil = silhouette_score(Xn, labels, metric="cosine")
        except Exception:
            sil = float("nan")
        scores.append(sil)
    best_index = int(np.nanargmax(scores)) if any(np.isfinite(scores)) else 0
    return int(candidate_ks[best_index]), candidate_ks, scores



def cluster_and_score(df, kmin, kmax, random_state=42):
    X = np.array(df["embedding_list"].tolist())
    normalizer = Normalizer()
    Xn = normalizer.fit_transform(X)

    best_k, _, _ = choose_k_by_silhouette(Xn, kmin, kmax, random_state)
    km = KMeans(n_clusters=best_k, init='k-means++', random_state=random_state, n_init=10)
    labels = km.fit_predict(Xn)

    # metrics only meaningful when k >= 2
    if best_k >= 2 and len(np.unique(labels)) >= 2:
        sil = silhouette_score(Xn, labels, metric="cosine")
        db  = davies_bouldin_score(Xn, labels)
        ch  = calinski_harabasz_score(Xn, labels)
    else:
        sil = float("nan"); db = float("nan"); ch = float("nan")

    return labels, dict(k=best_k, sil=float(sil), db=float(db), ch=float(ch))



def persist_assignments(conn, run_name, df_with_labels):
    cur = conn.cursor()
    rows = [
        (row["id"], run_name, int(row["cluster"]), row.get("title", None), row.get("content", None))
        for _, row in df_with_labels.iterrows()
    ]
    cur.executemany(
        """
        INSERT INTO clusters_assignments_runs (post_id, run_name, cluster_id, title, content)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            cluster_id = VALUES(cluster_id),
            title      = VALUES(title),
            content    = VALUES(content)
        """,
        rows
    )
    conn.commit()
    cur.close()


def main():

    conn = mysql.connector.connect(
    host = "localhost",
    user = "root",
    password = "",
    database = "reddit_tech"
    )

    ensure_tables(conn)

    runs = available_runs(conn) if (isinstance(RUNS, str) and RUNS.strip().upper() == "ALL") else list(RUNS)
    if not runs:
        print("No runs available. Execute your Doc2Vec training first.")
        conn.close()
        return

    summaries = []
    for rn in runs:
        print(f"\n=== RUN: {rn} ===")
        df = load_run_df(conn, rn)
        if df.empty:
            print("No rows for this run; skipping.")
            continue

        labels, metrics = cluster_and_score(df, K_MIN, K_MAX, RANDOM_STATE)
        out = df.copy()
        out["cluster"] = labels

        persist_assignments(conn, rn, out)

        row = {
            "run": rn,
            "k": int(metrics["k"]),
            "silhouette_cos": (None if np.isnan(metrics["sil"]) else round(metrics["sil"], 4)),
            "davies_bouldin": (None if np.isnan(metrics["db"])  else round(metrics["db"], 4)),
            "calinski_harabasz": (None if np.isnan(metrics["ch"]) else round(metrics["ch"], 2)),
        }
        summaries.append(row)
        print(f"    k={row['k']} | sil_cos={row['silhouette_cos']} | DB={row['davies_bouldin']} | CH={row['calinski_harabasz']}")

    if summaries:
        cmp = pd.DataFrame(summaries).sort_values(by=["silhouette_cos"], ascending=[False], na_position="last")
        cmp.to_csv("doc2vec_comparison_summary.csv", index=False)
        print("\n=== Comparison Summary (sorted by silhouette_cos desc; NaNs last) ===")
        print(cmp.to_string(index=False))
        print("\nWrote summary -> doc2vec_comparison_summary.csv")

    conn.close()

if __name__ == "__main__":
    main()
