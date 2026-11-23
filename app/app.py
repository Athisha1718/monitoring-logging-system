
from flask import Flask, render_template, jsonify, request
import urllib.request
import urllib.parse
import json
import time
import os
from datetime import datetime, timezone
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

# Configurable endpoints with environment variable overrides
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
LOKI_URL = os.getenv("LOKI_URL", "http://loki:3100")
ALERTMANAGER_URL = os.getenv("ALERTMANAGER_URL", "http://alertmanager:9093")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
DEFAULT_CPU_CORES = int(os.getenv("TOTAL_CPU_CORES", str(os.cpu_count() or 8)))

# ----------------------------------------
# PROMETHEUS METRICS FOR THIS FLASK APP
# ----------------------------------------

REQUEST_COUNT = Counter(
    "monitoring_app_requests_total",
    "Total HTTP requests to the monitoring platform",
    ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "monitoring_app_request_latency_seconds",
    "HTTP request latency in seconds",
    ["endpoint"]
)

@app.before_request
def before_request():
    request._start_time = time.time()

@app.after_request
def after_request(response):
    if hasattr(request, "_start_time"):
        latency = time.time() - request._start_time
        endpoint = request.endpoint or "unknown"
        REQUEST_LATENCY.labels(endpoint=endpoint).observe(latency)
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=endpoint,
            status=response.status_code
        ).inc()
    return response

@app.route("/metrics")
def prometheus_metrics():
    """Prometheus scrape endpoint for monitoring-app itself."""
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


# ----------------------------------------
# DYNAMIC CPU CORES HELPER
# ----------------------------------------

def get_cpu_cores():
    """Dynamically determine CPU cores from Prometheus or fallback to system cores."""
    try:
        cores_data = get_prometheus_data("machine_cpu_cores")
        if cores_data and len(cores_data) > 0:
            val = float(cores_data[0]["value"][1])
            if val > 0:
                return int(val)
    except Exception:
        pass
    return DEFAULT_CPU_CORES



# ----------------------------------------
# PROMETHEUS CONNECTION
# ----------------------------------------

def get_prometheus_data(query):
    try:
        params = urllib.parse.urlencode({"query": query})
        url = f"{PROMETHEUS_URL}/api/v1/query?{params}"

        with urllib.request.urlopen(url, timeout=5) as response:
            result = json.loads(response.read().decode())

        if result.get("status") == "success":
            return result.get("data", {}).get("result", [])

        return None

    except Exception as e:
        print("Prometheus connection error:", e)
        return None


def get_prometheus_range_data(query, start_time, end_time, step="30s"):
    """Query Prometheus range data for historical charts."""
    try:
        params = urllib.parse.urlencode({
            "query": query,
            "start": str(start_time),
            "end": str(end_time),
            "step": str(step)
        })
        url = f"{PROMETHEUS_URL}/api/v1/query_range?{params}"

        with urllib.request.urlopen(url, timeout=8) as response:
            result = json.loads(response.read().decode())

        if result.get("status") == "success":
            return result.get("data", {}).get("result", [])

        return None

    except Exception as e:
        print("Prometheus range query error:", e)
        return None


def get_prometheus_alerts():
    """Retrieve active firing and pending alerts from Prometheus."""
    try:
        url = f"{PROMETHEUS_URL}/api/v1/alerts"

        with urllib.request.urlopen(url, timeout=5) as response:
            result = json.loads(response.read().decode())

        if result.get("status") == "success":
            raw_alerts = result.get("data", {}).get("alerts", [])
            alerts = []

            for item in raw_alerts:
                labels = item.get("labels", {})
                annotations = item.get("annotations", {})
                alerts.append({
                    "name": labels.get("alertname", "UnknownAlert"),
                    "state": item.get("state", "unknown"),
                    "severity": labels.get("severity", "warning"),
                    "container": labels.get("container", labels.get("name", "system")),
                    "summary": annotations.get("summary", annotations.get("description", "No description")),
                    "active_at": item.get("activeAt", "")
                })

            return alerts

        return None

    except Exception as e:
        print("Prometheus alerts error:", e)
        return None


# ----------------------------------------
# LOKI LOG CONNECTION
# ----------------------------------------

def get_loki_logs(container_filter=None, search_filter=None, level_filter=None, limit=100):

    try:
        end_time = time.time_ns()
        start_time = end_time - (60 * 60 * 1_000_000_000)

        # Base LogQL query
        if container_filter:
            query = f'{{job="docker", container="{container_filter}"}}'
        else:
            query = '{job="docker"}'

        # Optional keyword search
        if search_filter:
            query += f' |= "{search_filter}"'

        # Optional level regex filter
        if level_filter:
            query += f' |~ "(?i){level_filter}"'

        clamped_limit = min(max(1, limit), 500)

        params = urllib.parse.urlencode({
            "query": query,
            "start": str(start_time),
            "end": str(end_time),
            "limit": str(clamped_limit),
            "direction": "backward"
        })

        url = f"{LOKI_URL}/loki/api/v1/query_range?{params}"

        with urllib.request.urlopen(url, timeout=10) as response:
            result = json.loads(response.read().decode())

        if result.get("status") != "success":
            return None

        logs = []

        for stream in result.get("data", {}).get("result", []):
            container_name = stream.get("stream", {}).get(
                "container", "unknown"
            )

            for timestamp, message in stream.get("values", []):
                readable_time = datetime.fromtimestamp(
                    int(timestamp) / 1_000_000_000,
                    tz=timezone.utc
                ).astimezone().strftime("%Y-%m-%d %H:%M:%S")

                logs.append({
                    "container": container_name,
                    "timestamp": readable_time,
                    "message": message
                })

        logs.sort(
            key=lambda item: item["timestamp"],
            reverse=True
        )

        return logs

    except Exception as e:
        print("Loki connection error:", e)
        return None


import collections
import threading

# ----------------------------------------
# ASYNCHRONOUS METRICS ENGINE (NON-BLOCKING)
# ----------------------------------------

cached_container_metrics = []
cached_total_metrics = {"cpu_usage": 0.0, "memory_usage_mb": 0.0, "containers": 0}
metrics_history_buffer = collections.deque(maxlen=60)
metrics_cache_lock = threading.Lock()


def background_metrics_worker():
    """Background worker that continuously collects container stats without blocking web requests."""
    while True:
        try:
            import docker
            client = docker.from_env()
            # Retrieve all containers (both running and stopped/exited)
            containers = client.containers.list(all=True)
            now = time.time()
            container_list = []
            total_mem_mb = 0.0
            total_cpu_percent = 0.0
            running_containers_count = 0

            for c in containers:
                cname = c.name
                raw_status = c.status.lower()
                state_info = c.attrs.get("State", {})
                exit_code = state_info.get("ExitCode", 0)

                uptime_str = "Active"
                status = "Running"

                if raw_status == "running":
                    running_containers_count += 1
                    status = "Running"

                    try:
                        started_at = state_info.get("StartedAt", "")
                        if started_at:
                            clean_time = started_at.replace("Z", "+00:00").split(".")[0] + "+00:00"
                            dt = datetime.fromisoformat(clean_time)
                            delta = max(0, int(now - dt.timestamp()))
                            hrs = delta // 3600
                            mins = (delta % 3600) // 60
                            uptime_str = f"{hrs}h {mins}m" if hrs > 0 else f"{mins}m"
                    except Exception:
                        uptime_str = "Running"

                    # Stats calculation for active running containers
                    mem_mb = 0.0
                    cpu_pct = 0.0
                    try:
                        stats = c.stats(stream=False)
                        mem_bytes = stats.get("memory_stats", {}).get("usage", 0)
                        mem_mb = round(mem_bytes / (1024 * 1024), 2)
                        total_mem_mb += mem_mb

                        cpu_stats = stats.get("cpu_stats", {})
                        precpu_stats = stats.get("precpu_stats", {})
                        cpu_delta = cpu_stats.get("cpu_usage", {}).get("total_usage", 0) - precpu_stats.get("cpu_usage", {}).get("total_usage", 0)
                        system_delta = cpu_stats.get("system_cpu_usage", 0) - precpu_stats.get("system_cpu_usage", 0)
                        online_cpus = cpu_stats.get("online_cpus", 1) or 1
                        if system_delta > 0 and cpu_delta > 0:
                            cpu_pct = round((cpu_delta / system_delta) * online_cpus * 100.0, 2)
                        total_cpu_percent += cpu_pct
                    except Exception:
                        pass

                else:
                    # Stopped / Exited / Paused containers
                    status = f"Exited ({exit_code})" if raw_status == "exited" else raw_status.capitalize()
                    mem_mb = 0.0
                    cpu_pct = 0.0

                    try:
                        finished_at = state_info.get("FinishedAt", "")
                        if finished_at:
                            clean_time = finished_at.replace("Z", "+00:00").split(".")[0] + "+00:00"
                            dt = datetime.fromisoformat(clean_time)
                            delta = max(0, int(now - dt.timestamp()))
                            hrs = delta // 3600
                            mins = (delta % 3600) // 60
                            uptime_str = f"Stopped {hrs}h ago" if hrs > 0 else f"Stopped {mins}m ago"
                        else:
                            uptime_str = "Stopped"
                    except Exception:
                        uptime_str = "Stopped"

                container_list.append({
                    "name": cname,
                    "status": status,
                    "uptime": uptime_str,
                    "cpu_usage": cpu_pct,
                    "memory_usage_mb": mem_mb
                })

            now_str = datetime.now().strftime("%H:%M:%S")
            total_mem_mb = round(total_mem_mb, 2)
            total_cpu_percent = round(total_cpu_percent, 2)

            with metrics_cache_lock:
                cached_container_metrics.clear()
                cached_container_metrics.extend(container_list)
                cached_total_metrics["cpu_usage"] = total_cpu_percent
                cached_total_metrics["memory_usage_mb"] = total_mem_mb
                cached_total_metrics["containers"] = running_containers_count

                metrics_history_buffer.append({
                    "timestamp": now_str,
                    "cpu": total_cpu_percent,
                    "memory_mb": total_mem_mb
                })

        except Exception as err:
            print("Background metrics worker error:", err)

        time.sleep(3)


# Start background metrics worker thread automatically
_bg_thread = threading.Thread(target=background_metrics_worker, daemon=True)
_bg_thread.start()


# ----------------------------------------
# DASHBOARD HOME PAGE
# ----------------------------------------

@app.route("/")
def dashboard():
    return render_template("dashboard.html")


# ----------------------------------------
# OVERALL SYSTEM METRICS
# ----------------------------------------

@app.route("/api/metrics")
def metrics():
    with metrics_cache_lock:
        return jsonify({
            "status": "success",
            "cpu_usage": cached_total_metrics["cpu_usage"],
            "memory_usage_mb": cached_total_metrics["memory_usage_mb"],
            "containers": cached_total_metrics["containers"]
        })


# ----------------------------------------
# HISTORICAL SYSTEM METRICS (CHART.JS)
# ----------------------------------------

@app.route("/api/metrics/history")
def metrics_history():
    """Returns time-series CPU and Memory metrics for Chart.js rendering."""
    with metrics_cache_lock:
        timestamps = [p["timestamp"] for p in metrics_history_buffer]
        cpu_series = [p["cpu"] for p in metrics_history_buffer]
        mem_series = [p["memory_mb"] for p in metrics_history_buffer]

    if not timestamps:
        now_str = datetime.now().strftime("%H:%M:%S")
        timestamps = [now_str]
        cpu_series = [0.0]
        mem_series = [0.0]

    return jsonify({
        "status": "success",
        "timestamps": timestamps,
        "cpu": cpu_series,
        "memory_mb": mem_series
    })


# ----------------------------------------
# INDIVIDUAL DOCKER CONTAINER METRICS
# ----------------------------------------

@app.route("/api/containers")
def containers():
    with metrics_cache_lock:
        return jsonify({
            "status": "success",
            "containers": list(cached_container_metrics)
        })




# ----------------------------------------
# DOCKER LOGS API
# ----------------------------------------

@app.route("/api/logs")
def logs():
    container = request.args.get("container")
    search = request.args.get("search")
    level = request.args.get("level")

    try:
        limit = int(request.args.get("limit", 100))
    except ValueError:
        limit = 100

    log_data = get_loki_logs(
        container_filter=container,
        search_filter=search,
        level_filter=level,
        limit=limit
    )

    if log_data is None:
        return jsonify({
            "status": "error",
            "message": "Unable to retrieve logs from Loki"
        }), 503

    return jsonify({
        "status": "success",
        "count": len(log_data),
        "logs": log_data
    })


# ----------------------------------------
# ALERT MANAGEMENT API
# ----------------------------------------

@app.route("/api/alerts")
def alerts():
    """Retrieve active firing and pending alerts."""
    alert_data = get_prometheus_alerts()

    if alert_data is None:
        # Graceful response when alert manager / prometheus alerts is unreachable
        return jsonify({
            "status": "warning",
            "count": 0,
            "alerts": [],
            "message": "Prometheus alert manager disconnected"
        }), 200

    return jsonify({
        "status": "success",
        "count": len(alert_data),
        "alerts": alert_data
    })


# ----------------------------------------
# PLATFORM CONFIG / INTEGRATION API
# ----------------------------------------

@app.route("/api/config")
def config():
    """Expose service URLs for frontend navigation & integration."""
    return jsonify({
        "status": "success",
        "grafana_url": GRAFANA_URL,
        "prometheus_url": PROMETHEUS_URL,
        "loki_url": LOKI_URL,
        "alertmanager_url": ALERTMANAGER_URL
    })


# ----------------------------------------
# PROMETHEUS HEALTH CHECK
# ----------------------------------------

@app.route("/api/health")
def health():

    result = get_prometheus_data("up")

    if result is None:
        return jsonify({
            "status": "error",
            "prometheus": "disconnected"
        }), 503

    return jsonify({
        "status": "success",
        "prometheus": "connected"
    })


# ----------------------------------------
# RUN FLASK APPLICATION
# ----------------------------------------

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
