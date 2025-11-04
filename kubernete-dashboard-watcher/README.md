# 🧩 Kubernetes Dashboard Watcher

A lightweight Python service that automatically synchronizes container resource **limits** with **requests** for Deployments created by the **Kubernetes Dashboard**.

---

## 📘 Overview

When users create Deployments via the Kubernetes Dashboard, sometimes resource **requests** are defined without matching **limits**. This watcher listens for new Deployment events and automatically patches those deployments so that:

> For each container: `resources.limits[key] = resources.requests[key]`

This ensures consistent and predictable resource configurations across dashboard-managed workloads.

---

## ⚙️ Features

* Watches all namespaces for new Deployments.
* Detects Deployments created by the **Dashboard API**.
* Automatically synchronizes resource limits with requests.
* Logs all detected, updated, or skipped deployments.

---

## 📁 Project Structure

```
.
├── app.py                 # Main watcher logic
├── Dockerfile             # Docker build configuration
├── requirements.txt       # Python dependencies
└── resources.yaml         # Kubernetes manifests (RBAC + Deployment)
```

---

## 🐍 app.py Summary

* Connects to the Kubernetes cluster using `load_incluster_config()`.
* Uses the Kubernetes API (`AppsV1Api`) and a `watch.Watch()` stream.
* Listens for `ADDED` Deployment events.
* Identifies deployments managed by `dashboard-api`.
* Updates container `resources.limits` to match `resources.requests`.

### Example Log Output

```
[INFO] 2025-11-04 10:21:15 - Dashboard watcher started...
[INFO] 2025-11-04 10:21:18 - Detected dashboard-created deployment: mynamespace/myapp
[OK]   Updated resources for deployment: mynamespace/myapp
```

---

## 🐳 Dockerfile

```dockerfile
FROM registry.docker.ir/python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
CMD ["python3", "app.py"]
```

Build the image:

```bash
docker build -t kubernetes-dashboard-watcher:v1.0.1 .
```

Push it to your registry:

```bash
docker push <your_registry>/dashboard/kubernetes-dashboard-watcher:v1.0.1
```

---

## ☸️ Kubernetes Manifests (resources.yaml)

This file defines the ServiceAccount, ClusterRole, ClusterRoleBinding, and Deployment needed to run the watcher inside the `kubernetes-dashboard` namespace.

Apply it with:

```bash
kubectl apply -f resources.yaml
```

---

## 🧪 Testing

After deploying:

```bash
kubectl logs -n kubernetes-dashboard -l app=kubernetes-dashboard-watcher -f
```

You should see messages like:

```
[INFO] Detected dashboard-created deployment: team-a/app1
[OK] Updated resources for deployment: team-a/app1
```

---

## 🔧 Troubleshooting

| Issue                     | Cause                   | Fix                                                             |
| ------------------------- | ----------------------- | --------------------------------------------------------------- |
| `Forbidden` when patching | Missing RBAC permission | Ensure ClusterRole has `patch` and `update` on `deployments`    |
| Watch stops unexpectedly  | API timeout             | The watcher reconnects automatically after 2 seconds            |
| No logs seen              | Namespace mismatch      | Confirm the watcher runs in the same namespace as the Dashboard |

---

## 🧾 Requirements

Python Dependencies:

```
kubernetes
```

Install locally (optional):

```bash
pip install -r requirements.txt
```
