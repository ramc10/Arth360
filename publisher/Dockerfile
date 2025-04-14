FROM arth360-base:latest

WORKDIR /app/publisher

# Copy publisher specific files
COPY publisher/ .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the publisher service
CMD ["python", "telegram_publisher.py"] 