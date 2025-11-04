#!/usr/bin/env python3
import base64
import json
import os
from flask import Flask, request, jsonify
from kubernetes import client, config

app = Flask(__name__)

# ---------------------------
# Kubernetes Connection Setup
# ---------------------------
def k8s_init():
    """Load Kubernetes config - prefer in-cluster."""
    try:
        config.load_incluster_config()
    except Exception:
        kubeconf = os.environ.get("KUBECONFIG")
        if kubeconf:
            config.load_kube_config(config_file=kubeconf)
        else:
            config.load_kube_config()

k8s_init()
v1 = client.CoreV1Api()

# ---------------------------
# Decode JWT from Dashboard Token
# ---------------------------
def decode_jwt(token: str) -> dict:
    """Decode JWT payload (without verifying signature)."""
    try:
        header_b64, payload_b64, _ = token.split(".")
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        data = base64.urlsafe_b64decode(padded)
        return json.loads(data)
    except Exception as e:
        raise ValueError(f"Invalid JWT: {e}")

# ---------------------------
# Extract team name from ServiceAccount name
# ---------------------------
def extract_team_from_sa(sa_name: str) -> str | None:
    """
    Extract team name from ServiceAccount name.
    Example: dashboard-application-platform-airanmanesh -> application-platform
    """
    parts = sa_name.split("-")
    if len(parts) >= 3:
        # assuming format: dashboard-<team>-<user>
        return "-".join(parts[1:-1])
    return None

# ---------------------------
# Get namespaces by label team=<team_name>
# ---------------------------
def get_team_namespaces(team_name: str):
    """Return all namespaces that have label team=<team_name>."""
    try:
        ns_list = v1.list_namespace(label_selector=f"team={team_name}")
        return ns_list.items
    except Exception as e:
        print(f"[ERROR] Fetching namespaces for team {team_name}: {e}")
        return []

# ---------------------------
# Format output like Kubernetes Dashboard
# ---------------------------
def format_dashboard_output(namespaces):
    formatted = {"listMeta": {"totalItems": len(namespaces)}, "namespaces": [], "errors": []}
    for ns in namespaces:
        item = {
            "objectMeta": {
                "name": ns.metadata.name,
                "labels": ns.metadata.labels or {},
                "annotations": ns.metadata.annotations or {},
                "creationTimestamp": (
                    ns.metadata.creation_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
                    if ns.metadata.creation_timestamp else None
                ),
                "uid": ns.metadata.uid,
            },
            "typeMeta": {"kind": "namespace"},
            "phase": ns.status.phase,
        }
        formatted["namespaces"].append(item)
    return formatted

# ---------------------------
# Main endpoint
# ---------------------------
@app.route("/", methods=["GET"])
def list_namespaces():
    # ---------------------------
    # Extract Bearer token
    # ---------------------------
    token = None
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    else:
        cookie = request.headers.get("cookie", "")
        if "token=" in cookie:
            token = cookie.split("token=")[1].split(";")[0].strip()

    if not token:
        return jsonify({"error": "No token found"}), 401

    # ---------------------------
    # Decode token and extract team
    # ---------------------------
    try:
        payload = decode_jwt(token)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    sa_name = payload.get("kubernetes.io/serviceaccount/service-account.name")
    if not sa_name:
        return jsonify({"error": "Token missing ServiceAccount name"}), 400

    team_name = extract_team_from_sa(sa_name)
    if not team_name:
        return jsonify({"error": f"Could not extract team from ServiceAccount '{sa_name}'"}), 400

    # ---------------------------
    # Get namespaces with team label
    # ---------------------------
    allowed_ns_objs = get_team_namespaces(team_name)
    return jsonify(format_dashboard_output(allowed_ns_objs)), 200

# ---------------------------
# Healthcheck endpoint
# ---------------------------
@app.route("/healthz")
def health():
    return "ok", 200

# ---------------------------
# Entrypoint
# ---------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 80)))

