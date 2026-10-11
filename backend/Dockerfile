FROM public.ecr.aws/docker/library/python:3.12-slim

# Include AWS Lambda Web Adapter (enables FastAPI/Uvicorn to run on Lambda without code changes)
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter

ENV PORT=8000 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system build dependencies required for compiling C-extensions if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Install pinned Python dependencies
COPY backend/requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
RUN pip install --no-cache-dir boto3

# Copy backend package and install
COPY backend/ ./backend/
RUN pip install --no-cache-dir --no-deps -e ./backend

EXPOSE 8000

# Start Uvicorn bound to port 8000
CMD ["uvicorn", "airguard.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
