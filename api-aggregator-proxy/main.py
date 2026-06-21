#!/usr/bin/env python3
from flask import Flask, jsonify, request
from kubernetes import client, config
import os, traceback, logging
from datetime import datetime, timezone
import ssl

from api.discovery import bp as discovery_bp
from api.whoami import bp as whoami_bp
from api.mynamespace import bp as ns_bp

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

werkzeug_logger = logging.getLogger("werkzeug")
werkzeug_logger.setLevel(logging.ERROR)

# ---------------------------
# Request logging
# ---------------------------
IGNORED_PATH_PREFIXES = ("/openapi",)
IGNORED_EXACT_PATHS = ("/apis",)

@app.before_request
def log_request():
    path = request.path or ""
    user = request.headers.get("X-Remote-User", "-")
    remote = request.remote_addr or "-"

    if path in IGNORED_EXACT_PATHS or any(path.startswith(p) for p in IGNORED_PATH_PREFIXES):
        return

    logger.info(
        f"Incoming request: {request.method} {path} "
        f"from {remote} | User: {user}"
    )

# ---------------------------
app.register_blueprint(discovery_bp)
app.register_blueprint(whoami_bp)
app.register_blueprint(ns_bp)

@app.route("/healthz")
def health():
    return "ok", 200

# ---------------------------
@app.errorhandler(404)
def handle_404(e):
    path = request.path
    user = request.headers.get("X-Remote-User", "-")

    if path.startswith("/apis/custom.api.local"):
        logger.warning(f"Unhandled 404 for path {path} from user '{user}'")

    return jsonify({
        "kind": "Status",
        "apiVersion": "v1",
        "status": "Failure",
        "metadata": {},
        "message": f"The requested resource '{path}' was not found",
        "reason": "NotFound",
        "code": 404
    }), 404

# ---------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8443))
    cert = "/tls/tls.crt"
    key = "/tls/tls.key"
    ca = "/ca/front-proxy-ca.crt"

    if os.path.exists(cert) and os.path.exists(key):
        ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_ctx.load_cert_chain(certfile=cert, keyfile=key)
        ssl_ctx.load_verify_locations(cafile=ca)
        ssl_ctx.verify_mode = ssl.CERT_REQUIRED
    else:
        ssl_ctx = None

    logger.info(f"Starting server on port {port} (TLS={'enabled' if ssl_ctx else 'disabled'})")

    app.run(host="0.0.0.0", port=port, ssl_context=ssl_ctx)