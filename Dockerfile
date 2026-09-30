# Una sola imagen: build de React + FastAPI (design.md 6, roadmap Fase 7).

FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY config/ config/
COPY --from=frontend /frontend/dist frontend/dist
# Gold de servicio (rol A): el backend lo detecta solo en /srv/data/gold/gold.duckdb.
# Si alguna vez no está, el backend usa los stubs (ver /api/health → data_manifest).
COPY data/gold/gold.duckdb data/gold/gold.duckdb
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8000}"]
