# Use a slim Python 3.12 image for size optimization
FROM python:3.12-slim

# Prevent Python from writing pyc files and keep stdout unbuffered
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/home/appuser/.cache/ms-playwright

# Create a non-root user for security
RUN useradd -m -r appuser

# Set working directory
WORKDIR /app

# Install system dependencies required for Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY req.txt .

# Install Python requirements
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r req.txt

# Install Playwright OS dependencies and Chromium natively
RUN playwright install chromium --with-deps && \
    rm -rf /var/lib/apt/lists/*

# Copy the rest of the application code
COPY . .

# Set proper ownership so appuser can write to data folders if needed
RUN chown -R appuser:appuser /app /home/appuser

# Switch to the non-root user
USER appuser

# Expose the Streamlit port
EXPOSE 8501

# Entry point for the Streamlit application
ENTRYPOINT ["streamlit", "run", "ui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
