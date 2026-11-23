
import os
import time
import threading
import requests
import docker

# ----------------------------------------
# CONFIGURATION
# ----------------------------------------

LOKI_URL = os.getenv(
    "LOKI_URL",
    "http://localhost:3100/loki/api/v1/push"
)
SCAN_INTERVAL = int(os.getenv("LOG_SCAN_INTERVAL", "5"))
IGNORE_CONTAINERS = set(
    filter(None, os.getenv("IGNORE_CONTAINERS", "log-collector,monitoring-log-collector").split(","))
)

# Active container worker threads: {container_id: threading.Thread}
active_workers = {}
active_workers_lock = threading.Lock()
shutdown_flag = threading.Event()


def get_docker_client():
    """Connect to Docker with error handling."""
    try:
        return docker.from_env()
    except Exception as error:
        print(f"Docker connection error: {error}")
        return None


def send_to_loki(container_name, log_line):
    """Send one Docker log entry to Loki."""
    timestamp = str(time.time_ns())

    payload = {
        "streams": [
            {
                "stream": {
                    "job": "docker",
                    "container": container_name,
                    "service_name": container_name
                },
                "values": [
                    [timestamp, log_line]
                ]
            }
        ]
    }

    try:
        response = requests.post(
            LOKI_URL,
            json=payload,
            timeout=5
        )

        if response.status_code != 204:
            print("Loki error:", response.text)

    except requests.RequestException as error:
        print("Loki connection error:", error)


def collect_logs(container_name, client=None, container_id=None):
    """Continuously collect logs from one container."""
    if client is None:
        client = get_docker_client()
        if client is None:
            return

    lookup_id = container_id or container_name
    display_id = container_id[:12] if container_id else container_name
    print(f"Started log collection for: {container_name} ({display_id})")

    try:
        container = client.containers.get(lookup_id)
        logs = container.logs(
            stream=True,
            follow=True,
            since=int(time.time()),
            timestamps=False
        )

        for log in logs:
            if shutdown_flag.is_set():
                break

            message = log.decode(
                "utf-8",
                errors="replace"
            ).strip()

            if message:
                print(f"[{container_name}] {message}")
                send_to_loki(container_name, message)

    except Exception as error:
        print(f"Stopped log collection for {container_name}: {error}")
    finally:
        with active_workers_lock:
            if container_id:
                active_workers.pop(container_id, None)
            else:
                active_workers.pop(container_name, None)
        print(f"Worker finished for: {container_name}")


def reconcile_containers(client):
    """Discover new running containers and spawn collector threads dynamically."""
    try:
        running_containers = client.containers.list()
    except Exception as error:
        print(f"Error listing containers: {error}")
        return

    with active_workers_lock:
        for container in running_containers:
            cid = container.id
            cname = container.name

            if cname in IGNORE_CONTAINERS:
                continue

            # If container is active and not yet monitored, start collector thread
            if cid not in active_workers or not active_workers[cid].is_alive():
                thread = threading.Thread(
                    target=collect_logs,
                    args=(cname, client, cid),
                    daemon=True
                )
                active_workers[cid] = thread
                thread.start()


def main():
    print("Docker Log Collector Started")
    print(f"Pushing logs to: {LOKI_URL}")

    client = None
    while not shutdown_flag.is_set():
        if client is None:
            client = get_docker_client()
            if client is None:
                print("Retrying connection to Docker daemon in 5s...")
                time.sleep(5)
                continue

        reconcile_containers(client)
        time.sleep(SCAN_INTERVAL)

    print("Docker Log Collector Stopped")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        shutdown_flag.set()
        print("\nShutting down Docker Log Collector...")
