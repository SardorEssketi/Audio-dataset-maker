"""
Test script for DirectPipelineExecutor.
Verifies that pipeline runs correctly with progress tracking.
"""

import sys
from pathlib import Path

# Add scripts directory to path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

# Add backend directory to path
backend_dir = script_dir.parent / "backend"
sys.path.insert(0, str(backend_dir))

import asyncio
from datetime import datetime


class MockWebSocketManager:
    """Mock WebSocket manager for testing."""

    def __init__(self):
        self.messages = []

    async def broadcast(self, job_id, **kwargs):
        """Mock broadcast - store messages."""
        self.messages.append({
            'job_id': job_id,
            'timestamp': datetime.utcnow().isoformat(),
            **kwargs
        })
        print(f"[WS] {kwargs.get('step', '?')}: {kwargs.get('status', '?')} - {kwargs.get('progress', 0)}%")


async def test_pipeline_executor():
    """Test DirectPipelineExecutor with mock WebSocket."""

    from backend.services.pipeline_executor import DirectPipelineExecutor, PipelineStepTracker
    from backend.database import init_db, SessionLocal

    print("=" * 60)
    print("Testing DirectPipelineExecutor")
    print("=" * 60)

    # Initialize database
    init_db()
    db = SessionLocal()

    # Create mock user (if not exists)
    from backend.models.user import User
    user = db.query(User).filter_by(username="test_user").first()
    if not user:
        user = User(username="test_user", email="test@example.com", hashed_password="hash")
        db.add(user)
        db.commit()
        print(f"Created test user: {user.id}")
    else:
        print(f"Using existing test user: {user.id}")

    # Create WebSocket manager mock
    ws_manager = MockWebSocketManager()

    # Create executor
    executor = DirectPipelineExecutor(ws_manager)

    # Test configuration
    test_source_type = "local"  # Use local for testing
    test_source_value = str(Path(__file__).parent.parent / "data" / "raw")

    # Create a test job
    from backend.models.pipeline_job import PipelineJob
    job = PipelineJob(
        user_id=user.id,
        status='pending',
        source_type=test_source_type,
        source_value=test_source_value,
        file_count=0,
        total_size_bytes=0
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    print(f"\nCreated test job: {job.id}")
    print(f"Source type: {test_source_type}")
    print(f"Source value: {test_source_value}")
    print(f"User ID: {user.id}")

    # Test step tracker
    print("\n" + "=" * 60)
    print("Testing PipelineStepTracker")
    print("=" * 60)

    tracker = PipelineStepTracker(job.id, db, ws_manager)
    tracker.create_step_records()

    print(f"\nCreated {len(tracker.steps)} step records")

    # Simulate progress updates
    print("\nSimulating progress updates...")
    await tracker.update_step('download', 'running', progress=0, message='Starting...')
    await asyncio.sleep(0.1)

    await tracker.update_step('download', 'running', progress=50, message='Processing...')
    await asyncio.sleep(0.1)

    await tracker.update_step('download', 'completed', progress=100, message='Done!')
    await asyncio.sleep(0.1)

    await tracker.update_step('normalize', 'running', progress=0, message='Starting...')
    await asyncio.sleep(0.1)

    await tracker.update_step('normalize', 'failed', progress=25, message='Error occurred')

    # Print all step statuses
    print("\n" + "=" * 60)
    print("Step Statuses")
    print("=" * 60)

    for step_name in tracker.STEPS_ORDER:
        status = tracker.get_step_status(step_name)
        if status:
            print(f"{step_name:20s} | {status['status']:10s} | {status['progress']:3d}% | {status['message'][:30]}")

    # Print WebSocket messages
    print("\n" + "=" * 60)
    print(f"WebSocket Messages ({len(ws_manager.messages)})")
    print("=" * 60)

    for msg in ws_manager.messages:
        print(f"[{msg.get('step', '?')}] {msg.get('status', '?'):10s} | {msg.get('progress', 0):3d}% | {msg.get('message', '')[:40]}")

    # Clean up
    db.delete(job)
    db.commit()
    print(f"\nDeleted test job: {job.id}")

    print("\n" + "=" * 60)
    print("Test completed successfully!")
    print("=" * 60)


async def test_with_real_pipeline():
    """Test with actual AudioPipeline execution (requires sample audio)."""

    from backend.services.pipeline_executor import DirectPipelineExecutor
    from backend.database import SessionLocal
    from backend.models.pipeline_job import PipelineJob

    db = SessionLocal()

    # Create mock user
    from backend.models.user import User
    user = db.query(User).filter_by(username="test_user").first()
    if not user:
        user = User(username="test_user", email="test@example.com", hashed_password="hash")
        db.add(user)
        db.commit()

    # Create WebSocket manager mock
    ws_manager = MockWebSocketManager()
    executor = DirectPipelineExecutor(ws_manager)

    # Create job
    job = PipelineJob(
        user_id=user.id,
        status='pending',
        source_type="local",
        source_value=str(Path(__file__).parent.parent / "data" / "raw"),
        file_count=0,
        total_size_bytes=0
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    print(f"\nRunning real pipeline for job {job.id}...")

    try:
        returncode = await executor.execute_job(
            job_id=job.id,
            user_id=user.id,
            db=db,
            source_type="local",
            source_value=str(Path(__file__).parent.parent / "data" / "raw"),
            skip_download=True,  # Skip download for testing
            skip_push=True     # Skip push for testing
        )

        print(f"\nPipeline completed with exit code: {returncode}")
        print(f"WebSocket messages sent: {len(ws_manager.messages)}")

    finally:
        # Clean up
        db.delete(job)
        db.commit()


if __name__ == "__main__":
    print("Choose test:")
    print("1. Test step tracker (no actual pipeline)")
    print("2. Test with real pipeline execution")

    choice = input("Enter choice (1 or 2): ").strip()

    if choice == "1":
        asyncio.run(test_pipeline_executor())
    elif choice == "2":
        asyncio.run(test_with_real_pipeline())
    else:
        print("Invalid choice. Running test 1...")
        asyncio.run(test_pipeline_executor())
