import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv


load_dotenv() 


ENCRYPTION_KEY = os.environ.get("MY_APP_SECRET_KEY")
if not ENCRYPTION_KEY:
    raise ValueError("MY_APP_SECRET_KEY missing for encryption")
    
cipher_suite = Fernet(ENCRYPTION_KEY.encode())


def encrypt(text: str) -> str:
    return cipher_suite.encrypt(text.encode()).decode()

def decrypt(token: str) -> str:
    return cipher_suite.decrypt(token.encode()).decode()