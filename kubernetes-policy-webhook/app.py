from flask import Flask, request, jsonify
import logging
import json
import base64
import copy
from kubernetes import client, config
from celpy import Environment

# ------------------------
# Logging
# ------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("k8s-admission-webhook")

# ------------------------
# Flask app
# ------------------------
app = Flask(__name__)

# ------------------------
# Kubernetes client init
# ------------------------
try:
    config.load_incluster_config()
    logger.info("Loaded in-cluster config")
except Exception:
    config.load_kube_config(config_file="config")
    logger.info("Loaded kubeconfig")

custom_api = client.CustomObjectsApi()

# ------------------------
# Constants
# ------------------------
POLICY_GROUP = "policy.example.com"
POLICY_VERSION = "v1"

CLUSTER_MUTATE_PLURAL = "clustercelmutationpolicies"
NAMESPACE_MUTATE_PLURAL = "namespacecelmutationpolicies"

CLUSTER_VALIDATE_PLURAL = "clustercelvalidationpolicies"
NAMESPACE_VALIDATE_PLURAL = "namespacecelvalidationpolicies"

cel_env = Environment()

# ------------------------
# Helper functions
# ------------------------
def list_cluster_policies(plural):
    try:
        return custom_api.list_cluster_custom_object(
            POLICY_GROUP,
            POLICY_VERSION,
            plural
        )["items"]
    except client.exceptions.ApiException as e:
        if e.status == 404:
            logger.warning(f"Cluster policy CRD '{plural}' not found")
            return []
        raise

def list_namespace_policies(namespace, plural):
    if not namespace:
        return []

    try:
        return custom_api.list_namespaced_custom_object(
            POLICY_GROUP,
            POLICY_VERSION,
            namespace,
            plural
        )["items"]
    except client.exceptions.ApiException as e:
        if e.status == 404:
            logger.warning(f"Namespace policy CRD '{plural}' not found")
            return []
        raise

def generate_patch(original, modified):
    patch = []
    for k, v in modified.get("metadata", {}).get("labels", {}).items():
        orig_val = original.get("metadata", {}).get("labels", {}).get(k)
        if orig_val != v:
            patch.append({"op": "add" if orig_val is None else "replace", "path": f"/metadata/labels/{k}", "value": v})
    return patch

def allow(uid, warnings=None):
    resp = {
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "response": {
            "uid": uid,
            "allowed": True
        }
    }
    if warnings:
        resp["response"]["warnings"] = warnings
    return jsonify(resp)

def deny(uid, message):
    resp = {
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "response": {
            "uid": uid,
            "allowed": False,
            "status": {"message": str(message)}
        }
    }
    logger.info(f"Denying request: {message}")
    return jsonify(resp)

def eval_cel(expression, context):
    try:
        ast = cel_env.compile(expression)
        program = cel_env.program(ast)
        return program.evaluate(context)
    except Exception as e:
        logger.error(f"CEL evaluation error: {e}")
        return False

# ------------------------
# Mutating webhook
# ------------------------
@app.route("/mutate", methods=["POST"])
def mutate():
    review = request.get_json()
    req = review["request"]
    uid = req["uid"]
    obj = req.get("object") or req.get("oldObject")
    namespace = obj.get("metadata", {}).get("namespace") if obj else None
    original_obj = copy.deepcopy(obj)

    # Load policies
    policies = list_cluster_policies(CLUSTER_MUTATE_PLURAL)
    policies += list_namespace_policies(namespace, NAMESPACE_MUTATE_PLURAL)

    # Apply labels
    for policy in policies:
        spec = policy.get("spec", {})
        match = spec.get("match", {})
        if req["kind"]["kind"] not in match.get("resources", []):
            continue
        if req["operation"] not in match.get("operations", []):
            continue
        labels = spec.get("labels", {})
        for k, v in labels.items():
            obj.setdefault("metadata", {}).setdefault("labels", {})[k] = v
            logger.info(f"Applied label: {k}={v}")

    patch = generate_patch(original_obj, obj)
    if patch:
        return jsonify({
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {
                "uid": uid,
                "allowed": True,
                "patchType": "JSONPatch",
                "patch": base64.b64encode(json.dumps(patch).encode()).decode()
            }
        })
    return jsonify({"apiVersion": "admission.k8s.io/v1", "kind": "AdmissionReview", "response": {"uid": uid, "allowed": True}})

# ------------------------
# Validating webhook
# ------------------------
@app.route("/validate", methods=["POST"])
def validate():
    review = request.get_json()
    req = review["request"]
    uid = req["uid"]
    operation = req["operation"]
    kind = req["kind"]["kind"]
    user = req.get("userInfo", {})

    obj = req.get("object") or req.get("oldObject")
    namespace = obj.get("metadata", {}).get("namespace") if obj else None
    name = obj.get("metadata", {}).get("name") if obj else None

    warnings = []

    logger.info(
        f"Admission request: user={user.get('username')} "
        f"groups={user.get('groups')} "
        f"operation={operation} kind={kind} "
        f"namespace={namespace} name={name}"
    )

    policies = []
    for p in list_cluster_policies(CLUSTER_VALIDATE_PLURAL):
        p["_scope"] = "cluster"
        policies.append(p)
    for p in list_namespace_policies(namespace, NAMESPACE_VALIDATE_PLURAL):
        p["_scope"] = "namespace"
        policies.append(p)

    for policy in policies:
        spec = policy.get("spec", {})
        match = spec.get("match", {})

        if kind not in match.get("resources", []):
            continue
        if operation not in match.get("operations", []):
            continue
        if policy["_scope"] == "namespace" and namespace != policy["metadata"]["namespace"]:
            continue

        context = {
            "object": obj,
            "request": req,
            "params": None,
            "namespace": namespace if policy["_scope"] == "namespace" else None,
            "policyScope": policy["_scope"]
        }

        for rule in spec.get("validations", []):
            logger.info(f"Evaluating policy={policy['metadata']['name']} scope={policy['_scope']} rule={rule['expression']}")
            ok = eval_cel(rule["expression"], context)

            if not ok:
                message = eval_cel(rule.get("messageExpression", '"validation failed"'), context)
                logger.info(f"Rule failed: policy={policy['metadata']['name']} scope={policy['_scope']} enforcement={rule['enforcement']} message={message}")

                if rule["enforcement"] == "enforce":
                    return deny(uid, message)
                elif rule["enforcement"] == "warn":
                    warnings.append(message)

    if warnings:
        logger.info(f"Warnings for {kind} {name}: {warnings}")

    logger.info(f"Allowing {kind} {name} in namespace {namespace}")
    return allow(uid, warnings)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok"
    }), 200

# ------------------------
# Main
# ------------------------
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8443,
        ssl_context=("tls/tls.crt", "tls/tls.key")
    )

