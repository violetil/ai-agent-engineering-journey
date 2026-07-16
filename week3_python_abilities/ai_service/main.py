from fastapi import FastAPI, status, HTTPException
from llm_call import ask_llm, ask_llm_many
from db.models import User
from service.auth import write_user, check_password
from pydantic import BaseModel, Field


app = FastAPI(
  title="Violet AI API Service"
)


# ---------- Schemas ----------
class ChatCompletionsIn(BaseModel):
  prompt: str
  

class SignIn(BaseModel):
  email: str
  password: str


# ---------- Routers ----------
@app.get("/")
def root():
  return {
    "message": "Violet AI API Service"
  }
  

@app.post("/chat/completions")
async def chat_completions(input: ChatCompletionsIn) -> str:
  return await ask_llm(input.prompt)


@app.post("/chat/completions/multi")
async def multi_chat_completions(input: list[ChatCompletionsIn]) -> list[str]:
  return await ask_llm_many([t.prompt for t in input])


@app.post("/auth/sign_up", status_code=status.HTTP_201_CREATED)
def sign_up(user: User):
  """Create an user in database"""
  
  write_user(user)


@app.post("/auth/sign_in")
def sign_in(input: SignIn) -> str:
  if check_password(input.email, input.password):
    return f"access token {input.email}"
  raise HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, 
    detail="密码或账号错误"
  )