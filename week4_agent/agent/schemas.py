# week4_agent/agent/schemas.py
from pydantic import BaseModel, Field
from typing import Literal
from dataclasses import dataclass, field


class PlanStep(BaseModel):
  id: int = Field(description="步骤编号，从1开始")
  goal: str = Field(description="这一步要达成的目标，一句话，必须可独立执行")
  depends_on: list[int] = Field(default_factory=list, description="依赖哪些步骤的结果")
  suggested_tool: str | None = Field(default=None, description="建议使用的工具名，可为空")
  
  
class Plan(BaseModel):
  reasoning: str = Field(description="为什么这样拆分，两三句话")
  steps: list[PlanStep] = Field(max_length=8, description="步骤列表，最多8步")
  

class StepResult(BaseModel):
  status: Literal["success", "failed", "partial"]
  output: str = Field(description="给后续步骤用的事实性结论，不要客套话")
  note: str | None = Field(default=None, description="遇到的问题或不确定之处")
  
  
@dataclass
class Blackboard:
  results: dict[int, str] = field(default_factory=dict)
  failures: dict[int, str] = field(default_factory=dict)
  
  def context_for(self, step: PlanStep) -> str:
    lines = []
    for dep in step.depends_on:
      if dep in self.results:
        lines.append(f"步骤 {dep} 的结果：{self.results[dep]}")
      elif dep in self.failures:
        lines.append(f"步骤 {dep} 执行失败：{self.failures[dep]}")
    return "\n".join(lines)