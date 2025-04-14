FROM arth360-base:latest

WORKDIR /app/content

# Install additional dependencies and download NLTK data
RUN pip install lxml_html_clean nltk && \
    python -c "import nltk; nltk.download(['punkt', 'punkt_tab'])"

# Copy content specific files
COPY content/ .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the content service
CMD ["python", "content.py"] 