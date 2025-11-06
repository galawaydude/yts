# Use an official Python 3.11 image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your backend code
COPY . .

# Expose the port Gunicorn will run on
EXPOSE 8000

# Run the app using Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:8000", "run:app"]