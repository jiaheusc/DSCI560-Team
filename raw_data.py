import time, datetime
import mysql.connector as mysql
import yfinance as yf
import pandas as pd
import time
from datetime import timezone

db_config = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "",
    "autocommit": True
}


def get_connection():
    try:
        connection = mysql.connect(**db_config)
        if connection.is_connected():
            return mysql.connect(**db_config)
    except Exception as e:
        print(f"Error: {e}")
        return None
    except mysql.Error as e:
        print("MySQL Error:", e)

def get_all_tickers(connection):
    cursor = connection.cursor()

    sql_query = "SELECT ticker FROM stocks;"
    cursor.execute(sql_query)
    results = cursor.fetchall()
    return [item[0] for item in results]

def fetch_last_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        stock_info = stock.fast_info
        if not stock_info or stock_info.last_price is None:
            return None
        return stock_info
    except Exception as e:
        print(f"Error: {e}")
        return None
    
def utc_now_in_sec():
    return datetime.datetime.now(timezone.utc).replace(microsecond=0)

def get_stock_id(connection, ticker):
    cursor = connection.cursor()
    cursor.execute("SELECT stock_id FROM stocks WHERE ticker=%s", (ticker,))
    row = cursor.fetchone()
    cursor.close()
    return row[0] if row else None

def upsert_stock_price(connection, stock_id, price, volume, ts_sec):
    sql = """
        INSERT INTO stock_price (stock_id, `timestamp`, price, volume)
        VALUES (%s, %s, %s, %s)
    """
    cursor = connection.cursor()
    cursor.execute(sql, (stock_id, ts_sec, float(price), volume))
    cursor.close()

def fetch_real_time_price(tickers, poll_seconds, connection):
    try:
        while True:
            for ticker in tickers:
                stock_info = fetch_last_price(ticker)
                if stock_info is not None:
                    stock_id = get_stock_id(connection, ticker)
                    price = stock_info.last_price
                    volume = stock_info.last_volume
                    ts_sec = utc_now_in_sec()
                    upsert_stock_price(connection, stock_id, price, volume, ts_sec)
                else:
                    print("no last_price")
            time.sleep(poll_seconds)
    finally:
        connection.close()

# at most 7 days
def fetch_today_price(tickers):
    try:
        # can change to period="7d" for the first time
        data = yf.download(tickers, period="1d", interval="1m", group_by='ticker')
        if data.empty:
            print("No today stock price data")
            return None
        return data
    except Exception as e:
        print(f"Error: {e}")
        return None


if __name__ == "__main__":
    connection = get_connection()
    tickers = get_all_tickers(connection)
    
    # use fast_info
    poll_seconds = 30
    fetch_real_time_price(tickers, poll_seconds, connection)
    
    # use download
    # today_data = fetch_today_price(tickers)
    # print(today_data)
    # connection.close()
