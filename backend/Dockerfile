# Use official Python slim image as base
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Copy only requirements for caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire app (adjusted for your structure)
COPY . .

# Create non-root user and switch to it
RUN useradd -m -r appuser && chown appuser:appuser /app
USER appuser

# Expose FastAPI's default port
EXPOSE 8000

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl -f http://localhost:8000/ || exit 1

# Start FastAPI with Uvicorn (tweaked for production)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]