FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY . .

CMD ["sh", "-c", "uv sync && uv run python manage.py migrate && uv run python dev_server.py"]
