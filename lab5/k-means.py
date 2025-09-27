import mysql.connector
import pandas as pd
import numpy as np
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.preprocessing import Normalizer
from sklearn.metrics import silhouette_score
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.manifold import TSNE
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import json
import joblib



db = mysql.connector.connect(
    host = "localhost",
    user = "root",
    password = "",
    database = ""
)

def clear_table():
    cursor = db.cursor()
    create_sql = '''
            CREATE TABLE IF NOT EXISTS clusters (
                cluster_id        INT PRIMARY KEY,
                keywords          JSON NOT NULL
            ) ENGINE=InnoDB
        '''
    create_sql_mes = '''
            CREATE TABLE IF NOT EXISTS clusters_messages (
                post_id         VARCHAR(20) PRIMARY KEY,
                cluster_id      INT,
                title           TEXT,
                content         TEXT,
                tsne_x          REAL,
                tsne_y          REAL
            ) ENGINE=InnoDB
        '''
    sql_c = "TRUNCATE TABLE clusters"
    sql_m = "TRUNCATE TABLE clusters_messages"
    cursor.execute(create_sql)
    cursor.execute(create_sql_mes)
    cursor.execute(sql_c)
    cursor.execute(sql_m)
    db.commit()
    print("[!] Table reddit_posts has been cleared.")
    cursor.close()

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

    joblib.dump(normalizer, "normalizer.joblib")
    joblib.dump(k_means, 'kmeans_model.joblib')
    return df, Xn

def generate_wordcloud(text, cluster_id):
    wordcloud = WordCloud(
        width=800, 
        height=400, 
        background_color='white',
        max_words=50,
        colormap='viridis'
    ).generate(text)
    
    plt.figure(figsize=(10, 5))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.title(f'Cluster {cluster_id} - Word Cloud')
    plt.axis('off')
    plt.tight_layout()
    plt.show()

def display_cluster_messages(df, cluster_id, keywords):
    cluster_df = df[df['cluster'] == cluster_id]
    
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
    print(f"\n{'-'*40}")

def generate_cluster_samples(df, Xn):
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
        cluster_texts = ' '.join(df[df['cluster'] == cluster_id]['full_text'])
        generate_wordcloud(cluster_texts, cluster_id)

        row = tfidf_matrix.toarray()[i]
        top_indices = row.argsort()[-5:][::-1]
        top_words = [feature_names[index] for index in top_indices]
        cluster_keywords[cluster_id] = top_words

    rows = []
    for cluster_id, keywords in cluster_keywords.items():
        keywords_json = json.dumps(keywords)
        rows.append((int(cluster_id), keywords_json))
    
    insert_sql = '''
            INSERT INTO clusters (cluster_id, keywords)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE keywords = VALUES(keywords)
        '''
    cursor = db.cursor()
    cursor.executemany(insert_sql, rows)
    db.commit()

    # plot
    tsne = TSNE(n_components=2, perplexity=30, max_iter=300, random_state=42)
    tsne_results = tsne.fit_transform(Xn)
    df['tsne_x'] = tsne_results[:, 0]
    df['tsne_y'] = tsne_results[:, 1]

    insert_sql_mes = '''
            INSERT INTO clusters_messages (post_id, cluster_id, title, content, tsne_x, tsne_y)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                cluster_id = VALUES(cluster_id),
                title = VALUES(title),
                content = VALUES(content),
                tsne_x = VALUES(tsne_x),
                tsne_y = VALUES(tsne_y)
        '''
    
    message_rows = []
    for _, row in df.iterrows():
        message_rows.append((
            row['id'],
            int(row['cluster']),
            row['title'],
            row['content'],
            float(row['tsne_x']),
            float(row['tsne_y'])
        ))
    cursor.executemany(insert_sql_mes, message_rows)
    db.commit()
    cursor.close()

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
    clear_table()
    df = load_data()
    [df_w_cluster, Xn] = k_mean_model(df)
    generate_cluster_samples(df_w_cluster, Xn)
    db.close()