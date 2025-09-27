import mysql.connector
from gensim.models.doc2vec import Doc2Vec, TaggedDocument
import json
db = mysql.connector.connect(
    host = "localhost",
    user = "root",
    password = "DSCI560&team",
    database = "reddit_tech"
)

cursor = db.cursor()

cursor.execute("SELECT id, content, keywords, image_text FROM reddit_posts")
rows = cursor.fetchall()   # [(id, content, keywords, image_text), ...]

# Prepare documents for Doc2Vec 
documents = []
for row in rows:
    post_id, content, keywords, img_text = row
    parts = []
    if content and content.strip():
        parts.append(content)
    if keywords and keywords.strip():
        parts.append(keywords)
    if img_text and img_text.strip():
        parts.append(img_text)
    combined_text = " ".join(parts)

    if combined_text.strip():
        documents.append(TaggedDocument(words=combined_text.split(), tags=[post_id]))

# Train Doc2Vec model
model = Doc2Vec(vector_size=100, min_count=2, epochs=40)
model.build_vocab(documents)
model.train(documents, total_examples=model.corpus_count, epochs=model.epochs)
model.save("doc2vec.model")

# create embeddings table
cursor.execute("""
CREATE TABLE IF NOT EXISTS reddit_embeddings (
    id VARCHAR(20) PRIMARY KEY,
    embedding JSON
)
""")
db.commit()

# insert embeddings 
for row in rows:
    post_id, content, keywords, img_text = row
    parts = []
    if content and content.strip():
        parts.append(content)
    if keywords and keywords.strip():
        parts.append(keywords)
    if img_text and img_text.strip():
        parts.append(img_text)
    combined_text = " ".join(parts)

    if not combined_text.strip():
        continue

    vector = model.infer_vector(combined_text.split()).tolist()
    cursor.execute(
        "REPLACE INTO reddit_embeddings (id, embedding) VALUES (%s, %s)",
        (post_id, json.dumps(vector))
    )
db.commit()


print("Embeddings inserted into reddit_embeddings")

cursor.close()
db.close()
