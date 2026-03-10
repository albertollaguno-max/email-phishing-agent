FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if required for some python packages
# RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose API port
EXPOSE 8000

# We will start the FastAPI server via uvicorn. 
# The background agent task can be launched via APScheduler within the FastAPI app lifespan, 
# or via a separate process entrypoint. We'll use the FastAPI lifespan option for simplicity.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
