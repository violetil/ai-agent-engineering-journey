from fastapi import FastAPI, status, HTTPException
from app.schemas.auth import UserCreate, UserOut, SignInIn, UserRecord
from app.services.auth_service import hash_password, verify_password
from app.repositories.user_repo import add_user, get_user


app = FastAPI(
  title="Violet AI API Service"
)


# ---------- Routers ----------
@app.get("/")
def root():
  return {
    "message": "Violet AI API Service"
  }
  

# @app.post("/chat/completions")
# async def chat_completions(input: ChatCompletionsIn) -> str:
#   return await ask_llm(input.prompt)
# 
# 
# @app.post("/chat/completions/multi")
# async def multi_chat_completions(input: list[ChatCompletionsIn]) -> list[str]:
#   return await ask_llm_many([t.prompt for t in input])


@app.post("/auth/sign_up", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def sign_up(user: UserCreate):
  """Create an user in database"""
  
  hashed = hash_password(user.password)
  
  try:
    add_user(UserRecord(
      email=user.email,
      username=user.username,
      password_hash=hashed
    ))
    return UserOut(email=user.email, username=user.username)
  except:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="创建用户错误"
    )


@app.post("/auth/sign_in")
def sign_in(input: SignInIn) -> bool:
  """Check email and password."""
  
  user: UserRecord = get_user(input.email)
  return verify_password(input.password, user.password_hash)