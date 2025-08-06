# Use Python 3.12-slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    netcat-openbsd \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK data
RUN python -m nltk.downloader stopwords punkt

# Pre-download the AI model to cache it in the Docker image
RUN python -c "from transformers import AutoTokenizer, AutoModelForSeq2SeqLM; \
    model_name = 'facebook/bart-large-cnn'; \
    print('Downloading BART model...'); \
    tokenizer = AutoTokenizer.from_pretrained(model_name); \
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name); \
    print('Model downloaded and cached successfully!')"

# Copy the application code
COPY app/ ./app/
COPY frontend/ ./frontend/
COPY start.sh ./
COPY .env .

# Create cache directory
RUN mkdir -p ./cache

# Expose ports
EXPOSE 8000 8501

# Make startup script executable
RUN chmod +x start.sh

# Create health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
    CMD curl -f http://localhost:8000/status || exit 1

# Default command
CMD ["./start.sh"]
