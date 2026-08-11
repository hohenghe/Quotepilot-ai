"""
QuotePilot AI — Backend API Server
Main application entry point.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import init_db
from app.api.products import router as products_router
from app.api.inquiries import router as inquiries_router
from app.api.quotes import router as quotes_router
from app.api.dashboard import router as dashboard_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="QuotePilot AI",
    description="AI-powered sales assistant for international trade",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products_router)
app.include_router(inquiries_router)
app.include_router(quotes_router)
app.include_router(dashboard_router)


@app.get("/")
async def root():
    return {"service": "QuotePilot AI", "version": "0.1.0", "status": "running"}


@app.get("/api/health")
async def health():
    return {"status": "healthy"}
