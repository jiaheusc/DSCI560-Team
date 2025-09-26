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
import pytesseract
from PIL import Image
import requests
from io import BytesIO
from urllib.parse import urlparse
#run once
nltk.download('punkt')
nltk.download('stopwords')
nltk.download('punkt_tab')

db = mysql.connector.connect(
    host = "localhost",
    user = "root",
    password = "DSCI560&team",
    database = "reddit_tech"
)

cursor = db.cursor()


reddit = praw.Reddit(
    client_id = "G65tr8NzM-5oR0vrnHLw5A",    
    client_secret = "688TvEkmV-RJrLkx6oXaZlWcosq0yA", 
    user_agent = "linux:lab5:v1.0 (by u/jiahecai)"
)
HEADERS = {
    "User-Agent": "linux:lab5:v1.0 (by u/jiahecai)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
def fetch_url_content(url, timeout=10):
    """
    Try to extract readable content from an arbitrary URL.
    Returns (content_text, content_type, notes)
    """
    try:
        # quick sanitize
        if not url or url.strip() == "":
            return "", "empty", "no url"

        parsed = urlparse(url)
        host = parsed.netloc.lower()

        # 1) quick decision by extension
        lower = url.lower()
        if lower.endswith((".pdf",)):
            return extract_pdf_text(url, timeout), "pdf", "pdf by ext"

        if lower.endswith((".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")):
            # image: OCR
            return extract_image_text(url, timeout), "image", "ocr by ext"

        # 2) request page (allow redirects)
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        content_type = resp.headers.get("Content-Type", "").lower()

        # if the response is a PDF served with content-type
        if "application/pdf" in content_type:
            return extract_pdf_from_bytes(resp.content), "pdf", "pdf by content-type"

        # if image mime
        if content_type.startswith("image/"):
            return ocr_from_bytes(resp.content), "image", "ocr by mime"

        # handle HTML pages
        if "text/html" in content_type or "application/xhtml+xml" in content_type:
            html = resp.text

            # try newspaper3k (best for article pages)
            try:
                art = Article(url)
                art.set_html(html)
                art.parse()
                text = art.text.strip()
                if len(text) > 50:
                    return clean_text(text), "article", "newspaper3k"
            except Exception:
                pass

            # fallback: readability-like approach: try <article>, then big <p> blocks, then meta description
            soup = BeautifulSoup(html, "html.parser")

            # 1) <article>
            article_tag = soup.find("article")
            if article_tag:
                text = article_tag.get_text(separator=" ", strip=True)
                if len(text) > 40:
                    return clean_text(text), "article", "article tag"

            # 2) meta description
            meta = soup.find("meta", {"name": "description"})
            if meta and meta.get("content"):
                desc = meta["content"].strip()
                if len(desc) > 20:
                    return clean_text(desc), "meta", "meta description"

            # 3) collect long paragraph blocks (heuristic)
            paragraphs = [p.get_text(separator=" ", strip=True) for p in soup.find_all("p")]
            long_paras = [p for p in paragraphs if len(p) > 80]
            if long_paras:
                text = "\n\n".join(long_paras[:8])
                return clean_text(text), "html_paragraphs", "p tags"

            # 4) fallback: full text (may be noisy)
            full = soup.get_text(separator=" ", strip=True)
            if len(full) > 40:
                return clean_text(full)[:2000], "full_text", "fallback full text"

            return "", "empty", "no extracted text"

        # unknown content-type -> return empty
        return "", "unknown", f"content-type:{content_type}"

    except requests.exceptions.RequestException as e:
        return "", "error", f"request failed: {e}"
    except Exception as e:
        return "", "error", f"extract error: {e}"

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


def extract_text_from_image(url):
    try:
        response = requests.get(url, timeout=10)
        img = Image.open(BytesIO(response.content))
        text = pytesseract.image_to_string(img)
        return clean_text(text)
    except Exception as e:
        print(f"[!] OCR failed for {url}: {e}")
        return ""



def fetch_reddit(total_post):
    tech_sub = reddit.subreddit('tech')
    max_limit = 1000
    fetched = 0
    last_post = None

    while fetched < total_post: 
        remaining = total_post - fetched
        limit = min(max_limit, remaining)

        posts = tech_sub.hot(limit=limit, params={"after": last_post})

        print(f'fetching and saving {limit} posts')

        for post in posts:
            post_id = post.id
            title = clean_text(post.title)
            author = mask_username(str(post.author))
            timestamp = datetime.fromtimestamp(post.created_utc)

            # 1️⃣ Start with selftext
            content = clean_text(post.selftext)

            # 2️⃣ If no selftext, try to fetch from URL
            if not content.strip():
                extracted, ctype, note = fetch_url_content(post.url)
                if extracted.strip():
                    content = extracted
                else:
                    # fallback: at least keep the URL
                    content = f"URL: {post.url} (no text extracted, note={note})"

            # 3️⃣ Handle image OCR separately (optional, you already do this)
            image_text = ""
            if post.url.lower().endswith((".jpg", ".jpeg", ".png")):
                image_text = extract_text_from_image(post.url)

            # 4️⃣ Build combined content for keyword extraction
            combined_content = f"{title} {content} {image_text}"
            keywords = extract_keywords(combined_content)

            # 5️⃣ Insert into DB
            sql_query = """
            INSERT IGNORE INTO reddit_posts (id, title, content, author_masked, timestamp, keywords, image_text)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql_query, (post_id, title, content, author, timestamp, keywords, image_text))
            db.commit()

            last_post = post.name
            fetched += 1

        if fetched == total_post:
            print('extract all the posts')
            break  
        else:
            print(f'right now already fetched {fetched} posts')

def clear_table():
    sql = "TRUNCATE TABLE reddit_posts"
    cursor.execute(sql)
    db.commit()
    print("[!] Table reddit_posts has been cleared.")

if __name__ == "__main__":

    num = int(sys.argv[1])
    clear_table() 
    fetch_reddit(num)

    cursor.close()
    db.close()





    
