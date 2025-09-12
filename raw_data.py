import time
import mysql.connector as mysql
import yfinance as yf
import pandas as pd

db_config = {
            'host': 'localhost',
            'user': 'root',
            'password': '',     # your mysql password
            'database': ''      # your database
        }

def get_connection():
    try:
        connection = mysql.connect(**db_config)
        if connection.is_connected():
            return mysql.connect(**db_config)
    except Exception as e:
        print(f"Error: {e}")
        return None

def get_all_tickers(connection):
    cursor = connection.cursor()

    sql_query = "SELECT ticket FROM stocks;"
    cursor.execute(sql_query)
    results = cursor.fetchall()
    return [item[0] for item in results]

def fetch_last_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        # stock_info = stock.info
        stock_info = stock.fast_info
        if not stock_info or stock_info.last_price is None:
            return None
        return stock_info
    except Exception as e:
        print(f"Error: {e}")
        return None

def fetch_real_time_price(tickers, poll_seconds, connection):
    try:
        while True:
            for tk in tickers:
                price = fetch_last_price(tk)
                if price is not None:
                    # use fast_info or info --> preprocessing data here
                    print("process")
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
    
    # use fast_info or info
    # poll_seconds = 30
    # fetch_real_time_price(tickers, poll_seconds, connection)
    
    # use download
    today_data = fetch_today_price(tickers)
    print(today_data)
    # if use download --> preprocessing data here
    connection.close()
