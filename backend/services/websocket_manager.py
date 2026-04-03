"""
WebSocket connection manager.
Manages active WebSocket connections and broadcasts progress updates.
"""

from typing import Dict, Set, Optional
from fastapi import WebSocket
from datetime import datetime, timezone
from enum import Enum


class MessageType(Enum):
    """WebSocket message types."""
    PROGRESS = "progress"
    STATUS = "status"
    ERROR = "error"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    PING = "ping"


class WebSocketManager:
    """
    Manages WebSocket connections for real-time pipeline updates.
    """

    def __init__(self) -> None:
        """
        Initialize WebSocket manager.
        """
        # Map of job_id to set of WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}

        # Map of connection to job_id set (for cleanup)
        self.connection_jobs: Dict[WebSocket, Set[int]] = {}

    async def connect(self, websocket: WebSocket, job_id: int) -> None:
        """
        Accept a new WebSocket connection.

        Args:
            websocket: WebSocket connection
            job_id: Pipeline job ID to follow
        """
        await websocket.accept()

        if job_id not in self.active_connections:
            self.active_connections[job_id] = set()
        self.active_connections[job_id].add(websocket)

        if websocket not in self.connection_jobs:
            self.connection_jobs[websocket] = set()
        self.connection_jobs[websocket].add(job_id)

    def disconnect(self, websocket: WebSocket) -> None:
        """
        Disconnect a WebSocket connection and clean all references.

        Args:
            websocket: WebSocket connection to remove
        """
        job_ids = self.connection_jobs.pop(websocket, set())

        for job_id in job_ids:
            connections = self.active_connections.get(job_id)
            if not connections:
                continue

            connections.discard(websocket)

            if not connections:
                del self.active_connections[job_id]

    async def send_personal(self, websocket: WebSocket, message: dict) -> None:
        """
        Send a message to a specific WebSocket connection.

        Args:
            websocket: Target WebSocket connection
            message: Message dict to send
        """
        try:
            await websocket.send_json(message)
        except Exception:
            self.disconnect(websocket)

    async def send_to_job(self, job_id: int, message: dict) -> None:
        """
        Send a message to all connections watching a specific job.

        Args:
            job_id: Job ID
            message: Message dict to send
        """
        connections = self.active_connections.get(job_id)
        if not connections:
            return

        disconnected = []

        for connection in list(connections):
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(connection)

    async def broadcast(self, job_id: int, **kwargs) -> None:
        """
        Broadcast a progress update to all connections for a job.

        Args:
            job_id: Job ID
            **kwargs: Progress data
        """
        message = {
            "job_id": job_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        message.update(kwargs)

        await self.send_to_job(job_id, message)

    async def broadcast_progress(
        self,
        job_id: int,
        step: str,
        progress: int,
        message: str = "",
        **data
    ) -> None:
        """
        Broadcast progress update.

        Args:
            job_id: Job ID
            step: Current step name
            progress: Progress percentage (0-100)
            message: Raw message
            **data: Additional data
        """
        await self.broadcast(
            job_id,
            type=MessageType.PROGRESS.value,
            step=step,
            progress=progress,
            message=message,
            **data
        )

    async def broadcast_status(self, job_id: int, status: str) -> None:
        """
        Broadcast job status update.

        Args:
            job_id: Job ID
            status: Job status
        """
        await self.broadcast(
            job_id,
            type=MessageType.STATUS.value,
            status=status
        )

    async def broadcast_error(
        self,
        job_id: int,
        error_message: str,
        traceback: Optional[str] = None
    ) -> None:
        """
        Broadcast error message.

        Args:
            job_id: Job ID
            error_message: Error description
            traceback: Full stack trace
        """
        await self.broadcast(
            job_id,
            type=MessageType.ERROR.value,
            error_message=error_message,
            traceback=traceback
        )

    async def broadcast_completed(self, job_id: int, **data) -> None:
        """
        Broadcast job completion message.

        Args:
            job_id: Job ID
            **data: Additional completion data
        """
        await self.broadcast(
            job_id,
            type=MessageType.COMPLETED.value,
            **data
        )

    async def broadcast_cancelled(self, job_id: int) -> None:
        """
        Broadcast job cancellation message.

        Args:
            job_id: Job ID
        """
        await self.broadcast(
            job_id,
            type=MessageType.CANCELLED.value
        )

    def get_connection_count(self, job_id: int) -> int:
        """
        Get number of active connections for a job.
        """
        return len(self.active_connections.get(job_id, set()))

    def get_all_connection_counts(self) -> Dict[int, int]:
        """
        Get connection counts for all active jobs.
        """
        return {
            job_id: len(connections)
            for job_id, connections in self.active_connections.items()
        }

    async def cleanup_job_connections(self, job_id: int) -> None:
        """
        Clean up all connections for a completed job.

        Args:
            job_id: Job ID to cleanup
        """
        connections = self.active_connections.get(job_id)
        if not connections:
            return

        for connection in list(connections):
            # Удаляем связь job_id <-> websocket
            if connection in self.connection_jobs:
                self.connection_jobs[connection].discard(job_id)
                if not self.connection_jobs[connection]:
                    del self.connection_jobs[connection]

            try:
                await connection.close(code=1000, reason="Job completed")
            except Exception:
                pass

        del self.active_connections[job_id]

    async def ping_job_connections(self, job_id: int) -> None:
        """
        Send ping to keep connections alive.

        Args:
            job_id: Job ID
        """
        connections = self.active_connections.get(job_id)
        if not connections:
            return

        message = {
            "type": MessageType.PING.value,
            "job_id": job_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        disconnected = []

        for connection in list(connections):
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(connection)


# Global WebSocket manager instance
manager = WebSocketManager()