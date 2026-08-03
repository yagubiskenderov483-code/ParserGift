# ParserGift — fresh image, no cached old main.py
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PARSERGIFT_BUILD=2026-08-03-v3-rewrite

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Fail the build loudly if somehow the OLD main.py got copied
RUN python - <<'PY'
from pathlib import Path
text = Path("main.py").read_text(encoding="utf-8")
assert "async def _amain" in text, "OLD main.py detected (missing _amain)"
assert "2026-08-03-v3-rewrite" in text, "OLD main.py detected (missing build stamp)"
assert "no pyro.connect() on startup" in text, "OLD main.py detected"
print("main.py OK, lines=", len(text.splitlines()))
PY

CMD ["python", "-u", "main.py"]
