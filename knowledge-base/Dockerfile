# Use an official Python runtime as a parent image.
FROM python:3.12-slim

# Set environment variables.
# Prevent Python from writing pyc files to disc and buffering stdout/stderr.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies.
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install additional dependencies required for Playwright.
RUN apt-get update && apt-get install -y \
    wget \
    libgbm1 \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory.
WORKDIR /app

# Copy the requirements.txt file.
COPY requirements.txt /app/

# Install Python dependencies.
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers.
RUN playwright install --with-deps

# Copy the rest of the application code.
COPY . /app/

# Expose any ports if your application listens on one (optional).
# EXPOSE 8000

# Define the command to run your app.
# Here we assume your app's entrypoint is main.py inside the knowledge_base_agent package.
CMD ["python", "-m", "knowledge_base_agent.main"]
