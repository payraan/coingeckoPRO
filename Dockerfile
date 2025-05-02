FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Use PORT environment variable with fallback to 8080
ENV PORT=${PORT:-8080}

# Expose the port
EXPOSE ${PORT}

# Command to run the application
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
