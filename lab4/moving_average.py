import pandas as pd
import mysql.connector as mysql
import numpy as np

db_config = {
    "host": "localhost",
    "user": "root",
    "password" : "DSCI560&team",
    "database" : "stock_database",
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

def get_latest_date(connection):
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT MAX(trade_date) FROM stock_1d")
        latest_date = cursor.fetchone()[0]
        cursor.close()
        return latest_date
    except Exception as e:
        print(f"Error: {e}")

def calculate_sma(connection, target_date):
    start_date = target_date - pd.Timedelta(days=350)
    sql = """
        SELECT stock_id, trade_date, close
        FROM stock_1d
        WHERE trade_date BETWEEN %s AND %s
        ORDER BY stock_id, trade_date
    """

    df = pd.read_sql(sql, connection, params=(start_date, target_date))
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df["sma_5"] = (
        df.sort_values(["stock_id","trade_date"])
            .groupby("stock_id")["close"].transform(lambda s: s.rolling(5).mean())
    )
    df["sma_50"] = (
        df.sort_values(["stock_id","trade_date"])
            .groupby("stock_id")["close"].transform(lambda s: s.rolling(50).mean())
    )
    df["sma_200"] = (
        df.sort_values(["stock_id","trade_date"])
            .groupby("stock_id")["close"].transform(lambda s: s.rolling(200).mean())
    )

    latest_data = df[df['trade_date'] == target_date].copy()
    return latest_data

def upsert_moving_average_data(connection, table_name, ma_data):
    create_sql = f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id              BIGINT AUTO_INCREMENT PRIMARY KEY,
                        stock_id        INT       NOT NULL,
                        trade_date      DATETIME      NOT NULL,
                        close           DECIMAL(10,4) NULL,
                        sma_5           DECIMAL(10,4) NULL,
                        sma_50          DECIMAL(10,4) NULL,
                        sma_200         DECIMAL(10,4) NULL,
                        UNIQUE KEY uniq_stock_date (stock_id, trade_date)
                    ) ENGINE=InnoDB;
                """
    insert_sql = f"""
        INSERT INTO {table_name}
        (stock_id, trade_date, close, sma_5, sma_50, sma_200)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            close = VALUES(close),
            sma_5 = VALUES(sma_5),
            sma_50 = VALUES(sma_50),
            sma_200 = VALUES(sma_200);
    """
    cursor = connection.cursor()
    try:
        cursor.execute(create_sql)
        rows = [
            (
                int(row["stock_id"]),
                row["trade_date"],
                float(row["close"]),
                float(row["sma_5"]),
                float(row["sma_50"]),
                float(row["sma_200"])
            )
            for _, row in ma_data.iterrows()
        ]
        cursor.executemany(insert_sql, rows)
    except Exception as e:
        print(f"Error: {e}")
        connection.rollback()
        raise
    finally:
        cursor.close()

if __name__ == "__main__":
    table_name="moving_average"
    try:
        connection = get_connection()
        target_date = get_latest_date(connection)
        sma_data = calculate_sma(connection, target_date)
        upsert_moving_average_data(connection, table_name, sma_data)
    finally:
        connection.close()
