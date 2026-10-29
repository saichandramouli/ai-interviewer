# AI Interviewer

Standalone AI-driven interview platform with recruiter scheduling, automated phone/voice interviews, resume parsing, and structured evaluations.

## Project Structure

```
ai-interviewer/
├── backend/          # Django REST Framework API, Celery tasks, models
├── frontend/         # React + Vite client
├── voice_service/    # Real-time voice orchestrator & telephony adapter
├── docs/             # Documentation and architecture references
├── scripts/          # Helper scripts for local development
├── .env.example      # Environment variables template
└── .gitignore        # Git ignore rules
```

## Local Development Prerequisites (Windows)

1. **Python**: 3.14+ (or 3.11/3.12).
2. **Node.js**: v20+ with npm.
3. **PostgreSQL**: PostgreSQL 18 is installed locally as a Windows service (`postgresql-x64-18`).
   - Default CLI path: `C:\Program Files\PostgreSQL\18\bin`
   - To use `psql` directly from PowerShell, add `C:\Program Files\PostgreSQL\18\bin` to your System PATH or call it with full path.
4. **Redis**:
   - Available via WSL2 Ubuntu (`/usr/bin/redis-server`).
   - Start redis inside WSL: `wsl -d Ubuntu sudo service redis-server start`
   - Default port: `6379` accessible from localhost on Windows.

## Setup Instructions

### 1. Backend Setup

```powershell
# Create & activate virtual environment (if not already created)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r backend\requirements.txt

# Copy environment variables
Copy-Item .env.example .env
# Edit .env with your local PostgreSQL password and settings
```

### 2. Database Setup

Ensure PostgreSQL service is running and create the database:
```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -c "CREATE DATABASE ai_interviewer;"
```
