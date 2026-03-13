FROM python:3.11-slim

WORKDIR /usr/src/app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8909

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PORT=8909

# Run application
CMD ["python", "main.py"]
