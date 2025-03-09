# Use official Python base image
FROM python:3.9-slim

# Set working directory inside the container
WORKDIR /app

# Copy necessary files
COPY app.py .

# Install Flask and requests (needed for token verification)
RUN apt-get update && apt-get install -y curl

COPY requirements.txt .
RUN pip install -r requirements.txt

# Run the authentication service
CMD ["python", "app.py"]
