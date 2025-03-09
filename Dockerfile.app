# Use official Python base image
FROM python:3.9-slim

# Set working directory inside the container
WORKDIR /app

# Copy necessary files
COPY app.py .

# Install Flask and requests (needed for token verification)
RUN pip install flask requests

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 5000 for the URL shortener service
EXPOSE 5000

# Run the URL shortener service
CMD ["python", "app.py"]
