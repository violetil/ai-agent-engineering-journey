from app.schemas.auth import UserCreate, UserOut, UserRecord, SignInIn
from app.repositories.user_repo import add_user, get_user
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
  
  
def login(input: SignInIn) -> bool:
  user = get_user(input.email)
  if user is None:
    return False
  return verify_password(input.password, user.password_hash)