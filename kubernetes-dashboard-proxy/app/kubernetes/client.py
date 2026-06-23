import os

from kubernetes import client, config


def init_k8s():
    """Load Kubernetes config - prefer in-cluster."""
    try:
        config.load_incluster_config()

    except Exception:

        kubeconf = os.environ.get("KUBECONFIG")

        if kubeconf:
            config.load_kube_config(
                config_file=kubeconf
            )

        else:
            config.load_kube_config()


    return client.CoreV1Api()


v1 = init_k8s()