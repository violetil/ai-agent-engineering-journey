import bcrypt


def hash_password(plain: str) -> str:
  hashed = bcrypt.hashpw(plain.encode(), bcrypt.gensalt())
  return hashed.decode()


def verify_password(plain: str, hashed: str) -> bool:
  return bcrypt.checkpw(plain.encode(), hashed.encode())