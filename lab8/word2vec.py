import numpy as np
import pandas as pd
from gensim.models import Word2Vec
from sklearn.cluster import KMeans
from nltk.tokenize import word_tokenize
import mysql.connector
import nltk
import argparse
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt

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


def load_data_from_mysql():
# Connect to MySQL and load reddit_posts
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="reddit_tech"
    )
    query = "SELECT content FROM reddit_posts WHERE content IS NOT NULL;"
    df = pd.read_sql(query, db)
    db.close()
    print(f"Loaded {len(df)} posts from MySQL database 'reddit_tech.reddit_posts'.")
    return df['content'].astype(str).tolist()

def train_word2vec(tokenized_posts, vector_size=100):
    print(f"Training Word2Vec with {vector_size}-dimensional vectors...")
    model = Word2Vec(sentences=tokenized_posts, vector_size=vector_size, window=5, min_count=2, workers=4)
    return model

def cluster_words(word_vectors, k):
    words = list(word_vectors.index_to_key)
    X = word_vectors[words]
    print(f"Clustering {len(words)} word vectors into {k} bins...")
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    kmeans.fit(X)
    return {word: kmeans.labels_[i] for i, word in enumerate(words)}

def create_doc_vector(text, word_to_bin, k):
    tokens = word_tokenize(text.lower())
    bins = [word_to_bin.get(tok) for tok in tokens if tok in word_to_bin]
    vec = np.zeros(k)
    for b in bins:
        vec[b] += 1
        if len(bins) > 0:
            vec /= len(bins)
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

    np.save(args.output, reddit_vectors)
    pd.DataFrame({'post': posts, 'label': post_labels}).to_csv(args.labels, index=False)

    print(f"Embeddings saved to {args.output}")
    print(f"Cluster labels saved to {args.labels}")
    print(f"Embedding shape: {reddit_vectors.shape}")
    
    # visualize result using tsne and PCA
    visualize_clusters(reddit_vectors, post_labels)


if __name__ == "__main__":
    main()
