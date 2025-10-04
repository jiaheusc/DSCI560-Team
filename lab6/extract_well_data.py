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
            address                     VARCHAR(128),

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
        INSERT INTO wells (filename, api, longitude_raw, latitude_raw, well_name, address)
        VALUES (%(filename)s, %(api)s, %(longitude)s, %(latitude)s, %(well_name)s, %(address)s)
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
        'address': None
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

    # latitude & longitude
    longitude_patterns = [
        r'Longitude:?\s*(-?\d+)°\s*(\d+)\'\s*([\d.]+)\"\s*([NSEW])',
        r'Longitude:?\s*(-?\d+)°\s*(\d+)\'\s*([\d.]+)\s*([NSEW])',
        r'\bLatitude of Well Head\s*:?\s*(-?\d+)°\s*([\d.]+)\"(?:\s*([NSEW]))?'
    ]

    for pattern in longitude_patterns:
        lon_match = re.search(pattern, text, re.IGNORECASE)
        if lon_match:
            parts = lon_match.groups()
            deg, min_val, sec_str = parts[0], parts[1], parts[2]
            direction = ""
            if len(parts) > 3 and parts[3]:
                direction = parts[3]
            else:
                direction = 'W'
            full_longitude = f"{deg}° {min_val}' {sec_str}\" {direction}".strip()
            data['longitude'] = full_longitude
            break
    
    latitude_patterns = [
        r'Latitude:?\s*(-?\d+)°\s*(\d+)\'\s*([\d.]+)\"\s*([NSEW])',
        r'Latitude:?\s*(-?\d+)°\s*(\d+)\'\s*([\d.]+)\s*([NSEW])',
        r'\bLatitude of Well Head\s*:?\s*(-?\d+)°\s*([\d.]+)\"(?:\s*([NSEW]))?'
    ]

    for pattern in latitude_patterns:
        lat_match = re.search(pattern, text, re.IGNORECASE)
        if lat_match:
            parts = lat_match.groups()
            deg, min_val, sec_str = parts[0], parts[1], parts[2]
            direction = ""
            if len(parts) > 3 and parts[3]:
                direction = parts[3]
            else:
                direction = 'N'
            full_latitude = f"{deg}° {min_val}' {sec_str}\" {direction}".strip()
            data['latitude'] = full_latitude
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
            well_name = well_name_match.group(1).strip()
            if well_name and (':' in well_name or '|' in well_name):
                continue
            data['well_name'] = well_name
            break

    # address   
    address_patterns = [
        r'Surface Location:?\s*([\d,\'"]+\s*F[NSEW]L\s*[&,]\s*[\d,\'"]+\s*F[NSEW]L(?:\s+[a-z\s,.-]*?(?:Sec\.|Section).*?)?)',
        r'Surface Location:?\s*([^\n]+?)\s*\n\s*Footages:?\s*([^\n]+?)(?=\s*(?:County|State:|Basin:|Well Type:|$))',
        r'Surface Location:?\s*([^\n]+?)(?=\s*(?:FIELD/ PROSPECT:|Footages:|County|, McKenzie|State:|API|ND Well|$))',
    ]

    for pattern in address_patterns:
        address_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if address_match:
            groups = address_match.groups()
            if len(groups) >= 2 and groups[1]:
                surface = ' '.join(groups[0].split())
                footages = ' '.join(groups[1].split())
                data['address'] = f"{footages} {surface}"
            else:
                data['address'] = ' '.join(groups[0].split())
            break
    
    upsert_well_data(data)

    

if __name__ == '__main__':
    directory_path = 'DSCI560_Lab5'
    clear_table()
    for filename in sorted(os.listdir(directory_path)):
        pdf_file_path = os.path.join(directory_path, filename)
        print(f"processing file: {pdf_file_path}")
        full_ocr_text = extract_text_from_pdf(pdf_file_path)
        well_info = parse_well_data(full_ocr_text, filename)