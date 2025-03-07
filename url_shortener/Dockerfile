# Use official Python base image
FROM python:3.9-slim

# Set working directory inside the container
WORKDIR /app

# Copy necessary files
COPY app.py .

# Install (minimal dependencies for efficiency)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Expose port 5000 for the URL shortener service
EXPOSE 5000

# Run the URL shortener service
CMD ["python", "app.py"]
