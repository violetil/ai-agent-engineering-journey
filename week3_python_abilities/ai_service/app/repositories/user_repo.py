from schemas.auth import UserOut, UserRecord
import json


USER_REPO_FILE = "../../data/user.json"


def load_users() -> list[UserRecord]:
  """Get all users."""
  
  with open(USER_REPO_FILE, "r", encoding="utf-8") as f:
    users = json.load(f)
    
  return [UserRecord(user) for user in users]


def get_user(email: str) -> UserRecord | None:
  users = load_users()
  
  for user in users:
    if email == user.email:
      return user
  
  return None


def save_users(users: list[UserRecord]) -> bool:
  """Replace all users."""
  
  with open(USER_REPO_FILE, "w", encoding="utf-8") as f:
    try:
      json.dump([user.model_dump() for user in users], f, indent=2, ensure_ascii=False)
      return True
    except:
      return False
    
    
def add_user(user: UserRecord) -> bool:
  users = load_users()  
  users.append(user.model_dump())
  save_users([UserRecord(user) for user in users])