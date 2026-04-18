# Backend Host Runtime

This backend now targets Windows host execution instead of Docker. Use the local
virtual environment created by `uv`, and manage the process with PM2 from the
repository root.

## Requirements

- Python `3.13`
- `uv`
- `pm2`
- A local EXATA installation available on the host machine

## First-Time Setup

From [`backend`](E:/0-CodeVault/satelliteNetworkSystem/backend):

```powershell
uv sync
uv run python manage.py migrate
```

If you need a superuser:

```powershell
uv run python manage.py createsuperuser
```

## Runtime Configuration

The backend reads the repository root [`.env`](E:/0-CodeVault/satelliteNetworkSystem/.env).
For host execution, the expected defaults are:

```env
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8002
EXATA_MANAGED_EXTERNALLY=false
EXATA_SERVICE_HOST=127.0.0.1
EXATA_SERVICE_PORT=8005
EXATA_EXECUTABLE_PATH=E:\path\to\exata.exe
EXATA_RESTART_SCRIPT=restart_backend_pm2.bat
```

## PM2 Commands

From the repository root:

```powershell
pm2 start ecosystem.config.js
pm2 status
pm2 logs backend
pm2 logs frontend
pm2 restart backend
pm2 restart frontend
```

The backend process uses [`dev_server.py`](E:/0-CodeVault/satelliteNetworkSystem/backend/dev_server.py),
which starts Daphne with `BACKEND_HOST` and `BACKEND_PORT`.

## Notes

- `db.sqlite3` remains local and should not be committed.
- EXATA is now launched directly by the host backend process.
- `restart_daphne.bat` is kept only as a compatibility wrapper and now delegates
  to `restart_backend_pm2.bat`.
- Docker is no longer the primary runtime path for this backend.
