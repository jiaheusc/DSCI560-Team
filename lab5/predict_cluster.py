import mysql.connector
import numpy as np
import joblib
from gensim.models.doc2vec import Doc2Vec
import json
import pandas as pd
import matplotlib.pyplot as plt

doc2vec_model = Doc2Vec.load("doc2vec.model")
normalizer = joblib.load("normalizer.joblib")
kmeans_model = joblib.load('kmeans_model.joblib')

db = mysql.connector.connect(
    host = "localhost",
    user = "root",
    password = "",
    database = ""
)

def predict_cluster_for_text(text):
    words = text.lower().split()
    vec = doc2vec_model.infer_vector(words)
    X = vec.reshape(1, -1)
    X = normalizer.transform(X)
    target_dtype = getattr(kmeans_model.cluster_centers_, "dtype", np.float64)
    X = X.astype(target_dtype, copy=False)
    return int(kmeans_model.predict(X)[0])

def get_cluster_keywords(cluster_id):
    cursor = db.cursor()
    sql = "SELECT keywords FROM clusters WHERE cluster_id = %s"
    cursor.execute(sql, (cluster_id,))
    result = cursor.fetchone()
    cursor.close()
    return json.loads(result[0])

def get_all_messages():
    sql = "SELECT post_id, cluster_id, title, content, tsne_x, tsne_y FROM clusters_messages"
    return pd.read_sql(sql, con=db)

def visualize_cluster(cluster_id):
    keywords = get_cluster_keywords(cluster_id)
    df = get_all_messages()

    cluster_mask = df["cluster_id"] == cluster_id
    cluster_df = df[cluster_mask]

    plt.figure(figsize=(16, 10))
    plt.scatter(df.loc[~cluster_mask, "tsne_x"], df.loc[~cluster_mask, "tsne_y"],
            s=8, c="#7c7c7c", alpha=0.35, linewidths=0, label="other clusters")
    plt.scatter(df.loc[cluster_mask, "tsne_x"], df.loc[cluster_mask, "tsne_y"],
            s=20, alpha=0.9, linewidths=0, label=f"cluster {cluster_id}")
    if keywords:
        cx, cy = df.loc[cluster_mask, ["tsne_x","tsne_y"]].mean(0)
        plt.text(cx, cy, ", ".join(keywords[:5]), fontsize=9, weight="bold")
    plt.title(f"t-SNE — highlight cluster {cluster_id}")
    plt.legend(loc="lower right")
    plt.tight_layout()
    plt.show()

    print(f"\n{'-'*40}")
    print(f"CLUSTER {cluster_id}")
    print(f"Keywords: {', '.join(keywords[:5])}")
    sample_size = min(5, len(cluster_df))
    samples = cluster_df.sample(n=sample_size, random_state=42)
    for idx, (_, row) in enumerate(samples.iterrows(), 1):
        print(f"\n--- Message {idx} ---")
        print(f"Title: {row['title'][:100]}{'...' if len(row['title']) > 100 else ''}")
        if pd.notna(row['content']) and row['content'].strip():
            content_preview = row['content'][:150] + '...' if len(row['content']) > 150 else row['content']
            print(f"Content: {content_preview}")
        print("-" * 40)

    

if __name__ == "__main__":

    print("Please enter context")
    print("Enter q to quit\n")
    try:
        while True:
            user_input = input("please enter text: ")
            if user_input.lower() == 'q':
                break
            if not user_input.strip():
                continue
            cluster_id = predict_cluster_for_text(user_input)
            visualize_cluster(cluster_id)
    finally:
        db.close()
        