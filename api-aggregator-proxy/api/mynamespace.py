from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
import logging
import traceback

from k8s.client import init_k8s_client
from k8s.rbac import can_list_namespaces
from utils.auth import extract_team
from services.namespace_service import filter_namespaces, format_namespaces

bp = Blueprint("namespace", __name__)

v1, auth_v1 = init_k8s_client()
logger = logging.getLogger("namespace-api")

NAMESPACE_TEAM_LABEL = "team"

@bp.route("/apis/custom.api.local/v1/mynamespace")
def mynamespace():
    user = request.headers.get("X-Remote-User", "")
    logger.info(f"Request from user: {user}")

    team_name = extract_team(user)
    logger.info(f"Extracted team name: {team_name}")

    try:
        user_can_list = can_list_namespaces(auth_v1, user)
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
        items = filter_namespaces(items, team_name, NAMESPACE_TEAM_LABEL)

    namespaces = format_namespaces(items)

    if not namespaces:
        namespaces.append({
            "metadata": {
                "name": f"No namespaces found for team '{team_name}' (user '{user}')",
                "creationTimestamp": datetime.now(timezone.utc).isoformat()
            },
            "status": {"phase": "Unknown"}
        })

    return jsonify({
        "kind": "NamespaceList",
        "apiVersion": "v1",
        "metadata": {},
        "items": namespaces
    }), 200, {"Content-Type": "application/json"}