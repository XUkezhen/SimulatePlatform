# mytestdjango_five_final

This repository is ready to work with `uv` so teammates can clone it and create the same Python environment locally.

## Requirements

- Python `3.13`
- `uv` installed on your machine

Install `uv`:

- Windows PowerShell: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
- Or with pip: `pip install uv`

Official docs:

- https://docs.astral.sh/uv/

## First-time setup

Clone the repository, then run:

```powershell
uv sync
uv run python manage.py migrate
```

If you need a superuser:

```powershell
uv run python manage.py createsuperuser
```

## Run the project

Development server:

```powershell
uv run python manage.py runserver
```

ASGI server with Daphne:

```powershell
uv run daphne -b 0.0.0.0 -p 8000 mytest.asgi:application
```

## Common workflow for collaborators

After pulling the latest code:

```powershell
uv sync
uv run python manage.py migrate
```

When dependencies change:

```powershell
uv lock
uv sync
```

Then commit both of these files if they changed:

- `pyproject.toml`
- `uv.lock`

## Notes

- The local virtual environment `.venv/` should not be committed.
- `db.sqlite3` is ignored, so each collaborator can keep a local database.
- Some features appear to depend on a local EXATA installation. That executable is not managed by `uv`; teammates will still need their own EXATA install and may need to adjust the hard-coded path in the code.
- `requirements.txt` is kept for reference, but `pyproject.toml` should be treated as the source of truth for dependencies.
