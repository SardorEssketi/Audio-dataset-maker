"""
Minimal Pipeline API with REAL AudioPipeline integration.

Two variants:
1. Direct function call (recommended) - runs AudioPipeline.run_full_pipeline()
2. CLI subprocess call - runs main.py as subprocess

Both integrate with WebSocket, progress tracking, and database updates.
"""

import asyncio
import json
import sys
import subprocess
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

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
    """Minimal pipeline job model with PipelineStep-like progress."""
    __tablename__ = "jobs_real"

    id = Column(Integer, primary_key=True, autoincrement=True)
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    source_type = Column(String(20))
    source_value = Column(Text)
    progress = Column(Integer, default=0)
    current_step = Column(String(30))
    message = Column(Text)
    error = Column(Text, nullable=True)
    traceback = Column(Text, nullable=True)
    last_successful_step = Column(String(30), nullable=True)

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
            "current_step": self.current_step,
            "message": self.message,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


# SQLite database
engine = create_engine("sqlite:///minimal_real_pipeline.db", echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def get_db():
    """Database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        pass  # Executor manages its own session


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
            if websocket in self.active_connections[job_id]:
                self.active_connections[job_id].remove(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

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
# VARIANT 1: Direct AudioPipeline Call
# =====================

class DirectAudioPipelineExecutor:
    """
    Variant 1: Run AudioPipeline directly via function call.

    Pros:
    - Fast startup (no subprocess overhead)
    - Direct progress callback access
    - Better error handling

    Cons:
    - Runs in same process (resource sharing)
    - AudioPipeline.run_full_pipeline() is blocking
    """

    def __init__(self, ws_manager: WebSocketManager):
        self.ws_manager = ws_manager
        self.active_jobs: Dict[int, asyncio.Task] = {}

    def _create_temp_config(
        self,
        user_config: dict,
        source_type: str,
        source_value: str
    ) -> Path:
        """
        Create temporary config file with user settings merged.

        Args:
            user_config: User's custom configuration
            source_type: Source type
            source_value: Source value

        Returns:
            Path to temporary config file
        """
        import tempfile
        import yaml
        from backend.services.config_service import load_default_config

        # Load default config
        default_config = load_default_config()

        # Merge user config
        config = default_config.copy()

        # Apply user overrides
        if user_config:
            for key, value in user_config.items():
                # Handle nested keys like 'huggingface.repo_id'
                parts = key.split('.')
                if len(parts) == 2:
                    section, key_name = parts
                    if section not in config:
                        config[section] = {}
                    config[section][key_name] = value
                else:
                    config[key] = value

        # Ensure paths exist
        import os
        data_dir = Path(tempfile.gettempdir()) / "pipeline_data"
        data_dir.mkdir(parents=True, exist_ok=True)

        config['paths'] = {
            'raw_audio': str(data_dir / 'raw'),
            'normalized_audio': str(data_dir / 'normalized'),
            'denoised_audio': str(data_dir / 'denoised'),
            'vad_segments': str(data_dir / 'vad_segments'),
            'transcriptions': str(data_dir / 'transcriptions'),
            'outputs': str(data_dir / 'outputs'),
            'models': str(data_dir / 'models'),
        }

        # Create temp file
        temp_dir = Path(tempfile.gettempdir()) / "pipeline_configs"
        temp_dir.mkdir(parents=True, exist_ok=True)
        config_path = temp_dir / f"job_config_{datetime.now().timestamp()}.yaml"

        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f)

        return config_path

    async def execute(self, job_id: int, source_type: str, source_value: str):
        """
        Execute AudioPipeline directly.

        Uses ThreadPoolExecutor to run blocking pipeline async.
        """
        db = SessionLocal()

        try:
            job = db.query(Job).filter_by(id=job_id).first()
            if not job:
                print(f"Job {job_id} not found")
                return

            # Create progress callback
            def progress_callback(data: dict):
                """Callback from AudioPipeline.emit_progress()."""
                self._on_progress(job, db, data)

            # Create config file
            config_path = self._create_temp_config({}, source_type, source_value)

            # Update status
            job.status = "running"
            job.started_at = datetime.utcnow()
            job.message = "Starting pipeline..."
            db.commit()
            await self._broadcast(job)

            # Import AudioPipeline (lazy)
            script_dir = Path(__file__).parent.parent / "scripts"
            sys.path.insert(0, str(script_dir))

            # Import AFTER adding scripts to path
            import importlib
            import spec

            # Load main module
            main_path = str(Path(__file__).parent / "main.py")
            spec = spec.from_file_location("main_module", main_path)
            main_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(main_module)

            AudioPipeline = main_module.AudioPipeline

            # Create pipeline instance with callback
            pipeline = AudioPipeline(
                config_path=str(config_path),
                progress_callback=progress_callback
            )

            # Run in executor (blocking call in async context)
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: pipeline.run_full_pipeline(
                    source=source_value,
                    source_type=source_type
                )
            )

            # Handle results
            if results.get('status') == 'success':
                job.status = "completed"
                job.progress = 100
                job.message = "Pipeline completed successfully!"
                job.completed_at = datetime.utcnow()
            else:
                errors = results.get('errors', [])
                job.status = "failed"
                job.error = errors[0] if errors else "Unknown error"
                job.message = f"Pipeline failed: {job.error}"
                job.completed_at = datetime.utcnow()

            db.commit()
            await self._broadcast(job)

        except Exception as e:
            import traceback
            traceback_str = traceback.format_exc()
            print(f"Pipeline error: {e}\n{traceback_str}")

            job.status = "failed"
            job.error = str(e)
            job.traceback = traceback_str
            job.message = f"Error: {str(e)}"
            job.completed_at = datetime.utcnow()
            db.commit()

            await self._broadcast(job)

        finally:
            db.close()

            if job_id in self.active_jobs:
                del self.active_jobs[job_id]

    def _on_progress(self, job: Job, db: Session, data: dict):
        """Handle progress callback from AudioPipeline."""
        step = data.get('step', '')
        status = data.get('status', '')
        progress = data.get('progress', 0)
        message = data.get('message', '')

        # Update job
        job.current_step = step
        job.progress = progress
        job.message = message

        # Update last successful step
        if status in ['completed', 'completed']:
            job.last_successful_step = step

        db.commit()

        # Broadcast
        asyncio.create_task(self._broadcast(job))

    async def _broadcast(self, job: Job):
        """Broadcast job status."""
        await self.ws_manager.broadcast(job.id, job.to_dict())

    def cancel(self, job_id: int) -> bool:
        """Cancel running job."""
        if job_id not in self.active_jobs:
            return False

        task = self.active_jobs[job_id]
        task.cancel()

        # Update database
        db = SessionLocal()
        try:
            job = db.query(Job).filter_by(id=job_id).first()
            if job:
                job.status = "failed"
                job.error = "Cancelled by user"
                job.message = "Cancelled"
                job.completed_at = datetime.utcnow()
                db.commit()
                asyncio.create_task(self._broadcast(job))

            del self.active_jobs[job_id]
            return True
        finally:
            db.close()


# =====================
# VARIANT 2: CLI Subprocess Call
# =====================

class CLIAudioPipelineExecutor:
    """
    Variant 2: Run AudioPipeline via CLI subprocess.

    Pros:
    - True isolation (separate process)
    - No resource sharing issues
    - Can kill subprocess cleanly

    Cons:
    - Slower startup
    - Progress parsed from stdout (less accurate)
    - Harder error handling
    """

    def __init__(self, ws_manager: WebSocketManager):
        self.ws_manager = ws_manager
        self.active_processes: Dict[int, asyncio.subprocess.Process] = {}

    def _create_temp_config(self, source_type: str, source_value: str) -> Path:
        """Create temporary config for CLI execution."""
        import tempfile
        import yaml

        # Load default
        default_config = yaml.safe_load(
            open(Path(__file__).parent / "config" / "config.yaml")
        )

        # Create paths
        data_dir = Path(tempfile.gettempdir()) / "pipeline_data_cli"
        data_dir.mkdir(parents=True, exist_ok=True)

        default_config['paths'] = {
            'raw_audio': str(data_dir / 'raw'),
            'normalized_audio': str(data_dir / 'normalized'),
            'denoised_audio': str(data_dir / 'denoised'),
            'vad_segments': str(data_dir / 'vad_segments'),
            'transcriptions': str(data_dir / 'transcriptions'),
            'outputs': str(data_dir / 'outputs'),
            'models': str(data_dir / 'models'),
        }

        # Create temp file
        temp_dir = Path(tempfile.gettempdir()) / "pipeline_configs"
        temp_dir.mkdir(parents=True, exist_ok=True)
        config_path = temp_dir / f"job_cli_config_{datetime.now().timestamp()}.yaml"

        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f)

        return config_path

    async def execute(
        self,
        job_id: int,
        source_type: str,
        source_value: str
    ):
        """Execute AudioPipeline via CLI subprocess."""
        db = SessionLocal()

        try:
            job = db.query(Job).filter_by(id=job_id).first()
            if not job:
                print(f"Job {job_id} not found")
                return

            # Create config
            config_path = self._create_temp_config(source_type, source_value)

            # Build CLI command
            cmd = [
                sys.executable,
                str(Path(__file__).parent / "main.py"),
                "--config", str(config_path),
                "--source", source_value,
                "--type", source_type
            ]

            # Update status
            job.status = "running"
            job.started_at = datetime.utcnow()
            job.message = "Starting pipeline subprocess..."
            db.commit()
            await self._broadcast(job)

            # Start subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(Path(__file__).parent)
            )

            self.active_processes[job_id] = process

            # Parse output
            step_mapping = {
                "STEP 1: Downloading": "download",
                "STEP 2: Normalizing": "normalize",
                "STEP 3: Applying noise reduction": "noise_reduction",
                "STEP 4: Segmenting": "vad_segmentation",
                "STEP 5: Transcribing": "transcription",
                "STEP 6: Filtering": "filter",
                "STEP 7: Pushing": "push",
            }

            current_step = None
            step_progress = 0

            async for line in process.stdout:
                line_text = line.decode('utf-8', errors='ignore')

                # Detect step changes
                for step_marker, step_name in step_mapping.items():
                    if step_marker in line_text:
                        current_step = step_name
                        step_progress = 0

                        job.current_step = step_name
                        job.message = f"Running: {step_name}"
                        db.commit()
                        await self._broadcast(job)

                # Parse progress patterns
                import re
                progress_match = re.search(r'Progress[:\s*(\d+)%?', line_text)
                if progress_match:
                    step_progress = int(progress_match.group(1))
                    overall_progress = self._calculate_overall_progress(current_step, step_progress)
                    job.progress = overall_progress
                    db.commit()
                    await self._broadcast(job)

                # Parse step completion
                for step_marker, step_name in step_mapping.items():
                    if step_marker in line_text and "✓" in line_text:
                        if current_step == step_name:
                            current_step = step_name
                            job.last_successful_step = step_name
                            db.commit()

            # Wait for completion
            returncode = await process.wait()

            # Handle result
            if returncode == 0:
                job.status = "completed"
                job.progress = 100
                job.message = "Pipeline completed successfully!"
                job.completed_at = datetime.utcnow()
            else:
                job.status = "failed"
                job.error = f"Exit code: {returncode}"
                job.message = f"Pipeline failed (exit code {returncode})"
                job.completed_at = datetime.utcnow()

            db.commit()
            await self._broadcast(job)

        except asyncio.CancelledError:
            # Job was cancelled
            job.status = "failed"
            job.error = "Cancelled by user"
            job.message = "Cancelled"
            job.completed_at = datetime.utcnow()
            db.commit()

            await self._broadcast(job)

            # Kill subprocess
            if job_id in self.active_processes:
                process = self.active_processes[job_id]
                try:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    process.kill()

            raise

        except Exception as e:
            import traceback
            traceback_str = traceback.format_exc()

            job.status = "failed"
            job.error = str(e)
            job.traceback = traceback_str
            job.message = f"Error: {str(e)}"
            job.completed_at = datetime.utcnow()
            db.commit()

            await self._broadcast(job)

        finally:
            db.close()

            if job_id in self.active_processes:
                del self.active_processes[job_id]

    def _calculate_overall_progress(self, step: str, step_progress: int) -> int:
        """Calculate overall progress based on step and step progress."""
        steps = ["download", "normalize", "noise_reduction", "vad_segmentation", "transcription", "filter", "push"]
        step_count = len(steps)

        try:
            step_index = steps.index(step)
        except ValueError:
            return step_progress

        # Overall progress = (completed_steps * 100) + current_step_progress
        # Divided by total steps for percentage
        overall = (step_index * 100 + step_progress) / step_count
        return int(overall)

    async def _broadcast(self, job: Job):
        """Broadcast job status."""
        await self.ws_manager.broadcast(job.id, job.to_dict())

    def cancel(self, job_id: int) -> bool:
        """Cancel running subprocess."""
        if job_id not in self.active_processes:
            return False

        process = self.active_processes[job_id]

        try:
            process.terminate()
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

        # Update database
        db = SessionLocal()
        try:
            job = db.query(Job).filter_by(id=job_id).first()
            if job:
                job.status = "failed"
                job.error = "Cancelled by user"
                job.message = "Cancelled"
                job.completed_at = datetime.utcnow()
                db.commit()
                asyncio.create_task(self._broadcast(job))

            del self.active_processes[job_id]
            return True
        finally:
            db.close()


# =====================
# SELECT VARIANT
# =====================

# Change this to switch between variants:
#   True = Direct function call (VARIANT 1)
#   False = CLI subprocess (VARIANT 2)
USE_DIRECT_EXECUTOR = True

if USE_DIRECT_EXECUTOR:
    PipelineExecutor = DirectAudioPipelineExecutor
    print("Using DirectAudioPipelineExecutor (Variant 1)")
else:
    PipelineExecutor = CLIAudioPipelineExecutor
    print("Using CLIAudioPipelineExecutor (Variant 2)")


# =====================
# FASTAPI APP
# =====================

class CreateJobRequest(BaseModel):
    source_type: str
    source_value: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifecycle."""
    print("=" * 60)
    print(f"Minimal Pipeline API (Real AudioPipeline)")
    print(f"Executor: {'Direct (V1)' if USE_DIRECT_EXECUTOR else 'CLI (V2)'}")
    print("=" * 60)
    yield
    print("\nShutting down...")


app = FastAPI(
    title="Minimal Pipeline API",
    description="Minimal example with real AudioPipeline integration",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "message": "Minimal Pipeline API with Real AudioPipeline",
        "executor": "Direct (V1)" if USE_DIRECT_EXECUTOR else "CLI (V2)",
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
    request: CreateJobRequest
):
    """Create a new pipeline job."""
    db = SessionLocal()

    try:
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

        # Start pipeline
        executor = PipelineExecutor(ws_manager)
        task = asyncio.create_task(executor.execute(job.id, request.source_type, request.source_value))

        if hasattr(executor, 'active_jobs'):
            executor.active_jobs[job.id] = task
        elif hasattr(executor, 'active_processes'):
            executor.active_processes[job.id] = task

        return job.to_dict()

    finally:
        db.close()


@app.get("/api/pipelines")
def list_jobs(
    status: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """List all pipeline jobs."""
    query = db.query(Job)

    if status:
        query = query.filter_by(status=status)

    jobs = query.order_by(Job.created_at.desc()).limit(limit).all()

    return {
        "count": len(jobs),
        "executor": "Direct (V1)" if USE_DIRECT_EXECUTOR else "CLI (V2)",
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
    job_id: int
):
    """Cancel a running job."""
    db = SessionLocal()

    try:
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

        executor = PipelineExecutor(ws_manager)
        cancelled = executor.cancel(job_id)

        if not cancelled:
            return {"success": False, "message": "Job is not running"}

        return {
            "success": True,
            "message": f"Job {job_id} cancelled",
            "job": job.to_dict()
        }

    finally:
        db.close()


@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: int):
    """WebSocket endpoint for real-time progress."""
    db = SessionLocal()

    try:
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


if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 60)
    print("MINIMAL PIPELINE API WITH REAL AUDIOPIPELINE")
    print("=" * 60)
    print("\nSet USE_DIRECT_EXECUTOR in file to switch variants:")
    print("  USE_DIRECT_EXECUTOR = True   # Direct function call (recommended)")
    print("  USE_DIRECT_EXECUTOR = False  # CLI subprocess call")
    print("=" * 60)
    print()

    uvicorn.run(
        "minimal_with_real_pipeline:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
