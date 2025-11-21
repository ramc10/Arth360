FROM arth360-base:latest

WORKDIR /app

# Install system dependencies for WeasyPrint
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libffi-dev \
    libjpeg-dev \
    libopenjp2-7-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY newsletter-publisher/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY newsletter-publisher/*.py ./
COPY newsletter-publisher/templates ./templates/

# Create output and logs directories
RUN mkdir -p output logs

# Run the publisher
CMD ["python", "-u", "publisher.py"]
