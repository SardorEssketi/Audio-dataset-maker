"""
Minimal working example of Pipeline API.

Features:
- POST /api/pipelines - create job
- Queue system
- Pipeline execution
- Status updates
- WebSocket for progress

No frontend required - test with curl or Python requests.
"""

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import uuid

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session


# =====================
# DATABASE
# =====================

Base = declarative_base()

class Job(Base):
    """Minimal pipeline job model."""
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    source_type = Column(String(20))
    source_value = Column(Text)
    progress = Column(Integer, default=0)
    message = Column(Text)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    def to_dict(self):
        """Convert to dict for API response."""
        return {
            "id": self.id,
            "status": self.status,
            "source_type": self.source_type,
            "source_value": self.source_value,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


# SQLite database
engine = create_engine("sqlite:///minimal_jobs.db", echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def get_db():
    """Database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        # Don't close here - executor manages its own session
        pass


# =====================
# WEBSOCKET MANAGER
# =====================

class WebSocketManager:
    """Simple WebSocket manager for progress broadcasts."""

    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, job_id: int):
        """Accept new connection."""
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)
        print(f"WebSocket connected for job {job_id}")

    def disconnect(self, websocket: WebSocket, job_id: int):
        """Remove connection."""
        if job_id in self.active_connections:
            self.active_connections[job_id].remove(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]
        print(f"WebSocket disconnected for job {job_id}")

    async def broadcast(self, job_id: int, data: dict):
        """Send data to all connections for a job."""
        if job_id not in self.active_connections:
            return

        disconnected = []
        for ws in self.active_connections[job_id]:
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.append(ws)

        # Clean up disconnected
        for ws in disconnected:
            self.disconnect(ws, job_id)


# Global WebSocket manager
ws_manager = WebSocketManager()


# =====================
# PIPELINE EXECUTOR
# =====================

class MinimalPipelineExecutor:
    """Minimal pipeline executor with progress tracking."""

    def __init__(self, ws_manager: WebSocketManager):
        self.ws_manager = ws_manager
        self.active_jobs: Dict[int, asyncio.Task] = {}

    async def execute(self, job_id: int):
        """Execute pipeline for a job."""
        # Create own DB session
        db = SessionLocal()

        try:
            job = db.query(Job).filter_by(id=job_id).first()
            if not job:
                print(f"Job {job_id} not found")
                return

            print(f"Starting pipeline for job {job_id}...")

            # Update status
            job.status = "running"
            job.started_at = datetime.utcnow()
            job.message = "Starting pipeline..."
            job.progress = 0
            db.commit()
            await self._broadcast(job)

            # Simulate pipeline steps (replace with real AudioPipeline)
            steps = [
                ("download", "Downloading files..."),
                ("normalize", "Normalizing audio..."),
                ("transcribe", "Transcribing with Whisper..."),
                ("push", "Pushing to HuggingFace..."),
            ]

            for i, (step_name, step_msg) in enumerate(steps):
                # Start step
                job.message = f"Step {i+1}/4: {step_msg}"
                db.commit()
                await self._broadcast(job)

                # Simulate work (replace with real pipeline)
                for progress in range(0, 101, 25):
                    job.progress = i * 25 + progress
                    await asyncio.sleep(0.2)  # Simulate work
                    await self._broadcast(job)
                    job.message = f"{step_msg} ({progress}%)"
                    db.commit()

            # Complete
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            job.progress = 100
            job.message = "Pipeline completed successfully!"
            db.commit()
            await self._broadcast(job)

            print(f"Pipeline completed for job {job_id}")

        finally:
            db.close()

            # Clean up
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]

    async def _broadcast(self, job: Job):
        """Broadcast job status via WebSocket."""
        await self.ws_manager.broadcast(job.id, job.to_dict())

    def cancel(self, job_id: int) -> bool:
        """Cancel a running job."""
        if job_id not in self.active_jobs:
            return False

        task = self.active_jobs[job_id]
        task.cancel()

        # Update job status - create own session
        db = SessionLocal()
        try:
            job = db.query(Job).filter_by(id=job_id).first()
            if job:
                job.status = "failed"
                job.error = "Cancelled by user"
                job.completed_at = datetime.utcnow()
                db.commit()
                asyncio.create_task(self._broadcast(job))

            del self.active_jobs[job_id]
            return True
        finally:
            db.close()


# =====================
# FASTAPI APP
# =====================

# Request models
class CreateJobRequest(BaseModel):
    source_type: str
    source_value: str


# Lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifecycle."""
    print("=" * 60)
    print("Minimal Pipeline API starting...")
    print("=" * 60)
    yield
    print("\nShutting down...")


# Create app
app = FastAPI(
    title="Minimal Pipeline API",
    description="Minimal working example of pipeline management",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================
# ROUTES
# =====================

@app.get("/")
def root():
    """Root endpoint."""
    return {
        "message": "Minimal Pipeline API",
        "docs": "/docs",
        "endpoints": {
            "POST /api/pipelines": "Create a new pipeline job",
            "GET /api/pipelines": "List all jobs",
            "GET /api/pipelines/{id}": "Get job details",
            "POST /api/pipelines/{id}/cancel": "Cancel a job",
            "WebSocket /ws/{id}": "Real-time progress",
        }
    }


@app.post("/api/pipelines", status_code=201)
async def create_job(
    request: CreateJobRequest,
    db: Session = Depends(get_db)
):
    """
    Create a new pipeline job.

    Creates job record and adds to execution queue.
    """
    # Create job
    job = Job(
        source_type=request.source_type,
        source_value=request.source_value,
        status="pending",
        progress=0,
        message="Job created, waiting in queue..."
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    print(f"Job {job.id} created: {request.source_type} - {request.source_value}")

    # Start pipeline in background
    executor = MinimalPipelineExecutor(ws_manager)
    task = asyncio.create_task(executor.execute(job.id))
    executor.active_jobs[job.id] = task

    return job.to_dict()


@app.get("/api/pipelines")
def list_jobs(
    status: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    List all pipeline jobs.

    Optional status filter: ?status=running
    Pagination: ?limit=10
    """
    query = db.query(Job)

    if status:
        query = query.filter_by(status=status)

    jobs = query.order_by(Job.created_at.desc()).limit(limit).all()

    return {
        "count": len(jobs),
        "jobs": [job.to_dict() for job in jobs]
    }


@app.get("/api/pipelines/{job_id}")
def get_job(
    job_id: int,
    db: Session = Depends(get_db)
):
    """Get details of a specific job."""
    job = db.query(Job).filter_by(id=job_id).first()

    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")

    return job.to_dict()


@app.post("/api/pipelines/{job_id}/cancel")
def cancel_job(
    job_id: int,
    db: Session = Depends(get_db)
):
    """Cancel a running job."""
    job = db.query(Job).filter_by(id=job_id).first()

    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in ["pending", "running"]:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job with status: {job.status}"
        )

    executor = MinimalPipelineExecutor(ws_manager)
    cancelled = executor.cancel(job_id)

    if not cancelled:
        return {"success": False, "message": "Job is not running"}

    return {
        "success": True,
        "message": f"Job {job_id} cancelled",
        "job": job.to_dict()
    }


@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: int):
    """
    WebSocket endpoint for real-time progress.

    Connect to: ws://localhost:8000/ws/{job_id}
    """
    # Check if job exists
    db = SessionLocal()
    job = db.query(Job).filter_by(id=job_id).first()
    db.close()

    if not job:
        await websocket.close(code=4004, reason="Job not found")
        return

    # Accept connection
    await ws_manager.connect(websocket, job_id)

    try:
        # Send initial state
        await websocket.send_json(job.to_dict())

        # Keep connection alive
        while True:
            data = await websocket.receive_json()
            print(f"Received from client: {data}")

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for job {job_id}")
    finally:
        ws_manager.disconnect(websocket, job_id)


# =====================
# MAIN
# =====================

if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("MINIMAL PIPELINE API")
    print("=" * 60)
    print("\nTest with curl:")
    print()
    print("# Create job:")
    print('curl -X POST http://localhost:8000/api/pipelines \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"source_type": "youtube", "source_value": "https://youtube.com/watch?v=xxx"}\'')
    print()
    print("# List jobs:")
    print('curl http://localhost:8000/api/pipelines')
    print()
    print("# Get job:")
    print('curl http://localhost:8000/api/pipelines/1')
    print()
    print("# Cancel job:")
    print('curl -X POST http://localhost:8000/api/pipelines/1/cancel')
    print()
    print("# WebSocket (use websocat or similar):")
    print('websocat ws://localhost:8000/ws/1')
    print("=" * 60)
    print()

    uvicorn.run(
        "minimal_example:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
