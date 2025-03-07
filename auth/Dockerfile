# Use official Python base image
FROM python:3.9-slim

# Set working directory inside the container
WORKDIR /app

# Copy necessary files
COPY app.py .

# Install (minimal dependencies for efficiency)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Expose port 5001 for the authentication service
EXPOSE 5001

# Run the authentication service
CMD ["python", "app.py"]
