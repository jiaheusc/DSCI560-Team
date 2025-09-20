import mysql.connector
import pandas as pd


portfolio_test_stocks_id = [1,2,3]

connection = mysql.connector.connect(
    host = "localhost",
    user = "root",
    password = "",
    database = ""
)

def generate_signal(previous_day_price, prediction):
    if previous_day_price < prediction:
        return 'BUY'
    elif previous_day_price > prediction:
        return 'SELL'
    else:
        return 'HOLD'

def prev_day_price(stock_id):
    query = """
        SELECT close
        FROM stock_1d
        WHERE stock_id = %s
        ORDER BY trade_date DESC
        LIMIT 1
    """
    return pd.read_sql(query, connection, params=(stock_id,)).iloc[0,0]

#get prediction from LSTM 
def lstm_pred(stock_id):
    query = """
        SELECT predicted_price
        FROM stock_forecasts
        WHERE stock_id = %s
        ORDER BY forecast_date DESC
        LIMIT 1
    """
    return pd.read_sql(query, connection, params=(stock_id,)).iloc[0,0]

#get prediction from prophet
def prophet_pred(stock_id):
    query = """
        SELECT predicted_price
        FROM forecast_prices_prophet
        WHERE stock_id = %s
        ORDER BY forecast_date DESC
        LIMIT 1
    """
    return pd.read_sql(query, connection, params=(stock_id,)).iloc[0,0]


funding = 10000

holdings = {}
#initialization
for id in portfolio_test_stocks_id:
    holdings[id] = 0


def buy_and_sell(portfolio_stocks_id, cash):
    signals = []
    buy_candidates = []
    sell_candidates = []
    all_stocks = []
    for stock_id in portfolio_stocks_id:
        pred_price_lstm  = lstm_pred(stock_id)
        pred_price_prophet  = prophet_pred(stock_id)
        prev_price = prev_day_price(stock_id)
        
        #we can always change to another way of computing the overall prediction
        final_pred = ( pred_price_lstm  + pred_price_prophet ) / 2

        signal = generate_signal(prev_price, final_pred)

        signals.append(signal)

        if signal == 'BUY':
            buy_candidates.append((stock_id, prev_price, final_pred))
        elif signal == 'SELL':
            sell_candidates.append((stock_id, prev_price, final_pred))

        all_stocks.append((stock_id, prev_price, final_pred))
    
    #SELL
    if len(sell_candidates) != 0:
        for id, prev_price, pred in sell_candidates:
            cash += (holdings[id] * prev_price)
            holdings[id] = 0


    #BUY
    weights = []

    for id, prev_price, pred in buy_candidates:
        weights.append((pred - prev_price) / prev_price)

    total = sum(weights)

    for (id, prev_price, pred), w in zip(buy_candidates, weights):
        money = cash * ( w / total )
        share = int(money // prev_price)
        holdings[id] += share



    portfolio_value = 0
    for id, prev_price, pred_price in all_stocks:
        portfolio_value += holdings[id] * pred_price
    
    print(f"Portfolio now has a total value of: {portfolio_value:.2f} dollars")

    return portfolio_value



portfolio_value = buy_and_sell(portfolio_test_stocks_id, funding)
for id, share in holdings.items():
    print(f'stock {id}  now has {share} share')


daily_return = ( portfolio_value - funding ) / funding 
print(f"Daily Return: {daily_return:.4%}")





    

