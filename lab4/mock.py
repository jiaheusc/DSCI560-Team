import mysql.connector
import pandas as pd
import yfinance as yf

portfolio_test_stocks_id = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]

connection = mysql.connector.connect(
    host = "localhost",
    user = "root",
    password = "",
    database = ""
)


def generate_signal(curr_price, lstm_pred, prophet_pred, smas, buy_threshold, sell_threshold):

    prophet_lower = prophet_pred.get('predicted_lower')
    prophet_higher = prophet_pred.get('predicted_upper')

    # if two models divarication, signal is not reliable
    models_agree = prophet_lower <= lstm_pred <= prophet_higher
    if not models_agree:
        return 'HOLD'
    
    sma50 = smas.get('sma_50')
    sma200 = smas.get('sma_200')

    print(
        f"curr_price: {curr_price}\n"
        f"prophet_lower: {prophet_lower}, "
        f"lstm_pred: {lstm_pred}, "
        f"prophet_higher: {prophet_higher}\n"
        f"sma50: {sma50}, "
        f"sma200: {sma200}, "
    )
    return_on_worst_case = (prophet_lower - curr_price) / curr_price
    if return_on_worst_case > buy_threshold:
        is_strong_uptrend = curr_price > sma50 and sma50 > sma200
        if is_strong_uptrend:
            return 'BUY'
    
    return_on_best_case = (prophet_higher - curr_price) / curr_price
    if return_on_best_case < -sell_threshold:
        is_weakening = curr_price < sma50
        if is_weakening:
            return 'SELL'
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


def sma_last(stock_id):
    query = """
        SELECT sma_50, sma_200
        FROM moving_average
        WHERE stock_id = %s
        ORDER BY trade_date DESC
        LIMIT 1
    """
    return pd.read_sql(query, connection, params=(stock_id,)).to_dict('records')[0]

def prophet_pred(stock_id):
    query = """
        SELECT predicted_price, predicted_lower, predicted_upper
        FROM forecast_prices_prophet
        WHERE stock_id = %s
        ORDER BY forecast_date DESC
        LIMIT 1
    """
    return pd.read_sql(query, connection, params=(stock_id,)).to_dict('records')[0]

def get_ticker_by_id(connection, stock_id):
    sql = "SELECT ticker FROM stocks WHERE stock_id = %s"
    cursor = connection.cursor()
    try:
        cursor.execute(sql, (stock_id,))
        row = cursor.fetchone()
        return row[0]
    finally:
        cursor.close()


#funding = 10000

#holdings = {}
#initialization
#for id in portfolio_test_stocks_id:
    #holdings[id] = 0


#load holdings from db
def load_holdings_from_db():
    query = """
        SELECT h.stock_id, h.shares, h.cash, h.portfolio_value
        FROM holdings h
        INNER JOIN (
            SELECT stock_id, MAX(trade_date) as latest
            FROM holdings
            GROUP BY stock_id
        ) t
        ON h.stock_id = t.stock_id AND h.trade_date = t.latest
    """
    df = pd.read_sql(query, connection)

    if df.empty:
        # empty holdings
        return {sid: 0 for sid in portfolio_test_stocks_id}, 10000, 10000

    holdings = {row["stock_id"]: row["shares"] for _, row in df.iterrows()}
    cash = df["cash"].iloc[0]  
    portfolio_value = df["portfolio_value"].iloc[0]

    print(f"Loaded holdings: {holdings}, cash = {cash}, value = {portfolio_value}")
    return holdings, cash, portfolio_value

holdings, cash, portfolio_value_before = load_holdings_from_db()

for sid in portfolio_test_stocks_id:
    holdings.setdefault(sid, 0)


def buy_and_sell(portfolio_stocks_id, cash):
    signals = []
    buy_candidates = []
    sell_candidates = []
    all_stocks = []
    for stock_id in portfolio_stocks_id:
        pred_price_lstm  = lstm_pred(stock_id)
        pred_price_prophet  = prophet_pred(stock_id)
        smas = sma_last(stock_id)
        ticker = get_ticker_by_id(connection, stock_id)
        stock = yf.Ticker(ticker)
        stock_info = stock.fast_info
        curr_price = stock_info.last_price
        #we can always change to another way of computing the overall prediction
        signal = generate_signal(curr_price, pred_price_lstm, pred_price_prophet, smas, buy_threshold=0.02, sell_threshold=0.01)
        print(f"signal is: {signal}, id is: {stock_id}")
    
        signals.append(signal)

        pred = pred_price_prophet.get('predicted_lower')

        if signal == 'BUY':
            buy_candidates.append((stock_id, curr_price, pred))
        elif signal == 'SELL':
            sell_candidates.append((stock_id, curr_price, pred))

        all_stocks.append((stock_id, curr_price, pred))
    
    #SELL
    if len(sell_candidates) != 0:
        for id, curr_price, pred in sell_candidates:
            cash += (holdings[id] * curr_price)
            holdings[id] = 0


    #BUY
    weights = []

    for id, curr_price, pred in buy_candidates:
        weights.append((pred - curr_price) / curr_price)

    total = sum(weights)

    for (id, curr_price, pred), w in zip(buy_candidates, weights):
        if total == 0:
            continue
        money = cash * ( w / total )
        share = int(money // curr_price)
        holdings[id] += share
        cash -= share * curr_price


    portfolio_value = cash
    for id, curr_price, pred_price in all_stocks:
        portfolio_value += holdings[id] * curr_price
    
    print(f"Portfolio now has a total value of: {portfolio_value:.2f} dollars")

    return portfolio_value



portfolio_value = buy_and_sell(portfolio_test_stocks_id, cash)
for id, share in holdings.items():
    print(f'stock {id}  now has {share} share')


cursor = connection.cursor()

for stock_id, shares in holdings.items():
    query = """
            INSERT INTO holdings (stock_id, shares, cash, portfolio_value)
            VALUES (%s, %s, %s, %s)
        """
    cursor.execute(query, (stock_id, shares, cash, portfolio_value))

connection.commit()

if portfolio_value == 0.0:
     daily_return = 0.0
else:
     daily_return = ( portfolio_value - portfolio_value_before) / portfolio_value_before
print(f"Daily Return: {daily_return:.4%}")