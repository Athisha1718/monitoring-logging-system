FROM python:3.12-slim

WORKDIR /app

COPY app/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy application source and log collector
COPY app/ .
COPY log_collector.py .

EXPOSE 5000

CMD ["python", "app.py"]
