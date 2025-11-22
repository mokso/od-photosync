FROM python:3.12-alpine

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py /app/

# Create directories
RUN mkdir -p /app/data /photos

# Set environment variable
ENV RUNNING_IN_CONTAINER=true
ENV DATA_DIR=/app/data

# Run as non-root user
RUN adduser -D photosync && \
    chown -R photosync:photosync /app /photos
USER photosync

# Default command
CMD ["python", "photosync.py"]
