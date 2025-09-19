import mysql.connector as mysql
import yfinance as yf

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
            print("is connected")
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

def get_stock_ids(connection, tickers):
    placeholders = ','.join(['%s'] * len(tickers))
    sql = f"SELECT ticker, stock_id FROM stocks WHERE ticker IN ({placeholders})"
    cursor = connection.cursor()
    cursor.execute(sql, tuple(tickers))
    mapping = dict(cursor.fetchall())
    cursor.close()
    return mapping

def upsert_stock_price(connection, tickers, data):
    with connection.cursor() as c:
        c.execute("SET time_zone = '+00:00'")

    stock_id_map = get_stock_ids(connection, tickers)

    df = data.copy()
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_convert("UTC").tz_localize(None)
    create_sql = """
                CREATE TABLE IF NOT EXISTS stock_1d (
                    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
                    stock_id    INT NOT NULL,
                    trade_date  TIMESTAMP NOT NULL,
                    open        DECIMAL(10,4) NULL,
                    high        DECIMAL(10,4) NULL,
                    low         DECIMAL(10,4) NULL,
                    close       DECIMAL(10,4) NOT NULL,
                    volume      BIGINT UNSIGNED,
                    UNIQUE KEY uniq_stock_date (stock_id, trade_date)
                ) ENGINE=InnoDB;
            """
    insert_sql = """
                INSERT INTO stock_1d
                    (stock_id, `trade_date`, open, high, low, close, volume)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE
                        open=VALUES(open),
                        high=VALUES(high),
                        low =VALUES(low),
                        close=VALUES(close),
                        volume=VALUES(volume)
            """

    batch, BATCH_SIZE = [], 1000
    cursor = connection.cursor()

    try:
        cursor.execute(create_sql)
        for ticker in tickers:
            col_level0 = df.columns.get_level_values(0)
            if ticker not in set(col_level0):
                continue
            sid = stock_id_map.get(ticker)
            
            if sid is None:
                continue
            sub = df[ticker].dropna(how="all")
            for ts, row in sub.iterrows():
                o, h, l, c = row["Open"], row["High"], row["Low"], row["Close"]
                v = row.get("Volume", None)
                batch.append((sid, ts, float(o), float(h), float(l), float(c), v))
                if len(batch) >= BATCH_SIZE:
                    cursor.executemany(insert_sql, batch)
                    batch.clear()
            
            if batch:
                cursor.executemany(insert_sql, batch)
                batch.clear()
    except Exception as e:
        print(f"Error: {e}")
        connection.rollback()
        raise
    finally:
        cursor.close()

def fetch_price(tickers, period, interval):
    try:
        data = yf.download(tickers, period=period, interval=interval, group_by='ticker')
        if data.empty:
            print("No stock price data")
            return None
        return data
    except Exception as e:
        print(f"Error: {e}")
        return None

    
if __name__ == "__main__":
    connection = get_connection()
    try:
        tickers = get_all_tickers(connection)

        period = "7y"
        interval = "1d"
        data = fetch_price(tickers, period, interval)
        upsert_stock_price(connection, tickers, data)
    finally:
        connection.close()