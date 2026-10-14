FROM python:3.10-slim

# Install system dependencies: ffmpeg, DejaVu fonts (required for video text overlay)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu-core \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces runs as a non-root user with UID 1000
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PORT=7860

WORKDIR $HOME/app

# Install Python dependencies first (leverages Docker cache)
COPY --chown=user:user backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r ./backend/requirements.txt

# Copy all application files
COPY --chown=user:user . $HOME/app

# Create necessary runtime directories
RUN mkdir -p backend/uploads backend/output backend/assets

# Hugging Face Spaces default port
EXPOSE 7860

WORKDIR $HOME/app/backend

CMD ["python", "app.py"]
