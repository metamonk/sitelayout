# Multi-stage build for Python backend
FROM python:3.11-slim as builder

# Install system dependencies for geospatial libraries and build tools
RUN apt-get update && apt-get install -y \
    build-essential \
    g++ \
    gcc \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    libspatialindex-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . .

# Create uploads directory
RUN mkdir -p uploads

# Copy and make startup script executable
COPY start.sh .
RUN chmod +x start.sh

# Expose port
EXPOSE 8000

# Run the application with migrations
CMD ["./start.sh"]
