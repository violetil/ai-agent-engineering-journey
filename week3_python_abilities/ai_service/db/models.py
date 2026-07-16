from pydantic import BaseModel, Field


class User(BaseModel):
  email: str
  username: str
  password: str