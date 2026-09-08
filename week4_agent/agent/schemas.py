# week4_agent/agent/schemas.py
from pydantic import BaseModel, Field
from typing import Literal


class PlanStep(BaseModel):
  id: int = Field(description="步骤编号，从1开始")
  goal: str = Field(description="这一步要达成的目标，一句话，必须可独立执行")
  depends_on: list[int] = Field(default_factory=list, description="依赖哪些步骤的结果")
  suggested_tool: str | None = Field(default=None, description="建议使用的工具名，可为空")
  
  
class Plan(BaseModel):
  reasoning: str = Field(description="为什么这样拆分，两三句话")
  steps: list[PlanStep] = Field(max_length=8, description="步骤列表，最多8步")