from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.clock import Clock

app = FastAPI(title="NovaStart")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    """探活接口：server_time 是前端校准时钟的唯一来源。"""
    return {"status": "ok", "server_time": Clock().now().isoformat()}
