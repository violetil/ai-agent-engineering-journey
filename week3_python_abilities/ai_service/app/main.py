from fastapi import FastAPI, status, HTTPException
from app.schemas.auth import UserCreate, UserOut, SignInIn, TokenOut
from app.schemas.chat import ChatPrompt
from app.llm.llm_call import ask_llm
from app.services.auth_service import register_user, login
from app.api.deps import CurrentUser


app = FastAPI(
  title="Violet AI API Service"
)


# ---------- Routers ----------
@app.get("/")
def root():
  return {
    "message": "Violet AI API Service"
  }
  

@app.post("/chat/completions")
async def chat_completions(body: ChatPrompt, user: CurrentUser) -> str:
  return await ask_llm(body.prompt)


# @app.post("/chat/completions/multi")
# async def multi_chat_completions(input: list[ChatCompletionsIn]) -> list[str]:
#   return await ask_llm_many([t.prompt for t in input])


@app.post("/auth/sign_up", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def sign_up(user: UserCreate):
  """Create an user in database"""
  
  try:
    return register_user(user)
  except:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="用户已存在"
    )


@app.post("/auth/sign_in", response_model=TokenOut)
def sign_in(body: SignInIn):
  """Check email and password."""
  
  try:
    return login(body)
  except:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="邮箱或密码错误"
    )