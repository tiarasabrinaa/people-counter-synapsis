# /Users/tiarasabrina/Documents/PROJECT/dashboard-people-counter/backend/app/main.py

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import sys

from app.config import settings
from app.database import MongoDB
from app.routers import stats_router, config_router
from app.routers.video import router as video_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for startup and shutdown"""
    # Startup
    logger.info("Starting People Counting API...")
    try:
        await MongoDB.connect_db()
        logger.info("✓ Application started successfully")
        
        # Log CORS origins
        cors_origins = settings.get_cors_origins()
        logger.info(f"✓ CORS enabled for origins: {cors_origins}")
    except Exception as e:
        logger.error(f"✗ Startup error: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down People Counting API...")
    await MongoDB.close_db()
    logger.info("✓ Application shut down successfully")


# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API for People Counting System with Object Detection and Tracking",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Configure CORS - FIXED VERSION
cors_origins = settings.get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info(f"CORS configured with origins: {cors_origins}")


# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "message": "Internal server error",
            "detail": str(exc)
        }
    )


# Include routers
app.include_router(stats_router)
app.include_router(config_router)
app.include_router(video_router)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "message": "People Counting API",
        "version": settings.VERSION,
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc"
    }


# Health check
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        db = MongoDB.get_db()
        if db is None:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "database": "disconnected"
                }
            )
        
        # Ping database
        await db.command('ping')
        
        return {
            "status": "healthy",
            "database": "connected",
            "version": settings.VERSION,
            "cors_origins": cors_origins
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


# API Info
@app.get("/api/info", tags=["Info"])
async def api_info():
    """Get API information"""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "endpoints": {
            "statistics": {
                "GET /api/stats/": "Get historical statistics",
                "GET /api/stats/live": "Get live statistics",
                "GET /api/stats/detections": "Get detection records",
                "GET /api/stats/events": "Get counting events",
                "POST /api/stats/forecast": "Generate forecast"
            },
            "configuration": {
                "GET /api/config/areas": "Get all area configurations",
                "GET /api/config/area/{area_name}": "Get specific area",
                "POST /api/config/area": "Create new area",
                "PUT /api/config/area/{area_name}": "Update area",
                "DELETE /api/config/area/{area_name}": "Delete area",
                "POST /api/config/area/{area_name}/reset": "Reset area data"
            },
            "video": {
                "GET /api/video/stream": "Live video stream (MJPEG)",
                "GET /api/video/snapshot": "Single frame snapshot"
            }
        },
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_json": "/openapi.json"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD,
        log_level="info"
    )