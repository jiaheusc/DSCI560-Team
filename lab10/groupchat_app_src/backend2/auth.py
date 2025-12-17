import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
# 1. 移除 passlib 导入
# from passlib.context import CryptContext 
# 2. 新增 bcrypt 导入
import bcrypt

from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

load_dotenv()

# 3. 移除 pwd_context 定义
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

security = HTTPBearer()

JWT_SECRET = os.getenv("JWT_SECRET", "change_me")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "43200"))
ALGORITHM = "HS256"

class TokenData(BaseModel):
    username: str
    role: str
    user_id: int

def get_password_hash(password: str) -> str:
    # bcrypt hard limit — must truncate (保留你原有的截断逻辑)
    if len(password.encode("utf-8")) > 72:
        password = password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
    
    # 4. 改用原生 bcrypt 生成哈希
    # bcrypt 需要 bytes 类型
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    
    # 存入数据库时转回 string
    return hashed.decode('utf-8')


def verify_password(plain_password: str, password_hash: str) -> bool:
    # 保留截断逻辑
    if len(plain_password.encode("utf-8")) > 72:
        plain_password = plain_password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
    
    # 5. 改用原生 bcrypt 验证
    try:
        pwd_bytes = plain_password.encode('utf-8')
        # 数据库里的 hash 是 string，需要转成 bytes
        hash_bytes = password_hash.encode('utf-8')
        
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except (ValueError, TypeError):
        # 如果哈希格式不对，直接返回 False
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=JWT_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> TokenData:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        token_data = TokenData(**payload)
        return token_data
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
def verify_websocket_token(token: str) -> TokenData | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        
        token_data = TokenData(**payload)
        return token_data
    
    except (JWTError, ValidationError, Exception):
        return None