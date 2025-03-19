# Use official Python image as base
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy only requirements first for better caching
COPY backend/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire backend folder into the container
COPY backend/ /app/

# Expose FastAPI's default port
EXPOSE 8000

# Start FastAPI with Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
