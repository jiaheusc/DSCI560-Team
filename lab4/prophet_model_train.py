import pandas as pd
import mysql.connector as mysql
import numpy as np
from prophet import Prophet
import os
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings(
    "ignore"
)
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
            print("is connected to sql")
            return connection
    except Exception as e:
        print(f"Error: {e}")
        return None
    except mysql.Error as e:
        print("MySQL Error:", e)

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

def predict_error(model, forecast, actual_df):
    comparison_df = pd.DataFrame({
                'date': actual_df['ds'],
                'actual_price': actual_df['y'].values,
                'predicted_price': forecast['yhat'].values,
                'predicted_lower': forecast['yhat_lower'].values,
                'predicted_upper': forecast['yhat_upper'].values
            })
    comparison_df['error'] = comparison_df['actual_price'] - comparison_df['predicted_price']
    mae = comparison_df['error'].abs().mean()
    mse = (comparison_df['error'] ** 2).mean()
    rmse = mse ** 0.5
    print(f"MAE : {mae:.4f}")
    print(f"RMSE: {rmse:.4f}")

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

        train_df = df.iloc[:-60]
        actual_df = df.iloc[-60:]
        model1 = Prophet(weekly_seasonality=True, daily_seasonality=False)
        model1.fit(train_df)
        future1 = model1.make_future_dataframe(periods=60, freq='B')
        forecast1 = model1.predict(future1)

        # plot
        print(f"\nweekly train")
        forecast_df1 = forecast1.iloc[-60:]
        print(f"stock id: {stock_id}")
        predict_error(model1, forecast_df1, actual_df)

        # model 2
        print(f"\nweekly & daily train")
        model2 = Prophet(weekly_seasonality=True, daily_seasonality=True)
        model2.fit(train_df)
        future2 = model2.make_future_dataframe(periods=30, freq='B')
        forecast2 = model2.predict(future2)
        forecast_df2 = forecast2.iloc[-60:]
        predict_error(model2, forecast_df2, actual_df)


        return forecast_df2

    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    connection = get_connection()
    stock_ids = get_stock_ids(connection)
    
    for stock_id in stock_ids:
        forecast_date = build_prophet_model(connection, stock_id)
    connection.close()
	

