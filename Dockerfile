# Stage 1: Build frontend
FROM node:20-alpine AS frontend-build
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.cloud.tencent.com/g' /etc/apk/repositories
WORKDIR /build
COPY frontend/package*.json ./
RUN npm config set registry https://mirrors.cloud.tencent.com/npm/ && npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Production
FROM python:3.11-slim
WORKDIR /app

RUN sed -i 's/deb.debian.org/mirrors.cloud.tencent.com/g' /etc/apt/sources.list.d/debian.sources \
    && sed -i 's/security.debian.org/mirrors.cloud.tencent.com/g' /etc/apt/sources.list.d/debian.sources

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -i https://mirrors.cloud.tencent.com/pypi/simple/ --trusted-host mirrors.cloud.tencent.com -r requirements.txt

COPY backend/app ./app
COPY backend/scripts ./scripts
COPY --from=frontend-build /build/dist ./app/static

ENV TZ=Asia/Shanghai
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
