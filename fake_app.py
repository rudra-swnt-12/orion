# In /fake_app.py

import logging
import time
import random
import threading
from flask import Flask, Response
from prometheus_client import Gauge, Counter, generate_latest, REGISTRY

# --- 1. Setup Flask App ---
app = Flask(__name__)

# --- 2. Setup Logging ---
# We will log to a file inside the container
LOG_FILE = "/app/logs/fake_app.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s",
)
log = logging.getLogger("fake_app")

# --- 3. Setup Prometheus Metrics ---
CPU_USAGE = Gauge("fake_app_cpu_usage_percent", "Fake CPU usage percentage")
REQUEST_LATENCY = Gauge(
    "fake_app_request_latency_seconds", "Fake request latency in seconds"
)
ERRORS_TOTAL = Counter(
    "fake_app_errors_total", "Total fake errors encountered", ["error_type"]
)


# --- 4. The Main "Chaos" Loop ---
def run_chaos_loop():
    """Generates metrics and logs in a loop."""
    log.info("Fake app started. Generating metrics and logs...")
    while True:
        try:
            # Generate normal metrics
            cpu = random.uniform(10.0, 30.0)
            lat = random.uniform(0.1, 0.4)
            CPU_USAGE.set(cpu)
            REQUEST_LATENCY.set(lat)
            log.info(
                f"OK: Service running normally. CPU: {cpu:.2f}%, Latency: {lat:.3f}s"
            )

            # 10% chance to generate a "critical" error
            if random.random() < 0.1:
                # This is the "root cause" Orion will hunt for!
                ERRORS_TOTAL.labels(error_type="db_connection").inc()
                log.error(
                    "FATAL: Database connection limit reached! Cannot connect to payment-db."
                )

            # 30% chance of a "warning"
            elif random.random() < 0.3:
                log.warning("WARN: High query latency detected on user_service.")

            time.sleep(2)
        except Exception as e:
            log.critical(f"Chaos loop failed: {e}")
            time.sleep(5)


# --- 5. Flask Routes ---
@app.route("/")
def index():
    return "Fake App for Project Orion. Check /metrics"


@app.route("/metrics")
def metrics():
    """Exposes Prometheus metrics."""
    return Response(generate_latest(REGISTRY), mimetype="text/plain")


if __name__ == "__main__":
    # Start the chaos loop in a background thread
    chaos_thread = threading.Thread(target=run_chaos_loop, daemon=True)
    chaos_thread.start()

    # Run the Flask web server
    app.run(host="0.0.0.0", port=8080)
