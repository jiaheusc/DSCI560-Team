import praw
import mysql.connector
from datetime import datetime
from bs4 import BeautifulSoup
import re
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from collections import Counter
import sys

#run once
nltk.download('punkt')
nltk.download('stopwords')

db = mysql.connector.connect(
    host = "localhost",
    user = "",
    password = "",
    database = "reddit_tech"
)

cursor = db.cursor()


reddit = praw.Reddit(
    client_id = "Dry_Wrongdoer3477",    
    client_secret = "MLSyPOBc8GCT2gk_8Yk6B-jaJS9swQ", 
    user_agent = "Lab5"
)

def clean_text(raw_text):
    soup = BeautifulSoup(raw_text, "html.parser")
    text = soup.get_text()
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)
    return " ".join(text.split())

#mask name
def mask_username(username):
    if username is None:
        return "anonymous"
    return "user_" + str(abs(hash(username)) % 10000)

#extract top five frequent keywords
def extract_keywords(text, top_n = 5):
    words = word_tokenize(text.lower())
    words = [w for w in words if w.isalpha() and w not in stopwords.words("english")]
    freq = Counter(words)
    return ",".join([w for w, _ in freq.most_common(top_n)])




def fetch_reddit(total_post):
    tech_sub = reddit.subreddit('tech')
    max_limit = 1000
    #max_time = 60
    fetched = 0
    last_post = None

    while fetched < total_post: 
        remaining = total_post - fetched
        limit = min(max_limit, remaining)

        posts = tech_sub.hot(limit=limit, params={"after": last_post})

        for post in posts:
            post_id = post.id
            title = clean_text(post.title)
            content = clean_text(post.selftext)
            author = mask_username(str(post.author))
            timestamp = datetime.fromtimestamp(post.created_utc)

            title_content = f"{title} {content}"
            keywords = extract_keywords(title_content )

            
            sql_query = """
            INSERT IGNORE INTO reddit_posts (id, title, content, author_masked, timestamp, keywords)
            VALUES (%s, %s, %s, %s, %s, %s)
            """

            cursor.execute(sql_query, (post_id, title, content, author, timestamp, keywords))
            db.commit()

            last_post = post.name
            fetched += 1

        if fetched == total_post:
            print('extract all the posts')
            break  
        else:
            print(f'right now fetched {fetched} posts')


if __name__ == "__main__":

    num = int(sys.argv[1])

    fetch_reddit(num)

    cursor.close()
    db.close()





    