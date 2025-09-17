import mysql.connector
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import MinMaxScaler
import joblib

# ---------- 1. 读取数据 ----------
conn = mysql.connector.connect(
    host="localhost", 
    user="root", 
    password="",
    database="", autocommit=True
)
query = "SELECT stock_id, trade_date, close FROM stock_1d ORDER BY trade_date ASC;"
df = pd.read_sql(query, conn)
conn.close()

pivot_df = df.pivot(index='trade_date', columns='stock_id', values='close').sort_index()
pivot_df = pivot_df.fillna(method='ffill').fillna(method='bfill')

# ---------- 2. 缩放 & 序列 ----------
scaler = MinMaxScaler()
scaled = scaler.fit_transform(pivot_df.values)
SEQ_LEN = 30

def create_sequences(data, seq_len):
    X, y = [], []
    for i in range(len(data)-seq_len):
        X.append(data[i:i+seq_len])
        y.append(data[i+seq_len])
    return np.array(X), np.array(y)

X, y = create_sequences(scaled, SEQ_LEN)
split = int(len(X)*0.8)
X_train, y_train = X[:split], y[:split]
X_val, y_val = X[split:], y[split:]

X_train = torch.tensor(X_train, dtype=torch.float32)
y_train = torch.tensor(y_train, dtype=torch.float32)
X_val = torch.tensor(X_val, dtype=torch.float32)
y_val = torch.tensor(y_val, dtype=torch.float32)

class StockDataset(Dataset):
    def __init__(self,X,y): self.X,self.y=X,y
    def __len__(self): return len(self.X)
    def __getitem__(self,i): return self.X[i], self.y[i]

train_loader = DataLoader(StockDataset(X_train,y_train), batch_size=64, shuffle=True)

# ---------- 3. 定义模型 ----------
class MultiStockLSTM(nn.Module):
    def __init__(self,input_size,hidden_size=128,num_layers=3):
        super().__init__()
        self.lstm = nn.LSTM(input_size,hidden_size,num_layers,batch_first=True,dropout=0.2)
        self.fc = nn.Linear(hidden_size,input_size)
    def forward(self,x):
        out,_=self.lstm(x)
        return self.fc(out[:,-1,:])

input_size = X_train.shape[2]
model = MultiStockLSTM(input_size)
criterion = nn.MSELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)

# ---------- 4. 训练 ----------
best_loss = np.inf
patience, no_improve = 10, 0
for epoch in range(200):
    model.train(); total_loss=0
    for xb,yb in train_loader:
        optimizer.zero_grad()
        out = model(xb)
        loss = criterion(out,yb)
        loss.backward(); nn.utils.clip_grad_norm_(model.parameters(),5.0)
        optimizer.step()
        total_loss += loss.item()
    val_loss = criterion(model(X_val),y_val).item()
    print(f"Epoch {epoch+1}, Train:{total_loss/len(train_loader):.6f}, Val:{val_loss:.6f}")
    if val_loss < best_loss-1e-5:
        best_loss=val_loss; no_improve=0
        torch.save(model.state_dict(),"best_model.pt")
    else:
        no_improve+=1
        if no_improve>=patience:
            print("Early stopping."); break

# ---------- 5. 保存 scaler ----------
joblib.dump(scaler,"scaler.save")

