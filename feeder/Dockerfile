FROM arth360-base:latest

WORKDIR /app/feeder

# Copy feeder specific files
COPY feeder/ .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the feeder service
CMD ["python", "feeder.py"] 