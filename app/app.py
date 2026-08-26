from flask import Flask
import logging
import time

from prometheus_client import Counter, generate_latest

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

REQUEST_COUNT = Counter(
    "app_requests_total",
    "Total number of requests"
)


@app.route("/")
def home():
    REQUEST_COUNT.inc()
    logging.info("Home page accessed")
    return "Monitoring Application is running"


@app.route("/success")
def success():
    REQUEST_COUNT.inc()
    logging.info("Successful request")
    return "Success"


@app.route("/error")
def error():
    REQUEST_COUNT.inc()
    logging.error("Test error generated")
    return "Error generated"


@app.route("/slow")
def slow():
    REQUEST_COUNT.inc()
    logging.warning("Slow request started")
    time.sleep(3)
    return "Slow response"


@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {
        "Content-Type": "text/plain"
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)