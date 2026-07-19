from pydantic import BaseModel


class UserCreate(BaseModel):
  email: str
  username: str
  password: str
  
  
class UserOut(BaseModel):
  email: str
  username: str
  
  
class SignInIn(BaseModel):
  email: str
  password: str
  
  
class UserRecord(BaseModel):
  email: str
  username: str
  password_hash: str