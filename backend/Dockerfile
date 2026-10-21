FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# WEB_CONCURRENCY above 1 requires REDIS_URL: without shared session state the
# POST that starts a run and the GET that streams it can land on different
# workers. /api/health reports multi_worker_safe so this is checkable.
ENV WEB_CONCURRENCY=1
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY}"]
