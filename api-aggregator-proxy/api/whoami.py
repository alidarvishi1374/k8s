from flask import Blueprint, request, jsonify
from datetime import datetime, timezone

bp = Blueprint("whoami", __name__)

@bp.route("/apis/custom.api.local/v1/whoami")
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