"""StoryTale FastAPI 앱 뼈대.

S4: 라우터 구조, 미들웨어(CORS, 에러핸들링), 헬스체크.
"""

import json
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from storytale.api.router import api_router

app = FastAPI(
    title="StoryTale API",
    version="0.1.0",
    description="개인화 아동 그림책 생성 API",
)

# CORS 설정
origins_str = os.getenv("CORS_ORIGINS", '["http://localhost:8081"]')
try:
    origins = json.loads(origins_str)
except json.JSONDecodeError:
    origins = ["http://localhost:8081"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 커스텀 에러 핸들러
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.status_code, "message": exc.detail}},
    )


@app.exception_handler(Exception)
async def custom_general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": {"code": 500, "message": "Internal Server Error"}},
    )


# 라우터 등록
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict:
    """헬스체크 엔드포인트."""
    return {"status": "ok", "version": "0.1.0"}
