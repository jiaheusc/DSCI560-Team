# DSCI560-Team
# 1. Clone the repository
```bash
git clone https://github.com/jiaheusc/DSCI560-Team
cd DSCI560-Team/groupchat_app_src/sql

# 2. Set up the database
mysql -u root -p < schema.sql

# 3. Set up the backend
```bash
cd ../backend
With your Python virtual environment activated, run:
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000

# 4. Set up the frontend
```bash
cd ../frontend/groupchat-react-app
npm install
npm start

How to run on Android Phone:
1. Using Capacitor to add our app to Android Studio
2. Run our app in Android Studio to install the app in phone
3. computer and phone are using the same Wi-Fi
4. change from localhost to Internet IP
5. run backend 
