#!/usr/bin/env python3
from flask import Flask, jsonify, request
from kubernetes import client, config
import os, traceback, logging
from datetime import datetime, timezone



app = Flask(__name__)

# ---------------------------
# Logging setup
# ---------------------------
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("namespace-api")

# Suppress werkzeug access logs (they produce the GET ... 404 - lines)
werkzeug_logger = logging.getLogger("werkzeug")
werkzeug_logger.setLevel(logging.ERROR)  # show only errors from werkzeug

# ---------------------------
# Kubernetes client init
# ---------------------------
def init_k8s_client():
    try:
        config.load_incluster_config()
        logger.info("Loaded in-cluster Kubernetes configuration")
    except Exception:
        kubeconf = os.environ.get("KUBECONFIG")
        if kubeconf and os.path.exists(kubeconf):
            logger.info(f"Loading kubeconfig from {kubeconf}")
            config.load_kube_config(config_file=kubeconf)
        else:
            logger.info("Loading default kubeconfig from ~/.kube/config")
            config.load_kube_config()
    return client.CoreV1Api(), client.AuthorizationV1Api()

v1, auth_v1 = init_k8s_client()
NAMESPACE_TEAM_LABEL = os.environ.get("NAMESPACE_TEAM_LABEL", "team")

# ---------------------------
# Request logging: filter noisy aggregator discovery paths
# ---------------------------
IGNORED_PATH_PREFIXES = (
    "/openapi",    # ignore /openapi and /openapi/v2
)
IGNORED_EXACT_PATHS = (
    "/apis",       # exact /apis (discovery probe)
)

@app.before_request
def log_request():
    path = request.path or ""
    user = request.headers.get("X-Remote-User", "-")
    remote = request.remote_addr or "-"
    # If it's exact /apis or startswith /openapi -> skip noisy logs
    if path in IGNORED_EXACT_PATHS or any(path.startswith(p) for p in IGNORED_PATH_PREFIXES):
        # if you ever need to debug these, switch this to logger.debug(...)
        return

    # Keep logging for custom.api.local API paths and others
    # e.g. /apis/custom.api.local/v1 and healthz etc.
    logger.info(
        f"Incoming request: {request.method} {path} "
        f"from {remote} | User: {user}"
    )

# ---------------------------
@app.route("/apis/custom.api.local/v1")
def api_root():
    return jsonify({
        "kind": "APIResourceList",
        "apiVersion": "v1",
        "groupVersion": "custom.api.local/v1",
        "resources": [
            {"name": "whoami", "namespaced": False, "kind": "WhoAmI", "verbs": ["get"]},
            {"name": "mynamespace", "namespaced": False, "kind": "MyNamespaceList", "verbs": ["get"]}
        ]
    })

# ---------------------------
@app.route("/apis/custom.api.local/v1/whoami")
def whoami():
    user = request.headers.get("X-Remote-User", "")
    groups = request.headers.get("X-Remote-Group", "")
    groups_list = [g for g in (groups.split(",") if groups else []) if g]
    now_iso = datetime.now(timezone.utc).isoformat()

    response = {
            "metadata": {
                "name": f"user: {user} and groups: {groups_list}",
                "creationTimestamp": now_iso
            }
        }
    return jsonify({
            "apiVersion": "v1",
            "kind": "NamespaceList",
            "metadata": {},
            "items": [response]
        }), 200, {"Content-Type": "application/json"}    

# ---------------------------
@app.route("/apis/custom.api.local/v1/mynamespace")
def mynamespace():
    user = request.headers.get("X-Remote-User", "")
    groups_header = request.headers.get("X-Remote-Group", "")
    groups = [g for g in (groups_header.split(",") if groups_header else []) if g and not g.startswith("system:")]

    if not groups:
        logger.warning(f"Access denied: No group found for user '{user}'")
        fake_item = {
            "metadata": {
                "name": "",
                "annotations": {"custom-message": f"User '{user}' has no accessible namespaces"}
            }
        }
        return jsonify({
            "apiVersion": "v1",
            "kind": "NamespaceList",
            "metadata": {},
            "items": [fake_item]
        }), 200, {"Content-Type": "application/json"}

    try:
        sar = client.V1SubjectAccessReview(
            spec=client.V1SubjectAccessReviewSpec(
                user=user,
                groups=groups,
                resource_attributes=client.V1ResourceAttributes(
                    verb="list",
                    resource="namespaces",
                    group="",
                ),
            )
        )
        sar_resp = auth_v1.create_subject_access_review(body=sar)
        user_can_list = sar_resp.status.allowed
        logger.info(f"SAR for user '{user}' allowed={user_can_list}")
    except Exception as e:
        logger.error(f"SubjectAccessReview failed for user '{user}': {e}\n{traceback.format_exc()}")
        return jsonify({
            "kind": "Status",
            "apiVersion": "v1",
            "status": "Failure",
            "message": f"SAR failed for user '{user}': {e}",
            "reason": "InternalError",
            "code": 500
        }), 500

    try:
        ns_list = v1.list_namespace()
    except Exception as e:
        logger.error(f"Failed to list namespaces: {e}\n{traceback.format_exc()}")
        return jsonify({
            "kind": "Status",
            "apiVersion": "v1",
            "status": "Failure",
            "message": f"Failed to list namespaces: {e}",
            "reason": "InternalError",
            "code": 500
        }), 500

    items = ns_list.items
    if not user_can_list:
        items = [
            ns for ns in items
            if ns.metadata.labels and ns.metadata.labels.get(NAMESPACE_TEAM_LABEL) in groups
        ]

    namespaces = []
    for ns in items:
        namespaces.append({
            "metadata": {
                "name": ns.metadata.name,
                "creationTimestamp": ns.metadata.creation_timestamp.isoformat() if ns.metadata.creation_timestamp else None
            },
            "status": {
                "phase": ns.status.phase if ns.status else "Unknown"
            }
        })

    if not namespaces:
        now_iso = datetime.now(timezone.utc).isoformat()
        fake_item = {
            "metadata": {
                "name": f"No namespaces for user '{user}'",
                "creationTimestamp": now_iso
            },
            "status": {
                "phase": "Unknown"
            }
        }
        namespaces.append(fake_item)

    result = {
        "kind": "NamespaceList",
        "apiVersion": "v1",
        "metadata": {},
        "items": namespaces
    }

    return jsonify(result), 200, {"Content-Type": "application/json"}


# ---------------------------
@app.route("/healthz")
def health():
    return "ok", 200

# ---------------------------
# custom 404 to return Kubernetes-like JSON status (and avoid werkzeug double-logging)
@app.errorhandler(404)
def handle_404(e):
    path = request.path
    user = request.headers.get("X-Remote-User", "-")
    # log only if it's our custom api root missing; otherwise keep silent
    if path.startswith("/apis/custom.api.local"):
        logger.warning(f"Unhandled 404 for path {path} from user '{user}'")
    # return k8s-style Status
    return jsonify({
        "kind": "Status",
        "apiVersion": "v1",
        "metadata": {},
        "status": "Failure",
        "message": f"The requested resource '{path}' was not found",
        "reason": "NotFound",
        "code": 404
    }), 404

# ---------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8443))
    cert = "/tls/tls.crt"
    key = "/tls/tls.key"
    ssl_ctx = (cert, key) if os.path.exists(cert) and os.path.exists(key) else None
    logger.info(f"Starting server on port {port} (TLS={'enabled' if ssl_ctx else 'disabled'})")
    app.run(host="0.0.0.0", port=port, ssl_context=ssl_ctx)

