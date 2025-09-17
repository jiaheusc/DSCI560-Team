import time, datetime
import mysql.connector as mysql
import yfinance as yf
import pandas as pd
import time


db_config = {
    "host": "localhost",
    "user": "root",
    "password": "", #your password
    "database": "", #your database name
    "autocommit": True
}

tickers = [
    "AMD",
    "TSM",
    "AMZN",
    "META",
    "NVDA",
    "IBM",
    "MSFT",
    "XLK",
    "GOOG",
    "COST",
    "SMH",
    "DIS",
    "WFC",
    "AAPL",
    "JPM",
    "UAL",
    "HD",
    "TSLA"
]


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


connection = get_connection()
cursor = connection.cursor()

def create_portfolio(name):
    cursor.execute("INSERT INTO portfolios (name) VALUES (%s)", (name,))
    connection.commit()
    print(f"Portfolio '{name}' is successfully created.")
    return cursor.lastrowid 

def add_stock(id, ticker):

    if ticker not in tickers:
        print('Invalid name! ')
        return False 
    
    cursor.execute("INSERT INTO portfolio_stocks (portfolio_id, ticker) VALUES (%s, %s)",
                   (id, ticker.upper()))
    
    connection.commit()
    print(f'{ticker} is successfully added! ')


def remove_stock(id, ticker):

    if ticker not in tickers:
        print('Invalid name! ')
        return False 
    
    cursor.execute("DELETE FROM portfolio_stocks WHERE portfolio_id=%s AND ticker=%s",
        (id, ticker.upper()))
    
    connection.commit()

    print(f'{ticker} is successfully removed! ')


def display_all_portfolios():
    cursor.execute("SELECT * FROM portfolios")
    for pid, name, creation_date in cursor.fetchall():
        print(f'\nPortfolio Name: {name}   created on {creation_date}')
        cursor.execute("SELECT ticker FROM portfolio_stocks WHERE portfolio_id=%s", (pid,))
        stocks = [row[0] for row in cursor.fetchall()]
        print('Stocks: ' , ",".join(stocks) )
    

    

if __name__ == "__main__":
    while True:
        print('1, create a new portfolio with a list of stocks')
        print('2, add a stock')
        print('3, remove a stock')
        print('4, display portfolio')
        print('5, exit')

        choice = input("Enter your choice: ")

        if choice == '1':
            name = input("input your portfolio name: ")
            port_id = create_portfolio(name)

            names = input("input a list of stock tickers that you want to add to this portfolio(seperated by commas):  ")
            name_list = [n.strip().upper() for n in names.split(',')]

            for name in name_list:
                add_stock(port_id, name)

        elif choice == '2':
            port_id = input('Enter the portfolio ID ')
            stock_ticker = input('Enter the stock ticker you want to add')
            add_stock(port_id, stock_ticker)

        elif choice == '3':
            port_id = input('Enter the portfolio ID ')
            stock_ticker = input('Enter the stock ticker you want to remove')
            remove_stock(port_id, stock_ticker)

        elif choice == '4':
            display_all_portfolios()

        elif choice == '5':
            print('Exit!')
            break



    


        