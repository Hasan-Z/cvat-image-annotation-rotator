FROM python:3.12-slim AS backend
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY pyproject.toml README.md /app/
COPY backend /app/backend
RUN pip install --no-cache-dir -e .

FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json /app/frontend/
RUN npm install
COPY frontend /app/frontend
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=backend /usr/local /usr/local
COPY --from=frontend /app/frontend/dist /app/frontend/dist
COPY backend /app/backend
COPY pyproject.toml README.md /app/
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
