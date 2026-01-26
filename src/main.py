"""Hire Katie - FastAPI application entry point."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from .config import load_config
from .routes import admin, api, webhooks
from .services.stripe_service import init_stripe
from .utils.db import init_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    config = load_config()
    
    # Initialize database
    logger.info("Initializing database...")
    init_db()
    
    # Initialize Stripe
    if config.stripe.secret_key:
        logger.info("Initializing Stripe...")
        init_stripe(config.stripe.secret_key)
    else:
        logger.warning("Stripe secret key not configured")
    
    # Create FastAPI app
    app = FastAPI(
        title="Hire Katie",
        description="AI developer subscription service",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc"
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://blackabee.com",
            "http://localhost:8081",
            "http://127.0.0.1:8081"
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(webhooks.router, tags=["webhooks"])
    app.include_router(api.router, tags=["api"])
    app.include_router(admin.router, tags=["admin"])
    
    # Mount static files
    try:
        app.mount("/hire", StaticFiles(directory="static/hire", html=True), name="hire")
        logger.info("Mounted static files at /hire")
    except Exception as e:
        logger.warning(f"Could not mount static files: {e}")
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "ok"}
    
    logger.info("Application created successfully")
    return app


app = create_app()


if __name__ == "__main__":
    config = load_config()
    logger.info(f"Starting server on {config.server.host}:{config.server.port}")
    uvicorn.run(
        "src.main:app",
        host=config.server.host,
        port=config.server.port,
        reload=False
    )
