FROM python:3.12-slim

WORKDIR /app

COPY apps/backend/requirements.txt ./apps/backend/requirements.txt
COPY packages/game-engine ./packages/game-engine
RUN pip install --no-cache-dir -r ./apps/backend/requirements.txt \
    && pip install --no-cache-dir ./packages/game-engine

RUN groupadd --system app && useradd --system --gid app --create-home app

COPY --chown=app:app apps/backend ./apps/backend
RUN chown -R app:app /app/packages/game-engine

WORKDIR /app/apps/backend
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
