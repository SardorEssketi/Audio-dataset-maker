#!/usr/bin/env python3
"""
Quick setup script for the project.
Generates secure .env file with random SECRET_KEY.
"""

import secrets
import os
from pathlib import Path


def generate_secret_key(length=64):
    """Generate a secure random secret key."""
    return secrets.token_hex(length)


def setup_env_file():
    """Create .env file with secure values."""
    env_path = Path(__file__).parent / '.env'

    if env_path.exists():
        print(f"✓ .env file already exists at {env_path}")
        overwrite = input("Overwrite existing .env? (y/N): ").strip().lower()
        if overwrite != 'y':
            print("Keeping existing .env file.")
            return

    # Generate secure values
    secret_key = generate_secret_key()
    encryption_key = generate_secret_key()

    # Write .env file
    env_content = f"""# Audio Pipeline Web App Configuration
# Generated automatically by setup_env.py

# API Configuration
SECRET_KEY={secret_key}
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Server Configuration
HOST=0.0.0.0
PORT=8000

# Pipeline Limits
MAX_CONCURRENT_JOBS=3
MAX_USER_CONCURRENT=1
MAX_INPUT_SIZE_MB=2048
MAX_FILE_COUNT=5

# CORS Origins (comma-separated)
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# Config Encryption Key (optional, defaults to SECRET_KEY)
CONFIG_ENCRYPTION_KEY={encryption_key}
"""

    env_path.write_text(env_content)
    print(f"✓ Created .env file at {env_path}")
    print(f"  - SECRET_KEY: {secret_key[:16]}...")
    print(f"  - ENCRYPTION_KEY: {encryption_key[:16]}...")


def print_next_steps():
    """Print next steps for setup."""
    print("\n" + "="*60)
    print("NEXT STEPS:")
    print("="*60)
    print("\n1. Backend setup:")
    print("   source .venv311/Scripts/activate  # Windows")
    print("   # source .venv311/bin/activate  # Linux/Mac")
    print("   python -m uvicorn backend.app:app --reload")
    print("\n2. Frontend setup:")
    print("   cd frontend")
    print("   npm install")
    print("   npm run dev")
    print("\n3. Access the app:")
    print("   Backend: http://localhost:8000")
    print("   Frontend: http://localhost:5173")
    print("   API Docs: http://localhost:8000/api/docs")
    print("\n" + "="*60)


if __name__ == '__main__':
    print("Audio Pipeline Web App - Quick Setup")
    print("="*40)
    setup_env_file()
    print_next_steps()