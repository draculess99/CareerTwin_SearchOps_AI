FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (needed for compiling some python packages)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Make the start script executable
RUN chmod +x render-start.sh

# Command to run both services using the start script
CMD ["./render-start.sh"]
