import mysql.connector
import requests
from bs4 import BeautifulSoup
import time
import re
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="DS560Team6"
)
cursor = db.cursor(dictionary=True)

cursor.execute("SELECT id, api FROM wells WHERE api IS NOT NULL")
apis = cursor.fetchall()

HEADERS = {
    "User-Agent": "linux:lab5:v1.0 (by u/jiahecai)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
def get_html(url):
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.text
def parse_latlon(text):
    t = " ".join(str(text).split())
    m = re.search(r'(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)', t)
    if m:
        lat = m.group(1); lon = m.group(2)
        try:
            lat_dec = float(lat); lon_dec = float(lon)
        except ValueError:
            lat_dec = lon_dec = None
        return lat, lon, lat_dec, lon_dec
def parse_number(value):
    val = str(value).lower().replace(",", "").strip()
    
    try:
        if val.endswith("k"):  # e.g. '1.2k' => 1200
            return int(float(val[:-1]) * 1000)
        else:
            return int(float(val))
    except Exception:
        return None
        
def scrape_well_info(api_no):
    api_no = api_no.replace("-", "").strip()
    
    search_url = f"https://www.drillingedge.com/search?type=wells&operator_name=&well_name=&api_no={api_no}"
    print(search_url)
    html = get_html(search_url)
    soup = BeautifulSoup(html, "html.parser")

    # Find well name <a> link
    link_tag = soup.select_one("td a[href*='/wells/']")
    if not link_tag:
        print(f"[WARN] API {api_no} not found.")
        return None

    well_link = link_tag["href"]
    if not well_link.startswith("http"):
        well_link = "https://www.drillingedge.com" + well_link

    # detail page
    detail_html = get_html(well_link)
    detail_soup = BeautifulSoup(detail_html, "html.parser")

    # Extract Well Status, Well Type, Closest City
    def extract_value(th_text):
        th = detail_soup.find("th", string=th_text)
        if th:
            td = th.find_next("td")
            return td.get_text(strip=True) if td else None
        return None
    well_name = extract_value("Well Name")
    well_status = extract_value("Well Status")
    well_type = extract_value("Well Type")
    closest_city = extract_value("Closest City")
    latlon_text = extract_value("Latitude / Longitude")
    lat_raw, lon_raw, lat_dec, lon_dec = parse_latlon(latlon_text)
    
    oil_prod, gas_prod = None, None
    for p in detail_soup.select("p.block_stat"):
        text = p.get_text(strip=True)
        if "Barrels of Oil Produced" in text:
            oil_prod = p.find("span", class_="dropcap").get_text(strip=True)
        elif "MCF of Gas Produced" in text:
            gas_prod = p.find("span", class_="dropcap").get_text(strip=True)

    return {
        "name": well_name,
        "status": well_status,
        "type": well_type,
        "city": closest_city,
        "oil_prod": oil_prod,
        "gas_prod": gas_prod,
        "lat_raw": lat_raw,
        "lon_raw": lon_raw,
        "lat_dec": lat_dec,
        "lon_dec": lon_dec,
    }

# Loop over APIs & update MySQL 
update_sql = """
    UPDATE wells
    SET well_name=%s,well_status=%s, well_type=%s, closest_city=%s,
        latest_oil_production_bbl=%s, latest_gas_production_mcf=%s,latitude_raw=%s,
        longitude_raw=%s
    WHERE id=%s
"""


for row in apis:
    api = row["api"]
    print(f"Scraping API: {api} ...")

    data = scrape_well_info(api)
    if data:
        cursor.execute(update_sql, (data["name"],data["status"], data["type"], data["city"],parse_number(data["oil_prod"]),
        parse_number(data["gas_prod"]),data["lat_raw"],
        data["lon_raw"], row["id"]))
        db.commit()
        print(f"  ✅ Updated {api}: {data}")
    time.sleep(1)  

cursor.close()
db.close()

