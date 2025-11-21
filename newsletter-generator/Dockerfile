FROM arth360-base:latest

WORKDIR /app

# Copy requirements and install dependencies
COPY newsletter-generator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY newsletter-generator/*.py ./

# Create logs directory
RUN mkdir -p logs

# Run the generator
CMD ["python", "-u", "generator.py"]
