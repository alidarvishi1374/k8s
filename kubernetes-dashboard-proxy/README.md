# kubernetes-dashboard-proxy — README

> **Summary:** This repository contains a lightweight Flask-based proxy service designed to return the list of namespaces a given ServiceAccount is authorized to view. The proxy decodes the Dashboard JWT token, extracts the ServiceAccount name, derives the associated **team name**, and fetches all namespaces labeled `team=<team>`. The output is formatted to resemble the Kubernetes Dashboard namespace API response.

---

## Table of Contents

* [Architecture and Logic](#architecture-and-logic)
* [Repository Structure](#repository-structure)
* [Prerequisites](#prerequisites)
* [Local Build and Run](#local-build-and-run)
* [Build and Push Docker Image](#build-and-push-docker-image)
* [Kubernetes Deployment](#kubernetes-deployment)
* [Testing and Example Requests](#testing-and-example-requests)
* [Security Considerations](#security-considerations)
* [Common Issues](#common-issues)
* [Development and Improvements](#development-and-improvements)
* [Useful kubectl Commands](#useful-kubectl-commands)
* [FAQ](#faq)
* [License](#license)

---

## Architecture and Logic

1. **Request Flow**

   * A client (typically the Kubernetes Dashboard) sends an HTTP request to the proxy with either an `Authorization: Bearer <token>` header or a `cookie` containing `token=`.

2. **JWT Decoding**

   * The function `decode_jwt` base64-decodes the JWT payload without verifying the signature.
   * The payload field `kubernetes.io/serviceaccount/service-account.name` is extracted to identify the ServiceAccount name.

3. **Team Extraction**

   * The `extract_team_from_sa` function assumes a naming pattern like `dashboard-<team>-<user>` and extracts the `<team>` portion. Example: `dashboard-application-platform-alireza` → `application-platform`.

4. **Kubernetes API Query**

   * Using `CoreV1Api` with `labelSelector=team=<team_name>`, the proxy fetches namespaces labeled for that team.

5. **Response Formatting**

   * The output is formatted like the Dashboard API’s namespace list: `listMeta`, `namespaces[]`, and `errors`.

> **Design Note:** The proxy has read-only permissions via a `ClusterRole` limited to `get` and `list` namespaces. If RBAC is misconfigured, you may receive empty or forbidden results.

---

## Repository Structure

* `app.py` — Main Flask application implementing logic and Kubernetes API interaction.
* `Dockerfile` — Builds a minimal image based on `python:3.11-slim` (or your private registry image).
* `requirements.txt` — Dependencies (`flask`, `kubernetes`).
* `resources.yaml` — Kubernetes manifests for ServiceAccount, ClusterRole, ClusterRoleBinding, Deployment, and Service.
* `ingress.yaml` — Traefik Middleware and Ingress for HTTPS routing.

---

## Prerequisites

* A running Kubernetes cluster with valid `kubectl` access.
* `cluster-admin` privileges for deploying ClusterRole and ClusterRoleBinding.
* A DNS/host mapping (e.g., `dashboard.sb.sre`) pointing to your ingress controller.
* Docker registry access if you plan to push your image.

---

## Local Build and Run

### Option 1 — Run directly with Python (for development)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Use local kubeconfig
export KUBECONFIG=$HOME/.kube/config

# Run the app
python3 app.py
# Defaults to port 80 (set PORT=8080 for local testing)
```

### Option 2 — Run in Docker

```bash
docker build -t dashboard-proxy:dev .
docker run --rm -p 8080:80 \
  -e KUBECONFIG=/root/.kube/config \
  -v $KUBECONFIG:/root/.kube/config:ro \
  dashboard-proxy:dev
```

Access at `http://localhost:8080/`.

> In local runs, provide your kubeconfig. In-cluster mode automatically loads pod credentials.

---

## Build and Push Docker Image

```bash
IMAGE=registry.example.com/yourproj/kubernetes-dashboard-proxy:1.0.0
docker build -t $IMAGE .
docker push $IMAGE
```

Then update `resources.yaml` with your image reference.

---

## Kubernetes Deployment

```bash
kubectl apply -f resources.yaml
kubectl apply -f ingress.yaml

# Verify
kubectl -n kubernetes-dashboard get all
kubectl -n kubernetes-dashboard describe deployment kubernetes-dashboard-proxy
```

Ensure the deployment uses `serviceAccountName: ns-access-sa` and that the account exists.

---

## Testing and Example Requests

### Healthcheck

```bash
curl -v http://<proxy-host>/healthz
# Response: ok
```

### Fetch namespaces with token (Header)

```bash
curl -H "Authorization: Bearer <DASHBOARD_TOKEN>" https://dashboard.sb.sre/api/v1/namespace
```

### Using a Cookie

```bash
curl -b "token=<DASHBOARD_TOKEN>" https://dashboard.sb.sre/api/v1/namespace
```

### Extract a Dashboard Token

```bash
kubectl -n kubernetes-dashboard get sa
kubectl -n kubernetes-dashboard get secret | grep ns-access-sa
kubectl -n kubernetes-dashboard get secret <secret-name> -o jsonpath='{.data.token}' | base64 -d
```

**Expected output:** JSON object listing namespaces labeled with `team=<team>`.

---

## Security Considerations

* **JWT Signature Not Verified:** The proxy decodes JWTs without verifying signatures. For production, verify tokens with the Kubernetes API server public key.
* **RBAC Scope:** The provided `ClusterRole` only grants `get`/`list` on namespaces. Adjust if finer-grained access is needed.
* **Logging:** The current implementation uses basic `print` logging. Replace with a proper structured logger for production.
* **Exposure:** Do not expose this endpoint publicly without authentication or firewall restrictions.

---

## Common Issues

| Error                               | Cause                               | Fix                                                      |
| ----------------------------------- | ----------------------------------- | -------------------------------------------------------- |
| `401 No token found`                | Missing `Authorization` or `cookie` | Ensure token header/cookie present                       |
| `Token missing ServiceAccount name` | JWT missing field                   | Use a ServiceAccount-issued token                        |
| Empty namespace list                | Namespace lacks `team` label        | Check `kubectl get ns --show-labels`                     |
| `Forbidden`                         | Missing RBAC permission             | Verify Role/Binding setup                                |
| `Invalid JWT`                       | Malformed or truncated token        | Ensure proper token with 3 segments (header.payload.sig) |

---

## Development and Improvements

* Implement JWT signature validation for security.
* Cache namespace results per team to reduce API calls.
* Add structured logging and Prometheus metrics.
* Extend endpoints to return related resources (e.g., quotas, RBAC info).

---

## Useful kubectl Commands

```bash
kubectl -n kubernetes-dashboard logs deployment/kubernetes-dashboard-proxy
kubectl -n kubernetes-dashboard describe deployment kubernetes-dashboard-proxy
kubectl get sa -n kubernetes-dashboard ns-access-sa -o yaml
kubectl auth can-i list namespaces --as system:serviceaccount:kubernetes-dashboard:ns-access-sa
```

---

## FAQ

**Q:** Why doesn’t my token contain `service-account.name`?
**A:** Likely it’s a user token or from an external identity provider. Kubernetes ServiceAccount tokens include this field.

**Q:** How can I customize the response format?
**A:** Edit the `format_dashboard_output` function in `app.py`.
