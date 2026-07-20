from app.schemas.auth import UserCreate, UserOut, UserRecord, SignInIn, TokenOut
from app.repositories.user_repo import add_user, get_user
from app.core.security import create_access_token
import bcrypt


def hash_password(plain: str) -> str:
  hashed = bcrypt.hashpw(plain.encode(), bcrypt.gensalt())
  return hashed.decode()


def verify_password(plain: str, hashed: str) -> bool:
  return bcrypt.checkpw(plain.encode(), hashed.encode())


def register_user(user: UserCreate) -> UserOut:
  if get_user(user.email) is not None:
    raise Exception({ "content": "用户已存在" })
  add_user(UserRecord(
    email=user.email,
    username=user.username,
    password_hash=hash_password(user.password)
  ))
  return UserOut(email=user.email, username=user.username)
  
  
def login(body: SignInIn) -> TokenOut:
  user = get_user(body.email)
  
  if user is None or not verify_password(body.password, user.password_hash):
    raise Exception({ "content": "邮箱或密码错误" })
  
  token = create_access_token(body.email)
  return TokenOut(access_token=token)