#!/usr/bin/env python3
from flask import Flask, request, Response, redirect
import requests
from OpenSSL import crypto
import ssl
import yaml

app = Flask(__name__)


with open("/etc/proxy-certs/config.yaml") as f:
    cfg = yaml.safe_load(f)

K8S_API = cfg["k8s"]["api_server"]
CA_CERT = cfg["k8s"]["ca_cert"]
SERVER_CERT = cfg["tls"]["server_cert"]
SERVER_KEY = cfg["tls"]["server_key"]
TOKEN = cfg["auth"]["token"]

METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]

INTERACTIVE_PATH_KEYWORDS = ["exec", "attach", "portforward"]

@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
def proxy(path):
    try:
        query = request.query_string.decode()

        lower_path = path.lower()
        if any(k in lower_path for k in INTERACTIVE_PATH_KEYWORDS):
            location = f"{K8S_API}/{path}" + ("?" + query if query else "")
            return redirect(location, code=307)

        peer_cert = request.environ.get("SSL_CLIENT_CERT")
        if not peer_cert:
            return Response("❌ No client certificate presented", status=401)

        x509 = crypto.load_certificate(crypto.FILETYPE_PEM, peer_cert)
        user_cn = x509.get_subject().CN
        try:
            user_org = x509.get_subject().O
        except Exception:
            user_org = None

        method = request.method

        if method == "GET" and path.strip("/") == "api/v1/namespaces" and query == "limit=500":
            path = "apis/custom.api.local/v1/mynamespace"


        headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
        headers["Impersonate-User"] = user_cn
        if user_org:
            headers["Impersonate-Group"] = user_org

        headers["Authorization"] = f"Bearer {TOKEN}"

        data = request.get_data()

        resp = requests.request(
            method=method,
            url=f"{K8S_API}/{path}" + ("?" + query if query else ""),
            headers=headers,
            data=data,
            verify=CA_CERT,
            stream=True,
            timeout=120
        )

        response_headers = {k: v for k, v in resp.headers.items() if k.lower() not in ["transfer-encoding", "content-encoding"]}

        return Response(resp.raw, status=resp.status_code, headers=response_headers, direct_passthrough=True)

    except Exception as e:
        return Response(f"Proxy error: {e}", status=500)


if __name__ == "__main__":
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile=SERVER_CERT, keyfile=SERVER_KEY)
    context.load_verify_locations(CA_CERT)
    context.verify_mode = ssl.CERT_REQUIRED

    app.run(host="0.0.0.0", port=8443, ssl_context=context, threaded=True)

