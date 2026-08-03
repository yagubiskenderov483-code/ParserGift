FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libffi-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py parse_tonnel.py parse_portals.py parse_mrkt.py main.py ./

RUN python -c "import main; assert 'full-2026-08-03' in open('main.py').read(); print('OK')"

CMD ["python", "-u", "main.py"]
