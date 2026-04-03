# 🎙️ Audio Pipeline Web App - MVP

Minimal working MVP for audio processing pipeline management.

## 📋 Features

- ✅ User authentication (JWT)
- ✅ Dashboard with job list
- ✅ Run new pipeline jobs
- ✅ Real-time progress via WebSocket
- ✅ Settings management (HuggingFace, download, processing)
- ✅ Job status monitoring
- ✅ Error handling with tracebacks
- ✅ Multi-user support with data isolation

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Generate .env file with secure keys
python setup_env.py
```

This creates `.env` with:
- Random `SECRET_KEY` (64 chars)
- Random `CONFIG_ENCRYPTION_KEY`
- Default configuration values

### 2. Backend

```bash
# Activate virtual environment
.venv311/Scripts/activate    # Windows
# source .venv311/bin/activate  # Linux/Mac

# Run backend
python -m uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at: http://localhost:8000
API docs: http://localhost:8000/api/docs

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at: http://localhost:5173

## 📁 Project Structure

```
all_in_with_agent/
├── backend/                    # FastAPI backend
│   ├── app.py                # Main FastAPI app
│   ├── config.py             # Settings configuration
│   ├── database.py           # DB session & user paths
│   ├── models/               # SQLAlchemy models
│   ├── routes/               # API endpoints
│   ├── services/             # Business logic
│   └── utils/                # Helper functions
├── frontend/                   # React + Vite frontend
│   ├── src/
│   │   ├── api/            # API client (axios)
│   │   ├── components/      # React components
│   │   ├── context/        # Auth context
│   │   ├── hooks/          # Custom hooks
│   │   ├── pages/          # Page components
│   │   └── main.jsx        # Entry point
│   ├── package.json
│   └── vite.config.js
├── config/
│   ├── config.yaml           # Pipeline configuration
│   └── bot_config.yaml      # Telegram bot config
├── scripts/                  # Pipeline scripts
│   ├── download_audio.py
│   ├── normalize.py
│   ├── noise_reduction.py
│   ├── vad_cut.py
│   ├── whisper.py
│   ├── filter_transcriptions.py
│   └── push.py
├── main.py                   # Pipeline orchestrator
└── .env                      # Environment variables (NOT in git)
```

## 🔐 Environment Variables

Create `.env` file (or run `python setup_env.py`):

```bash
# Required
SECRET_KEY=your_secure_random_key_min_32_chars

# Optional (with defaults)
HOST=0.0.0.0
PORT=8000
MAX_CONCURRENT_JOBS=3
MAX_USER_CONCURRENT=1
CORS_ORIGINS=http://localhost:5173
```

## 📡 API Endpoints

### Auth
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get JWT
- `GET /api/auth/me` - Get current user
- `PUT /api/auth/me` - Update profile
- `POST /api/auth/logout` - Logout

### Pipelines
- `POST /api/pipelines` - Create new job
- `GET /api/pipelines` - List jobs
- `GET /api/pipelines/{id}` - Get job details
- `POST /api/pipelines/{id}/cancel` - Cancel job
- `DELETE /api/pipelines/{id}` - Delete job
- `GET /api/pipelines/{id}/logs` - Get logs

### Config
- `GET /api/config` - Get user config
- `PUT /api/config` - Update config
- `DELETE /api/config` - Reset to defaults
- `GET /api/config/huggingface/token` - Get masked HF token
- `PUT /api/config/huggingface/token` - Set HF token
- `DELETE /api/config/huggingface/token` - Delete HF token

### WebSocket
- `WS /ws/jobs/{job_id}?token=JWT_TOKEN` - Real-time progress

## 🔧 Pipeline Configuration

Edit `config/config.yaml`:

```yaml
huggingface:
  repo_id: your-username/your-dataset
  token: your_hf_token  # OR set via web UI
  private: false

whisper:
  model_name: OvozifyLabs/whisper-small-uz-v1
  language: uz
  mode: auto  # auto | local | api

download:
  max_workers: 4

noise_reduction:
  enabled: true

filtering:
  enabled: true
```

## 🧪 Testing the MVP

### Manual Test Script

```python
import requests
import json

# 1. Register
requests.post('http://localhost:8000/api/auth/register', json={
    'username': 'testuser',
    'password': 'testpass123'
})

# 2. Login
response = requests.post('http://localhost:8000/api/auth/login', json={
    'username': 'testuser',
    'password': 'testpass123'
})
token = response.json()['access_token']

# 3. Create job
headers = {'Authorization': f'Bearer {token}'}
response = requests.post(
    'http://localhost:8000/api/pipelines',
    json={
        'source_type': 'local',
        'source_value': './data/raw'
    },
    headers=headers
)
job_id = response.json()['job_id']

# 4. Check status
response = requests.get(
    f'http://localhost:8000/api/pipelines/{job_id}',
    headers=headers
)
print(response.json())
```

## ⚠️ Known Limitations (MVP)

1. **Job Cancellation**: Cancel button doesn't fully stop CPU-bound pipeline
   - Workaround: Job status shows as "cancelled"
   - Pipeline continues running in background

2. **No Email Verification**: Email field exists but not verified

3. **SQLite in Production**: For production, switch to PostgreSQL

4. **No Rate Limiting**: API has no request limits

5. **File Upload**: Local source requires manual file placement

## 🔍 Debugging

### Backend
```bash
# Check if running
curl http://localhost:8000/health

# Check API docs
# Open http://localhost:8000/api/docs in browser
```

### Frontend
```bash
# Check Vite console output for errors
# Check browser DevTools (F12) for network issues
```

### WebSocket
```javascript
// Test WebSocket connection in browser console
const socket = new WebSocket('ws://localhost:8000/ws/jobs/1?token=YOUR_JWT');
socket.onmessage = (e) => console.log('Message:', JSON.parse(e.data));
```

## 📦 Dependencies

### Backend
See `requirements.txt`:
- FastAPI, Uvicorn, SQLAlchemy
- Pydantic, Python-JOSE
- Transformers, Torch, Whisper
- HuggingFace Hub, Librosa

### Frontend
See `frontend/package.json`:
- React 18, React Router
- Material UI (MUI)
- Axios, Socket.io-client
- date-fns

## 🚨 Troubleshooting

### "Module not found" errors
```bash
# Backend
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

### "SECRET_KEY required" error
```bash
python setup_env.py  # Generates .env file
```

### WebSocket connection failed
- Check backend is running
- Check JWT token is valid
- Check CORS origins in .env

### Pipeline job fails
- Check `config/config.yaml` is valid
- Check HuggingFace token is set
- Check backend logs for errors

## 📝 Development

### Backend hot reload
```bash
python -m uvicorn backend.app:app --reload
```

### Frontend hot reload
```bash
cd frontend
npm run dev
```

## 🎯 MVP Acceptance Criteria

- [x] User can register and login
- [x] User can configure HuggingFace settings
- [x] User can select source type
- [x] User can run pipeline job
- [x] User sees real-time progress
- [x] User sees job status (pending, running, completed, failed)
- [x] User can view error logs
- [x] User can retry failed jobs
- [x] User can delete jobs
- [x] Data is isolated per user

## 🚀 Production Deployment

1. Set `SECRET_KEY` and `CONFIG_ENCRYPTION_KEY` via environment
2. Use PostgreSQL instead of SQLite
3. Set `CORS_ORIGINS` to production domain
4. Set `HOST=0.0.0.0` to bind all interfaces
5. Use process manager (systemd, supervisord)
6. Add reverse proxy (nginx)
7. Enable HTTPS

## 📄 License

MIT