import jwt
import os
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta


load_dotenv()


ACCESS_TOKEN_EXPIRE_MINUTES = 60
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"


def create_access_token(subject: str, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
  payload = {
    "sub": subject,
    "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
  }
  
  return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
  return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])