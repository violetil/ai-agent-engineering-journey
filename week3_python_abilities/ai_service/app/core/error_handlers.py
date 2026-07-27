import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.errors import (
  AppError,
  InvalidCredentialsError,
  UnsupportedModelError,
  UpstreamServiceError,
  UpstreamTimeoutError,
  UserAlreadyExistsError,
)


# 业务异常类型映射表
ERROR_MAP: dict[type[AppError], tuple[int, str]] = {
  UserAlreadyExistsError: (409, "USER_ALREADY_EXISTS"),
  InvalidCredentialsError: (401, "INVALID_CREDENTIALS"),
  UnsupportedModelError: (422, "UNSUPPORTED_MODEL"),
  UpstreamTimeoutError: (504, "UPSTREAM_TIMEOUT"),
  UpstreamServiceError: (504, "UPSTREAM_ERROR")
}


logger = logging.getLogger(__name__)


def _error_json(status_code: int, code: str, message: str) -> JSONResponse:
  return JSONResponse(
    status_code=status_code,
    content={"error": {"code": code, "message": message}}
  )


def register_error_handlers(app: FastAPI) -> None:
  
  @app.exception_handler(AppError)
  async def handle_app_error(request: Request, exc: AppError):
    """所有业务异常:查业务异常类型表翻译成 HTTP 响应"""
    status_code, code = ERROR_MAP.get(type(exc), (400, "BAD_REQUEST"))
    if status_code >= 500:
      logger.warning("上游错误 %s %s: %s", request.method, request.url, exc)
    return _error_json(status_code, code, exc.message)
  
  @app.exception_handler(RequestValidationError)
  async def handle_validation_error(request: Request, exc: RequestValidationError):
    """把 FastAPI 自带的 422 也收编成统一格式。"""
    first = exc.errors()[0]
    field = ".".join(str(x) for x in first["loc"])
    return _error_json(422, "VALIDATION_ERROR", f"{field}: {first['msg']}")
  
  @app.exception_handler(Exception)
  async def handle_unexpected(request: Request, exc: Exception):
    """最后的兜底：真正的 bug 走这里。"""
    logger.exception("未处理异常 %s %s", request.method, request.url.path)
    return _error_json(500, "INTERNAL_ERROR", "服务器内部错误，请稍后重试")