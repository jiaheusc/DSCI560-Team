import numpy as np
import pandas as pd
from gensim.models import Word2Vec
from sklearn.cluster import KMeans
from nltk.tokenize import word_tokenize
import mysql.connector
import nltk
import argparse
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
import matplotlib.pyplot as plt
from sklearn.preprocessing import normalize
from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score
from sklearn.metrics.pairwise import cosine_similarity
import os

def visualize_clusters(embeddings, labels, output_path="reddit_clusters_plot.png"):
    print("Visualizing clusters with PCA...")
    pca = PCA(n_components=2)
    reduced = pca.fit_transform(embeddings)

    plt.figure(figsize=(8, 6))
    scatter = plt.scatter(reduced[:, 0], reduced[:, 1], c=labels, cmap='tab10', s=50)
    plt.title("Reddit Post Clusters (PCA projection)")
    plt.xlabel("PCA 1")
    plt.ylabel("PCA 2")
    plt.colorbar(scatter, label="Cluster ID")
    plt.tight_layout()
    plt.savefig(output_path)
    print(f"Cluster visualization saved as {output_path}")

def visualize_clusters_tsne(Xn, labels, k, run_name, random_state=42):
    output_path = f"word2vec_plot_k{run_name}_tsne.png"
    print(f"Visualizing t-SNE word2vec (k={k})")

    tsne = TSNE(
        n_components=2,
        perplexity=30,
        metric="cosine",
        learning_rate="auto",
        init="pca",
        early_exaggeration=12.0,
        max_iter=1000,
        random_state=random_state
    )

    reduced = tsne.fit_transform(Xn)

    plt.figure(figsize=(12, 9))
    scatter = plt.scatter(reduced[:, 0], reduced[:, 1], c=labels, s=20, alpha=0.7)
    plt.title(f"t-SNE Visualization for word2vec '{run_name}' (k={k})")
    plt.xlabel("t-SNE Component 1")
    plt.ylabel("t-SNE Component 2")
    try:
        if k <= 10:
             handles, _ = scatter.legend_elements()
             plt.legend(handles, [f"Cluster {i}" for i in range(k)], title="Clusters")
        else:
            plt.colorbar(scatter, label="Cluster ID")
    except Exception:
         plt.colorbar(scatter, label="Cluster ID")
    plt.tight_layout()
    plt.savefig(output_path)
    print(f"t-SNE cluster visualization saved as {output_path}")
    plt.close()

def load_data_from_mysql():
# Connect to MySQL and load reddit_posts
    db = mysql.connector.connect(
    host = "localhost",
    user = "root",
    password = "DSCI560&team",
    database = "reddit_tech"
)
    query = "SELECT CONCAT_WS(' ', title, content) AS content FROM reddit_posts WHERE content IS NOT NULL;"
    df = pd.read_sql(query, db)
    db.close()
    print(f"Loaded {len(df)} posts from MySQL database 'reddit_tech.reddit_posts'.")
    return df['content'].astype(str).tolist()

def train_word2vec(tokenized_posts, vector_size=100):
    print(f"Training Word2Vec with {vector_size}-dimensional vectors...")
    model = Word2Vec(sentences=tokenized_posts, vector_size=vector_size, window=5, min_count=2, workers=4, sample=1e-4, seed=42)
    model.wv.fill_norms()
    return model

def find_optimal_k(X, k_range=range(2, 21)):
    silhouette_scores = []
    for k in k_range:
        kmeans = KMeans(n_clusters=k, init='k-means++', random_state=42, n_init=10)
        labels = kmeans.fit_predict(X)
        score = silhouette_score(X, labels, metric="cosine")
        silhouette_scores.append(score)
    
    best_k = k_range[np.argmax(silhouette_scores)]
    return best_k

def cluster_words(word_vectors, k):
    words = list(word_vectors.index_to_key)
    X = word_vectors[words]
    X = normalize(X, norm="l2", axis=1)
    print(f"Clustering {len(words)} word vectors into {k} bins...")
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    kmeans.fit(X)
    return {word: kmeans.labels_[i] for i, word in enumerate(words)}

def cluster_documents(embeddings, k):
    X = np.asarray(embeddings)
    km = KMeans(n_clusters=k, init='k-means++', random_state=42, n_init=10)
    labels = km.fit_predict(X)
    return np.asarray(labels).ravel(), km

def create_doc_vector(text, word_to_bin, k):
    tokens = word_tokenize(text.lower())
    bins = [word_to_bin.get(tok) for tok in tokens if tok in word_to_bin]
    vec = np.zeros(k, dtype=float)
    for b in bins:
        vec[b] += 1

    if len(bins) > 0:
        vec = vec / len(bins)

    return vec

def build_embeddings(posts, word_to_bin, k):
    print("Building document embeddings...")
    vectors = []
    labels = []
    for post in posts:
        vec = create_doc_vector(post, word_to_bin, k)
        vectors.append(vec)
        labels.append(int(np.argmax(vec)))  # Dominant bin label for each post
    return np.array(vectors), labels

def analyze_space(X):
    sim = cosine_similarity(X)
    np.fill_diagonal(sim, 0)
    print(f"mean={sim.mean():.3f}, std={sim.std():.3f}, max={sim.max():.3f}, min={sim.min():.3f}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--k', type=int, default=3, help='Number of clusters / embedding dimension')
    parser.add_argument('--output', type=str, default='./reddit_word2vec_embeddings.npy', help='Output .npy file')
    parser.add_argument('--labels', type=str, default='./reddit_clusters.csv', help='Output CSV file for labels')
    args = parser.parse_args()

    posts = load_data_from_mysql()
    tokenized_posts = [word_tokenize(p.lower()) for p in posts]

    w2v_model = train_word2vec(tokenized_posts, vector_size=100)
    word_vectors = w2v_model.wv
    word_to_bin = cluster_words(word_vectors, args.k)

    reddit_vectors, post_labels = build_embeddings(posts, word_to_bin, args.k)

    Xn = normalize(reddit_vectors, norm="l2", axis=1)
    best_k = find_optimal_k(Xn, k_range=range(2, 21))
    post_labels, _ = cluster_documents(Xn, best_k)

    np.save(args.output, reddit_vectors)
    pd.DataFrame({'post': posts, 'label': post_labels}).to_csv(args.labels, index=False)

    print(f"Embeddings saved to {args.output}")
    print(f"Cluster labels saved to {args.labels}")
    print(f"Embedding shape: {reddit_vectors.shape}")
    
    analyze_space(Xn)
    # visualize result using tsne and PCA
    # visualize_clusters(reddit_vectors, post_labels)
    visualize_clusters_tsne(Xn, post_labels, best_k, args.k)
    sil = silhouette_score(Xn, post_labels, metric="cosine")
    db  = davies_bouldin_score(Xn, post_labels)
    ch  = calinski_harabasz_score(Xn, post_labels)
    print(f"Silhouette score for k={args.k}: {sil:.4f}")
    print(f"Davies Bouldin score for k={args.k}: {db:.4f}")
    print(f"Calinski Harabasz score for k={args.k}: {ch:.4f}")


if __name__ == "__main__":
    main()
