FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
RUN mkdir -p src/kirana && touch src/kirana/__init__.py
RUN pip install --no-cache-dir -e .

COPY src/ src/
COPY alembic.ini .
COPY alembic/ alembic/

RUN mkdir -p /app/output && \
    useradd --create-home --uid 1000 kirana && \
    chown -R kirana:kirana /app

USER kirana

ENV OUTPUT_DIR=/app/output
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

CMD ["python", "-m", "kirana.bot.telegram_bot"]
