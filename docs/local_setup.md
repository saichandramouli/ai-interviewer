# Local Windows Setup & Environment Guide

This document details the environment configuration and service availability for running AI Interviewer locally on Windows without AWS dependencies.

## 1. Services Overview

| Service | Local Mechanism | Host / Port | Status / Verification |
|---------|-----------------|-------------|-----------------------|
| PostgreSQL | Windows Service (`postgresql-x64-18`) | `localhost:5432` | Running; TCP port verified; CLI at `C:\Program Files\PostgreSQL\18\bin\psql.exe` |
| Redis | WSL2 Ubuntu (`/usr/bin/redis-server`) | `localhost:6379` | Running; Verified responding `PONG` to Windows Python |
| Python Environment | Local Virtual Environment (`.venv`) | Python 3.14.7 | Verified; `backend/requirements.txt` installed |

## 2. PostgreSQL Configuration

The PostgreSQL 18 service runs automatically. 
To add `psql` to your current user/system environment PATH, you can run PowerShell as Administrator:
```powershell
[System.Environment]::SetEnvironmentVariable('Path', $env:Path + ';C:\Program Files\PostgreSQL\18\bin', 'User')
```
Or execute CLI commands via:
```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres
```

## 3. Redis Configuration

Redis runs inside the WSL2 Ubuntu distribution and forwards port `6379` directly to `localhost` on Windows:
```powershell
# Check status
wsl -d Ubuntu redis-cli ping

# Start redis if stopped
wsl -d Ubuntu sudo service redis-server start
```

## 4. Verification

Run the verification test suite or import checks from `.venv`:
```powershell
.\.venv\Scripts\python.exe -c "import django, rest_framework, psycopg, celery, redis; print('All core packages verified!')"
```
