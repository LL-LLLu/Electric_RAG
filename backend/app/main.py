import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import documents, search, equipment, health
from app.db.session import init_db
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    logger.info("Starting up...")
    init_db()
    logger.info("Database initialized")

    yield

    logger.info("Shutting down...")


app = FastAPI(
    title="Electrical Drawing RAG API",
    description="API for searching and querying electrical plant drawings",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["Health"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(search.router, prefix="/api/search", tags=["Search"])
app.include_router(equipment.router, prefix="/api/equipment", tags=["Equipment"])


@app.get("/")
async def root():
    return {
        "message": "Electrical Drawing RAG API",
        "docs": "/docs",
        "health": "/health"
    }
