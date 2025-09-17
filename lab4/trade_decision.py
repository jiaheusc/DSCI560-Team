import mysql.connector, json, csv
import pandas as pd, numpy as np, torch, joblib
import torch.nn as nn
from sklearn.metrics import mean_absolute_error, mean_squared_error

# --- 参数 ---
INITIAL_CASH=100000
FEE_BPS=10; RET_THRESHOLD=0.0
ALLOW_SHORT=False; MAX_LEV=1.0

# --- 1. 读取数据、模型、scaler ---
conn = mysql.connector.connect(
    host="localhost", 
    user="root", 
    password="",
    database="", autocommit=True
)
df = pd.read_sql("SELECT stock_id, trade_date, close FROM stock_1d ORDER BY trade_date ASC;", conn)
pivot_df = df.pivot(index='trade_date',columns='stock_id',values='close').sort_index().fillna(method='ffill').fillna(method='bfill')

scaler = joblib.load("scaler.save")
scaled = scaler.transform(pivot_df.values)

SEQ_LEN=30
def create_seq(data,seq_len):
    X,y=[],[]
    for i in range(len(data)-seq_len):
        X.append(data[i:i+seq_len]); y.append(data[i+seq_len])
    return np.array(X), np.array(y)

X,y = create_seq(scaled,SEQ_LEN)
X_torch = torch.tensor(X,dtype=torch.float32)

# 模型定义和加载
class MultiStockLSTM(nn.Module):
    def __init__(self,input_size,hidden_size=128,num_layers=3):
        super().__init__()
        self.lstm=nn.LSTM(input_size,hidden_size,num_layers,batch_first=True,dropout=0.2)
        self.fc=nn.Linear(hidden_size,input_size)
    def forward(self,x):
        out,_=self.lstm(x)
        return self.fc(out[:,-1,:])

input_size=X_torch.shape[2]
model=MultiStockLSTM(input_size)
model.load_state_dict(torch.load("best_model.pt"))
model.eval()

# --- 2. 预测 ---
with torch.no_grad():
    preds=model(X_torch).numpy()

# 反缩放回真实价格
pred_rescaled=scaler.inverse_transform(preds)
y_rescaled=scaler.inverse_transform(y)

# 计算回归类指标
mae=mean_absolute_error(y_rescaled[:,0], pred_rescaled[:,0])
rmse=np.sqrt(mean_squared_error(y_rescaled[:,0], pred_rescaled[:,0]))
mape=np.mean(np.abs((y_rescaled[:,0]-pred_rescaled[:,0])/y_rescaled[:,0]))*100
direction_acc=np.mean(
    np.sign(np.diff(y_rescaled[:,0]))==np.sign(np.diff(pred_rescaled[:,0]))
)

print(f"MAE: {mae:.4f}\nRMSE: {rmse:.4f}\nMAPE: {mape:.2f}%\nDirection Accuracy: {direction_acc:.2%}")

# --- 3. 交易权重 ---
prices=pivot_df.values[-len(preds):]
prev_prices=pivot_df.values[-len(preds)-1:-1]
dates=pivot_df.index[-len(preds):]
pred_ret=(pred_rescaled/prev_prices)-1.0
weights=np.zeros_like(pred_ret)
for t in range(len(pred_ret)):
    pos=pred_ret[t]>RET_THRESHOLD
    if np.any(pos):
        w=np.zeros(input_size)
        w[pos]=1.0/pos.sum()
        weights[t]=w

# --- 4. 回测 + 写数据库 ---
fee_rate=FEE_BPS/10000
cash=INITIAL_CASH
shares=np.zeros(input_size)
portfolio_values=[]
with open("trades.csv","w",newline='') as f: csv.writer(f).writerow(["date","stock_id","action","shares","price","notional","fee"])

cursor=conn.cursor()
for t in range(len(weights)):
    price=prices[t]; date=dates[t]
    port_val=cash+np.sum(shares*price)
    portfolio_values.append(port_val)
    target_val=port_val*weights[t]
    trade_val=target_val-shares*price
    buy=np.sum(trade_val.clip(min=0)); sell=-np.sum(trade_val.clip(max=0))
    fee=fee_rate*(buy+sell)
    cash=cash-buy-fee+sell
    delta=trade_val/price; shares+=delta

    with open("trades.csv","a",newline='') as f:
        w=csv.writer(f)
        for idx,d in enumerate(delta):
            if abs(d)>1e-6:
                action='BUY' if d>0 else 'SELL'
                w.writerow([date.strftime('%Y-%m-%d'),pivot_df.columns[idx],action,round(float(d),2),
                            round(float(price[idx]),2),round(float(d*price[idx]),2),round(float(fee),2)])

    holdings={str(pivot_df.columns[i]):float(shares[i]) for i in range(len(shares)) if abs(shares[i])>1e-6}
    cursor.execute(
        "INSERT INTO positions (trade_date,cash,total_value,details) VALUES (%s,%s,%s,%s)",
        (date.strftime('%Y-%m-%d'),cash,port_val,json.dumps(holdings))
    )
    conn.commit()

cursor.close(); conn.close()

# --- 5. 投资组合绩效指标 ---
pv=pd.Series(portfolio_values,index=dates)
def max_drawdown(series):
    cum=series.cummax()
    return (series/cum-1).min()
def sharpe_ratio(series,freq=252,rf=0.0):
    r=series.pct_change().dropna()
    return np.sqrt(freq)*(r.mean()-rf/freq)/r.std()

total_return=pv.iloc[-1]/pv.iloc[0]-1
mdd=max_drawdown(pv)
sharpe=sharpe_ratio(pv)

print("\n=== Portfolio Performance ===")
print(f"Initial Value: {INITIAL_CASH:,.2f}")
print(f"Final Value  : {pv.iloc[-1]:,.2f}")
print(f"Total Return : {total_return:.2%}")
print(f"Max Drawdown : {mdd:.2%}")
print(f"Sharpe Ratio : {sharpe:.2f}")

