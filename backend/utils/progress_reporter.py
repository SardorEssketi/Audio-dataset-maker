"""
Pipeline progress reporter.
Parses stdout from pipeline subprocess and broadcasts via WebSocket.
"""

import re
import json
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineProgressReporter:
    """
    Parses pipeline stdout and tracks progress for WebSocket broadcasting.
    """

    # Step patterns in pipeline output
    STEP_PATTERNS = {
        "STEP 1: Downloading": "download",
        "STEP 2: Normalizing": "normalize",
        "STEP 3: Applying noise reduction": "noise_reduction",
        "STEP 4: Segmenting": "vad_segmentation",
        "STEP 5: Transcribing": "transcription",
        "STEP 6: Filtering": "filter",
        "STEP 7: Pushing": "push",
    }

    # Progress patterns
    PROGRESS_PATTERNS = {
        'download': [
            (r'Downloaded:\s*(\d+)\s*files', lambda m: {'files_count': int(m.group(1)), 'progress': 100}),
            (r'Downloading.*?(\d+)%?', lambda m: {'progress': int(m.group(1))}),
        ],
        'normalize': [
            (r'Normalized:\s*(\d+)\s*files', lambda m: {'files_count': int(m.group(1)), 'progress': 100}),
            (r'Normalizing.*?(\d+)%?', lambda m: {'progress': int(m.group(1))}),
        ],
        'noise_reduction': [
            (r'Denoised:\s*(\d+)\s*files', lambda m: {'files_count': int(m.group(1)), 'progress': 100}),
        ],
        'vad_segmentation': [
            (r'Created:\s*(\d+)\s*segments', lambda m: {'segments_count': int(m.group(1)), 'progress': 100}),
        ],
        'transcription': [
            (r'Transcribed:\s*(\d+)\s*files', lambda m: {'files_count': int(m.group(1)), 'progress': 100}),
            (r'\((\d+)/(\d+)\)', lambda m: {'progress': int(m.group(1)) / int(m.group(2)) * 100}),
        ],
        'filter': [
            (r'Valid:\s*(\d+)\s*files', lambda m: {'valid': int(m.group(1)), 'progress': 100}),
            (r'Rejected:\s*(\d+)\s*files', lambda m: {'rejected': int(m.group(1)), 'progress': 100}),
        ],
        'push': [
            (r'Dataset pushed to:', lambda m: {'progress': 100, 'url': m.group(0)}),
        ],
    }

    def __init__(self, job_id: int, ws_manager):
        """
        Initialize progress reporter.

        Args:
            job_id: Pipeline job ID
            ws_manager: WebSocketManager instance for broadcasting
        """
        self.job_id = job_id
        self.ws_manager = ws_manager
        self.current_step: Optional[str] = None
        self.step_progress: int = 0
        self.last_output: List[str] = []
        self.last_successful_step: Optional[str] = None
        self.max_output_lines = 1000

    def parse_line(self, line: str) -> None:
        """
        Parse a single line from pipeline stdout.

        Updates current step and progress.
        Broadcasts updates via WebSocket.
        """
        # Store last output for error context
        self.last_output.append(line)
        if len(self.last_output) > self.max_output_lines:
            self.last_output.pop(0)

        # Detect step changes
        for step_marker, step_name in self.STEP_PATTERNS.items():
            if step_marker in line:
                if self.current_step and self.step_progress == 100:
                    self.last_successful_step = self.current_step

                self.current_step = step_name
                self.step_progress = 0
                self._create_step_record(step_name, StepStatus.RUNNING)
                self._broadcast(status=StepStatus.RUNNING.value, step=step_name, progress=0)
                return

        # Parse progress for current step
        if self.current_step:
            self._parse_progress(line)

    def _parse_progress(self, line: str) -> None:
        """
        Parse progress information from line.
        """
        step_patterns = self.PROGRESS_PATTERNS.get(self.current_step, [])

        for pattern, extractor in step_patterns:
            match = re.search(pattern, line)
            if match:
                data = extractor(match)
                if 'progress' in data:
                    self.step_progress = min(100, int(data['progress']))

                # Broadcast update with additional info
                self._broadcast(
                    status=StepStatus.RUNNING.value,
                    step=self.current_step,
                    progress=self.step_progress,
                    message=line.strip(),
                    **data
                )
                return

    def _create_step_record(self, step_name: str, status: StepStatus) -> None:
        """
        Create a step record in the database.

        Args:
            step_name: Step name (download, normalize, etc.)
            status: Step status
        """
        # This will be called by the pipeline service
        # which has database access
        pass

    def _broadcast(self, status: str, step: str, progress: int, message: str = "", **kwargs) -> None:
        """
        Broadcast progress update via WebSocket.

        Args:
            status: Job status
            step: Current step name
            progress: Progress percentage (0-100)
            message: Raw message
            **kwargs: Additional data (files_count, url, etc.)
        """
        payload = {
            'job_id': self.job_id,
            'status': status,
            'step': step,
            'progress': progress,
            'message': message,
            'timestamp': datetime.utcnow().isoformat(),
        }

        # Add additional data
        payload.update(kwargs)

        self.ws_manager.broadcast(self.job_id, payload)

    def get_last_output(self, lines: int = 100) -> str:
        """
        Get last N lines of output.

        Args:
            lines: Number of lines to return

        Returns:
            String with last N lines
        """
        recent = self.last_output[-lines:]
        return '\n'.join(recent)

    def set_step_completed(self, step_name: str) -> None:
        """
        Mark current step as completed.
        """
        self.last_successful_step = step_name
        self.step_progress = 100
        self._broadcast(
            status=StepStatus.COMPLETED.value,
            step=step_name,
            progress=100
        )

    def set_step_failed(self, step_name: str, error_message: str) -> None:
        """
        Mark current step as failed.
        """
        self._broadcast(
            status=StepStatus.FAILED.value,
            step=step_name,
            progress=self.step_progress,
            message=error_message
        )

    def set_job_completed(self) -> None:
        """
        Mark entire job as completed.
        """
        if self.current_step:
            self.last_successful_step = self.current_step

        self._broadcast(
            status='completed',
            step=self.current_step,
            progress=100,
            message='Pipeline completed successfully'
        )

    def set_job_failed(self, error_message: str, traceback: Optional[str] = None) -> None:
        """
        Mark entire job as failed.

        Args:
            error_message: Short error description
            traceback: Full stack trace if available
        """
        self._broadcast(
            status='failed',
            step=self.current_step,
            progress=self.step_progress,
            message=error_message,
            traceback=traceback,
            last_successful_step=self.last_successful_step,
            last_output=self.get_last_output(500)
        )