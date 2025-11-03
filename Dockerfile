FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install flask prometheus-client

# Create the log directory
RUN mkdir -p /app/logs

# Copy the app
COPY fake_app.py .

# Expose the metrics port and run the app
EXPOSE 8080
CMD ["python", "fake_app.py"]