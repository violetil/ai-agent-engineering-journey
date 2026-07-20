from pydantic import BaseModel, EmailStr, Field
from typing import Annotated


class TokenOut(BaseModel):
  access_token: str
  token_type: str = "bearer"


class UserOut(BaseModel):
  email: EmailStr
  username: Annotated[str, Field(min_length=3, max_length=15)]
  
  
class UserCreate(UserOut):
  password: Annotated[str, Field(min_length=8)]
  

class SignInIn(BaseModel):
  email: EmailStr
  password: Annotated[str, Field(min_length=8)]
  
  
class UserRecord(UserOut):
  password_hash: str