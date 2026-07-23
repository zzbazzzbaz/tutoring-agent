import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """业务错误，handler 转为带 detail 包裹的统一错误体。"""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.status_code = status
        self.code = code
        self.message = message


class LightRAGError(Exception):
    """LightRAG 上游调用失败，handler 转 502。"""


def _error_body(code: str, message: str) -> dict:
    return {"detail": {"error": {"code": code, "message": message}}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=_error_body(exc.code, exc.message))

    @app.exception_handler(LightRAGError)
    async def lightrag_error_handler(request: Request, exc: LightRAGError) -> JSONResponse:
        return JSONResponse(status_code=502, content=_error_body("LIGHTRAG_ERROR", str(exc)))

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("未捕获异常: %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content=_error_body("INTERNAL_ERROR", str(exc)))
