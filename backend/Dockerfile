# ========================
# FRONTEND BUILD STAGE
# ========================
FROM node:20-alpine AS frontend-builder

WORKDIR /app
COPY frontend/ ./frontend/
WORKDIR /app/frontend

RUN npm ci && npm run build


# ========================
# BACKEND BUILD STAGE
# ========================
FROM python:3.11-slim AS backend

# Set working directory
WORKDIR /app

# Copy only requirements first to cache installs
COPY backend/requirements.txt .

# Install only production dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./backend/

# Copy built frontend assets into backend (to serve statically)
COPY --from=frontend-builder /app/frontend/dist ./backend/app/static

# Expose FastAPI port
EXPOSE 8000

# Run the FastAPI app via uvicorn
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
