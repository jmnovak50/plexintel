# Dockerfile
FROM node:20-slim AS frontend-build

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


FROM python:3.11-slim AS runtime-deps

WORKDIR /build

COPY requirements.runtime.txt ./
RUN pip install --upgrade pip && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.runtime.txt


FROM python:3.11-slim

WORKDIR /app

LABEL org.opencontainers.image.source="https://github.com/jmnovak50/plexintel"

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.runtime.txt /app/requirements.runtime.txt
COPY --from=runtime-deps /wheels /wheels
RUN pip install --no-index --find-links=/wheels -r /app/requirements.runtime.txt \
    && rm -rf /wheels

COPY api /app/api
COPY bootstrap.sh create.sql /app/
COPY --from=frontend-build /frontend/dist /app/frontend/dist

EXPOSE 8489

CMD ["bash", "bootstrap.sh"]
