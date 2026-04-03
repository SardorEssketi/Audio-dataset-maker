"""
WebSocket routes.
Real-time progress updates for pipeline jobs.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from sqlalchemy.orm import Session
import logging

from backend.database import get_db
from backend.routes.auth import verify_access_token
from backend.models.pipeline_job import PipelineJob
from backend.services.websocket_manager import manager


router = APIRouter(prefix="/ws", tags=["websocket"])

# Configure logging
logger = logging.getLogger(__name__)


@router.websocket("/jobs/{job_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    job_id: int,
    token: str = Query(..., description="JWT access token"),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time job progress updates.

    Connection URL: ws://host/ws/jobs/{job_id}?token=YOUR_JWT_TOKEN

    Broadcasts:
    - Progress updates (step, progress percentage, messages)
    - Status changes (pending -> running -> completed/failed)
    - Error messages with traceback
    - Completion notifications
    """
    # Verify JWT token
    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return

    payload = verify_access_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid authentication token")
        return

    user_id = int(payload.get("sub"))
    if not user_id:
        await websocket.close(code=4001, reason="Invalid token payload")
        return

    # Verify job exists and user has access
    job = db.query(PipelineJob).filter_by(id=job_id).first()
    if not job:
        await websocket.close(code=4004, reason="Job not found")
        return

    if job.user_id != user_id:
        await websocket.close(code=4003, reason="Access denied")
        return

    # Accept connection
    await manager.connect(websocket, job_id)

    connection_count = manager.get_connection_count(job_id)
    logger.info(f"WebSocket connected for job {job_id}, user {user_id}, connections: {connection_count}")

    try:
        # Send initial status
        await manager.broadcast_status(job_id, job.status)

        # Send initial job details
        initial_data = {
            'type': 'initial',
            'job_id': job_id,
            'status': job.status,
            'source_type': job.source_type,
            'source_value': job.source_value,
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        }

        for connection in manager.active_connections.get(job_id, set()):
            try:
                await manager.send_personal(connection, initial_data)
            except Exception as e:
                logger.error(f"Error sending initial data: {e}")

        # Keep connection alive and listen for client messages
        while True:
            try:
                # Receive message from client (could be ping, keepalive, etc.)
                data = await websocket.receive_json()
                message_type = data.get('type', '')

                if message_type == 'ping':
                    # Respond to ping
                    await manager.send_personal(websocket, {'type': 'pong', 'timestamp': data.get('timestamp')})
                elif message_type == 'subscribe':
                    # Client wants to subscribe to this job (already done)
                    pass
                elif message_type == 'disconnect':
                    # Client requested disconnect
                    logger.info(f"Client requested disconnect for job {job_id}")
                    break

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for job {job_id}")
                break
            except Exception as e:
                logger.error(f"Error in WebSocket loop: {e}")
                break

    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}")

    finally:
        # Cleanup on disconnect
        manager.disconnect(websocket)
        connection_count = manager.get_connection_count(job_id)
        logger.info(f"WebSocket disconnected for job {job_id}, remaining connections: {connection_count}")


@router.get("/jobs/{job_id}/status")
def get_job_status_via_http(
    job_id: int,
    user_id: int = None
):
    """
    HTTP fallback for getting job status (for clients that don't use WebSocket).

    Returns current job status and last progress info.
    """
    # This could be used for polling fallback
    pass


@router.get("/active-connections")
def get_active_connections():
    """
    Get active WebSocket connections count per job.
    For monitoring/debugging.
    """
    return manager.get_all_connection_counts()
