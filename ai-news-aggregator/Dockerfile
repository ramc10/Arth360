FROM arth360-base:latest

WORKDIR /app

# Copy requirements and install dependencies
COPY ai-news-aggregator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY ai-news-aggregator/*.py ./

# Create logs directory
RUN mkdir -p logs

# Run the aggregator
CMD ["python", "-u", "aggregator.py"]
