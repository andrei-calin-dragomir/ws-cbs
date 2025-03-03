# Use official Python base image
FROM python:3.9-slim

# Set working directory inside the container
WORKDIR /app

# Copy necessary files
COPY login.py .

# Install Flask (minimal dependencies for efficiency)
RUN pip install flask

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 5001 for the authentication service
EXPOSE 5001

# Run the authentication service
CMD ["python", "login.py"]
