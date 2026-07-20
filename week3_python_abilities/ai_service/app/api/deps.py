from app.core.security import decode_access_token
from app.repositories.user_repo import get_user
from app.schemas.auth import UserRecord
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from typing import Annotated
import jwt


security = HTTPBearer()


def get_current_user(
  cred: Annotated[HTTPAuthorizationCredentials, Depends(security)]
) -> UserRecord:
  token = cred.credentials
  try:
    payload = decode_access_token(token)
    email = payload.get("sub")
  except jwt.PyJWTError:
    raise HTTPException(status_code=401, detail="无效或过期令牌")
  
  user = get_user(email)
  if user is None:
    raise HTTPException(status_code=401, detail="用户不存在")
  return user


CurrentUser = Annotated[UserRecord, Depends(get_current_user)]