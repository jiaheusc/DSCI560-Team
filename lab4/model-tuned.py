import mysql.connector, joblib, torch
import pandas as pd, numpy as np
import torch.nn as nn
import torch.optim as optim
from datetime import date
from sklearn.metrics import mean_absolute_error, mean_squared_error
import warnings
warnings.filterwarnings(
    "ignore"
)
# load data
SEQ_LEN = 30
FINE_TUNE_EPOCHS = 10
FINE_TUNE_LR = 1e-4
table_name = "stock_forecasts"

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password = "DSCI560&team",
    database = "stock_database",
    autocommit=True
)

df = pd.read_sql(
    "SELECT stock_id, trade_date, close FROM stock_1d ORDER BY trade_date ASC;", conn
)
pivot_df = (df.pivot(index='trade_date', columns='stock_id', values='close')
              .sort_index()
              .fillna(method='ffill')
              .fillna(method='bfill'))

scaler = joblib.load("scaler.save")
scaled = scaler.transform(pivot_df.values)

# load pretrained model
class MultiStockLSTM(nn.Module):
    def __init__(self, input_size, hidden_size=128, num_layers=3):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size, hidden_size, num_layers,
            batch_first=True, dropout=0.2
        )
        self.fc = nn.Linear(hidden_size, input_size)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])

input_size = pivot_df.shape[1]
model = MultiStockLSTM(input_size)
model.load_state_dict(torch.load("best_model.pt"))

# generate train/eval sequences
def create_seq(data, seq_len):
    X, y = [], []
    for i in range(len(data) - seq_len):
        X.append(data[i:i + seq_len])
        y.append(data[i + seq_len])
    return np.array(X), np.array(y)

# Use all but last 30 days for evaluation/fine-tune sequences
X_all, y_all = create_seq(scaled, SEQ_LEN)
# Split: last 60 days for fine-tuning, rest for evaluation
split_idx = len(X_all) - 60
X_eval, y_eval = X_all[:split_idx], y_all[:split_idx]
X_ft, y_ft   = X_all[split_idx:], y_all[split_idx:]

X_eval = torch.tensor(X_eval, dtype=torch.float32)
y_eval = torch.tensor(y_eval, dtype=torch.float32)
X_ft   = torch.tensor(X_ft,   dtype=torch.float32)
y_ft   = torch.tensor(y_ft,   dtype=torch.float32)

# fine-tune model use LR
for name, param in model.named_parameters():
    if "fc" not in name:
        param.requires_grad = False

criterion = nn.MSELoss()
optimizer = optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=FINE_TUNE_LR)

model.train()
for epoch in range(FINE_TUNE_EPOCHS):
    optimizer.zero_grad()
    output = model(X_ft)
    loss = criterion(output, y_ft)
    loss.backward()
    optimizer.step()
    print(f"Epoch {epoch+1}/{FINE_TUNE_EPOCHS}, Loss: {loss.item():.6f}")

# evaluation metrics
model.eval()
with torch.no_grad():
    pred_eval = model(X_eval).numpy()

y_eval_rescaled   = scaler.inverse_transform(y_eval.numpy())
pred_eval_rescaled= scaler.inverse_transform(pred_eval)

# Metrics for the first stock (index 0) as example
mae  = mean_absolute_error(y_eval_rescaled[:,0], pred_eval_rescaled[:,0])
rmse = np.sqrt(mean_squared_error(y_eval_rescaled[:,0], pred_eval_rescaled[:,0]))
mape = np.mean(np.abs((y_eval_rescaled[:,0] - pred_eval_rescaled[:,0]) / y_eval_rescaled[:,0])) * 100
direction_acc = np.mean(
    np.sign(np.diff(y_eval_rescaled[:,0])) == np.sign(np.diff(pred_eval_rescaled[:,0]))
)

print(f"\nEvaluation Metrics on Validation Set:")
print(f"MAE: {mae:.4f}")
print(f"RMSE: {rmse:.4f}")
print(f"MAPE: {mape:.2f}%")
print(f"Directional Accuracy: {direction_acc:.2%}\n")

# toady's stock price prediction
latest_seq = pivot_df.values[-SEQ_LEN:]
latest_scaled = scaler.transform(latest_seq)
X_latest = torch.tensor(latest_scaled[np.newaxis, :, :], dtype=torch.float32)

with torch.no_grad():
    pred_today_scaled = model(X_latest).numpy()

pred_today = scaler.inverse_transform(pred_today_scaled)

# store today's prediction
cursor = conn.cursor()
cursor.execute(f"DROP TABLE IF EXISTS {table_name};")
cursor.execute(f"""
CREATE TABLE {table_name} (
    id               BIGINT AUTO_INCREMENT PRIMARY KEY,
    stock_id         INT NOT NULL,
    forecast_date    DATETIME NOT NULL,
    predicted_price  DECIMAL(10,4) NOT NULL
);
""")

insert_sql = f"""
INSERT INTO {table_name} (stock_id, forecast_date, predicted_price)
VALUES (%s, %s, %s)
"""

today = date.today()
stock_ids = pivot_df.columns.tolist()
records = [
    (int(stock_id), today, float(pred_today[0, idx]))
    for idx, stock_id in enumerate(stock_ids)
]

cursor.executemany(insert_sql, records)
conn.commit()
print(f"Inserted {cursor.rowcount} rows for today's forecast ({today}).")

cursor.close()
conn.close()

