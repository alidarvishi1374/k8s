#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from kubernetes import client, config, watch
import logging
import sys
import traceback
import time

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    force=True
)

logging.info("Dashboard watcher started...")

config.load_incluster_config()
apps = client.AppsV1Api()
w = watch.Watch()

def sync_limits_with_requests(deployment):
    updated = False
    for container in deployment.spec.template.spec.containers:
        resources = container.resources or client.V1ResourceRequirements()
        requests = resources.requests or {}
        limits = resources.limits or {}

        for key, val in requests.items():
            if key not in limits or limits[key] != val:
                limits[key] = val
                updated = True

        resources.limits = limits
        container.resources = resources

    return updated

while True:
    try:
        for event in w.stream(apps.list_deployment_for_all_namespaces, timeout_seconds=0):
            dep = event["object"]
            etype = event["type"]
            name = dep.metadata.name
            ns = dep.metadata.namespace

            if etype == "ADDED":
                managers = [f.manager for f in (dep.metadata.managed_fields or [])]
                logging.debug(f"Managed fields for {ns}/{name}: {managers}")

                if any("dashboard-api" in (m or "") for m in managers):
                    logging.info(f"Detected dashboard-created deployment: {ns}/{name}")

                    updated = sync_limits_with_requests(dep)

                    if updated:
                        patch_body = {
                            "spec": {
                                "template": {
                                    "spec": {
                                        "containers": [
                                            {
                                                "name": c.name,
                                                "resources": c.resources.to_dict()
                                            } for c in dep.spec.template.spec.containers
                                        ]
                                    }
                                }
                            }
                        }

                        try:
                            apps.patch_namespaced_deployment(
                                name=name,
                                namespace=ns,
                                body=patch_body
                            )
                            logging.info(f"[OK] Updated resources for deployment: {ns}/{name}")
                        except Exception as patch_err:
                            logging.error(f"[ERROR] Failed to patch {ns}/{name}: {patch_err}")
                            traceback.print_exc()
                    else:
                        logging.info(f"[SKIP] No changes needed for: {ns}/{name}")

    except Exception as e:
        logging.error(f"Exception in watcher loop: {e}")
        traceback.print_exc()
        time.sleep(2)
