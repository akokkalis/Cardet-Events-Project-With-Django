# Dockerfile

FROM python:3.11-slim

# Prevents Python from writing .pyc files and forces unbuffered logs
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set working directory
WORKDIR /app

# Install system dependencies for mysqlclient and other common libs
RUN apt-get update && apt-get install -y \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*


RUN apt-get update && apt-get install -y fonts-dejavu-core && rm -rf /var/lib/apt/lists/*



# Install Python dependencies
COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy project code
COPY . .


COPY core/static/fonts/DejaVuSans.ttf /app/core/static/fonts/DejaVuSans.ttf

RUN chmod +x /app/docker-entrypoint.sh /app/scripts/fetch_vendor_assets.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Default run command (overridden in docker-compose, kept here as a safe fallback)
CMD ["gunicorn", "event_management.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60", "--max-requests", "1000", "--max-requests-jitter", "100"]
