from kubernetes import client, config
import os
import logging

logger = logging.getLogger("namespace-api")

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