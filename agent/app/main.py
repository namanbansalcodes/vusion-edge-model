from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app import db
from app.ws import clients as ws_clients


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_pool()
    print("DB pool ready")
    yield
    await db.close_pool()
    print("DB pool closed")


app = FastAPI(title="Store #142 Retail Agent", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in ws_clients:
            ws_clients.remove(ws)


from app.routes.events import router as events_router
from app.routes.manager import router as manager_router
from app.routes.workers import router as workers_router
from app.routes.dashboard import router as dashboard_router

app.include_router(events_router)
app.include_router(manager_router)
app.include_router(workers_router)
app.include_router(dashboard_router)


@app.get("/health")
async def health():
    row = await db.fetch_one("SELECT 1 AS ok")
    return {"status": "healthy" if row else "db_error", "db": "mysql", "tts": "edge-tts"}