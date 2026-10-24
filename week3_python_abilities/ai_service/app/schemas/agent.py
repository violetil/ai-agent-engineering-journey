# ai_service/app/schemas/agent.py
from typing import Literal
from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
  task: str = Field(min_length=10, max_length=2000)
  mode: Literal["loop", "plan"] = "loop"
  max_steps: int = Field(default=10, ge=1, le=20)