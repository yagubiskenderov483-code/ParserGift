FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PARSERGIFT_BUILD=scratch-2026-08-03

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Refuse to ship the broken pre-rewrite binary
RUN python - <<'PY'
from pathlib import Path
app = Path("app.py").read_text(encoding="utf-8")
assert "scratch-2026-08-03" in app, "wrong app.py"
assert "class Runtime" in app, "missing Runtime"
main = Path("main.py").read_text(encoding="utf-8")
assert "from app import main" in main, "main.py must wrap app.py"
print("image content OK")
PY

CMD ["python", "-u", "app.py"]
