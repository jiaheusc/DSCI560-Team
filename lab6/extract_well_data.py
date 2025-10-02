import mysql.connector
import re
from pdf2image import convert_from_path
import pytesseract
import os

db = mysql.connector.connect(
    host = "localhost",
    user = "root",
    password = os.getenv("DB_PASSWORD"),
    database = "DS560Team6"
)

def clear_table():
    cursor = db.cursor()
    well_create_sql = '''
        CREATE TABLE IF NOT EXISTS wells (
            id                          INT PRIMARY KEY AUTO_INCREMENT,
            filename                    VARCHAR(255) NOT NULL,
            api                         VARCHAR(32) UNIQUE,
            longitude_raw               VARCHAR(32),
            latitude_raw                VARCHAR(32),
            well_name                   VARCHAR(128),
            street                      VARCHAR(128),
            city                        VARCHAR(32),
            state                       CHAR(2),
            zipcode                     VARCHAR(10),

            well_status                 VARCHAR(64),
            well_type                   VARCHAR(64),
            closest_city                VARCHAR(128),
            latest_oil_production_bbl   INT,
            latest_gas_production_mcf   DECIMAL(10, 2),
            latest_production_date      VARCHAR(64)
        );
    '''
    sql_w = "TRUNCATE TABLE wells"

    cursor.execute(well_create_sql)
    cursor.execute(sql_w)
    db.commit()
    cursor.close()


def extract_text_from_pdf(pdf_path):
    try:
        images = convert_from_path(pdf_path, dpi=150, grayscale=True)
        page_limit = 160
        total_pages = len(images)
        pages_to_process = total_pages

        full_text = ""
        if page_limit and page_limit < total_pages:
            pages_to_process = page_limit

        for i in range(pages_to_process):
            image = images[i]
            full_text += pytesseract.image_to_string(image) + "\n"
        print("finish extract text from pdf")
        return full_text
    except Exception as e:
        print(f"Error: {e}")
        return ""

def upsert_well_data(data):
    cursor = db.cursor()
    sql = '''
        INSERT INTO wells (filename, api, longitude_raw, latitude_raw, well_name, street, city, state, zipcode)
        VALUES (%(filename)s, %(api)s, %(longitude)s, %(latitude)s, %(well_name)s, %(street)s, %(city)s, %(state)s, %(zipcode)s)
    '''
    cursor.execute(sql, data)
    db.commit()
    cursor.close()


def parse_well_data(text, filename):
    data = {
        'filename': filename,
        'api': None,
        'longitude': None,
        'latitude': None,
        'well_name': None,
        'street': None, 
        'city': None, 
        'state': None, 
        'zipcode': None
    }

    # api
    api_patterns = [
        r"\bAPI(?:\s*(?:No\.?|Number))?\s*[:#]?\s*(\d{2}[-\s]?\d{3}[-\s]?\d{5})\b",
        r"\bAPI\s*#\s*(\d{2}[-\s]?\d{3}[-\s]?\d{5})\b",
        r"\b(\d{2}-\d{3}-\d{5})\b"
    ]
    for pattern in api_patterns:
        api_match = re.search(pattern, text, re.IGNORECASE)
        if api_match:
            data["api"] = api_match.group(1)
            break

    upsert_well_data(data)

    

if __name__ == '__main__':
    directory_path = 'DSCI560_Lab5'
    for filename in sorted(os.listdir(directory_path)):
        pdf_file_path = os.path.join(directory_path, filename)
        print(f"processing file: {pdf_file_path}")
        full_ocr_text = extract_text_from_pdf(pdf_file_path)
        well_info = parse_well_data(full_ocr_text)