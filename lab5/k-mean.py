import mysql.connector
import pandas as pd
import numpy as np
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.preprocessing import Normalizer
from sklearn.metrics import silhouette_score
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.manifold import TSNE
import matplotlib.pyplot as plt
import json
import joblib

db = mysql.connector.connect(
    host = "localhost",
    user = "root",
    password = "",
    database = ""
)

def parse_embedding(x):
    s = x.strip()
    v = json.loads(s)
    return [float(u) for u in v]

def load_data():
    sql = """
        SELECT
            p.id,
            p.title,
            p.content,
            e.embedding
        FROM reddit_posts AS p
        JOIN reddit_embeddings AS e ON p.id = e.id;
    """
    df = pd.read_sql(sql, con=db)
    df["embedding_list"] = df["embedding"].apply(parse_embedding)
    return df

def get_best_k(X):
    silhouette_scores = []
    k_range = range(2, 21)
    for k in k_range:
        kmeans = KMeans(n_clusters=k, init='k-means++', random_state=42, n_init='auto')
        kmeans.fit(X)
        score = silhouette_score(X, kmeans.labels_)
        silhouette_scores.append(score)
    best_k_index = np.argmax(silhouette_scores)
    best_k = k_range[best_k_index]
    return best_k

def k_mean_model(df):
    X = np.array(df['embedding_list'].tolist())
    normalizer = Normalizer()
    Xn = normalizer.fit_transform(X)

    best_k = get_best_k(Xn)

    k_means = KMeans(n_clusters=best_k, init='k-means++', random_state=42, n_init='auto')
    cluster_labels = k_means.fit_predict(Xn)
    df['cluster'] = cluster_labels

    joblib.dump(k_means, 'kmeans_model.joblib')
    return df, Xn

def generate_cluster_samples(df):
    #TF-IDF to find keywords in each cluster
    df['full_text'] = df['title'].fillna('') + ' ' + df['content'].fillna('')
    aggregated_texts = df.groupby('cluster')['full_text'].apply(lambda texts: ' '.join(texts)).tolist()
    vectorizer = TfidfVectorizer(
        stop_words='english',
        max_features=1000,
        ngram_range=(1, 1)
    )
    tfidf_matrix = vectorizer.fit_transform(aggregated_texts)
    feature_names = vectorizer.get_feature_names_out()
    cluster_ids = sorted(df['cluster'].unique())
    cluster_keywords = {}
    for i, cluster_id in enumerate(cluster_ids):
        row = tfidf_matrix.toarray()[i]
        top_indices = row.argsort()[-5:][::-1]
        top_words = [feature_names[index] for index in top_indices]
        cluster_keywords[cluster_id] = top_words

    # print clusters with samples
    print("--- Cluster with Samples ---")
    for cluster_id, keywords in cluster_keywords.items():
        print(f"\nCluster {cluster_id}:")
        print(f"Keywords: {', '.join(keywords)}")
        
        cluster_df = df[df['cluster'] == cluster_id]
        sample_size = min(5, len(cluster_df)) 
        sample_titles = cluster_df.sample(n=sample_size, random_state=42)['title']
        
        print("Sample Post titles:")
        for title in sample_titles:
            print(f"{title}\n")

def generate_plot(df, Xn):
    # plot
    cluster_ids = sorted(df['cluster'].unique())
    tsne = TSNE(n_components=2, perplexity=30, max_iter=300, random_state=42)
    tsne_results = tsne.fit_transform(Xn)
    df['tsne_x'] = tsne_results[:, 0]
    df['tsne_y'] = tsne_results[:, 1]
    plt.figure(figsize=(16, 10))
    sns.scatterplot(
        x='tsne_x', y='tsne_y',
        hue='cluster',
        palette=sns.color_palette("hsv", n_colors=len(cluster_ids)),
        data=df,
        legend="full",
        alpha=0.8
    )
    plt.title('K-Means clustering')
    plt.xlabel('t-SNE dimension 1')
    plt.ylabel('t-SNE dimension 2')
    plt.legend(title='Cluster')
    plt.show()

if __name__ == "__main__":
    df = load_data()
    [df_w_cluster, Xn] = k_mean_model(df)
    generate_cluster_samples(df_w_cluster)
    generate_plot(df_w_cluster, Xn)
    db.close()