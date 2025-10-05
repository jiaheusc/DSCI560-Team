import mysql.connector
import re
from pdf2image import convert_from_path, pdfinfo_from_path
import multiprocessing
import pytesseract
from datetime import datetime
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
    stimulations_create_sql = '''
        CREATE TABLE IF NOT EXISTS stimulations (
            id                          INT PRIMARY KEY AUTO_INCREMENT,
            api                         VARCHAR(32) UNIQUE,
            date_stimulated             DATE,
            stimulated_formation        VARCHAR(128),
            top_ft                      INT,
            bottom_ft                   INT,
            stimulation_stages          INT,
            volume                      INT,
            volume_units                VARCHAR(64),
            type_treatment              VARCHAR(128),
            acid_percentage             DECIMAL(5, 2),
            lbs_proppant                BIGINT,
            max_treatment_pressure_psi  DECIMAL(10, 2),
            max_treatment_rate_bbls_min DECIMAL(10, 2),
            details                     TEXT
        );
    '''
    sql_w = "TRUNCATE TABLE wells"
    sql_s = "TRUNCATE TABLE stimulations"

    cursor.execute(well_create_sql)
    cursor.execute(stimulations_create_sql)
    cursor.execute(sql_w)
    cursor.execute(sql_s)
    db.commit()
    cursor.close()

def ocr_page(image):
    return pytesseract.image_to_string(image)

def extract_text_from_pdf(pdf_path):
    try:
        batch_size = 50
        info = pdfinfo_from_path(pdf_path)
        total_pages = info["Pages"]

        stimulation_pages = []
        text_chunks = []
        for i in range(1, total_pages + 1, batch_size):
            first_page = i
            last_page = min(i + batch_size - 1, total_pages)
            images_batch = convert_from_path(
                pdf_path,
                first_page=first_page,
                last_page=last_page,
                # use_threads=True 
            )
            
            with multiprocessing.Pool() as pool:
                results = pool.map(ocr_page, images_batch)

            for page_offset, text in enumerate(results):
                current_page = first_page + page_offset
                if re.search(r"well\s+specific\s+stimulations", text, re.IGNORECASE):
                    stimulation_pages.append(current_page)
                    
        
            text_chunks.append("\n".join(results))
        full_text = "\n".join(text_chunks)
        return full_text, stimulation_pages
    except Exception as e:
        print(f"Error: {e}")
        return ""


def upsert_well_data(data):
    cursor = db.cursor()
    sql = """ INSERT INTO wells (
        filename, api, longitude_raw, latitude_raw, well_name, address
    ) VALUES (
        %(filename)s, %(api)s, %(longitude)s, %(latitude)s, %(well_name)s, %(address)s
    ) AS new
        ON DUPLICATE KEY UPDATE
        wells.filename      = COALESCE(NULLIF(new.filename, ''), wells.filename),
        wells.longitude_raw = COALESCE(NULLIF(new.longitude_raw, ''), wells.longitude_raw),
        wells.latitude_raw  = COALESCE(NULLIF(new.latitude_raw, ''), wells.latitude_raw),
        wells.well_name     = COALESCE(NULLIF(new.well_name, ''), wells.well_name),
        wells.address       = COALESCE(NULLIF(new.address, ''), wells.address);
    """
    cursor.execute(sql, data)
    db.commit()
    cursor.close()

def upsert_stimulations_data(data):
    cursor = db.cursor()
    sql = """
        INSERT INTO stimulations (
            api, date_stimulated, stimulated_formation, top_ft, bottom_ft, 
            stimulation_stages, volume, volume_units, type_treatment, acid_percentage, 
            lbs_proppant, max_treatment_pressure_psi, max_treatment_rate_bbls_min, details
        ) 
        VALUES (%(api)s, %(date_stimulated)s, %(stimulated_formation)s, %(top_ft)s, %(bottom_ft)s,
            %(stimulation_stages)s, %(volume)s, %(volume_units)s, %(type_treatment)s, %(acid_percentage)s,
            %(lbs_proppant)s, %(max_treatment_pressure_psi)s, %(max_treatment_rate_bbls_min)s, %(details)s
        ) AS new
            ON DUPLICATE KEY UPDATE
            stimulations.date_stimulated             = COALESCE(new.date_stimulated, stimulations.date_stimulated),
            stimulations.stimulated_formation        = COALESCE(NULLIF(new.stimulated_formation, ''), stimulations.stimulated_formation),
            stimulations.top_ft                      = COALESCE(new.top_ft, stimulations.top_ft),
            stimulations.bottom_ft                   = COALESCE(new.bottom_ft, stimulations.bottom_ft),
            stimulations.stimulation_stages          = COALESCE(new.stimulation_stages, stimulations.stimulation_stages),
            stimulations.volume                      = COALESCE(new.volume, stimulations.volume),
            stimulations.volume_units                = COALESCE(NULLIF(new.volume_units, ''), stimulations.volume_units),
            stimulations.type_treatment              = COALESCE(NULLIF(new.type_treatment, ''), stimulations.type_treatment),
            stimulations.acid_percentage             = COALESCE(new.acid_percentage, stimulations.acid_percentage),
            stimulations.lbs_proppant                = COALESCE(new.lbs_proppant, stimulations.lbs_proppant),
            stimulations.max_treatment_pressure_psi  = COALESCE(new.max_treatment_pressure_psi, stimulations.max_treatment_pressure_psi),
            stimulations.max_treatment_rate_bbls_min = COALESCE(new.max_treatment_rate_bbls_min, stimulations.max_treatment_rate_bbls_min),
            stimulations.details                     = COALESCE(NULLIF(new.details, ''), stimulations.details)
    """
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
    if not data["api"]:
        return None
    
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
    return data['api']

PAT_LINE1_1 = re.compile(
    r"""
        ^\s*
        (?: (?P<date>\d{1,2}/\d{1,2}/\d{4}) )?
        \s*
        (?: (?P<form>[A-Za-z][A-Za-z \-/]*) )?
        [^\d\n\r]*?
        (?: (?P<top>\d{1,6}) )?
        [^\d\n\r]*?
        (?: (?P<bottom>\d{1,6}) )?
        \s*
        (?: (?P<stage>[A-Za-z][A-Za-z \-/]*) )?
        \s*
        (?: (?P<vol>\d{1,3}(?:,\d{3})*|\d+) )?
        \s*
        (?: (?P<unit>[A-Za-z]+) )?
        \s*$
    """,
    re.VERBOSE
)

PAT_LINE1_2 = re.compile(
    r"""
        ^\s*
        (?: (?P<date>\d{1,2}/\d{1,2}/\d{4}) )?
        \s*
        (?: (?P<form>[A-Za-z][A-Za-z \-/]*) )?
        [^\d\n\r]*?
        (?: (?P<top>\d{1,6}) )?
        [^\d\n\r]*?
        (?: (?P<bottom>\d{1,6}) )?
        [^\d\n\r]*?
        (?: (?P<stage>\d+) )?
        [^\d\n\r]*?
        (?: (?P<vol>\d{1,3}(?:,\d{3})*|\d+) )?
        \s*
        (?: (?P<unit>[A-Za-z]+) )?
        \s*$
    """,
    re.VERBOSE
)

PAT_LINE1_FALLBACK = re.compile(
    r"""
        ^\s*
        (?: (?P<date>\d{1,2}/\d{1,2}/\d{4}) )?
        \s*
        (?: (?P<form>[A-Za-z][A-Za-z \-/]*) )?
    """,
    re.VERBOSE
)

PAT_LINE2 = re.compile(
    r"""
        ^\s*
        (?P<type>[A-Za-z][A-Za-z \. \-/]*?)?
        [\s|_,;:]*
        (?P<lbs>\d{1,3}(?:,\d{3})*|\d+)?
        [\s|_,;:]*
        (?P<maxp>\d+(?:\.\d+)?)?
        [\s|_,;:]*
        (?P<rate>\d+(?:\.\d+)?)?
        [\s|_,;:]*$
    """,
    re.VERBOSE
)

def to_int_safe(s):
    if not s:
        return None
    digits = re.sub(r"[^\d]", "", str(s))
    return int(digits) if digits else None

def to_float_safe(s):
    if s is None:
        return None
    try:
        return float(str(s).strip())
    except ValueError:
        return None

def to_string_safe(s):
    if s is None:
        return None
    s_stripped = s.strip()
    if not s_stripped:
        return None
    return s_stripped

def to_date_safe(s):
    if s is None:
        return None
    s_stripped = s.strip()
    if not s_stripped:
        return None
    try:
        dt_object = datetime.strptime(s_stripped, '%m/%d/%Y')
        return dt_object.date()
    except ValueError:
        return None

    
def parse_positional_stimulation_record(text) -> dict | None:

    lines = text.splitlines()
    rec1 = {}
    rec2 = {}

    for i, line in enumerate(lines):

        if line.strip().startswith("Date Stimulated"):
            value_line1 = lines[i+1]
            if not value_line1:
                break
            value1 = value_line1.translate(str.maketrans('', '', '[|;!_'))
            m1_1 = PAT_LINE1_1.match(value1)
            if m1_1:
                g1 = m1_1.groupdict()
                rec1 = {
                    "Date Stimulated": to_date_safe(g1["date"]),
                    "Stimulated Formation": to_string_safe(g1["form"]),
                    "Top Ft": to_int_safe(g1["top"]),
                    "Bottom Ft": to_int_safe(g1["bottom"]),
                    "Stimulation Stages": None,
                    "Volume": to_int_safe(g1.get("vol")),
                    "Volume Units": to_string_safe(g1["unit"]),
                }
            else:
                m1_2 = PAT_LINE1_2.match(value1)
                if (m1_2):
                    g1 = m1_2.groupdict()
                    rec1 = {
                        "Date Stimulated": to_date_safe(g1["date"]),
                        "Stimulated Formation": to_string_safe(g1["form"]),
                        "Top Ft": to_int_safe(g1["top"]),
                        "Bottom Ft": to_int_safe(g1["bottom"]),
                        "Stimulation Stages": to_int_safe(g1["stage"]),
                        "Volume": to_int_safe(g1.get("vol")),
                        "Volume Units": to_string_safe(g1["unit"]),
                    }
                else:
                    fallback_match = PAT_LINE1_FALLBACK.match(value_line1)
                    if fallback_match:
                        parsed_data1 = fallback_match.groupdict()
                        rec1 = {
                            "Date Stimulated": to_date_safe(parsed_data1["date"]),
                            "Stimulated Formation": to_string_safe(parsed_data1["form"]),
                            "Top Ft": None,
                            "Bottom Ft": None,
                            "Stimulation Stages": None,
                            "Volume": None,
                            "Volume Units": None,
                        }
                    else:
                        rec1 = {
                            "Date Stimulated": None,
                            "Stimulated Formation": None,
                            "Top Ft": None,
                            "Bottom Ft": None,
                            "Stimulation Stages": None,
                            "Volume": None,
                            "Volume Units": None,
                        }
                        continue


        if line.strip().startswith("Type Treatment"):
            value_line2 = lines[i+1]
            if not value_line2:
                break
            value2 = value_line2.translate(str.maketrans('', '', '|;!_'))

            m2 = PAT_LINE2.match(value2)

            if m2:
                g2 = m2.groupdict()
                rec2 = {
                    "Type Treatment": to_string_safe(g2["type"]),
                    "Acid Percentage": None,
                    "Lbs Proppant": to_int_safe(g2["lbs"]),
                    "Max Treatment Pressure PSI": to_float_safe(g2["maxp"]),
                    "Max Treatment Rate BBLS Min": to_float_safe(g2["rate"])
                }
            else:
                rec2 = {
                    "Type Treatment": None,
                    "Acid Percentage": None,
                    "Lbs Proppant": None,
                    "Max Treatment Pressure PSI": None,
                    "Max Treatment Rate BBLS Min": None
                }
        
        if rec1 and rec2:
            break

    if not rec1:
        rec1 = {
            "Date Stimulated": None,
            "Stimulated Formation": None,
            "Top Ft": None,
            "Bottom Ft": None,
            "Stimulation Stages": None,
            "Volume": None,
            "Volume Units": None,
        }
    if not rec2:
        rec2 = {
            "Type Treatment": None,
            "Acid Percentage": None,
            "Lbs Proppant": None,
            "Max Treatment Pressure PSI": None,
            "Max Treatment Rate BBLS Min": None
        }
    
    final_record = rec1 | rec2
    details_pattern = re.compile(r"Details\s*(.*?) (?=\s*(?: Date\s+Stimulated | Stimulated\s+Formation | Type\s+Treatment | \Z))", re.IGNORECASE | re.VERBOSE | re.DOTALL)
    details_match = details_pattern.search(text) 
    if details_match:
        details_text = details_match.group(1)
        details_text = details_text.translate(str.maketrans('', '', '|'))
        final_record["Details"] = details_text.strip()
    else:
        final_record["Details"] = None

    snake_case_record = {key.lower().replace(' ', '_').replace('(', '').replace(')', ''): val for key, val in final_record.items()}

    return snake_case_record if final_record else None

def extract_stimulation(pdf_path, page_num):
    images = convert_from_path(
        pdf_path,
        dpi=300,
        first_page=page_num,
        last_page=page_num
    )
    image = images[0]
    
    page_text = pytesseract.image_to_string(image)

    record = parse_positional_stimulation_record(page_text)
    return record


if __name__ == '__main__':
    directory_path = 'DSCI560_Lab5'
    clear_table()

    for filename in sorted(os.listdir(directory_path)):
        pdf_file_path = os.path.join(directory_path, filename)
        print(f"processing file: {pdf_file_path}")
        full_ocr_text, stimulation_pages = extract_text_from_pdf(pdf_file_path)
        well_api = parse_well_data(full_ocr_text, filename)
        if stimulation_pages and well_api:
            record = extract_stimulation(pdf_file_path, stimulation_pages[0])
            if record:
                record["api"] = well_api
                upsert_stimulations_data(record)
            else:
                print("no stimulation record")
        print(f"finish processing {pdf_file_path}")
        