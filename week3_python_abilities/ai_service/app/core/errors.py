class AppError(Exception):
  """业务异常基类"""
  def __init__(self, message: str):
    super().__init__(message)
    self.message = message
    
    
class UserAlreadyExistsError(AppError):
  def __init__(self, email: str):
    super().__init__(f"用户 {email} 已存在")
    self.email = email
    

class UserNotExistsError(AppError):
  def __init__(self, email: str):
    super().__init__(f"用户 {email} 不存在")
    self.email = email
    
    
class InvalidCredentialsError(AppError):
  def __init__(self):
    super().__init__("邮箱或密码错误")
    
    
class UnsupportedModelError(AppError):
  def __init__(self, provider: str):
    super().__init__(f"暂不支持模型提供方：{provider}")
    self.provider = provider
    
    
class UpstreamServiceError(AppError):
  """上游(LLM)返回错误"""
    

class UpstreamTimeoutError(AppError):
  """上游(LLM)调用超时"""
  
  
class QuotaExceededError(AppError):
  """权限不够"""