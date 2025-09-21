import pandas as pd
import mysql.connector as mysql
from prophet import Prophet

db_config = {
    "host": "localhost",
    "user": "root",
    "password" : "",
    "database" : "",
    "autocommit": True
}

def get_connection():
    try:
        connection = mysql.connect(**db_config)
        if connection.is_connected():
            return connection
    except Exception as e:
        print(f"Error: {e}")
        return None

def get_stock_ids(connection):
    try:
        sql = "SELECT stock_id FROM stocks"
        cursor = connection.cursor()
        cursor.execute(sql)
        results = cursor.fetchall()
        cursor.close()
        return [item[0] for item in results]
    except Exception as e:
        print(f"Error: {e}")
        return None

def build_prophet_model(connection, stock_id):
    try: 
        sql = """
                SELECT trade_date, close
                FROM stock_1d
                WHERE stock_id = %s
                ORDER BY trade_date
            """
        df = pd.read_sql(sql, connection, params=(stock_id,))
        df['trade_date'] = pd.to_datetime(df['trade_date'])

        df.rename(columns={'trade_date': 'ds', 'close': 'y'}, inplace=True)

        model = Prophet(weekly_seasonality=True, daily_seasonality=True)
        model.fit(df)
        future = model.make_future_dataframe(periods=30, freq='B')
        forecast = model.predict(future)

        forecast_df = forecast[forecast['ds'] > df['ds'].max()].copy()
        final_output = forecast_df[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].rename(columns={
            'ds': 'forecast_date',
            'yhat': 'predicted_price',
            'yhat_lower': 'predicted_lower',
            'yhat_upper': 'predicted_upper'
        })
        final_output['stock_id'] = stock_id
        return final_output

    except Exception as e:
        print(f"Error: {e}")
        return None

def clear_table(connection, table_name):
    cursor = connection.cursor()
    try:
        cursor.execute(f"TRUNCATE TABLE {table_name};")
    except mysql.errors.ProgrammingError as e:
        if e.errno == 1146:
            # Table doesn't exist—just skip clearing
            print(f"Table {table_name} not found, skipping truncate.")
        else:
            raise
    finally:
        cursor.close()


def upsert_forecast_data(connection, table_name, forecast_data):
    create_sql = f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id               BIGINT AUTO_INCREMENT PRIMARY KEY,
                    stock_id         INT NOT NULL,
                    forecast_date    DATETIME NOT NULL,
                    predicted_price  DECIMAL(10,4) NOT NULL,
                    predicted_lower  DECIMAL(10,4) NOT NULL,
                    predicted_upper  DECIMAL(10,4) NOT NULL,
                    UNIQUE KEY uniq_stock_date (stock_id, forecast_date)
                ) ENGINE=InnoDB;
            """

    insert_sql = f"""
        INSERT INTO {table_name}
        (stock_id, forecast_date, predicted_price, predicted_lower, predicted_upper)
        VALUES (%s, %s, %s, %s, %s);
    """
    cursor = connection.cursor()
    try:
        cursor.execute(create_sql)
        rows = [
            (
                int(row["stock_id"]),
                row["forecast_date"],
                float(row["predicted_price"]),
                float(row["predicted_lower"]),
                float(row["predicted_upper"])
            )
            for _, row in forecast_data.iterrows()
        ]
        cursor.executemany(insert_sql, rows)
    except Exception as e:
        print(f"Error: {e}")
        connection.rollback()
        raise
    finally:
        cursor.close()

if __name__ == "__main__":
    table_name="forecast_prices_prophet"
    try:
        connection = get_connection()
        stock_ids = get_stock_ids(connection)
        clear_table(connection, table_name)
        for stock_id in stock_ids:
            forecast_data = build_prophet_model(connection, stock_id)
            upsert_forecast_data(connection, table_name, forecast_data)
    finally:
        connection.close()
