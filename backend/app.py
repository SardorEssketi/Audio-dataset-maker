"""
FastAPI application entry point.
Main server initialization, middleware, and dependency setup.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import init_db, get_db
from backend.services.websocket_manager import WebSocketManager, manager
from backend.services.pipeline_executor import DirectPipelineExecutor, BackgroundJobScheduler
from backend.services.pipeline_manager import PipelineJobManager

# Import routes
from backend.routes import auth, pipelines, config, files, websocket


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    print("Starting application...")
    print(f"Database URL: {settings.database_url or 'SQLite (default)'}")

    # Security warning for default secret key
    if settings.secret_key == "CHANGE_THIS_IN_PRODUCTION_USE_ENV_VAR" or len(settings.secret_key) < 32:
        print("\n" + "="*60)
        print("WARNING: Using insecure SECRET_KEY!")
        print("Please set SECRET_KEY environment variable (min 32 chars)")
        print("="*60 + "\n")

    # Initialize database tables
    init_db()
    print("Database initialized")

    # Initialize WebSocket manager
    # Use the single shared manager instance so /ws consumers and job executor
    # publish/subscribe on the same connection pool.
    ws_manager = manager
    app.state.ws_manager = ws_manager
    print("WebSocket manager initialized")

    # Initialize pipeline executor (direct execution mode)
    pipeline_executor = DirectPipelineExecutor(ws_manager)
    app.state.executor = pipeline_executor
    print("Pipeline executor initialized (direct mode)")

    # Yield control to the application
    yield

    # Shutdown
    print("Shutting down application...")

    # Clean up WebSocket connections
    if hasattr(app.state, 'ws_manager'):
        # Create async task for cleanup
        async def cleanup():
            for job_id in list(app.state.ws_manager.active_connections.keys()):
                await app.state.ws_manager.cleanup_job_connections(job_id)
            print("WebSocket connections cleaned up")

        # Run cleanup in event loop
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(cleanup())
            else:
                asyncio.run(cleanup())
        except Exception as e:
            print(f"Cleanup error: {e}")

    # Cancel running jobs
    if hasattr(app.state, 'executor'):
        running_jobs = app.state.executor.get_active_jobs()
        for job_id in running_jobs:
            app.state.executor.cancel_job(job_id)
        print(f"Cancelled {len(running_jobs)} running jobs")

    print("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Audio Pipeline API",
    description="Web application for managing Python audio processing pipelines",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency: get ws_manager from app state
def get_ws_manager(request: Request) -> WebSocketManager:
    """
    Get WebSocket manager from app state.
    """
    return request.app.state.ws_manager


# Dependency: get executor from app state
def get_executor(request: Request) -> DirectPipelineExecutor:
    """
    Get pipeline executor from app state.
    """
    return request.app.state.executor


# Dependency: get pipeline manager
def get_pipeline_manager(
    request: Request,
    db: Session = Depends(get_db),
    ws_manager: WebSocketManager = Depends(get_ws_manager)
) -> PipelineJobManager:
    """
    Get pipeline manager instance with WebSocket support.
    """
    return PipelineJobManager(db, ws_manager)


# Dependency: get background scheduler
def get_background_scheduler(
    request: Request,
    db: Session = Depends(get_db),
    ws_manager: WebSocketManager = Depends(get_ws_manager),
    executor: DirectPipelineExecutor = Depends(get_executor)
) -> BackgroundJobScheduler:
    """
    Get background job scheduler instance.
    """
    return BackgroundJobScheduler(
        pipeline_manager=PipelineJobManager(db, ws_manager),
        executor=executor,
        db=db
    )


# Override the dependency functions in pipelines.py to use our app-level dependencies
from backend import routes

# Monkey-patch the dependency functions in pipelines module
routes.pipelines.get_pipeline_manager = get_pipeline_manager
routes.pipelines.get_scheduler = get_background_scheduler


# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(pipelines.router, tags=["pipelines"])
# These routers already define their own prefixes.
app.include_router(config.router, tags=["config"])
app.include_router(files.router, tags=["files"])
app.include_router(websocket.router, tags=["websocket"])

# Serve frontend (SPA) if built assets exist.
# We mount assets under /assets and return index.html for any non-API route.
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
frontend_index = frontend_dist / "index.html"
frontend_assets = frontend_dist / "assets"

if frontend_dist.exists() and frontend_index.exists():
    if frontend_assets.exists():
        app.mount("/assets", StaticFiles(directory=str(frontend_assets)), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        # Let API/WebSocket routes behave normally.
        if full_path.startswith("api") or full_path.startswith("ws") or full_path.startswith("assets"):
            raise HTTPException(status_code=404, detail="Not Found")

        return FileResponse(frontend_index)

    print(f"Serving frontend from: {frontend_dist}")
else:
    print("Frontend dist directory not found. Skipping static file serving.")


# Health check endpoint
@app.get("/health")
def health_check():
    """
    Health check endpoint for monitoring.
    """
    return {
        "status": "healthy",
        "service": "audio-pipeline-api",
        "version": "1.0.0"
    }


# Root endpoint is handled by the SPA fallback when frontend/dist exists.


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )
