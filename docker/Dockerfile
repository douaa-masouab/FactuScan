FROM python:3.9-slim

WORKDIR /app



# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    libpng-dev \
    libjpeg-dev \
    libtiff-dev \
    libwebp-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY ./backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY ./backend/ .
# Create uploads directory
RUN mkdir -p /app/uploads

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]