import jwt
from datetime import datetime, timezone, timedelta
from app.core.config import JWT_SECRET_KEY


ACCESS_TOKEN_EXPIRE_MINUTES = 60
ALGORITHM = "HS256"


def create_access_token(subject: str, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
  payload = {
    "sub": subject,
    "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
  }
  
  return jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
  return jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])