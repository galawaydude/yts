# Use standard lightweight Python
FROM python:3.11-slim

# Keep Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1

# Set working directory inside the container
WORKDIR /app

# Install system dependencies required for some python packages
RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev && rm -rf /var/lib/apt/lists/*

# Copy requirements and install them
COPY requirements.txt .
# CRITICAL: Install gunicorn for the web server
RUN pip install --no-cache-dir -r requirements.txt && pip install gunicorn gevent

# Copy the rest of the backend code
COPY . .

# Make the start script executable
RUN chmod +x start.sh

# Run our custom start script
CMD ["./start.sh"]