"""
Pipeline executor.
Runs pipeline directly (without subprocess) with real-time progress tracking and database updates.
"""

import asyncio
import sys
import traceback
from pathlib import Path
from typing import Optional, Dict, Callable
from datetime import datetime

# Add scripts directory to path for AudioPipeline import
script_dir = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(script_dir))

from backend.database import SessionLocal


class PipelineStepTracker:
    """
    Tracks and updates PipelineStep records in database.
    Sends progress updates via WebSocket.
    """

    STEPS_ORDER = [
        'download', 'normalize', 'noise_reduction',
        'vad_segmentation', 'transcription', 'filter', 'push'
    ]

    def __init__(
        self,
        job_id: int,
        ws_manager,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        """
        Initialize step tracker.

        Args:
            job_id: Pipeline job ID
            ws_manager: WebSocket manager for broadcasts
        """
        self.job_id = job_id
        self.ws_manager = ws_manager
        self.loop = loop
        self.steps: Dict[str, Optional[int]] = {}
        self.current_step: Optional[str] = None
        self.last_successful_step: Optional[str] = None

    def create_step_records(self, db) -> None:
        """
        Create PipelineStep records for all pipeline steps.
        All steps start with 'pending' status.
        """
        from backend.models.pipeline_job import PipelineStep

        for step_name in self.STEPS_ORDER:
            step = PipelineStep(
                job_id=self.job_id,
                step_name=step_name,
                status='pending',
                progress=0
            )
            db.add(step)
            db.flush()
            self.steps[step_name] = step.id

        db.commit()

    def ensure_step_records(self, db) -> None:
        """
        Ensure step records exist and self.steps is populated.

        Background jobs must not rely on step ids created in a different DB session.
        """
        if self.steps:
            return

        from backend.models.pipeline_job import PipelineStep

        rows = (
            db.query(PipelineStep)
            .filter_by(job_id=self.job_id)
            .all()
        )

        if not rows:
            self.create_step_records(db)
            return

        for row in rows:
            self.steps[row.step_name] = row.id

    def update_step(
        self,
        db,
        step_name: str,
        status: str,
        progress: int = None,
        message: str = None,
        **data
    ) -> None:
        """
        Update PipelineStep record and send WebSocket broadcast.

        Args:
            step_name: Step name (download, normalize, etc.)
            status: New status (pending, running, completed, failed)
            progress: Progress percentage (0-100)
            message: Status message
            **data: Additional data (files_count, segments_count, etc.)
        """
        from backend.models.pipeline_job import PipelineStep

        if not self.steps:
            self.ensure_step_records(db)

        step_id = self.steps.get(step_name)
        if not step_id:
            print(f"Warning: Step {step_name} not found in tracker")
            return

        step = db.query(PipelineStep).filter_by(id=step_id).first()
        if not step:
            return

        # Update record
        step.status = status
        if progress is not None:
            step.progress = max(0, min(100, progress))
        if message:
            step.message = message[:1000]  # Limit message length

        if status == 'running' and not step.started_at:
            step.started_at = datetime.utcnow()

        if status == 'completed':
            step.completed_at = datetime.utcnow()
            step.progress = 100
            self.last_successful_step = step_name

        if status == 'failed':
            if not step.completed_at:
                step.completed_at = datetime.utcnow()

        db.commit()

        # Send WebSocket message
        payload = dict(
            type='progress',
            step=step_name,
            status=status,
            progress=step.progress,
            message=message or '',
            timestamp=datetime.utcnow().isoformat(),
            **data,
        )

        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.ws_manager.broadcast(self.job_id, **payload), self.loop)
        else:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.ws_manager.broadcast(self.job_id, **payload))
            except RuntimeError:
                # Progress callback may be invoked in a worker thread without an event loop.
                pass

        self.current_step = step_name

    def mark_step_failed(self, db, step_name: str, error_message: str) -> None:
        """
        Mark a step as failed.

        Args:
            step_name: Step name
            error_message: Error description
        """
        self.update_step(
            db,
            step_name=step_name,
            status='failed',
            message=f"Error: {error_message}"
        )

    def get_step_status(self, db, step_name: str) -> Optional[Dict]:
        """
        Get current status of a step.

        Args:
            step_name: Step name

        Returns:
            Dict with step status or None if not found
        """
        from backend.models.pipeline_job import PipelineStep

        step = db.query(PipelineStep).filter_by(
            job_id=self.job_id,
            step_name=step_name
        ).first()

        if not step:
            return None

        return {
            'status': step.status,
            'progress': step.progress,
            'message': step.message,
            'started_at': step.started_at.isoformat() if step.started_at else None,
            'completed_at': step.completed_at.isoformat() if step.completed_at else None,
        }

    def get_all_steps_status(self, db) -> Dict[str, Dict]:
        """
        Get status of all steps.

        Returns:
            Dict mapping step_name to status dict
        """
        from backend.models.pipeline_job import PipelineStep

        steps = db.query(PipelineStep).filter_by(
            job_id=self.job_id
        ).all()

        return {
            step.step_name: {
                'status': step.status,
                'progress': step.progress,
                'message': step.message,
            }
            for step in steps
        }


class DirectPipelineExecutor:
    """
    Executes AudioPipeline directly (without subprocess).
    Updates PipelineStep records in database.
    Sends real-time progress via WebSocket.
    """

    def __init__(self, ws_manager):
        """
        Initialize pipeline executor.

        Args:
            ws_manager: WebSocket manager for progress broadcasts
        """
        self.ws_manager = ws_manager
        self.active_jobs: Dict[int, asyncio.Task] = {}

    async def execute_job(
        self,
        job_id: int,
        user_id: int,
        db,
        source_type: str,
        source_value: str,
        skip_download: bool = False,
        skip_push: bool = False,
        file_paths: list = None
    ) -> int:
        """
        Execute pipeline job directly (no subprocess).

        Args:
            job_id: Pipeline job ID
            user_id: User ID
            db: Database session
            source_type: Type of source (url, youtube, json, huggingface, local)
            source_value: Source value (URL, path, dataset name, etc.)
            skip_download: Skip download step
            skip_push: Skip push to HuggingFace
            file_paths: List of file paths (for local source type)

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        # Create step tracker. Progress callbacks run in a worker thread, so
        # WS broadcasts are scheduled onto this loop.
        tracker = PipelineStepTracker(job_id, self.ws_manager, loop=asyncio.get_running_loop())
        tracker.ensure_step_records(db)

        try:
            # Get user config with paths
            from backend.services.config_service import get_user_config_dict_with_paths
            config_dict = get_user_config_dict_with_paths(user_id, db)

            # Save config snapshot (without tokens) to job
            import json
            from backend.models.pipeline_job import PipelineJob
            job = db.query(PipelineJob).filter_by(id=job_id).first()
            if job:
                # Remove sensitive fields for snapshot
                config_snapshot = {}
                for k, v in config_dict.items():
                    if k != 'huggingface':
                        config_snapshot[k] = v
                    else:
                        # Store huggingface without token
                        hf_copy = v.copy() if isinstance(v, dict) else {}
                        hf_copy.pop('token', None)
                        config_snapshot[k] = hf_copy
                job.config_snapshot = json.dumps(config_snapshot)
                db.commit()

            # Create temporary config file
            import tempfile
            import yaml

            temp_dir = Path(tempfile.gettempdir()) / f"pipeline_job_{job_id}"
            temp_dir.mkdir(exist_ok=True, parents=True)
            config_path = temp_dir / "config.yaml"

            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_dict, f)

            # Handle local source with uploaded files
            if source_type == 'local' and file_paths:
                from backend.database import get_job_temp_dir
                job_temp_dir = get_job_temp_dir(user_id, job_id)

                # Copy files to job temp directory
                import shutil
                for file_path in file_paths:
                    if isinstance(file_path, Path):
                        dest_path = job_temp_dir / file_path.name
                        shutil.copy(str(file_path), str(dest_path))

                # Update source_value to point to job temp directory
                source_value = str(job_temp_dir)

            # Import AudioPipeline (lazy import to avoid circular dependencies)
            from main import AudioPipeline

            # Create progress callback
            def progress_callback(data: dict):
                """Callback for AudioPipeline progress updates."""
                self._on_progress(tracker, data)

            # Create pipeline instance with callback
            pipeline = AudioPipeline(
                config_path=str(config_path),
                progress_callback=progress_callback,
                job_id=job_id,
                user_id=user_id,
            )

            # Mark download step as skipped if needed
            if skip_download:
                tracker.update_step(db, 'download', 'completed', progress=100, message='Skipped')
            else:
                tracker.update_step(db, 'download', 'running', progress=0, message='Starting...')

            # Mark push as skipped if needed (pipeline will not run the step).
            if skip_push:
                tracker.update_step(db, 'push', 'completed', progress=100, message='Skipped')

            # Run pipeline (synchronous) in executor
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(
                None,
                lambda: pipeline.run_full_pipeline(
                    source=source_value,
                    source_type=source_type,
                    skip_download=skip_download,
                    skip_push=skip_push
                )
            )

            # Update final status based on results
            if results.get('status') == 'success':
                from backend.models.pipeline_job import PipelineStep
                # Step updates were committed via separate sessions in the worker thread.
                # Ensure we don't use stale ORM state in this session.
                db.expire_all()

                # Mark any remaining running steps as completed
                for step_name in tracker.STEPS_ORDER:
                    step_status = db.query(
                        PipelineStep
                    ).filter_by(
                        job_id=job_id,
                        step_name=step_name
                    ).first()

                    if step_status and step_status.status == 'running':
                        tracker.update_step(db, step_name, 'completed', progress=100)

                return 0
            else:
                # Pipeline reported failure
                error_msg = results.get('errors', ['Unknown error'])[0]
                if tracker.current_step:
                    tracker.mark_step_failed(db, tracker.current_step, error_msg)
                return 1

        except Exception as e:
            # Unhandled exception
            traceback_str = traceback.format_exc()
            print(f"Pipeline execution error: {e}\n{traceback_str}")

            # Mark current step as failed
            if tracker.current_step:
                tracker.mark_step_failed(db, tracker.current_step, str(e))

            return 1

        finally:
            # Cleanup temporary directory
            import shutil
            temp_dir = Path(tempfile.gettempdir()) / f"pipeline_job_{job_id}"
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def _on_progress(self, tracker: PipelineStepTracker, data: dict) -> None:
        """
        Callback for AudioPipeline progress updates.

        Called when AudioPipeline.emit_progress() is called.

        data format:
        {
            'step': 'download' | 'normalize' | ...,
            'status': 'running' | 'completed' | 'error',
            'progress': 0-100,
            'message': '...'
        }

        Args:
            tracker: Step tracker instance
            data: Progress data from AudioPipeline
        """
        step = data.get('step')
        status = data.get('status')
        progress = data.get('progress', 0)
        message = data.get('message', '')

        if not step or not status:
            return

        # Map AudioPipeline statuses to PipelineStep statuses
        step_status = status
        if status == 'error':
            step_status = 'failed'

        # Progress callbacks run inside the worker thread used by run_in_executor.
        # Use a dedicated DB session per event to avoid sharing a Session across threads.
        db = SessionLocal()
        try:
            tracker.update_step(
                db,
                step_name=step,
                status=step_status,
                progress=progress,
                message=message
            )
        finally:
            db.close()

    async def execute_job_with_timeout(
        self,
        job_id: int,
        user_id: int,
        db,
        source_type: str,
        source_value: str,
        skip_download: bool = False,
        skip_push: bool = False,
        file_paths: list = None,
        timeout: Optional[int] = None
    ) -> int:
        """
        Execute pipeline job with optional timeout.

        Args:
            timeout: Timeout in seconds (None for no timeout)

        Returns:
            Exit code
        """
        if timeout:
            try:
                return await asyncio.wait_for(
                    self.execute_job(
                        job_id, user_id, db,
                        source_type, source_value,
                        skip_download, skip_push, file_paths
                    ),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                # Mark job as failed due to timeout
                db2 = SessionLocal()
                try:
                    tracker = PipelineStepTracker(job_id, self.ws_manager, loop=asyncio.get_running_loop())
                    tracker.ensure_step_records(db2)
                    tracker.mark_step_failed(
                        db2,
                        tracker.current_step or 'download',
                        f"Job timed out after {timeout} seconds"
                    )
                finally:
                    db2.close()
                return -997
        else:
            return await self.execute_job(
                job_id, user_id, db,
                source_type, source_value,
                skip_download, skip_push, file_paths
            )

    def cancel_job(self, job_id: int) -> bool:
        """
        Cancel a running pipeline job.

        Note: Since we use direct execution (not subprocess),
        cancellation is handled by setting a flag that the pipeline
        should check periodically.

        Args:
            job_id: Job ID to cancel

        Returns:
            True if job was running and marked for cancellation
        """
        # For direct execution, we can't easily cancel a running thread
        # This is a limitation compared to subprocess approach
        # Future improvement: Add cancellation flag to AudioPipeline

        if job_id not in self.active_jobs:
            return False

        task = self.active_jobs[job_id]
        task.cancel()

        # Clean up
        if job_id in self.active_jobs:
            del self.active_jobs[job_id]

        return True

    def is_job_running(self, job_id: int) -> bool:
        """
        Check if a job is currently running.

        Args:
            job_id: Job ID

        Returns:
            True if job is running
        """
        return job_id in self.active_jobs and not self.active_jobs[job_id].done()

    def get_active_jobs(self) -> list:
        """
        Get list of currently running job IDs.

        Returns:
            List of job IDs
        """
        return list(self.active_jobs.keys())


class BackgroundJobScheduler:
    """
    Manages pipeline job scheduling with direct AudioPipeline execution.
    """

    def __init__(self, ws_manager, executor, db_factory):
        """
        Initialize job scheduler.

        Args:
            pipeline_manager: PipelineJobManager instance
            executor: DirectPipelineExecutor instance
            db: Database session
        """
        self.ws_manager = ws_manager
        self.executor = executor
        self.db_factory = db_factory

    async def schedule_and_execute(
        self,
        user_id: int,
        source_type: str,
        source_value: str,
        file_paths: Optional[list] = None,
        file_count: int = 0,
        total_size: int = 0,
        skip_download: bool = False,
        skip_push: bool = False
    ) -> Dict:
        """
        Schedule and execute a pipeline job.

        Args:
            user_id: User ID
            source_type: Type of source (url, youtube, json, huggingface, local)
            source_value: Source value (URL, path, dataset name, etc.)
            file_paths: File paths (for local source type)
            file_count: Number of files
            total_size: Total size in bytes
            skip_download: Skip download step
            skip_push: Skip push to HuggingFace

        Returns:
            Result dict with job_id and status
        """
        # Never use the request DB session in background work. Create a dedicated
        # session for this scheduling operation.
        db = self.db_factory()
        try:
            from backend.services.pipeline_manager import PipelineJobManager
            manager = PipelineJobManager(db, self.ws_manager)

            # Check if job can start
            can_start, error, job_id = manager.can_start_job(
                user_id, source_type, source_value,
                file_paths, file_count, total_size
            )

            if not can_start:
                return {
                    'success': False,
                    'error': error,
                    'job_id': None
                }

            # Create locks
            manager.create_user_lock(user_id, job_id)
            manager.create_system_limit(job_id)

            # Update status to running
            manager.update_job_status(job_id, status='running')

            # Execute in background
            task = asyncio.create_task(self._execute_with_cleanup(
                job_id, user_id, source_type, source_value,
                skip_download, skip_push, file_paths
            ))

            self.executor.active_jobs[job_id] = task

            return {
                'success': True,
                'job_id': job_id,
                'status': 'running'
            }
        finally:
            db.close()

    async def _execute_with_cleanup(
        self,
        job_id: int,
        user_id: int,
        source_type: str,
        source_value: str,
        skip_download: bool,
        skip_push: bool,
        file_paths: list = None
    ):
        """
        Execute job with automatic cleanup.
        """
        db = self.db_factory()
        try:
            from backend.services.pipeline_manager import PipelineJobManager
            manager = PipelineJobManager(db, self.ws_manager)

            returncode = await self.executor.execute_job(
                job_id, user_id, db,
                source_type, source_value,
                skip_download, skip_push, file_paths
            )

            # Derive last successful step from DB state.
            from backend.models.pipeline_job import PipelineStep
            completed = {
                row.step_name
                for row in db.query(PipelineStep).filter_by(job_id=job_id, status='completed').all()
            }
            last_successful_step = None
            for name in PipelineStepTracker.STEPS_ORDER:
                if name in completed:
                    last_successful_step = name
                else:
                    break

            # Update final status
            if returncode == 0:
                manager.update_job_status(
                    job_id, status='completed',
                    last_successful_step=last_successful_step
                )
            else:
                manager.update_job_status(
                    job_id, status='failed',
                    last_successful_step=last_successful_step
                )

        except Exception as e:
            from backend.services.pipeline_manager import PipelineJobManager
            manager = PipelineJobManager(db, self.ws_manager)
            manager.update_job_status(
                job_id, status='failed',
                error_message=str(e),
                error_traceback=traceback.format_exc()
            )

        finally:
            try:
                from backend.services.pipeline_manager import PipelineJobManager
                manager = PipelineJobManager(db, self.ws_manager)
                manager.release_locks(user_id, job_id)
            except Exception:
                pass

            # Cleanup temp files
            from backend.utils.file_utils import cleanup_job_temp
            cleanup_job_temp(user_id, job_id)

            # Remove from active jobs
            if job_id in self.executor.active_jobs:
                del self.executor.active_jobs[job_id]

            db.close()

    async def cancel_and_cleanup(self, job_id: int, user_id: int) -> Dict:
        """
        Cancel running job and cleanup.

        Args:
            job_id: Job ID
            user_id: User ID

        Returns:
            Result dict
        """
        # Cancel execution (in-memory)
        cancelled = self.executor.cancel_job(job_id)
        if not cancelled:
            return {
                'success': False,
                'error': 'Job is not running'
            }

        db = self.db_factory()
        try:
            from backend.services.pipeline_manager import PipelineJobManager
            manager = PipelineJobManager(db, self.ws_manager)

            manager.update_job_status(job_id, status='cancelled')
            manager.release_locks(user_id, job_id)

            # Cleanup temp files
            from backend.utils.file_utils import cleanup_job_temp
            cleanup_job_temp(user_id, job_id)

            return {
                'success': True,
                'message': 'Job cancelled'
            }
        finally:
            db.close()
