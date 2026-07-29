from app.schemas.auth import UserCreate, UserOut, UserRecord, SignInIn, TokenOut
from app.repositories.user_repo import add_user, get_user
from app.core.security import create_access_token
from app.core.errors import UserAlreadyExistsError, InvalidCredentialsError
from app.services.quota_service import ensure_daily_quota
import bcrypt


INITIAL_QUOTA = 3


# ---------- DEPENDS ----------
def hash_password(plain: str) -> str:
  hashed = bcrypt.hashpw(plain.encode(), bcrypt.gensalt())
  return hashed.decode()


def verify_password(plain: str, hashed: str) -> bool:
  return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---------- AUTH METHODS ----------
def register_user(user: UserCreate) -> UserOut:
  if get_user(user.email) is not None:
    raise UserAlreadyExistsError(str(user.email))
  add_user(UserRecord(
    email=user.email,
    username=user.username,
    password_hash=hash_password(user.password),
    daily_quota=INITIAL_QUOTA
  ))
  return UserOut(email=user.email, username=user.username, daily_quota=INITIAL_QUOTA)
  
  
def login(body: SignInIn) -> TokenOut:
  user = get_user(body.email)
  if user is None or not verify_password(body.password, user.password_hash):
    raise InvalidCredentialsError()
  ensure_daily_quota(user)
  token = create_access_token(body.email)
  return TokenOut(access_token=token)