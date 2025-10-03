import mysql.connector
import re
from pdf2image import convert_from_path, pdfinfo_from_path
import multiprocessing
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

def ocr_page(image):
    return pytesseract.image_to_string(image)

def extract_text_from_pdf(pdf_path):
    try:
        batch_size = 50
        info = pdfinfo_from_path(pdf_path)
        total_pages = info["Pages"]
        text_chunks = []
        for i in range(1, total_pages + 1, batch_size):
            first_page = i
            last_page = min(i + batch_size - 1, total_pages)
            images_batch = convert_from_path(
                pdf_path,
                # dpi=150,
                first_page=first_page,
                last_page=last_page,
                # use_threads=True 
            )
            with multiprocessing.Pool() as pool:
                results = pool.map(ocr_page, images_batch)
            
            text_chunks.append("\n".join(results))

        return "\n".join(text_chunks)
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
    
    # well name
    well_name_patterns = [
        r'\bWell\sName(?:(?:\s+and)?\s+Number)?\s*[:\n]\s*([^\n\r]+)',
        r'Well Name and Number\s*\n\s*([A-Za-z0-9&\.\-\s]+)(?=\s*\n\s*(?:Qtr-Qtr|Section|Operator|Location|Footages|Field|Address|County|API|Total))',
        r'Well Name and Number\s*\n\s*(.+)',
        r'Well Name:\s*([^\n]+)'
    ]

    for pattern in well_name_patterns:
        well_name_match = re.search(pattern, text)
        if well_name_match:
            data['well_name'] = well_name_match.group(1).strip()
            break

    upsert_well_data(data)

    

if __name__ == '__main__':
    directory_path = 'DSCI560_Lab5'
    for filename in sorted(os.listdir(directory_path)):
        pdf_file_path = os.path.join(directory_path, filename)
        print(f"processing file: {pdf_file_path}")
        full_ocr_text = extract_text_from_pdf(pdf_file_path)
        well_info = parse_well_data(full_ocr_text)