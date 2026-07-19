from app.schemas.auth import UserRecord
from pathlib import Path
import json


USER_REPO_FILE = Path(__file__).resolve().parents[2] / "data" / "users.json"


def load_users() -> list[UserRecord]:
  """Get all users."""
  
  if not USER_REPO_FILE.exists():
    return []
  users = json.loads(USER_REPO_FILE.read_text(encoding="utf-8"))
  return [UserRecord(**user) for user in users]


def save_users(users: list[UserRecord]) -> bool:
  """Replace all users."""
  
  USER_REPO_FILE.parent.mkdir(parents=True, exist_ok=True)
  
  payload = [user.model_dump() for user in users]
  
  try: 
    USER_REPO_FILE.write_text(
      json.dumps(payload, indent=2, ensure_ascii=False),
      encoding="utf-8"
    )
    return True
  except:
    return False
    
    
def get_user(email: str) -> UserRecord | None:
  users = load_users()
  
  for user in users:
    if email == user.email:
      return user
  
  return None
    
    
def add_user(user: UserRecord) -> bool:
  users: list[UserRecord] = load_users()  
  users.append(user)
  save_users(users)