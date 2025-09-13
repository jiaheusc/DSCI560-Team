import time, datetime
import mysql.connector as mysql
import yfinance as yf
import pandas as pd
import time
from datetime import timezone

db_config = {
    "host": "localhost",
    "user": "root",
    "password": "",#your password
    "database": "",#your database
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
def refill_missing(df):
    missing_summary = df.isna().sum()
    print("Missing values per column:\n", missing_summary)

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values(['stock_id', 'timestamp'])
    # Fill missing values within each stock_id 
    # First forward-fill (use previous value), then backward-fill (use next value if first is NaN)
    df[['price', 'volume']] = (
    df.groupby('stock_id')[['price','volume']]
      .apply(lambda g: g.ffill().bfill())
      .reset_index(level=0, drop=True)
)
    return df
def save_daily_to_mysql(connection, daily_df):
    cursor = connection.cursor()
    
    # create table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_stock (
            id INT AUTO_INCREMENT PRIMARY KEY,
            stock_id INT NOT NULL,
            date DATE NOT NULL,
            close DECIMAL(15,4),
            daily_volume BIGINT,
            daily_return DECIMAL(10,6)
        )
    """)
    
    records = [
        (int(row.stock_id), row.date, float(row.close), int(row.daily_volume), 
         None if pd.isna(row.daily_return) else float(row.daily_return))
        for row in daily_df.itertuples(index=False)
    ]
    
    sql = """
        INSERT INTO daily_stock (stock_id, date, close, daily_volume, daily_return)
        VALUES (%s, %s, %s, %s, %s)
    """
    
    cursor.executemany(sql, records)
    connection.commit()
    cursor.close()
    
if __name__ == "__main__":
    conn = get_connection()
    query = "SELECT stock_id, price, volume, timestamp FROM stock_price"
    df = pd.read_sql(query, conn)
    
    #refill missing value with the nearest timestamp
    df = refill_missing(df)
    
    #process timestamp
    df['date'] = df['timestamp'].dt.date
    
    #process daily data
    daily = (
    df.groupby(['stock_id','date'])
      .agg(close=('price','last'), daily_volume=('volume','sum'))
      .reset_index()
)
    daily['daily_return'] = daily.groupby('stock_id')['close'].pct_change()
    print(daily)
    
    save_daily_to_mysql(conn, daily)
    conn.close()
