"""
TiTiler — 独立 COG 瓦片服务

启动方式:
    python titiler_config.py

或者:
    uvicorn titiler_config:app --host 0.0.0.0 --port 8001
"""

from pathlib import Path
from titiler.core.factory import TilerFactory
from titiler.core.dependencies import ColorMapParams
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# COG 目录
COG_DIR = Path(__file__).resolve().parent.parent / "data" / "chongqing_demo" / "cog"
COG_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="山水智鉴 V0 — TiTiler COG 服务", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 使用 TiTiler 内置的 COG 工厂
cog = TilerFactory()
app.include_router(cog.router, prefix="/cog", tags=["COG Tiles"])


@app.get("/")
async def root():
    """TiTiler 服务状态"""
    return {
        "status": "running",
        "cog_dir": str(COG_DIR),
        "docs": "/docs",
        "cog_tilejson": "/cog/tilejson.json",
    }


if __name__ == "__main__":
    print(f"🚀 TiTiler COG Service starting...")
    print(f"   COG 目录: {COG_DIR}")
    print(f"   API 文档: http://localhost:8001/docs")
    uvicorn.run(app, host="0.0.0.0", port=8001)
