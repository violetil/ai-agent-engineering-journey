from fastapi import FastAPI, status
from app.schemas.auth import UserCreate, UserOut, SignInIn, TokenOut
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import chat_completions
from app.services.auth_service import register_user, login
from app.api.deps import CurrentUser
from app.core.error_handlers import register_error_handlers


app = FastAPI(title="Violet AI API Service")
register_error_handlers(app)


# ---------- Routers ----------
@app.get("/")
def root():
  return { "message": "Violet AI API Service" }
  

@app.post("/chat/completions", response_model=ChatResponse)
def _chat_completions(body: ChatRequest, user: CurrentUser):
  return chat_completions(body)


@app.post("/auth/sign_up", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def _sign_up(user: UserCreate):
  """Create an user in database"""
  return register_user(user)


@app.post("/auth/sign_in", response_model=TokenOut)
def _sign_in(body: SignInIn):
  """Check email and password."""
  return login(body)