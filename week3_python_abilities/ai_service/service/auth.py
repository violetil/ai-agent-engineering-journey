from db.models import User
import json


USER_FILE_PATH = "db/users.json"


# ---------- Dependencies ----------
def read_user_db():
  with open(USER_FILE_PATH, "r", encoding="utf-8") as f:
    return json.load(f)
  
  
def write_users_db(count: int, users: list[User]):
  with open(USER_FILE_PATH, "w", encoding="utf-8") as f:
    json.dump({ "count": count, "users": users }, f, indent=2)


# ---------- Operations ----------
def write_user(user: User):
  """Write user to db."""
  
  users_db = read_user_db()
  users_db["users"].append(user.model_dump())
  users_db["count"] += 1
  write_users_db(users_db["count"], users_db["users"])


def get_users() -> list[User]:
  """List all users in db."""
  
  users_db = read_user_db()
  return users_db.get("users", [])


def check_password(email: str, password: str) -> bool:
  users = get_users()
  for user in users:
    if user["email"] == email and user["password"] == password:
      return True
    
  return False


if __name__ == "__main__":
  print("Current users:")
  print(get_users())
  
  # print("\nCreate an user:")
  # user = { 
  #   "email": "violet@demo.com", 
  #   "username": "Violet", 
  #   "password": "password123" 
  # }
  # print(user)
  # 
  # users_db = read_user_db()
  # users_db["count"] += 1
  # users_db["users"].append(user)
  # write_users_db(users_db["count"], users_db["users"])
  # 
  # print("\nAfter create an user:")
  # print(get_users())
  
  email = input("\nInput email (check password func):")
  password = input("Input password (check password func):")
  if (check_password(email, password)):
    print("Password right.")
  else:
    print("Password wrong.")