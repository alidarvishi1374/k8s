import os
import json
import base64
import subprocess
import sys
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from kubernetes.client import V1MatchCondition
# ------------------------
# Constants
# ------------------------
NAMESPACE = os.environ.get("POD_NAMESPACE", "default")
SERVICE_NAME = "policy-webhook"
SECRET_NAME = "webhook-tls"
WORKDIR = "/work"
os.chdir(WORKDIR)

# ------------------------
# Load Kubernetes config
# ------------------------
try:
    config.load_incluster_config()
except config.ConfigException:
    print("This script must run inside a Kubernetes cluster")
    sys.exit(1)

v1 = client.CoreV1Api()
admission_api = client.AdmissionregistrationV1Api()

# ------------------------
# Helper: read file as base64 string
# ------------------------
def read_b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

# ------------------------
# 1. Check Secret
# ------------------------
ca_bundle_b64 = None

try:
    secret = v1.read_namespaced_secret(SECRET_NAME, NAMESPACE)
    print(f"Secret '{SECRET_NAME}' already exists, skipping TLS generation")
    ca_bundle_b64 = secret.data.get("ca.crt")  # base64 string
except ApiException as e:
    if e.status != 404:
        raise

    # ------------------------
    # 2. Generate TLS/CA with OpenSSL
    # ------------------------
    print("Generating CA key and certificate...")
    subprocess.run(["openssl", "genrsa", "-out", "ca.key", "4096"], check=True)
    subprocess.run([
        "openssl", "req", "-x509", "-new", "-nodes",
        "-key", "ca.key",
        "-sha256",
        "-days", "3650",
        "-out", "ca.crt",
        "-subj", "/CN=MyWebhookCA"
    ], check=True)

    print("Generating TLS key and CSR...")
    subprocess.run(["openssl", "genrsa", "-out", "tls.key", "4096"], check=True)
    subprocess.run([
        "openssl", "req", "-new",
        "-key", "tls.key",
        "-out", "tls.csr",
        "-config", "csr.conf"
    ], check=True)

    print("Signing TLS certificate with CA...")
    subprocess.run([
        "openssl", "x509", "-req",
        "-in", "tls.csr",
        "-CA", "ca.crt",
        "-CAkey", "ca.key",
        "-CAcreateserial",
        "-out", "tls.crt",
        "-days", "365",
        "-extensions", "v3_req",
        "-extfile", "csr.conf"
    ], check=True)

    # ------------------------
    # 3. Create Kubernetes Secret
    # ------------------------
    secret = client.V1Secret(
        metadata=client.V1ObjectMeta(name=SECRET_NAME),
        type="kubernetes.io/tls",
        data={
            "ca.crt": read_b64("ca.crt"),
            "tls.crt": read_b64("tls.crt"),
            "tls.key": read_b64("tls.key"),
        }
    )
    v1.create_namespaced_secret(NAMESPACE, secret)
    print(f"TLS Secret '{SECRET_NAME}' created successfully")
    ca_bundle_b64 = read_b64("ca.crt")  # string

# ------------------------
# Helper: create webhook
# ------------------------
def create_webhook(webhook_type: str, config_env: str):
    cfg = json.loads(os.environ.get(config_env, "{}"))

    name = cfg.get("name", f"default-{webhook_type}.example.com")
    failure_policy = cfg.get("failurePolicy", "Ignore")
    timeout_seconds = cfg.get("timeoutSeconds", 5)
    rules_cfg = cfg.get("rules", [])
    match_conditions_cfg = cfg.get("matchConditions", [])

    # Rules
    rules = []
    for r in rules_cfg:
        rules.append(client.V1RuleWithOperations(
            api_groups=r.get("apiGroups", ["*"]),
            api_versions=r.get("apiVersions", ["*"]),
            operations=r.get("operations", ["CREATE", "UPDATE", "DELETE"]),
            resources=r.get("resources", ["*"])
        ))

    # MatchConditions
    match_conditions = []
    for m in match_conditions_cfg:
        match_conditions.append(V1MatchCondition(
            name=m.get("name"),
            expression=m.get("expression")
        ))

    client_cfg = {
        "service": {
            "name": SERVICE_NAME,
            "namespace": NAMESPACE,
            "path": f"/{webhook_type}",
            "port": 443
        },
        "caBundle": ca_bundle_b64
    }



    webhook_kwargs = dict(
        name=name,
        admission_review_versions=["v1"],
        side_effects="None",
        failure_policy=failure_policy,
        timeout_seconds=timeout_seconds,
        client_config=client_cfg,
        rules=rules,
        match_conditions=match_conditions
    )

    if webhook_type == "mutate":
        webhook = client.V1MutatingWebhook(**webhook_kwargs)
        config_obj = client.V1MutatingWebhookConfiguration(
            metadata=client.V1ObjectMeta(name=name),
            webhooks=[webhook]
        )
        create_or_replace(admission_api.create_mutating_webhook_configuration,
                          admission_api.replace_mutating_webhook_configuration,
                          config_obj, name)
    else:
        webhook = client.V1ValidatingWebhook(**webhook_kwargs)
        config_obj = client.V1ValidatingWebhookConfiguration(
            metadata=client.V1ObjectMeta(name=name),
            webhooks=[webhook]
        )
        create_or_replace(admission_api.create_validating_webhook_configuration,
                          admission_api.replace_validating_webhook_configuration,
                          config_obj, name)

def create_or_replace(create_fn, replace_fn, obj, name):
    try:
        create_fn(obj)
        print(f"{name} created")
    except ApiException as e:
        if e.status == 409:  # Already exists
            existing = None
            if hasattr(obj, "webhooks") and isinstance(obj, client.V1MutatingWebhookConfiguration):
                existing = admission_api.read_mutating_webhook_configuration(name)
            elif hasattr(obj, "webhooks") and isinstance(obj, client.V1ValidatingWebhookConfiguration):
                existing = admission_api.read_validating_webhook_configuration(name)
            if existing:
                obj.metadata.resource_version = existing.metadata.resource_version
                replace_fn(name, obj)
                print(f"{name} replaced")
        else:
            raise

# ------------------------
# Apply webhooks dynamically
# ------------------------
create_webhook("mutate", "MUTATING_CONFIG")
create_webhook("validate", "VALIDATING_CONFIG")
print("Webhook configurations applied successfully")
