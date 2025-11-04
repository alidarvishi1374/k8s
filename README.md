# Kubernetes Dashboard Extensions

This repository contains a collection of tools designed to extend and enhance the functionality of the Kubernetes . Each subproject serves a specific role in improving observability, security, and automation across Kubernetes clusters.

## 📁 Project Structure

```bash
.
├── api-aggregator-proxy          # Custom API aggregator proxy for routing dashboard requests
├── kubernetes-dashboard-proxy    # Proxy for secure dashboard access and authentication
└── kubernete-dashboard-watcher   # Watcher service that monitors and scales deployments dynamically
```

## 🚀 Overview

| Component                       | Description                                                                                         |
| ------------------------------- | --------------------------------------------------------------------------------------------------- |
| **api-aggregator-proxy**        | Aggregates multiple APIs into a single accessible endpoint for dashboard and external consumers.    |
| **kubernetes-dashboard-proxy**  | Provides secure, token-based access to the Kubernetes Dashboard. Supports TLS and RBAC integration. |
| **kubernete-dashboard-watcher** | Watches deployments and adjusts replica counts or states based on defined policies or events.       |

## 🧰 Requirements

* Kubernetes 1.34+
* Python 3.11+
* Docker or Podman for containerization
