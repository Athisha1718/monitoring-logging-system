# Docker-Based Monitoring & Logging System

## 📌 Project Overview

A Docker-based monitoring and logging system designed to monitor container performance, collect application logs, visualize metrics, and generate alerts using open-source DevOps tools.

The project integrates **Prometheus, Grafana, cAdvisor, Loki, and Promtail** to provide centralized monitoring and logging for Docker containers.

---

## 🛠️ Technologies Used

- Docker
- Prometheus
- Grafana
- cAdvisor
- Loki
- Promtail
- Python
- Flask
- Git & GitHub

---

## 🏗️ Architecture

```text
                    ┌─────────────────────┐
                    │   Monitoring App    │
                    │      Flask          │
                    │     Port 5000       │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │       Docker        │
                    │     Containers      │
                    └─────────┬───────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
       ┌─────────────┐                 ┌─────────────┐
       │   cAdvisor  │                 │  Promtail   │
       │   Metrics   │                 │    Logs     │
       └──────┬──────┘                 └──────┬──────┘
              │                               │
              ▼                               ▼
       ┌─────────────┐                 ┌─────────────┐
       │ Prometheus  │                 │    Loki     │
       │   Metrics   │                 │    Logs     │
       └──────┬──────┘                 └──────┬──────┘
              │                               │
              └──────────────┬────────────────┘
                             ▼
                    ┌─────────────────────┐
                    │      Grafana        │
                    │ Dashboards & Alerts │
                    └─────────────────────┘
