from app.schemas.auth import UserRecord
from pathlib import Path
import json


# ---------- GLOBAL VARIABLES ----------
USER_REPO_FILE = Path(__file__).resolve().parents[2] / "data" / "users.json"


# ----------- PRECONDITIONS ----------
# make sure the user repo file exists.
USER_REPO_FILE.parent.mkdir(parents=True, exist_ok=True)
if not USER_REPO_FILE.exists():
  with open(USER_REPO_FILE, "w", encoding="utf-8") as f:
    json.dump([], f, indent=2, ensure_ascii=False)


# ---------- REPO METHODS ----------
def load_users() -> list[UserRecord]:
  """Get all users."""
  users = json.loads(USER_REPO_FILE.read_text(encoding="utf-8"))
  return [UserRecord(**user) for user in users]


def save_users(users: list[UserRecord]):
  """Replace all users."""
  payload = [user.model_dump() for user in users]
  USER_REPO_FILE.write_text(
    json.dumps(payload, indent=2, ensure_ascii=False),
    encoding="utf-8"
  )
    
    
def get_user(email: str) -> UserRecord | None:
  """Get user by email."""
  users = load_users()
  for user in users:
    if email == user.email:
      return user
  return None
    
    
def add_user(user: UserRecord):
  """Add a user to user repositorie."""
  users = load_users()  
  users.append(user)
  save_users(users)